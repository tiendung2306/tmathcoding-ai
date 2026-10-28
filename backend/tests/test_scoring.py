import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.scoring import ScoringItem, ScoringPair, ScoringProfile, ScoringRun, ScoringState
from app.scoring.calibration import calibrate
from app.scoring.policy import Policy, default_policy, point_value, source_grade
from app.scoring.service import enqueue, leaderboard, publish, reprice_active


class ModelTests(unittest.TestCase):
    def test_grades_only_accept_source_ids_and_reject_manual_overrides(self):
        self.assertEqual([source_grade(value) for value in (4, 5, 6, 7, 8, 13)], list("ABCDEF"))
        self.assertIsNone(source_grade(None))
        self.assertIsNone(source_grade(1))
        self.assertIsNone(source_grade(999))
        data = default_policy().model_dump()
        data["overrides"] = {1: "F"}
        with self.assertRaises(ValidationError):
            Policy.model_validate(data)
        data = default_policy().model_dump()
        data["unclassified_points"] = 900
        with self.assertRaises(ValidationError):
            Policy.model_validate(data)

    def test_grade_validation_and_rounding(self):
        policy = default_policy()
        self.assertEqual(point_value(325, policy.bands["A"]), 350)
        self.assertEqual(point_value(99999, policy.bands["A"]), 450)
        self.assertEqual(point_value(-100, policy.bands["A"]), 100)
        for change in ({"minimum": 700}, {"maximum": 123}, {"initial": 0}):
            data = policy.model_dump()
            data["bands"]["A"].update(change)
            with self.assertRaises(ValidationError):
                Policy.model_validate(data)

    def test_same_grade_separates_difficulty_and_respects_bounds(self):
        policy = default_policy()
        policy.min_attempted, policy.min_each_outcome = 5, 1
        items = [{"problem_id": i, "grade": "C"} for i in (1, 2)]
        pairs = [{"profile_id": u, "problem_id": i, "has_ac": u < (75 if i == 1 else 25)}
                 for u in range(100) for i in (1, 2)]
        output, diagnostics = calibrate(items, pairs, policy)
        self.assertLess(output[0]["points"], output[1]["points"])
        self.assertEqual(diagnostics["observations"], 200)
        for row in output:
            self.assertTrue(900 <= row["points"] <= 1250)
            self.assertEqual(row["points"] % 50, 0)
        self.assertEqual(output, calibrate(items, pairs, policy)[0])

    def test_sparse_and_one_sided_data_keep_initial_or_published_points(self):
        items = [{"problem_id": 1, "grade": "A"}, {"problem_id": 2, "grade": "B"}]
        pairs = [{"profile_id": u, "problem_id": 1, "has_ac": False} for u in range(100)]
        result, _ = calibrate(items, pairs, default_policy(), {1: {"grade": "A", "points": 400}})
        self.assertEqual((result[0]["points"], result[0]["method"]), (400, "RETAINED"))
        self.assertEqual((result[1]["points"], result[1]["method"]), (700, "PROVISIONAL"))

    def test_unclassified_and_empty_observations_are_not_failures(self):
        output, metrics = calibrate([{"problem_id": 1, "grade": None}], [], default_policy())
        self.assertEqual(output, [])
        self.assertEqual(metrics["observations"], 0)


class AsyncDB:
    def __init__(self, session): self.session = session
    async def execute(self, statement, *args): return self.session.execute(statement, *args)
    async def get(self, model, key): return self.session.get(model, key)
    async def commit(self): self.session.commit()
    def add(self, value): self.session.add(value)


class StorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in (ScoringState, ScoringRun, ScoringProfile, ScoringItem, ScoringPair):
            model.__table__.create(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.db = AsyncDB(self.session)
        self.session.add(ScoringState(id=1, revision=1, policy=default_policy().model_dump(mode="json")))
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def ready_run(self, run_id="r1", base=None):
        row = ScoringRun(id=run_id, kind="calibrate", status="READY", actor_id=2, policy_revision=1,
            policy=default_policy().model_dump(mode="json"), base_run_id=base, manifest={"catalog_version": "v1"},
            source_as_of=utc_now(), progress="Ready")
        self.session.add(row)
        self.session.commit()
        return row

    async def test_enqueue_rejects_duplicate_active_job(self):
        first = await enqueue(self.db, 2)
        self.assertEqual(first["status"], "QUEUED")
        with self.assertRaises(HTTPException) as error:
            await enqueue(self.db, 2)
        self.assertEqual(error.exception.status_code, 409)

    async def test_enqueue_ignores_stored_editable_configuration(self):
        current = self.session.get(ScoringState, 1)
        current.policy = {"bands": {}, "overrides": {1: "F"}}
        await enqueue(self.db, 2)
        row = self.session.query(ScoringRun).one()
        self.assertEqual(row.policy, default_policy().model_dump(mode="json"))

    async def test_scoring_http_routes_cannot_write_policy_or_publish(self):
        import httpx
        from fastapi import FastAPI
        from app.api.v1.endpoints.scoring import router
        app = FastAPI()
        app.include_router(router, prefix="/scoring")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for method, path in (("PUT", "/scoring/policy"), ("POST", "/scoring/runs"),
                                 ("POST", "/scoring/runs/any/publish")):
                response = await client.request(method, path, json={})
                self.assertEqual(response.status_code, 404)

    async def test_publish_atomic_pointer_idempotence_and_stale_base(self):
        self.ready_run()
        source = SimpleNamespace(get_analytics_catalog=AsyncMock(return_value=(SimpleNamespace(catalog_version="v1"), None, False)))
        await publish(self.db, "r1", source, 2)
        await publish(self.db, "r1", source, 2)
        self.assertEqual(self.session.get(ScoringState, 1).active_run_id, "r1")
        self.ready_run("stale")
        with self.assertRaises(HTTPException):
            await publish(self.db, "stale", source, 2)
        self.assertEqual(self.session.get(ScoringState, 1).active_run_id, "r1")

    async def test_policy_and_catalog_changes_prevent_publication(self):
        self.ready_run()
        source = SimpleNamespace(get_analytics_catalog=AsyncMock(return_value=(SimpleNamespace(catalog_version="v2"), None, False)))
        with self.assertRaises(HTTPException):
            await publish(self.db, "r1", source, 2)
        self.session.get(ScoringState, 1).revision = 2
        with self.assertRaises(HTTPException):
            await publish(self.db, "r1", source, 2)
        self.assertIsNone(self.session.get(ScoringState, 1).active_run_id)

    async def test_rank_before_search_ties_and_page_boundary(self):
        self.ready_run()
        self.session.get(ScoringState, 1).active_run_id = "r1"
        self.session.execute(insert(ScoringProfile), [
            {"run_id": "r1", "profile_id": i, "name": f"Student {i}", "username": f"u{i}",
             "total_points": points, "solved_count": 1, "unscored_count": 0}
            for i, points in ((1, 100), (2, 900), (3, 900), (4, 0))])
        self.session.commit()
        first = await leaderboard(self.db, 1, 2)
        second = await leaderboard(self.db, 2, 2)
        self.assertEqual([row["user_id"] for row in first["items"]], [2, 3])
        self.assertEqual([row["rank"] for row in first["items"]], [1, 1])
        self.assertEqual([row["user_id"] for row in second["items"]], [1, 4])
        self.assertEqual((await leaderboard(self.db, q="Student 1"))["items"][0]["rank"], 3)
        ascending = await leaderboard(self.db, sort="points_asc")
        self.assertEqual([row["user_id"] for row in ascending["items"]], [4, 1, 2, 3])
        self.assertEqual([row["rank"] for row in ascending["items"]], [4, 3, 1, 1])
        by_name = await leaderboard(self.db, sort="name_desc")
        self.assertEqual([row["user_id"] for row in by_name["items"]], [4, 3, 2, 1])
        with self.assertRaises(HTTPException):
            await leaderboard(self.db, run_id="old-generation")

    async def test_default_points_backfill_preserves_source_grade_and_is_repeatable(self):
        original = self.ready_run()
        original.status, original.published_at = "PUBLISHED", utc_now()
        self.session.get(ScoringState, 1).active_run_id = original.id
        self.session.add_all([
            ScoringItem(run_id=original.id, problem_id=1, code="p1", title="Graded", source_group_id=4,
                        grade="A", points=300, attempted=1, solved=1, method="MODEL"),
            ScoringItem(run_id=original.id, problem_id=2, code="p2", title="No source grade", source_group_id=None,
                        grade=None, points=None, attempted=1, solved=1, method="UNCLASSIFIED"),
            ScoringProfile(run_id=original.id, profile_id=1, name="Student", username="u1",
                           total_points=300, solved_count=2, unscored_count=1),
            ScoringPair(run_id=original.id, profile_id=1, problem_id=1, has_ac=True),
            ScoringPair(run_id=original.id, profile_id=1, problem_id=2, has_ac=True),
        ])
        self.session.commit()
        source = SimpleNamespace(get_analytics_catalog=AsyncMock(
            return_value=(SimpleNamespace(catalog_version="v1"), None, False)))
        for _ in range(2):
            result = await reprice_active(self.db, source, 2)
            student = self.session.get(ScoringProfile, (result["id"], 1))
            item = self.session.get(ScoringItem, (result["id"], 2))
            self.assertEqual((student.total_points, student.unscored_count), (400, 0))
            self.assertEqual((item.grade, item.points, item.method), (None, 100, "DEFAULT"))
        self.assertIsNone(self.session.get(ScoringItem, (original.id, 2)).points)

import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.models.dmoj import JudgeProfile, JudgeProblem, JudgeProblemtype, JudgeProblemTypes, JudgeSubmission
from app.models.skill_config import SkillConfiguration
from app.schemas.skill_config import SkillDocument
from app.services.skill_taxonomy import fixed_document, DEFAULT_ASSIGNMENTS
from app.services import skill_problem_service as problems, skill_config_service as config
from db_fixtures import create_source_tables
from test_skill_configuration import AsyncSession


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        create_source_tables(self.engine, JudgeProfile, JudgeProblem, JudgeProblemtype, JudgeProblemTypes, JudgeSubmission)
        self.session = Session(self.engine)
        self.db = AsyncSession(self.session)
        self.session.execute(insert(JudgeProfile.__table__), [{"id": 2}, {"id": 3}])
        self.session.execute(insert(JudgeProblemtype.__table__), [{"id": 39, "name": "map"}])
        self.session.execute(insert(JudgeProblem.__table__), [{"id": i, "code": f"p{i:02}", "name": f"Problem {i}", "description": "$x^2$"} for i in range(1, 26)])
        self.session.execute(insert(JudgeProblemTypes.__table__), [{"id": i, "problem_id": i, "problemtype_id": 39} for i in range(1, 26)] + [{"id": 30, "problem_id": 1, "problemtype_id": 39}])
        anchor = datetime(2026, 1, 10)
        self.session.execute(insert(JudgeSubmission.__table__), [
            {"id": 1, "user_id": 2, "problem_id": 1, "result": "AC", "date": anchor - timedelta(days=8)},
            {"id": 2, "user_id": 2, "problem_id": 1, "result": "WA", "date": anchor},
            {"id": 3, "user_id": 2, "problem_id": 2, "result": "WA", "date": anchor},
            {"id": 4, "user_id": 3, "problem_id": 3, "result": "AC", "date": anchor},
        ])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_full_catalog_deduplicated_and_paginated(self):
        result = await problems.tag_problems(self.db, 39, 2)
        self.assertEqual((result["total"], len(result["items"]), result["total_pages"]), (25, 20, 2))
        result = await problems.tag_problems(self.db, 39, 2, page=2)
        self.assertEqual(len(result["items"]), 5)
        self.assertTrue(all(item["attempts"] == 0 for item in result["items"]))

    async def test_any_ac_not_last_result_and_no_other_student_attempts(self):
        result = await problems.tag_problems(self.db, 39, 2, status="ac")
        self.assertEqual([item["id"] for item in result["items"]], [1])
        self.assertEqual(result["items"][0]["attempts"], 2)
        result = await problems.tag_problems(self.db, 39, 2, status="unattempted")
        self.assertIn(3, [item["id"] for item in result["items"]])

    async def test_time_filter_uses_same_reference_as_skill_counts(self):
        result = await problems.tag_problems(self.db, 39, 2, time_range="7d", status="ac")
        self.assertEqual(result["total"], 0)
        result = await problems.tag_problems(self.db, 39, 2, time_range="7d", status="attempted")
        self.assertEqual([item["id"] for item in result["items"]], [1, 2])

    async def test_search_before_pagination_and_literal_wildcards(self):
        result = await problems.tag_problems(self.db, 39, 2, q="p25", page=9)
        self.assertEqual((result["total"], result["page"], result["items"][0]["id"]), (1, 1, 25))
        self.assertEqual((await problems.tag_problems(self.db, 39, 2, q="%"))["total"], 0)

    async def test_problem_history_is_student_scoped_and_paginated(self):
        result = await problems.problem_detail(self.db, 1, 2, page_size=1)
        self.assertEqual((result["description"], result["submissions"]["total"]), ("$x^2$", 2))
        self.assertEqual(result["submissions"]["items"][0]["id"], 2)
        result = await problems.problem_detail(self.db, 3, 2)
        self.assertEqual(result["submissions"]["total"], 0)

    async def test_invalid_profile_tag_or_problem_returns_404(self):
        for call in (problems.tag_problems(self.db, 39, 999), problems.tag_problems(self.db, 999, 2), problems.problem_detail(self.db, 999, 2)):
            with self.assertRaises(HTTPException) as caught:
                await call
            self.assertEqual(caught.exception.status_code, 404)

    async def test_fixed_nodes_cannot_change_but_assignment_can(self):
        engine = create_engine("sqlite://")
        SkillConfiguration.__table__.create(engine)
        with Session(engine, expire_on_commit=False) as session:
            doc = fixed_document()
            doc["assignments"] = {"39": "data-structures"}
            session.add(SkillConfiguration(id=1, revision=0, draft=doc, taxonomy_version=1))
            session.commit()
            altered = SkillDocument.model_validate(doc)
            altered.nodes[0].title = "Edited"
            with self.assertRaises(HTTPException) as caught:
                await config.write(AsyncSession(session), self.db, 0, altered, 2, True)
            self.assertEqual(caught.exception.status_code, 422)
            valid = SkillDocument.model_validate(doc)
            valid.assignments[39] = "other"
            result = await config.write(AsyncSession(session), self.db, 0, valid, 2, True)
            self.assertEqual(result["document"]["assignments"]["39"], "other")
        engine.dispose()


class TaxonomyTests(unittest.TestCase):
    def migration(self):
        path = Path("/app/migrations/versions/20261004_0003_fixed_skill_roots.py")
        if not path.exists():
            path = Path(__file__).parents[1] / "migrations/versions/20261004_0003_fixed_skill_roots.py"
        spec = importlib.util.spec_from_file_location("fixed_root_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_snapshot_matches_runtime_and_99_ids_unique(self):
        migration = self.migration()
        self.assertEqual(migration.fixed_document(), fixed_document())
        self.assertEqual(len(DEFAULT_ASSIGNMENTS), 99)
        self.assertEqual(len(fixed_document()["nodes"]), 11)
        self.assertEqual(sum(value == "other" for value in DEFAULT_ASSIGNMENTS.values()), 4)

    def test_migration_flattens_recognized_root_and_preserves_overrides(self):
        old = {"nodes": [{"id": "r", "title": "DP"}, {"id": "child", "title": "X", "parent_id": "r"}], "assignments": {39: "child", 999: "r"}}
        migrated = self.migration().converted_document(old)
        self.assertEqual(migrated["assignments"]["39"], "dp")
        self.assertEqual(migrated["assignments"]["999"], "dp")

    def test_migration_stops_on_unknown_assigned_custom_root(self):
        with self.assertRaises(RuntimeError):
            self.migration().converted_document({"nodes": [{"id": "r", "title": "Custom"}], "assignments": {39: "r"}})

"""Sessions are contests read from the Source API (no local start/stop)."""
import unittest
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI

from app.api.v1.endpoints.teacher import router as teacher_router
from app.api.v1.endpoints.virtual_class import router as virtual_router
from app.core.auth import get_current_user
from app.services.source_gateway import (
    SourceAccess, SourceContest, SourceContestProblem, SourceContestProblemList, SourcePage, SourceStudent,
    SourceSubmission, SourceSubmissionPage, get_source_gateway,
)

NOW = datetime.now(timezone.utc)


class SessionGateway:
    def __init__(self):
        self.contest = SourceContest(
            contest_id=5, code="live", title="Buổi luyện đồ thị", class_ids=[10, 11],
            starts_at=NOW - timedelta(hours=1), ends_at=NOW + timedelta(hours=1),
            status="active", is_public=False)
        self.class_submission_calls = []
        self.problems = None  # None = provider without the contest problems endpoint

    async def list_contest_problems(self, contest_id, *, actor_profile_id):
        if self.problems is None:
            from fastapi import HTTPException
            raise HTTPException(404, "not supported")
        return SourceContestProblemList(items=self.problems, as_of=NOW)

    async def get_teacher_contest(self, profile_id, contest_id, *, actor_profile_id):
        if contest_id != 5:
            from fastapi import HTTPException
            raise HTTPException(404, "missing")
        return self.contest

    async def list_class_students(self, class_id, *, actor_profile_id, cursor=None, limit=100):
        rosters = {
            10: [SourceStudent(profile_id=1, name="An", username="an"), SourceStudent(profile_id=2, name="Bình", username="binh")],
            11: [SourceStudent(profile_id=2, name="Bình", username="binh"), SourceStudent(profile_id=3, name="Chi", username="chi")],
        }
        items = rosters[class_id]
        return SourcePage[SourceStudent](items=items, next_cursor=None, has_more=False, total=len(items), as_of=NOW)

    async def list_class_submissions(self, class_id, *, actor_profile_id, date_from=None, date_to=None,
                                     after_submission_id=None, cursor=None, limit=100):
        self.class_submission_calls.append(class_id)
        item = SourceSubmission(submission_id=100 + class_id, profile_id=class_id - 9, problem_id=7,
                                problem_code="GRAPH1", problem_title="Đồ thị 1", result="AC", points=100,
                                submitted_at=NOW - timedelta(minutes=class_id))
        other = SourceSubmission(submission_id=200 + class_id, profile_id=class_id - 9, problem_id=99,
                                 problem_code="PRACTICE", problem_title="Bài tự luyện", result="WA", points=0,
                                 submitted_at=NOW - timedelta(minutes=class_id))
        return SourceSubmissionPage(items=[item, other], next_cursor=None, has_more=False, total=2, as_of=NOW)


class ClassSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gateway = SessionGateway()
        self.app = FastAPI()
        self.app.include_router(teacher_router, prefix="/teacher")
        self.app.include_router(virtual_router, prefix="/virtual-class")

        async def gateway():
            return self.gateway

        async def actor():
            return SourceAccess(profile_id=2, exists=True, is_active=True, is_super_admin=True)

        self.app.dependency_overrides[get_source_gateway] = gateway
        self.app.dependency_overrides[get_current_user] = actor

    def client(self):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def test_there_is_no_local_start_or_stop(self):
        async with self.client() as client:
            self.assertEqual((await client.post("/virtual-class/10/start")).status_code, 404)
            self.assertEqual((await client.post("/virtual-class/sessions/1/stop")).status_code, 404)

    async def test_session_roster_merges_classes_and_keeps_non_submitters(self):
        async with self.client() as client:
            everyone = (await client.get("/teacher/my-contests/5/students")).json()
            one_class = (await client.get("/teacher/my-contests/5/students", params={"class_id": 11})).json()
            outside = await client.get("/teacher/my-contests/5/students", params={"class_id": 99})
        self.assertEqual([(row["user_id"], row["class_ids"]) for row in everyone], [(1, [10]), (2, [10, 11]), (3, [11])])
        self.assertEqual([row["user_id"] for row in one_class], [2, 3])
        self.assertEqual(outside.status_code, 404)

    async def test_live_submissions_can_focus_on_one_class(self):
        async with self.client() as client:
            both = (await client.get("/virtual-class/contests/5/live-submissions")).json()
            only = (await client.get("/virtual-class/contests/5/live-submissions", params={"class_id": 11})).json()
        self.assertEqual(sorted(self.gateway.class_submission_calls), [10, 11, 11])
        # Without a contest problem list every submission in the window is kept.
        self.assertEqual(len(both["events"]), 4)
        self.assertEqual(both["problems"], [])
        self.assertEqual(sorted(event["submission_id"] for event in only["events"]), [111, 211])
        self.assertTrue(only["is_active"])

    async def test_session_keeps_only_its_own_problems_in_contest_order(self):
        self.gateway.problems = [
            SourceContestProblem(problem_id=8, code="TREE", title="Cây", order=2),
            SourceContestProblem(problem_id=7, code="GRAPH1", title="Đồ thị 1", order=1, points=300, problem_points=100),
        ]
        async with self.client() as client:
            data = (await client.get("/virtual-class/contests/5/live-submissions", params={"class_id": 10})).json()
        self.assertEqual([(item["label"], item["code"]) for item in data["problems"]], [("A", "GRAPH1"), ("B", "TREE")])
        self.assertEqual([event["submission_id"] for event in data["events"]], [110])
        self.assertEqual(data["problems"][0]["points"], 300)
        self.assertEqual(data["events"][0]["record"]["score"], 300)  # AC earns the contest points

    def test_contest_score_follows_the_judge(self):
        from types import SimpleNamespace as Sub

        from app.api.v1.endpoints.virtual_class import contest_score
        from app.schemas.virtual_class import SessionProblem
        partial = SessionProblem(problem_id=1, code="P", title="P", label="A", points=100, problem_points=20)
        whole = partial.model_copy(update={"partial": False})
        self.assertEqual(contest_score(Sub(result="WA", points=5), partial), 25)
        self.assertEqual(contest_score(Sub(result="WA", points=5), whole), 0)
        self.assertEqual(contest_score(Sub(result="AC", points=20), whole), 100)
        self.assertIsNone(contest_score(Sub(result="AC", points=20), None))

    def test_problem_labels_continue_past_z(self):
        from app.api.v1.endpoints.virtual_class import problem_label
        self.assertEqual([problem_label(i) for i in (0, 1, 25, 26, 27, 51, 52)], ["A", "B", "Z", "AA", "AB", "AZ", "BA"])


if __name__ == "__main__":
    unittest.main()

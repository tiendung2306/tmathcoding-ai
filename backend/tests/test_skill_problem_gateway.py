import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.services.skill_problem_service import problem_detail, tag_problems
from app.services.source_gateway import (
    SourceProblem, SourceProblemFact, SourceProblemPage, SourceProblemFactsPage,
    SourceStudentAggregate, SourceStudentAggregateResponse, SourceSubmission,
    SourceSubmissionPage, SourceTag, SourceTagPage,
)


class FakeGateway:
    def __init__(self):
        self.reference_now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.catalog = [SourceProblem(
            problem_id=i, code=f"p{i:02}", title=f"Problem {i}", description=None,
            points=100, group_id=4, tag_ids=[39], version=1,
        ) for i in range(1, 26)]
        self.tags = [SourceTag(tag_id=39, key="map", title="Maps")]
        self.facts = [
            SourceProblemFact(
                problem_id=1, tag_ids=[39], group_id=4, attempt_count=2, ac_count=1,
                first_ac_submission_id=1, first_ac_at=self.reference_now - timedelta(days=8),
                failed_before_first_ac_count=1, best_ac_time=0.2,
                last_submission_at=self.reference_now, verdict_counts={"WA": 1, "AC": 1},
            ),
            SourceProblemFact(
                problem_id=2, tag_ids=[39], group_id=4, attempt_count=1, ac_count=0,
                first_ac_submission_id=None, first_ac_at=None, failed_before_first_ac_count=1,
                best_ac_time=None, last_submission_at=self.reference_now,
                verdict_counts={"WA": 1},
            ),
        ]
        self.calls = []

    async def get_student(self, profile_id, *, actor_profile_id):
        self.calls.append(("get_student", profile_id, actor_profile_id))
        return SimpleNamespace(profile_id=profile_id, name="Student")

    async def aggregate_students(self, profile_ids, *, actor_profile_id, date_from=None, date_to=None,
                                 tag_groups=None, include_problem_facts=False):
        self.calls.append(("aggregate_students", tuple(profile_ids), actor_profile_id,
                           date_from, include_problem_facts))
        facts = self.facts if include_problem_facts else None
        item = SourceStudentAggregate(
            profile_id=profile_ids[0], total_submissions=3, solved_unique_count=1,
            last_submission_at=self.reference_now, verdict_counts={"AC": 1, "WA": 2},
            tag_stats=[], group_stats=[], requested_group_stats=[], problem_facts=facts,
        )
        return SourceStudentAggregateResponse(
            students=[item], as_of=self.reference_now, reference_now=self.reference_now,
            catalog_version="catalog-v1",
        )

    async def list_tags(self, *, actor_profile_id, cursor=None, limit=100, if_none_match=None):
        self.calls.append(("list_tags", actor_profile_id, cursor, limit))
        page = SourceTagPage(items=self.tags, next_cursor=None, has_more=False,
                             catalog_version="catalog-v1", as_of=self.reference_now)
        return page, '"catalog-v1"', False

    async def list_problems(self, *, actor_profile_id, cursor=None, after_id=None, limit=100,
                            q=None, tag_id=None, group_id=None, ids=None, fields="summary"):
        self.calls.append(("list_problems", actor_profile_id, cursor, limit, q, tag_id, fields))
        rows = [item for item in self.catalog if tag_id is None or tag_id in item.tag_ids]
        if q:
            rows = [item for item in rows if q.casefold() in f"{item.code} {item.title}".casefold()]
        offset = int(cursor or 0)
        page = rows[offset:offset + limit]
        next_offset = offset + len(page)
        has_more = next_offset < len(rows)
        return SourceProblemPage(
            items=page, next_cursor=str(next_offset) if has_more else None,
            has_more=has_more, total=len(rows), as_of=self.reference_now,
            catalog_version="catalog-v1",
        )

    async def list_student_problem_facts(self, profile_id, *, actor_profile_id, date_from=None,
                                         date_to=None, cursor=None, limit=100):
        self.calls.append(("list_student_problem_facts", profile_id, actor_profile_id, date_from, cursor, limit))
        facts = self.facts if date_from is None else [fact for fact in self.facts if fact.problem_id == 2]
        offset = int(cursor or 0)
        page = facts[offset:offset + limit]
        next_offset = offset + len(page)
        return SourceProblemFactsPage(
            items=page, next_cursor=str(next_offset) if next_offset < len(facts) else None,
            has_more=next_offset < len(facts), total=len(facts),
            as_of=self.reference_now or datetime(2026, 1, 10, tzinfo=timezone.utc),
            catalog_version="catalog-v1",
        )

    async def get_problem(self, problem_id, *, actor_profile_id):
        self.calls.append(("get_problem", problem_id, actor_profile_id))
        return next((problem for problem in self.catalog if problem.problem_id == problem_id), None) or SourceProblem(
            problem_id=problem_id, code="special", title="Special", description="Statement",
            time_limit=2, memory_limit=512, group_id=4, tag_ids=[39], version=3,
        )

    async def list_student_submissions(self, profile_id, *, actor_profile_id, date_from=None, date_to=None,
                                       result=None, only_with_source=None, problem_id=None, cursor=None,
                                       limit=50, sort="desc"):
        self.calls.append(("list_student_submissions", profile_id, actor_profile_id, date_from,
                           problem_id, cursor, limit, sort))
        submissions = [
            SourceSubmission(submission_id=2, profile_id=profile_id, problem_id=problem_id,
                submitted_at=self.reference_now, result="WA", status="D", points=0, time=0.3, memory=512,
                has_source=False),
            SourceSubmission(submission_id=1, profile_id=profile_id, problem_id=problem_id,
                submitted_at=self.reference_now - timedelta(days=1), result=None, status="AC", points=100,
                time=0.2, memory=256, has_source=False),
        ]
        offset = int(cursor or 0)
        page = submissions[offset:offset + limit]
        next_offset = offset + len(page)
        return SourceSubmissionPage(items=page, next_cursor=str(next_offset) if next_offset < len(submissions) else None,
                                    has_more=next_offset < len(submissions), total=len(submissions),
                                    as_of=self.reference_now)


class SkillProblemGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_tag_catalog_is_filtered_before_numeric_pagination_without_per_problem_calls(self):
        gateway = FakeGateway()
        result = await tag_problems(gateway, 39, 7, page=2, page_size=20, actor_profile_id=9)
        self.assertEqual((result["total"], result["page"], result["total_pages"]), (25, 2, 2))
        self.assertEqual([item["id"] for item in result["items"]], [21, 22, 23, 24, 25])
        self.assertEqual(result["items"][0]["attempts"], 0)
        self.assertFalse(result["items"][0]["solved"])
        self.assertEqual(sum(call[0] == "get_problem" for call in gateway.calls), 0)
        self.assertTrue(any(call[0] == "list_problems" and call[5] == 39 for call in gateway.calls))

    async def test_status_and_time_range_use_final_facts_with_reference_now(self):
        gateway = FakeGateway()
        solved = await tag_problems(gateway, 39, 7, status="ac", actor_profile_id=9)
        self.assertEqual([item["id"] for item in solved["items"]], [1])
        self.assertEqual(solved["items"][0]["attempts"], 2)
        recent = await tag_problems(gateway, 39, 7, time_range="7d", status="ac", actor_profile_id=9)
        self.assertEqual(recent["items"], [])
        facts_calls = [call for call in gateway.calls if call[0] == "list_student_problem_facts"]
        self.assertEqual(facts_calls[-1][3], gateway.reference_now - timedelta(days=7))

    async def test_search_wildcards_are_passed_to_provider_as_literal_terms(self):
        gateway = FakeGateway()
        result = await tag_problems(gateway, 39, 7, q="%_\\", actor_profile_id=9)
        self.assertEqual(result["total"], 0)
        self.assertTrue(any(call[0] == "list_problems" and call[4] == "%_\\" for call in gateway.calls))

    async def test_catalog_version_change_between_facts_and_problems_fails_closed(self):
        gateway = FakeGateway()
        original = gateway.list_student_problem_facts

        async def changed_version(*args, **kwargs):
            page = await original(*args, **kwargs)
            page.catalog_version = "catalog-v2"
            return page

        gateway.list_student_problem_facts = changed_version
        # A non-all range forces a paged facts read; the problem catalog still
        # carries catalog-v1, so the provider detects the cross-read mismatch.
        with self.assertRaises(HTTPException) as caught:
            await tag_problems(gateway, 39, 7, time_range="7d", actor_profile_id=9)
        self.assertEqual(caught.exception.status_code, 409)

    async def test_missing_catalog_version_is_a_bad_upstream_response(self):
        gateway = FakeGateway()
        original = gateway.list_tags

        async def missing_version(**kwargs):
            page, etag, not_modified = await original(**kwargs)
            page.catalog_version = None
            return page, etag, not_modified

        gateway.list_tags = missing_version
        with self.assertRaises(HTTPException) as caught:
            await tag_problems(gateway, 39, 7, actor_profile_id=9)
        self.assertEqual(caught.exception.status_code, 502)

    async def test_missing_reference_clock_does_not_use_local_time(self):
        gateway = FakeGateway()
        gateway.reference_now = None
        await tag_problems(gateway, 39, 7, time_range="7d", actor_profile_id=9)
        calls = [call for call in gateway.calls if call[0] == "list_student_problem_facts"]
        self.assertIsNone(calls[-1][3])

    async def test_missing_tag_and_page_limits_are_rejected(self):
        gateway = FakeGateway()
        with self.assertRaises(HTTPException) as missing:
            await tag_problems(gateway, 999, 7, actor_profile_id=9)
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as oversized:
            await tag_problems(gateway, 39, 7, page_size=51, actor_profile_id=9)
        self.assertEqual(oversized.exception.status_code, 422)

    async def test_problem_detail_uses_problem_route_and_cursor_pages(self):
        gateway = FakeGateway()
        result = await problem_detail(gateway, 8, 7, page=2, page_size=1, actor_profile_id=9)
        self.assertEqual(result["id"], 8)
        self.assertEqual(result["description"], "")
        self.assertEqual(result["submissions"]["total"], 2)
        self.assertEqual(result["submissions"]["page"], 2)
        self.assertEqual(result["submissions"]["items"][0]["id"], 1)
        self.assertEqual(result["submissions"]["items"][0]["result"], "AC")
        calls = [call for call in gateway.calls if call[0] == "list_student_submissions"]
        self.assertEqual(len(calls), 2)
        self.assertEqual([call[5] for call in calls], [None, "1"])
        self.assertEqual(sum(call[0] == "get_problem" for call in gateway.calls), 1)

    async def test_problem_detail_rejects_repeated_upstream_cursor(self):
        gateway = FakeGateway()

        async def repeated_cursor(profile_id, **kwargs):
            return SourceSubmissionPage(
                items=[SourceSubmission(
                    submission_id=2, profile_id=profile_id, problem_id=8,
                    submitted_at=gateway.reference_now, result="WA", status="D",
                )], next_cursor="repeat", has_more=True, total=3,
                as_of=gateway.reference_now,
            )

        gateway.list_student_submissions = repeated_cursor
        with self.assertRaises(HTTPException) as caught:
            await problem_detail(gateway, 8, 7, page=3, page_size=1, actor_profile_id=9)
        self.assertEqual(caught.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()

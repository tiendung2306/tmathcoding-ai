import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException

from app.api.v1.endpoints.student import get_student_recent_submissions, get_student_tag_analytics
from app.api.v1.endpoints.teacher import get_managed_student_tag_analytics
from app.services.source_gateway import (
    SourceAnalyticsCatalog, SourcePage, SourceStudentAggregate,
    SourceStudentAggregateResponse, SourceTag, SourceTagPage,
    SourceTagProblemCount, SourceTagAggregateStat,
)
from app.services.tag_analytics_service import TagAnalyticsService


NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


class FakeGateway:
    def __init__(self):
        self.get_student = AsyncMock(return_value=SimpleNamespace(profile_id=17, name="Lin"))
        self.aggregate_students = AsyncMock(side_effect=self._aggregate)
        self.list_tags = AsyncMock(return_value=(SourceTagPage(
            items=[SourceTag(tag_id=4, key="arrays", title="Mảng")],
            next_cursor=None, has_more=False, catalog_version="c1", as_of=NOW,
        ), '"tags-v1"', False))
        self.get_analytics_catalog = AsyncMock(return_value=(SourceAnalyticsCatalog(
            catalog_version="c1", total_problem_count=19, tagged_problem_count=11,
            tag_problem_counts=[SourceTagProblemCount(tag_id=4, distinct_problem_count=5)],
            group_problem_counts=[], as_of=NOW,
        ), '"catalog-v1"', False))

    @staticmethod
    def _aggregate(profile_ids, *, date_from=None, **kwargs):
        elapsed = 0 if date_from is None else (NOW - date_from).days
        return SourceStudentAggregateResponse(
            students=[SourceStudentAggregate(
                profile_id=profile_ids[0], total_submissions=5 if elapsed == 0 else 3,
                solved_unique_count=2, last_submission_at=NOW, verdict_counts={"AC": 2, "WA": 3},
                tag_stats=[SourceTagAggregateStat(
                    tag_id=4, problem_count=5, solved_unique_count=2,
                    attempted_unique_count=3, verdict_counts={"AC": 2, "WA": 3},
                )], group_stats=[], requested_group_stats=[], problem_facts=None,
            )], as_of=NOW, reference_now=NOW, catalog_version="c1",
        )


class TagAnalyticsGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_metrics_use_provider_reference_and_tagged_problem_denominator(self):
        source = FakeGateway()
        result = await TagAnalyticsService.get_student_tag_analytics(
            17, source, "7d", actor_profile_id=9,
        )
        self.assertEqual(result.student_name, "Lin")
        self.assertEqual(result.summary.total_problems_in_system, 11)
        self.assertEqual(result.summary.total_submissions_period, 3)
        tag = result.tags[0]
        self.assertEqual((tag.total_problems, tag.ac_problems), (5, 2))
        self.assertEqual(tag.submissions_stat.wa_rate, 60.0)
        self.assertEqual(source.get_student.await_args.kwargs["actor_profile_id"], 9)
        self.assertEqual(source.aggregate_students.await_count, 2)
        self.assertEqual(source.aggregate_students.await_args_list[1].kwargs["date_from"], NOW - timedelta(days=7))
        # Calls are batched by endpoint; no per-tag or per-problem lookups.
        self.assertEqual(source.get_analytics_catalog.await_count, 1)
        self.assertEqual(source.list_tags.await_count, 1)

    async def test_empty_provider_has_no_local_reference_clock_fallback(self):
        source = FakeGateway()
        source.aggregate_students = AsyncMock(return_value=SourceStudentAggregateResponse(
            students=[SourceStudentAggregate(
                profile_id=17, total_submissions=0, solved_unique_count=0,
                last_submission_at=None, verdict_counts={}, tag_stats=[], group_stats=[],
                requested_group_stats=[], problem_facts=None,
            )], as_of=None, reference_now=None, catalog_version="c1",
        ))
        result = await TagAnalyticsService.get_student_tag_analytics(
            17, source, "7d", actor_profile_id=9,
        )
        self.assertEqual(source.aggregate_students.await_count, 1)
        self.assertIsNone(source.aggregate_students.await_args.kwargs["date_from"])
        self.assertEqual(result.summary.total_submissions_period, 0)

    async def test_provider_authorization_error_is_preserved(self):
        source = FakeGateway()
        source.get_student.side_effect = HTTPException(403, "forbidden")
        with self.assertRaises(HTTPException) as error:
            await TagAnalyticsService.get_student_tag_analytics(17, source, actor_profile_id=9)
        self.assertEqual(error.exception.status_code, 403)

    async def test_catalog_version_mismatch_returns_conflict_instead_of_mixing_metrics(self):
        source = FakeGateway()
        source.aggregate_students = AsyncMock(return_value=SourceStudentAggregateResponse(
            students=[SourceStudentAggregate(
                profile_id=17, total_submissions=1, solved_unique_count=1,
                last_submission_at=NOW, verdict_counts={"AC": 1}, tag_stats=[],
                group_stats=[], requested_group_stats=[], problem_facts=None,
            )], as_of=NOW, reference_now=NOW, catalog_version="stale-catalog",
        ))
        with self.assertRaises(HTTPException) as error:
            await TagAnalyticsService.get_student_tag_analytics(17, source, actor_profile_id=9)
        self.assertEqual(error.exception.status_code, 409)

    async def test_reference_clock_mismatch_returns_conflict(self):
        source = FakeGateway()
        first = source._aggregate([17])
        second = source._aggregate([17], date_from=NOW - timedelta(days=7))
        second.reference_now = NOW + timedelta(seconds=1)
        source.aggregate_students = AsyncMock(side_effect=[first, second])
        with self.assertRaises(HTTPException) as error:
            await TagAnalyticsService.get_student_tag_analytics(
                17, source, "7d", actor_profile_id=9,
            )
        self.assertEqual(error.exception.status_code, 409)

    async def test_student_and_teacher_routes_use_source_gateway_actor(self):
        source = FakeGateway()
        actor = SimpleNamespace(profile_id=9)
        await get_student_tag_analytics(17, "all", source, actor)
        await get_managed_student_tag_analytics(17, "all", source, actor)
        self.assertEqual(source.get_student.await_count, 2)
        self.assertEqual(source.get_student.await_args.kwargs["actor_profile_id"], 9)

    async def test_recent_submissions_exclude_ac_before_page_and_map_contract_fields(self):
        source = SimpleNamespace(list_student_submissions=AsyncMock(return_value=SimpleNamespace(items=[
            SimpleNamespace(submission_id=2, submitted_at=NOW, result="WA", points=50,
                            problem_id=31, problem_code="P31", problem_title="Problem 31"),
        ])))
        rows = await get_student_recent_submissions(17, True, 10, source, SimpleNamespace(profile_id=9))
        source.list_student_submissions.assert_awaited_once_with(
            17, actor_profile_id=9, exclude_result="AC", limit=10, sort="desc",
        )
        self.assertEqual((rows[0].id, rows[0].result, rows[0].problem_name), (2, "WA", "Problem 31"))


if __name__ == "__main__":
    unittest.main()

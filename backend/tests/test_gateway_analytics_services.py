import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.services.algorithm_competency_service import (
    AlgorithmCompetencyService,
    PILLAR_KEYS,
)
from app.services.heatmap_service import heatmap_service
from app.services.skill_tree_service import skill_tree_service


class ClassHeatmapGateway:
    def __init__(self, member_count=101):
        self.members = [
            SimpleNamespace(profile_id=i + 1, name=f"Student {i + 1}", points=10, problem_count=1,
                            display_rank="user", username=f"s{i + 1}", avatar_url=None)
            for i in range(member_count)
        ]
        self.aggregate_calls = []
        self.alert_calls = []
        self.reference = datetime(2026, 10, 13, tzinfo=timezone.utc)
        self.mismatch_reference = False

    async def get_class(self, class_id, *, actor_profile_id):
        return SimpleNamespace(class_id=class_id, name="Class A")

    async def list_class_students(self, class_id, *, actor_profile_id, cursor=None, limit=100):
        offset = 0 if cursor is None else int(cursor)
        items = self.members[offset:offset + limit]
        next_offset = offset + limit
        return SimpleNamespace(
            items=items,
            next_cursor=str(next_offset) if next_offset < len(self.members) else None,
            has_more=next_offset < len(self.members),
        )

    async def aggregate_students(self, profile_ids, *, actor_profile_id, date_from=None,
                                 date_to=None, tag_groups=(), include_problem_facts=False):
        call_index = len(self.aggregate_calls)
        self.aggregate_calls.append((tuple(profile_ids), date_from))
        reference = self.reference
        if self.mismatch_reference and call_index == 1:
            reference = datetime(2026, 10, 14, tzinfo=timezone.utc)
        requested = [
            SimpleNamespace(key=key, solved_unique_count=0, attempted_unique_count=0)
            for key in PILLAR_KEYS
        ]
        rows = [SimpleNamespace(profile_id=profile_id, requested_group_stats=requested)
                for profile_id in profile_ids]
        return SimpleNamespace(
            students=rows,
            reference_now=reference,
            as_of=reference,
            catalog_version="catalog-1",
        )

    async def get_student_alerts(self, profile_ids, *, actor_profile_id, at):
        self.alert_calls.append((tuple(profile_ids), at))
        return SimpleNamespace(items=[
            SimpleNamespace(profile_id=profile_id, last_submission_at=self.reference,
                            has_stuck_problem=False)
            for profile_id in profile_ids
        ], reference_now=self.reference)


class GatewayAnalyticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_actor_is_required_for_internal_analytics_calls(self):
        calls = [
            lambda: AlgorithmCompetencyService.get_student_radar(1, "all", object()),
            lambda: AlgorithmCompetencyService.get_class_competency_heatmap(1, "all", object()),
            lambda: heatmap_service.get_class_heatmap(1, "all", object()),
            lambda: heatmap_service.get_student_detail(1, object()),
            lambda: skill_tree_service.get_student_skill_tree(1, object()),
        ]
        for call in calls:
            with self.assertRaises(TypeError):
                call()

    async def test_class_radar_uses_bounded_batches_and_one_alert_call_per_batch(self):
        source = ClassHeatmapGateway()
        result = await AlgorithmCompetencyService.get_class_competency_heatmap(
            42, "30d", source, actor_profile_id=7,
        )

        self.assertEqual(len(result.students), 101)
        self.assertEqual(len(source.aggregate_calls), 4)  # two baseline + two period batches
        self.assertEqual([len(ids) for ids, _ in source.aggregate_calls], [100, 1, 100, 1])
        self.assertEqual([date_from is not None for _, date_from in source.aggregate_calls],
                         [False, False, True, True])
        self.assertEqual([len(ids) for ids, _ in source.alert_calls], [100, 1])
        self.assertEqual({at for _, at in source.alert_calls}, {source.reference})

    async def test_class_radar_rejects_mixed_baseline_reference_snapshots(self):
        source = ClassHeatmapGateway()
        source.mismatch_reference = True
        with self.assertRaises(HTTPException) as caught:
            await AlgorithmCompetencyService.get_class_competency_heatmap(
                42, "30d", source, actor_profile_id=7,
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(source.alert_calls, [])

    async def test_empty_configured_class_keeps_published_columns(self):
        class EmptyClassGateway:
            async def get_class(self, class_id, *, actor_profile_id):
                return SimpleNamespace(name="Empty")

            async def list_class_students(self, class_id, *, actor_profile_id, cursor=None, limit=100):
                return SimpleNamespace(items=[], next_cursor=None, has_more=False)

        config = SimpleNamespace(published={
            "nodes": [
                {"id": "custom", "title": "Custom", "description": "Custom root"},
                {"id": "other", "title": "Khác", "description": "Other topics"},
            ],
            "assignments": {},
        })
        with patch("app.services.skill_config_service.configuration", new=AsyncMock(return_value=config)), \
                patch("app.services.skill_config_service.class_ratings", new=AsyncMock(return_value=(['Custom', 'Khác'], {}))) as ratings:
            result = await AlgorithmCompetencyService.get_class_competency_heatmap(
                42, "all", EmptyClassGateway(), object(), actor_profile_id=7,
            )
        self.assertEqual(result.metric, "ac_count")
        self.assertEqual(result.columns, ["Custom", "Khác"])
        self.assertEqual(result.students, [])
        ratings.assert_awaited_once()

    async def test_configured_class_ratings_use_baseline_reference_anchor(self):
        config = SimpleNamespace(published={
            "nodes": [{"id": "other", "title": "Khác", "description": "Other topics"}],
            "assignments": {},
        })
        with patch("app.services.skill_config_service.configuration", new=AsyncMock(return_value=config)), \
                patch("app.services.skill_config_service.class_ratings", new=AsyncMock(return_value=(['Khác'], {1: [0]}))) as ratings:
            await AlgorithmCompetencyService.get_class_competency_heatmap(
                42, "all", ClassHeatmapGateway(member_count=1), object(), actor_profile_id=7,
            )
        self.assertEqual(ratings.await_args.kwargs["expected_reference_now"], ClassHeatmapGateway().reference)


if __name__ == "__main__":
    unittest.main()

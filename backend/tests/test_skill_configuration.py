import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.api.v1.endpoints.skill_config import router, require_admin, suggest as suggest_endpoint, cancel_suggestion
from app.services.source_gateway import (
    SourceAnalyticsCatalog, SourceProblem, SourceProblemFact, SourceProblemFactsPage, SourceProblemPage,
    SourceStudent, SourceStudentAggregate, SourceStudentAggregateResponse,
    SourceRequestedGroupAggregateStat, SourceTag, SourceTagPage, SourceTagProblemCount,
)
from app.services.source_gateway import get_source_gateway
from app.core.dashboard_database import get_dashboard_db
from app.core.config import settings
from app.core.time import utc_now
from app.models.dmoj import JudgeProfile, JudgeProblemtype, JudgeProblemTypes, JudgeProblem, JudgeSubmission
from app.models.skill_config import SkillConfiguration, SkillConfigurationVersion
from app.schemas.skill_config import SkillDocument, SkillAISuggestions, SkillProposalReview
from app.services import skill_config_service as service
from app.services.skill_tree_service import skill_tree_service
from db_fixtures import create_source_tables


def document():
    return SkillDocument.model_validate({"nodes": [
        {"id": "other", "title": "Khác", "description": "Chưa phân loại"},
        {"id": "ds", "title": "Cấu trúc dữ liệu", "description": "Các cấu trúc lưu trữ", "target": 2},
        {"id": "stl", "title": "STL", "description": "Container chuẩn", "parent_id": "ds", "target": 2},
        {"id": "map", "title": "Map", "description": "Ánh xạ", "parent_id": "stl", "target": 1},
        {"id": "set", "title": "Set", "description": "Tập hợp", "parent_id": "stl"},
        {"id": "empty", "title": "Rỗng", "description": "Chưa có bài"},
    ], "assignments": {39: "map", 38: "set"}})


class AsyncSession:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    def add(self, value):
        self.session.add(value)


class SkillSourceGateway:
    """Gateway fake backed by isolated fixture tables; service code sees DTOs only."""
    def __init__(self, session):
        self.session = session
        self.aggregate_batches = []
        self.reference_now = utc_now()
        self.tag_requests = 0
        self.problem_requests = 0

    def _version(self):
        counts = (self.session.query(JudgeProblemtype).count(), self.session.query(JudgeProblem).count(),
                  self.session.query(JudgeProblemTypes).count())
        return "fixture-" + "-".join(map(str, counts))

    async def get_analytics_catalog(self, *, actor_profile_id, if_none_match=None):
        tags = self.session.query(JudgeProblemtype).order_by(JudgeProblemtype.id).all()
        problems = self.session.query(JudgeProblem).order_by(JudgeProblem.id).all()
        counts = []
        for tag in tags:
            ids = {link.problem_id for link in self.session.query(JudgeProblemTypes).filter_by(problemtype_id=tag.id)}
            counts.append(SourceTagProblemCount(tag_id=tag.id, distinct_problem_count=len(ids)))
        version = self._version()
        return SourceAnalyticsCatalog(catalog_version=version, total_problem_count=len(problems),
            tagged_problem_count=len({link.problem_id for link in self.session.query(JudgeProblemTypes)}),
            tag_problem_counts=counts, group_problem_counts=[], as_of=utc_now()), f'"{version}"', False

    async def list_tags(self, *, actor_profile_id, cursor=None, limit=100, if_none_match=None):
        self.tag_requests += 1
        items = [SourceTag(tag_id=row.id, key=row.name or f"t{row.id}", title=row.full_name or row.name or str(row.id))
                 for row in self.session.query(JudgeProblemtype).order_by(JudgeProblemtype.id).all()]
        version = self._version()
        return SourceTagPage(items=items, catalog_version=version), f'"{version}"', False

    async def list_problems(self, *, actor_profile_id, cursor=None, after_id=None, limit=100, q=None,
                            tag_id=None, group_id=None, ids=None, fields="summary"):
        self.problem_requests += 1
        rows = self.session.query(JudgeProblem).order_by(JudgeProblem.id).all()
        if ids is not None:
            rows = [row for row in rows if row.id in ids]
        if after_id is not None:
            rows = [row for row in rows if row.id > after_id]
        if tag_id is not None:
            problem_ids = {link.problem_id for link in self.session.query(JudgeProblemTypes).filter_by(problemtype_id=tag_id)}
            rows = [row for row in rows if row.id in problem_ids]
        offset = int(cursor or 0)
        selected = rows[offset:offset + limit]
        items = []
        for row in selected:
            tags = [link.problemtype_id for link in self.session.query(JudgeProblemTypes).filter_by(problem_id=row.id)]
            items.append(SourceProblem(problem_id=row.id, code=row.code, title=row.name, tag_ids=tags,
                time_limit=row.time_limit, memory_limit=row.memory_limit, version=1))
        more = offset + len(selected) < len(rows)
        return SourceProblemPage(items=items, total=len(rows), next_cursor=str(offset + len(selected)) if more else None,
                                 has_more=more, catalog_version=self._version())

    async def get_student(self, profile_id, *, actor_profile_id):
        if self.session.get(JudgeProfile, profile_id) is None:
            from fastapi import HTTPException
            raise HTTPException(404, "Student not found")
        return SourceStudent(profile_id=profile_id)

    async def list_student_problem_facts(self, profile_id, *, actor_profile_id, date_from=None, date_to=None,
                                         cursor=None, limit=100):
        rows = self.session.query(JudgeSubmission).filter_by(user_id=profile_id).order_by(
            JudgeSubmission.problem_id, JudgeSubmission.date, JudgeSubmission.id).all()
        by_problem = {}
        for row in rows:
            by_problem.setdefault(row.problem_id, []).append(row)
        facts = []
        for problem_id, attempts in sorted(by_problem.items()):
            problem_row = self.session.get(JudgeProblem, problem_id)
            tags = [link.problemtype_id for link in self.session.query(JudgeProblemTypes).filter_by(problem_id=problem_id)]
            ac_rows = [row for row in attempts if row.result == "AC"]
            last = attempts[-1].date or utc_now()
            facts.append(SourceProblemFact(problem_id=problem_id, tag_ids=tags, group_id=problem_row.group_id if problem_row else None,
                attempt_count=len(attempts), ac_count=len(ac_rows), first_ac_submission_id=ac_rows[0].id if ac_rows else None,
                first_ac_at=ac_rows[0].date if ac_rows else None, failed_before_first_ac_count=0,
                best_ac_time=min((row.time for row in ac_rows if row.time is not None), default=None),
                first_ac_time=ac_rows[0].time if ac_rows else None,
                problem_time_limit=problem_row.time_limit if problem_row else None,
                problem_memory_limit=problem_row.memory_limit if problem_row else None,
                rapid_failure_pair_count=0, last_submission_at=last, verdict_counts={row.result or "UNKNOWN": sum(1 for item in attempts if item.result == row.result) for row in attempts}))
        offset = int(cursor or 0)
        selected = facts[offset:offset + limit]
        more = offset + len(selected) < len(facts)
        return SourceProblemFactsPage(items=selected, next_cursor=str(offset + len(selected)) if more else None,
            has_more=more, total=len(facts), as_of=utc_now(), catalog_version=self._version())

    async def aggregate_students(self, profile_ids, *, actor_profile_id, date_from=None, date_to=None,
                                 tag_groups=None, include_problem_facts=False):
        self.aggregate_batches.append(list(profile_ids))
        students = []
        for profile_id in profile_ids:
            facts_page = await self.list_student_problem_facts(profile_id, actor_profile_id=actor_profile_id,
                                                               date_from=date_from, date_to=date_to, cursor=None, limit=100)
            facts = facts_page.items
            requested = []
            for group in tag_groups or []:
                tag_ids = group.tag_ids if hasattr(group, "tag_ids") else group["tag_ids"]
                key = group.key if hasattr(group, "key") else group["key"]
                matching = [fact for fact in facts if set(fact.tag_ids) & set(tag_ids)]
                requested.append(SourceRequestedGroupAggregateStat(key=key,
                    solved_unique_count=sum(bool(item.ac_count) for item in matching),
                    attempted_unique_count=len(matching)))
            students.append(SourceStudentAggregate(profile_id=profile_id, total_submissions=sum(f.attempt_count for f in facts),
                solved_unique_count=sum(bool(f.ac_count) for f in facts), last_submission_at=None, verdict_counts={},
                tag_stats=[], group_stats=[], requested_group_stats=requested,
                problem_facts=facts if include_problem_facts else None))
        return SourceStudentAggregateResponse(students=students, as_of=utc_now(), reference_now=self.reference_now, catalog_version=self._version())


class ValidationTests(unittest.TestCase):
    def test_cycle_is_rejected(self):
        data = document().model_dump()
        data["nodes"][1]["parent_id"] = "map"
        with self.assertRaises(ValidationError):
            SkillDocument.model_validate(data)

    def test_other_must_remain_root_and_cannot_have_children(self):
        for field, value in (("title", "X"), ("parent_id", "ds")):
            data = document().model_dump()
            data["nodes"][0][field] = value
            with self.assertRaises(ValidationError):
                SkillDocument.model_validate(data)
        data = document().model_dump()
        data["nodes"][1]["parent_id"] = "other"
        with self.assertRaises(ValidationError):
            SkillDocument.model_validate(data)

    def test_mapping_to_unknown_node_is_rejected(self):
        data = document().model_dump()
        data["assignments"][39] = "missing"
        with self.assertRaises(ValidationError):
            SkillDocument.model_validate(data)

    def test_depth_limit(self):
        nodes = [{"id": "other", "title": "Khác", "description": "x"}]
        for i in range(9):
            nodes.append({"id": f"n{i}", "title": f"N{i}", "description": "x", "parent_id": f"n{i-1}" if i else None})
        with self.assertRaises(ValidationError):
            SkillDocument.model_validate({"nodes": nodes})

    def test_aggregation_deduplicates_tags_and_repeated_submissions(self):
        tags = [{"id": 39}, {"id": 38}, {"id": 99}]
        roots = service.build_forest(document(), tags, {39: {1, 2}, 38: {1, 3}, 99: {4}},
            [(10, 1, "AC"), (10, 1, "AC"), (11, 1, "AC"), (12, 2, "WA")])
        ds = next(root for root in roots if root["id"] == "ds")
        self.assertEqual((ds["problem_count"], ds["ac_count"], ds["attempted_count"], ds["submission_count"]), (3, 1, 2, 3))
        self.assertNotIn("score", ds)
        self.assertNotIn("target", ds)
        self.assertEqual(ds["children"][0]["ac_count"], 1)
        self.assertNotIn("empty", [root["id"] for root in roots])
        self.assertEqual(next(root for root in roots if root["id"] == "other")["problem_count"], 1)

    def test_unsolved_groups_stay_visible(self):
        roots = service.build_forest(document(), [{"id": 39}], {39: {1}}, [(10, 1, "WA")])
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["status"], "ATTEMPTED")
        self.assertEqual(roots[0]["ac_count"], 0)

    def test_counts_are_not_capped_and_legacy_targets_are_ignored(self):
        doc = document()
        pool = set(range(1, 132))
        roots = service.build_forest(doc, [{"id": 39}], {39: pool}, [(pid, pid, "AC") for pid in pool])
        self.assertEqual(roots[0]["ac_count"], 131)
        self.assertEqual(roots[0]["status"], "HAS_AC")
        self.assertNotIn("score", roots[0])
        self.assertNotIn("target", doc.model_dump(mode="json")["nodes"][1])

    def test_evidence_and_counts_share_current_catalog_scope(self):
        roots = service.build_forest(document(), [{"id": 39}], {39: {1}},
                                     [(1, 1, "AC"), (2, 99, "AC"), (3, 1, "WA")])
        self.assertEqual((roots[0]["ac_count"], roots[0]["attempted_count"], roots[0]["submission_count"]), (1, 1, 2))
        self.assertEqual([problem["id"] for problem in roots[0]["evidence"]], [1])


class StorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.source_engine = create_engine("sqlite://")
        create_source_tables(self.source_engine, JudgeProfile, JudgeProblemtype, JudgeProblemTypes, JudgeProblem, JudgeSubmission)
        self.source_session = Session(self.source_engine, expire_on_commit=False)
        self.source = SkillSourceGateway(self.source_session)
        service._catalog_cache.clear()
        self.source_session.execute(insert(JudgeProfile.__table__), [{"id": 2, "name": "Student"}])
        self.source_session.execute(insert(JudgeProblemtype.__table__), [{"id": 39, "name": "map", "full_name": "Map"}, {"id": 38, "name": "set", "full_name": "Set"}])
        self.source_session.execute(insert(JudgeProblem.__table__), [{"id": 1, "code": "p1", "name": "Problem"}])
        self.source_session.execute(insert(JudgeProblemTypes.__table__), [{"id": 1, "problem_id": 1, "problemtype_id": 39}, {"id": 2, "problem_id": 1, "problemtype_id": 38}])
        self.source_session.execute(insert(JudgeSubmission.__table__), [{"id": 1, "user_id": 2, "problem_id": 1, "result": "AC"}])
        self.source_session.commit()
        self.dashboard_engine = create_engine("sqlite://")
        SkillConfiguration.__table__.create(self.dashboard_engine)
        SkillConfigurationVersion.__table__.create(self.dashboard_engine)
        self.dashboard_session = Session(self.dashboard_engine, expire_on_commit=False)
        self.dashboard = AsyncSession(self.dashboard_session)
        initial = {"nodes": [{"id": "other", "title": "Khác", "description": "Chưa phân loại"}], "assignments": {}}
        self.dashboard.add(SkillConfiguration(id=1, revision=0, published_version=0, draft=initial))
        self.dashboard_session.commit()

    def tearDown(self):
        self.source_session.close()
        self.dashboard_session.close()
        self.source_engine.dispose()
        self.dashboard_engine.dispose()

    async def test_draft_does_not_publish_and_conflict_cannot_overwrite(self):
        result = await service.write(self.dashboard, self.source, 0, document(), 7, actor_profile_id=7)
        self.assertEqual(result["revision"], 1)
        self.assertIsNone((await service.configuration(self.dashboard)).published)
        with self.assertRaises(HTTPException) as caught:
            await service.write(self.dashboard, self.source, 0, document(), 7, actor_profile_id=7)
        self.assertEqual(caught.exception.status_code, 409)

    async def test_apply_updates_counts_without_creating_history(self):
        await service.write(self.dashboard, self.source, 0, document(), 7, True, actor_profile_id=7)
        saved = self.dashboard_session.get(SkillConfigurationVersion, 1)
        self.assertIsNone(saved)
        result = await skill_tree_service.get_student_skill_tree(2, self.source, dashboard_db=self.dashboard,
                                                                actor_profile_id=7)
        roots = {root["id"]: root for root in result.skill_forest}
        self.assertEqual(result.configuration_version, 1)
        self.assertNotIn("evidence", next(iter(roots.values())))
        self.assertNotIn("tags", next(iter(roots.values())))
        for axis in result.bloom_radar.axes:
            self.assertEqual(axis["ac_count"], roots[axis["key"]]["ac_count"])
            self.assertNotIn("score", axis)
        altered = document().model_copy(deep=True)
        altered.nodes[1].title = "Changed"
        await service.write(self.dashboard, self.source, 1, altered, 7, True, actor_profile_id=7)
        self.assertEqual((await service.configuration(self.dashboard)).published["nodes"][1]["title"], "Changed")
        self.assertIsNone(self.dashboard_session.get(SkillConfigurationVersion, 2))

    async def test_missing_source_tag_is_rejected(self):
        altered = document().model_copy(deep=True)
        altered.assignments[999] = "ds"
        with self.assertRaises(HTTPException) as caught:
            await service.write(self.dashboard, self.source, 0, altered, 7, actor_profile_id=7)
        self.assertEqual(caught.exception.status_code, 422)

    async def test_only_other_cannot_publish(self):
        row = await service.configuration(self.dashboard)
        with self.assertRaises(HTTPException) as caught:
            await service.write(self.dashboard, self.source, 0, SkillDocument.model_validate(row.draft), 7, True, actor_profile_id=7)
        self.assertEqual(caught.exception.status_code, 422)

    async def test_preview_reads_two_independent_databases_without_writing(self):
        result = await service.preview(document(), self.source, 2, actor_profile_id=7)
        self.assertEqual(result["roots"][0]["ac_count"], 1)
        self.assertEqual((await service.configuration(self.dashboard)).revision, 0)
        self.assertEqual(len(self.source_session.execute(select(JudgeProblemTypes)).all()), 2)

    async def test_class_scores_match_student_roots_and_hide_empty_groups(self):
        columns, scores = await service.class_ratings(document(), self.source, [2, 3], None, actor_profile_id=7)
        result = await service.preview(document(), self.source, 2, actor_profile_id=7)
        self.assertEqual(columns, [root["title"] for root in result["roots"]])
        self.assertEqual(scores[2], [root["ac_count"] for root in result["roots"]])
        self.assertEqual(scores[3], [0])
        leaf = result["roots"][0]["children"][0]["children"][0]["children"][0]
        self.assertEqual((leaf["id"], leaf["ac_count"]), ("topic:39", 1))

    async def test_class_scores_batch_more_than_one_hundred_students(self):
        profile_ids = list(range(1, 202))
        columns, scores = await service.class_ratings(document(), self.source, profile_ids, None,
                                                       actor_profile_id=7)
        self.assertEqual(len(scores), len(profile_ids))
        self.assertEqual([len(batch) for batch in self.source.aggregate_batches], [100, 100, 1])
        self.assertEqual(len(columns), 1)

    async def test_class_scores_reject_changed_reference_even_when_anchor_is_null(self):
        response = SourceStudentAggregateResponse(students=[], as_of=utc_now(), reference_now=utc_now(),
                                                   catalog_version=self.source._version())
        with patch.object(self.source, "aggregate_students", new=AsyncMock(return_value=response)):
            with self.assertRaises(HTTPException) as caught:
                await service.class_ratings(document(), self.source, [2], None,
                    actor_profile_id=7, expected_reference_now=None)
        self.assertEqual(caught.exception.status_code, 409)

    async def test_catalog_cache_hit_keeps_version_and_skips_full_fetch(self):
        first = await service.catalog(self.source, 7)
        tag_calls, problem_calls = self.source.tag_requests, self.source.problem_requests
        second = await service.catalog(self.source, 7)
        self.assertEqual(first[2], second[2])
        self.assertEqual((self.source.tag_requests, self.source.problem_requests), (tag_calls, problem_calls))

    async def test_configuration_reads_and_validation_do_not_scan_problems(self):
        state = await service.state(self.dashboard, self.source, actor_profile_id=7)
        await service.validate_document(document(), self.source, actor_profile_id=7)
        self.assertEqual(len(state["tags"]), 2)
        self.assertEqual(self.source.problem_requests, 0)

        _, pools, _ = await service.catalog(self.source, 7)
        self.assertEqual(pools[39], {1})
        self.assertEqual(self.source.problem_requests, 1)

    async def test_ai_only_suggests_unassigned_valid_roots(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {38: "set"}
        response = SkillAISuggestions.model_validate({"suggestions": [{"tag_id": 39, "node_id": "ds", "reason": "Lưu trữ ánh xạ"}]})
        with patch.object(service.llm_adapter, "generate_structured", new=AsyncMock(return_value=response)):
            result = await service.suggest(doc, self.source, actor_profile_id=7)
        self.assertEqual(result["suggestions"][0]["tag_id"], 39)
        self.assertEqual(doc.assignments, {38: "set"})
        response.suggestions[0].node_id = "map"
        with patch.object(service.llm_adapter, "generate_structured", new=AsyncMock(return_value=response)):
            with self.assertRaises(HTTPException) as caught:
                await service.suggest(doc, self.source, actor_profile_id=7)
        self.assertEqual(caught.exception.status_code, 502)

    async def test_ai_array_format_is_validated_and_batch_is_small(self):
        self.source_session.execute(insert(JudgeProblemtype.__table__), [{"id":40,"name":"tree"}, {"id":41,"name":"dp"}])
        self.source_session.commit()
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        response = SkillAISuggestions.model_validate([{"tag_id": tid, "node_id":"ds", "reason":"Lưu trữ"} for tid in [38,39,40]])
        with patch.object(service.llm_adapter, "generate_structured", new=AsyncMock(return_value=response)):
            result = await service.suggest(doc, self.source, actor_profile_id=7)
        self.assertEqual((result["batch_size"], result["remaining"]), (3,4))
        self.assertEqual([item["tag_id"] for item in result["suggestions"]], [38,39,40])
        self.assertEqual(doc.assignments, {})

    async def test_ai_errors_and_incomplete_result_do_not_change_configuration(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        for failure, expected in [(TimeoutError(),504), (ConnectionError("unavailable"),503)]:
            with patch.object(service.llm_adapter,"generate_structured",new=AsyncMock(side_effect=failure)):
                with self.assertRaises(HTTPException) as caught:
                    await service.suggest(doc,self.source,actor_profile_id=7)
            self.assertEqual(caught.exception.status_code, expected)
        response = SkillAISuggestions.model_validate({"suggestions":[{"tag_id":38,"node_id":"ds","reason":"Lưu trữ"}]})
        with patch.object(service.llm_adapter,"generate_structured",new=AsyncMock(return_value=response)):
            with self.assertRaises(HTTPException) as caught:
                await service.suggest(doc,self.source,actor_profile_id=7)
        self.assertEqual(caught.exception.status_code,502)
        self.assertEqual((await service.configuration(self.dashboard)).revision,0)
        self.assertEqual(doc.assignments,{})

    async def test_disconnected_client_cancels_model_work(self):
        cancelled = asyncio.Event()
        async def inference(*args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
        with patch.object(service, "suggest", new=inference):
            with self.assertRaises(HTTPException) as caught:
                await suggest_endpoint(document(), request, SimpleNamespace(source_profile_id=7), self.source)
        self.assertEqual(caught.exception.status_code,499)
        self.assertTrue(cancelled.is_set())

    async def test_proposals_persist_each_batch_without_applying_the_tree(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.store_proposals(self.dashboard, doc, [{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}])
        await service.store_proposals(self.dashboard, doc, [{"tag_id":39,"node_id":"ds","reason":"Ánh xạ"}])
        self.dashboard_session.expire_all()
        result = await service.state(self.dashboard, self.source, actor_profile_id=7)
        self.assertEqual([item["tag_id"] for item in result["proposals"]], [38,39])
        self.assertTrue(all(item["status"] == "pending" for item in result["proposals"]))
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["document"]["assignments"], {})
        self.assertFalse(result["has_published"])

    async def test_bulk_rejection_is_persistent_and_keeps_tags_unassigned(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.store_proposals(self.dashboard, doc, [{"tag_id":id,"node_id":"ds","reason":"Lưu trữ"} for id in [38,39]])
        payload = SkillProposalReview(document=doc, action="reject", tag_ids=[38,39])
        result = await service.review_proposals(self.dashboard, self.source, payload, actor_profile_id=7)
        self.dashboard_session.expire_all()
        self.assertTrue(all(item["status"] == "rejected" for item in result["proposals"]))
        row = await service.configuration(self.dashboard)
        self.assertEqual(row.revision,0)
        self.assertEqual(row.draft["assignments"],{})
        self.assertEqual([item["status"] for item in row.proposals], ["rejected","rejected"])
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"other","reason":"Kết quả đến muộn"}])
        self.assertEqual((await service.configuration(self.dashboard)).proposals[0]["status"],"rejected")

    async def test_assignment_status_commits_only_with_successful_apply(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}])
        doc.assignments = {38:"ds"}
        with self.assertRaises(HTTPException):
            await service.write(self.dashboard,self.source,99,doc,7,True,actor_profile_id=7)
        self.assertEqual((await service.configuration(self.dashboard)).proposals[0]["status"],"pending")
        result = await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        self.assertEqual(result["proposals"],[])
        self.assertEqual((await service.configuration(self.dashboard)).proposals[0]["status"],"assigned")
        self.assertEqual(result["document"]["assignments"],{"38":"ds"})

    async def test_manual_destination_immediately_applies_and_resolves_the_proposal(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}])
        doc.assignments = {38:"set"}
        result = await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        item = (await service.configuration(self.dashboard)).proposals[0]
        self.assertEqual((item["node_id"],item["source_node_id"],item["reason"]),("set","ds","Tập hợp"))
        self.assertEqual(result["proposals"],[])
        self.assertEqual((await service.configuration(self.dashboard)).published["assignments"],{"38":"set"})
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"other","reason":"Kết quả đến muộn"}])
        self.assertEqual((await service.state(self.dashboard,self.source,actor_profile_id=7))["proposals"],[])
        doc.assignments = {}
        result = await service.write(self.dashboard,self.source,1,doc,7,True,actor_profile_id=7)
        self.assertEqual(result["proposals"],[])
        self.assertEqual((await service.configuration(self.dashboard)).proposals,[])

    async def test_bulk_approval_applies_atomically_and_only_selected_tags(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        await service.store_proposals(self.dashboard,doc,[{"tag_id":id,"node_id":"ds","reason":"Lưu trữ"} for id in [38,39]])
        result = await service.review_proposals(self.dashboard,self.source,SkillProposalReview(document=doc,action="approve",revision=1,tag_ids=[38]),7,actor_profile_id=7)
        self.assertEqual(result["document"]["assignments"],{"38":"ds"})
        self.assertEqual([item["tag_id"] for item in result["proposals"]],[39])
        self.assertEqual((await service.configuration(self.dashboard)).published["assignments"],{"38":"ds"})

    async def test_one_rejected_row_prevents_the_entire_bulk_approval(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        await service.store_proposals(self.dashboard,doc,[{"tag_id":id,"node_id":"ds","reason":"Lưu trữ"} for id in [38,39]])
        await service.review_proposals(self.dashboard,self.source,SkillProposalReview(document=doc,action="reject",tag_ids=[39]),actor_profile_id=7)
        with self.assertRaises(HTTPException) as caught:
            await service.review_proposals(self.dashboard,self.source,SkillProposalReview(document=doc,action="approve",revision=1,tag_ids=[38,39]),7,actor_profile_id=7)
        self.assertEqual(caught.exception.status_code,409)
        row = await service.configuration(self.dashboard)
        self.assertEqual(row.published["assignments"],{})
        self.assertEqual(row.revision,1)

    async def test_approval_cannot_overwrite_unselected_assignment_from_payload(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {39:"map"}
        await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}])
        submitted = doc.model_copy(deep=True)
        submitted.assignments[39] = "other"
        result = await service.review_proposals(self.dashboard,self.source,SkillProposalReview(document=submitted,action="approve",revision=1,tag_ids=[38]),7,actor_profile_id=7)
        self.assertEqual(result["document"]["assignments"],{"39":"map","38":"ds"})

    async def test_stale_approval_revision_and_context_leave_everything_unchanged(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        await service.write(self.dashboard,self.source,0,doc,7,True,actor_profile_id=7)
        await service.store_proposals(self.dashboard,doc,[{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}])
        for revision, change_context in [(0,False),(1,True)]:
            submitted = doc.model_copy(deep=True)
            if change_context:
                submitted.nodes[1].description = "Phạm vi khác"
            with self.assertRaises(HTTPException) as caught:
                await service.review_proposals(self.dashboard,self.source,SkillProposalReview(document=submitted,action="approve",revision=revision,tag_ids=[38]),7,actor_profile_id=7)
            self.assertEqual(caught.exception.status_code,409)
        self.assertEqual((await service.configuration(self.dashboard)).published["assignments"],{})

    async def test_suggestion_endpoint_saves_valid_result_before_returning(self):
        doc = document().model_copy(deep=True)
        doc.assignments = {}
        response = {"suggestions":[{"tag_id":38,"node_id":"ds","reason":"Tập hợp"}]}
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        with patch.object(service,"suggest",new=AsyncMock(return_value=response)):
            await suggest_endpoint(doc,request,SimpleNamespace(source_profile_id=7),self.source,dashboard=self.dashboard)
        self.assertEqual((await service.state(self.dashboard,self.source,actor_profile_id=7))["proposals"][0]["tag_id"],38)

    async def test_explicit_stop_cancels_work_and_blocks_late_request(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def inference(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        with patch.object(service,"suggest",new=inference):
            pending = asyncio.create_task(suggest_endpoint(document(),request,SimpleNamespace(source_profile_id=7),self.source,run_id="unit-cancel-run"))
            await started.wait()
            await cancel_suggestion("unit-cancel-run")
            with self.assertRaises(HTTPException) as caught:
                await pending
            self.assertEqual(caught.exception.status_code,499)
            self.assertTrue(cancelled.is_set())
            with self.assertRaises(HTTPException) as caught:
                await suggest_endpoint(document(),request,SimpleNamespace(source_profile_id=7),self.source,run_id="unit-cancel-run")
            self.assertEqual(caught.exception.status_code,499)

    async def test_admin_guard_atomic_apply_and_removed_routes(self):
        app = FastAPI()
        app.include_router(router, prefix="/admin/skill-config")
        async def source():
            yield self.source
        async def dashboard():
            yield self.dashboard
        app.dependency_overrides[get_source_gateway] = lambda: self.source
        app.dependency_overrides[get_dashboard_db] = dashboard
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(source_profile_id=7)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put('/admin/skill-config', json={"revision": 0, "document": document().model_dump(mode="json")})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["has_published"])
            row = await service.configuration(self.dashboard)
            self.assertEqual(row.draft, row.published)
            self.assertEqual(row.updated_by, 7)
            self.assertNotIn("versions", response.json())
            self.assertEqual((await client.put('/admin/skill-config', json={"revision": 0, "document": document().model_dump(mode="json")})).status_code, 409)
            self.assertEqual((await client.post('/admin/skill-config/versions/1/restore', json={"revision": 1})).status_code, 404)
            self.assertEqual((await client.post('/admin/skill-config/preview', json={})).status_code, 404)

    async def test_skill_configuration_routes_use_gateway_and_dashboard_admin(self):
        app = FastAPI()
        app.include_router(router, prefix="/admin/skill-config")
        async def dashboard():
            yield self.dashboard
        app.dependency_overrides[get_source_gateway] = lambda: self.source
        app.dependency_overrides[get_dashboard_db] = dashboard
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(source_profile_id=7)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get('/admin/skill-config')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("tags", response.json())

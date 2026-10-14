import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException

from app.core.time_ranges import get_cutoff_date
from app.services.source_cleaner import prepare_source
from app.services.source_gateway import SourceGateway, SourceTagGroupRequest
from app.schemas.student import AlgorithmRadar, PillarBreakdownItem
from app.schemas.teacher import (
    ClassHeatmapResponse,
    HeatmapStudentRow,
    StudentBloomScore,
)
from app.services.competency_evaluator import CompetencyEvaluator

# 8 Trụ cột Thuật toán Cốt lõi (Ánh xạ từ các tag thực tế trong judge_problemtype)
ALGORITHM_PILLARS = {
    "quy_hoach_dong": {
        "name": "Quy hoạch động",
        "tag_ids": [14, 31, 61, 63, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 89, 106],
        "target_all": 25,
        "target_1y": 15,
        "target_30d": 6,
        "target_7d": 3,
        "target_1d": 1,
    },
    "cau_truc_du_lieu": {
        "name": "Cấu trúc dữ liệu",
        "tag_ids": [23, 44, 27, 28, 37, 38, 39, 56, 96, 92, 33, 108],
        "target_all": 20,
        "target_1y": 12,
        "target_30d": 5,
        "target_7d": 2,
        "target_1d": 1,
    },
    "xu_ly_xau": {
        "name": "Xử lý xâu",
        "tag_ids": [9, 62, 75, 26],
        "target_all": 20,
        "target_1y": 12,
        "target_30d": 5,
        "target_7d": 2,
        "target_1d": 1,
    },
    "ham_co_ban": {
        "name": "Hàm và Đệ quy",
        "tag_ids": [10, 13, 20, 4, 5, 6, 7, 8, 47, 59, 24, 87, 88, 90, 25, 74, 105, 45, 91, 94, 103, 110, 22, 16, 17, 18, 54],
        "target_all": 30,
        "target_1y": 20,
        "target_30d": 8,
        "target_7d": 4,
        "target_1d": 2,
    },
    "toan_hoc": {
        "name": "Toán học và Số học",
        "tag_ids": [11, 19, 32, 49, 52, 60, 66, 67, 68, 69, 70, 71, 72, 73, 95, 97, 100, 101, 102, 107],
        "target_all": 25,
        "target_1y": 15,
        "target_30d": 6,
        "target_7d": 3,
        "target_1d": 1,
    },
    "hinh_hoc": {
        "name": "Hình học tính toán",
        "tag_ids": [12],
        "target_all": 10,
        "target_1y": 6,
        "target_30d": 3,
        "target_7d": 1,
        "target_1d": 1,
    },
    "do_thi": {
        "name": "Lý thuyết đồ thị",
        "tag_ids": [15, 29, 30, 35, 40, 55, 57, 58, 64, 93, 98, 99, 104],
        "target_all": 25,
        "target_1y": 15,
        "target_30d": 6,
        "target_7d": 3,
        "target_1d": 1,
    },
    "tham_lam": {
        "name": "Thuật toán tham lam",
        "tag_ids": [21],
        "target_all": 15,
        "target_1y": 10,
        "target_30d": 4,
        "target_7d": 2,
        "target_1d": 1,
    },
}

PILLAR_KEYS = list(ALGORITHM_PILLARS.keys())
PILLAR_COLUMNS = [ALGORITHM_PILLARS[k]["name"] for k in PILLAR_KEYS]
PILLAR_DISPLAY_LABELS = {key: ALGORITHM_PILLARS[key]["name"] for key in PILLAR_KEYS}
INACTIVE_DAYS = 7


class AlgorithmCompetencyService:
    """Calculate student radars and class ratings from source API snapshots."""

    @staticmethod
    def get_cutoff_date(time_range: str, ref_now: datetime | None) -> datetime | None:
        return get_cutoff_date(time_range, ref_now) if ref_now is not None else None

    @staticmethod
    def get_target_benchmark(pillar_key: str, time_range: str) -> int:
        pillar = ALGORITHM_PILLARS.get(pillar_key, {})
        key = f"target_{time_range}" if time_range in {"1d", "7d", "30d", "1y"} else "target_all"
        return pillar.get(key, 20)

    @staticmethod
    def _tag_groups() -> list[SourceTagGroupRequest]:
        return [SourceTagGroupRequest(key=key, tag_ids=ALGORITHM_PILLARS[key]["tag_ids"])
                for key in PILLAR_KEYS]

    @staticmethod
    async def _facts_for_student(source: SourceGateway, profile_id: int, actor_profile_id: int,
                                 date_from: datetime | None, embedded) -> tuple[list, str | int | None]:
        if embedded is not None:
            return embedded, None
        facts = []
        cursor = None
        seen: set[str] = set()
        version = None
        while True:
            page = await source.list_student_problem_facts(
                profile_id, actor_profile_id=actor_profile_id, date_from=date_from,
                date_to=None, cursor=cursor, limit=100,
            )
            if version is None:
                version = page.catalog_version
            elif page.catalog_version != version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
            facts.extend(page.items)
            if not page.has_more:
                return facts, version
            cursor = page.next_cursor
            if not cursor or cursor in seen:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
            seen.add(cursor)

    @staticmethod
    async def _student_radar_data(source: SourceGateway, user_id: int, time_range: str,
                                 actor_profile_id: int):
        groups = AlgorithmCompetencyService._tag_groups()
        try:
            initial = await source.aggregate_students(
                [user_id], actor_profile_id=actor_profile_id, tag_groups=groups,
                include_problem_facts=True,
            )
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            initial = await source.aggregate_students(
                [user_id], actor_profile_id=actor_profile_id, tag_groups=groups,
                include_problem_facts=False,
            )
        reference_now = initial.reference_now
        cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, reference_now)
        window = initial
        if cutoff is not None:
            try:
                window = await source.aggregate_students(
                    [user_id], actor_profile_id=actor_profile_id, date_from=cutoff,
                    date_to=None, tag_groups=groups, include_problem_facts=True,
                )
            except HTTPException as exc:
                if exc.status_code != 422:
                    raise
                window = await source.aggregate_students(
                    [user_id], actor_profile_id=actor_profile_id, date_from=cutoff,
                    date_to=None, tag_groups=groups, include_problem_facts=False,
                )
            if window.catalog_version != initial.catalog_version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
        student = next((item for item in window.students if item.profile_id == user_id), None)
        if student is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")
        facts, facts_version = await AlgorithmCompetencyService._facts_for_student(
            source, user_id, actor_profile_id, cutoff, student.problem_facts,
        )
        if facts_version is not None and facts_version != window.catalog_version:
            raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
        try:
            samples = await source.list_student_submission_samples(
                user_id, actor_profile_id=actor_profile_id, date_from=cutoff,
                date_to=None, tag_ids=sorted({tag for group in groups for tag in group.tag_ids}),
                result="AC", per_group_limit=3,
            )
            sample_items = samples.items
        except HTTPException as exc:
            # Code quality is an optional radar component when the caller lacks
            # the provider's separate source-code scope.
            if exc.status_code != 403:
                raise
            sample_items = []
        return reference_now, cutoff, facts, sample_items, window.catalog_version

    @staticmethod
    async def get_student_radar(
        user_id: int,
        time_range: str,
        source: SourceGateway,
        dashboard_db=None,
        *, actor_profile_id: int,
    ) -> AlgorithmRadar:
        await source.get_student(user_id, actor_profile_id=actor_profile_id)
        reference_now, cutoff, facts, samples, _version = await AlgorithmCompetencyService._student_radar_data(
            source, user_id, time_range, actor_profile_id,
        )
        if dashboard_db is not None:
            from app.services.skill_config_service import configuration, preview
            from app.schemas.skill_config import SkillDocument
            config = await configuration(dashboard_db)
            if config.published is not None:
                forest = await preview(
                    SkillDocument.model_validate(config.published), source, user_id,
                    cutoff, actor_profile_id=actor_profile_id,
                )
                return AlgorithmRadar(time_range=time_range, axes=[{
                    "key": root["id"], "title": root["title"],
                    "ac_count": root["ac_count"], "attempted_count": root["attempted_count"],
                    "problem_count": root["problem_count"],
                } for root in forest["roots"]])

        scores: Dict[str, float] = {}
        breakdown: Dict[str, PillarBreakdownItem] = {}
        for key in PILLAR_KEYS:
            tags = set(ALGORITHM_PILLARS[key]["tag_ids"])
            matching = [fact for fact in facts if tags.intersection(fact.tag_ids)]
            problems_map = {}
            submissions = []
            for fact in matching:
                problems_map[fact.problem_id] = {
                    "group_id": fact.group_id,
                    "time_limit": fact.problem_time_limit or 1.0,
                    "memory_limit": fact.problem_memory_limit or 256000,
                    "attempts": fact.attempt_count,
                    "is_ac": fact.ac_count > 0,
                    "ac_time": (fact.first_ac_time if fact.first_ac_time is not None
                                else fact.best_ac_time or 0.0),
                    "ac_sub_id": fact.first_ac_submission_id,
                    "fail_before_ac": fact.failed_before_first_ac_count,
                    "rapid_failure_pair_count": fact.rapid_failure_pair_count,
                }
                for verdict, count in fact.verdict_counts.items():
                    submissions.extend({"problem_id": fact.problem_id, "result": verdict} for _ in range(count))

            sample_sources = []
            for item in samples:
                if tags.intersection(item.tag_ids) and item.source_code:
                    prepared = await asyncio.to_thread(
                        prepare_source, item.source_code, item.language_key or "unknown",
                    )
                    sample_sources.append(prepared.analysis_source)
            result = CompetencyEvaluator.evaluate_pillar(
                pillar_key=key, time_range=time_range, submissions=submissions,
                problems_map=problems_map, sample_sources=sample_sources[:3],
            )
            scores[key] = result["score"]
            breakdown[key] = PillarBreakdownItem(
                score=result["score"], base_score=result["base_score"],
                precision_mod=result["precision_mod"], efficiency_mod=result["efficiency_mod"],
                code_quality_mod=result["code_quality_mod"], ac_count=result["ac_count"],
                total_subs=result["total_subs"], avg_time_ratio=result["avg_time_ratio"],
                breakdown_items=result["breakdown_items"],
            )
        return AlgorithmRadar(
            time_range=time_range, quy_hoach_dong=scores["quy_hoach_dong"],
            cau_truc_du_lieu=scores["cau_truc_du_lieu"], xu_ly_xau=scores["xu_ly_xau"],
            ham_co_ban=scores["ham_co_ban"], toan_hoc=scores["toan_hoc"],
            hinh_hoc=scores["hinh_hoc"], do_thi=scores["do_thi"], tham_lam=scores["tham_lam"],
            breakdown=breakdown,
        )

    @staticmethod
    async def _class_students(source: SourceGateway, class_id: int, actor_profile_id: int):
        students = []
        cursor = None
        seen: set[str] = set()
        while True:
            page = await source.list_class_students(
                class_id, actor_profile_id=actor_profile_id, cursor=cursor, limit=100,
            )
            students.extend(page.items)
            if not page.has_more:
                return students
            cursor = page.next_cursor
            if not cursor or cursor in seen:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả phân trang lớp không hợp lệ.")
            seen.add(cursor)

    @staticmethod
    async def get_class_competency_heatmap(
        org_id: int,
        time_range: str,
        source: SourceGateway,
        dashboard_db=None,
        *, actor_profile_id: int,
    ) -> ClassHeatmapResponse:
        organization = await source.get_class(org_id, actor_profile_id=actor_profile_id)
        members = await AlgorithmCompetencyService._class_students(source, org_id, actor_profile_id)
        configured_document = None
        columns = PILLAR_COLUMNS
        if dashboard_db is not None:
            from app.services.skill_config_service import configuration, class_ratings
            from app.schemas.skill_config import SkillDocument
            config = await configuration(dashboard_db)
            if config.published is not None:
                configured_document = SkillDocument.model_validate(config.published)
        if not members:
            if configured_document is not None:
                from app.services.skill_config_service import class_ratings
                columns, _ = await class_ratings(
                    configured_document, source, [], None, actor_profile_id=actor_profile_id,
                )
                metric = "ac_count"
            else:
                columns = PILLAR_COLUMNS
                metric = "score"
            return ClassHeatmapResponse(
                organization_id=org_id, organization_name=organization.name or f"Lớp #{org_id}",
                time_range=time_range, columns=columns,
                metric=metric,
                students=[], class_averages=[0.0] * len(columns),
            )
        member_ids = [member.profile_id for member in members]
        groups = AlgorithmCompetencyService._tag_groups()
        baseline_pages = []
        for start in range(0, len(member_ids), 100):
            batch = await source.aggregate_students(
                member_ids[start:start + 100], actor_profile_id=actor_profile_id,
                tag_groups=groups,
            )
            if baseline_pages and batch.catalog_version != baseline_pages[0].catalog_version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải heatmap.")
            expected_ids = set(member_ids[start:start + 100])
            if {item.profile_id for item in batch.students} != expected_ids:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")
            baseline_pages.append(batch)
        baseline_version = baseline_pages[0].catalog_version
        references = [page.reference_now for page in baseline_pages]
        if any(value != references[0] for value in references[1:]):
            raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải heatmap.")
        reference = references[0]
        as_of = max((page.as_of for page in baseline_pages if page.as_of), default=None)
        at = reference or as_of
        if at is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu mốc thời gian snapshot.")
        cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, reference)

        aggregates = []
        for start in range(0, len(member_ids), 100):
            batch_ids = member_ids[start:start + 100]
            baseline_response = baseline_pages[start // 100]
            response = baseline_response if cutoff is None else await source.aggregate_students(
                batch_ids, actor_profile_id=actor_profile_id, date_from=cutoff, date_to=None,
                tag_groups=groups, include_problem_facts=False,
            )
            if response.catalog_version != baseline_version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải heatmap.")
            if response.reference_now != baseline_response.reference_now:
                raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải heatmap.")
            if {item.profile_id for item in response.students} != set(batch_ids):
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")
            aggregates.extend(response.students)
        alerts = {}
        for start in range(0, len(member_ids), 100):
            response = await source.get_student_alerts(
                member_ids[start:start + 100], actor_profile_id=actor_profile_id, at=at,
            )
            if response.reference_now != reference:
                raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải heatmap.")
            if {item.profile_id for item in response.items} != set(member_ids[start:start + 100]):
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu trạng thái học sinh.")
            for item in response.items:
                alerts[item.profile_id] = item

        col_sums = [0.0] * len(PILLAR_KEYS)
        rows = []
        by_id = {member.profile_id: member for member in members}
        for student in sorted(aggregates, key=lambda item: item.profile_id):
            profile = by_id.get(student.profile_id)
            counts = {stat.key: stat.solved_unique_count for stat in student.requested_group_stats}
            scores = []
            for i, key in enumerate(PILLAR_KEYS):
                target = AlgorithmCompetencyService.get_target_benchmark(key, time_range)
                score = min(100.0, round(counts.get(key, 0) / target * 100.0, 1)) if target else 0.0
                scores.append(score)
                col_sums[i] += score
            alert = alerts.get(student.profile_id)
            flags = []
            last = alert.last_submission_at if alert else None
            if last is None or (at - last > timedelta(days=INACTIVE_DAYS)):
                flags.append("INACTIVE")
            if alert and alert.has_stuck_problem:
                flags.append("STUCK")
            if ((counts.get("quy_hoach_dong", 0) >= 3 or counts.get("do_thi", 0) >= 3)
                    and counts.get("ham_co_ban", 0) == 0):
                flags.append("GAP")
            rows.append(HeatmapStudentRow(
                user_id=student.profile_id,
                student_name=(profile.name or f"User {student.profile_id}") if profile else f"User {student.profile_id}",
                scores=scores, alerts=flags,
            ))
        n = len(rows)
        averages = [round(total / n, 1) if n else 0.0 for total in col_sums]
        if configured_document is not None:
            from app.services.skill_config_service import class_ratings
            columns, configured_scores = await class_ratings(
                configured_document, source, member_ids, cutoff,
                actor_profile_id=actor_profile_id, expected_reference_now=reference,
            )
            for row in rows:
                row.scores = configured_scores.get(row.user_id, [0.0] * len(columns))
            averages = [round(sum(row.scores[i] for row in rows) / n, 1) for i in range(len(columns))] if n else [0.0] * len(columns)
        return ClassHeatmapResponse(
            organization_id=org_id, organization_name=organization.name or f"Lớp #{org_id}",
            time_range=time_range, columns=columns,
            metric="ac_count" if configured_document is not None else "score",
            students=rows, class_averages=averages,
        )


algorithm_competency_service = AlgorithmCompetencyService()

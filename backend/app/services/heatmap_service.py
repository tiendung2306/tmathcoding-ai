from datetime import timedelta
from typing import Dict, List

from fastapi import HTTPException

from app.schemas.teacher import (
    ClassHeatmapResponse,
    ClassStudentItem,
    StudentBloomScore,
    StudentDetailResponse,
    StudentDetailSummary,
)
from app.services.algorithm_competency_service import (
    AlgorithmCompetencyService,
    PILLAR_KEYS,
    PILLAR_DISPLAY_LABELS,
)
from app.services.source_gateway import SourceGateway, SourceTagGroupRequest


INACTIVE_DAYS = 7


class HeatmapService:
    """Assemble class and student views from source API snapshots."""

    @staticmethod
    async def get_class_heatmap(
        org_id: int,
        time_range: str,
        source: SourceGateway,
        dashboard_db=None,
        *, actor_profile_id: int,
    ) -> ClassHeatmapResponse:
        return await AlgorithmCompetencyService.get_class_competency_heatmap(
            org_id, time_range, source, dashboard_db, actor_profile_id=actor_profile_id,
        )

    @staticmethod
    async def get_student_detail(
        student_id: int,
        source: SourceGateway,
        time_range: str = "all",
        dashboard_db=None,
        *, actor_profile_id: int,
    ) -> StudentDetailResponse:
        profile = await source.get_student(student_id, actor_profile_id=actor_profile_id)
        groups = AlgorithmCompetencyService._tag_groups()
        baseline = await source.aggregate_students(
            [student_id], actor_profile_id=actor_profile_id, tag_groups=groups,
        )
        reference_now = baseline.reference_now
        cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, reference_now)
        period = baseline
        if cutoff is not None:
            period = await source.aggregate_students(
                [student_id], actor_profile_id=actor_profile_id, date_from=cutoff,
                date_to=None, tag_groups=groups,
            )
            if (period.catalog_version != baseline.catalog_version
                    or period.reference_now != reference_now):
                raise HTTPException(409, "Danh mục hoặc mốc dữ liệu đã thay đổi trong lúc tải; hãy thử lại.")
        aggregate = next((item for item in period.students if item.profile_id == student_id), None)
        if aggregate is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")

        radar = await AlgorithmCompetencyService.get_student_radar(
            student_id, time_range, source, dashboard_db, actor_profile_id=actor_profile_id,
        )
        if radar.axes is not None:
            bloom_scores = [
                StudentBloomScore(
                    group_id=index + 1,
                    label=axis["title"],
                    score=axis["ac_count"],
                )
                for index, axis in enumerate(radar.axes)
            ]
            metric = "ac_count"
        else:
            bloom_scores = [
                StudentBloomScore(
                    group_id=index + 1,
                    label=PILLAR_DISPLAY_LABELS.get(key, key),
                    score=getattr(radar, key, 0.0),
                )
                for index, key in enumerate(PILLAR_KEYS)
            ]
            metric = "score"

        catalog, _etag, not_modified = await source.get_analytics_catalog(
            actor_profile_id=actor_profile_id,
        )
        if not_modified or catalog is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn không trả danh mục analytics.")
        if catalog.catalog_version != baseline.catalog_version:
            raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")

        at = reference_now or baseline.as_of
        if at is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu mốc thời gian snapshot.")
        alerts_response = await source.get_student_alerts(
            [student_id], actor_profile_id=actor_profile_id, at=at,
        )
        if alerts_response.reference_now != reference_now:
            raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải chi tiết học sinh.")
        alerts_by_id = {item.profile_id: item for item in alerts_response.items}
        alert = alerts_by_id.get(student_id)
        if alert is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu trạng thái học sinh.")
        last_submission_at = alert.last_submission_at
        flags = []
        if last_submission_at is None or at - last_submission_at > timedelta(days=INACTIVE_DAYS):
            flags.append("INACTIVE")
        if alert.has_stuck_problem:
            flags.append("STUCK")

        return StudentDetailResponse(
            user_id=student_id,
            name=profile.name or f"User {student_id}",
            username=profile.username or f"user_{student_id}",
            time_range=time_range,
            points=profile.points or 0.0,
            performance_points=profile.performance_points or 0.0,
            problem_count=profile.problem_count or 0,
            display_rank=profile.display_rank or "user",
            organizations=[item.name for item in profile.classes],
            bloom_scores=bloom_scores,
            metric=metric,
            alerts=flags,
            last_submission_at=last_submission_at.isoformat() if last_submission_at else None,
            summary=StudentDetailSummary(
                total_problems_in_system=catalog.total_problem_count,
                total_solved_unique=aggregate.solved_unique_count,
                total_submissions_7d=aggregate.total_submissions,
                time_range=time_range,
                total_submissions_period=aggregate.total_submissions,
            ),
        )

    @staticmethod
    async def get_class_students(
        org_id: int,
        source: SourceGateway,
        actor_profile_id: int,
    ) -> List[ClassStudentItem]:
        organization = await source.get_class(org_id, actor_profile_id=actor_profile_id)
        members = await AlgorithmCompetencyService._class_students(
            source, org_id, actor_profile_id,
        )
        if not members:
            return []
        member_ids = [member.profile_id for member in members]
        baseline_pages = []
        for start in range(0, len(member_ids), 100):
            requested_ids = member_ids[start:start + 100]
            page = await source.aggregate_students(
                requested_ids, actor_profile_id=actor_profile_id, tag_groups=[],
            )
            if baseline_pages and page.catalog_version != baseline_pages[0].catalog_version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải chi tiết lớp.")
            if {item.profile_id for item in page.students} != set(requested_ids):
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")
            baseline_pages.append(page)
        references = [page.reference_now for page in baseline_pages]
        if any(value != references[0] for value in references[1:]):
            raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải chi tiết lớp.")
        at = references[0] or max((page.as_of for page in baseline_pages if page.as_of), default=None)
        if at is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu mốc thời gian snapshot.")
        alerts: Dict[int, object] = {}
        for start in range(0, len(members), 100):
            requested_ids = member_ids[start:start + 100]
            page = await source.get_student_alerts(
                requested_ids,
                actor_profile_id=actor_profile_id, at=at,
            )
            if page.reference_now != references[0]:
                raise HTTPException(409, "Mốc dữ liệu đã thay đổi trong lúc tải chi tiết lớp.")
            if {item.profile_id for item in page.items} != set(requested_ids):
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu trạng thái học sinh.")
            alerts.update({item.profile_id: item for item in page.items})
        if set(alerts) != set(member_ids):
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu trạng thái học sinh.")
        output = []
        for member in sorted(members, key=lambda item: (-item.points, item.profile_id)):
            alert = alerts[member.profile_id]
            flags = []
            if alert.last_submission_at is None or at - alert.last_submission_at > timedelta(days=INACTIVE_DAYS):
                flags.append("INACTIVE")
            if alert.has_stuck_problem:
                flags.append("STUCK")
            output.append(ClassStudentItem(
                user_id=member.profile_id,
                name=member.name or f"User {member.profile_id}",
                username=member.username or f"user_{member.profile_id}",
                avatar_url=member.avatar_url,
                points=round(member.points or 0.0, 1),
                problem_count=member.problem_count or 0,
                display_rank=member.display_rank or "user",
                alerts=flags,
                last_submission_at=alert.last_submission_at.isoformat() if alert.last_submission_at else None,
            ))
        return output


heatmap_service = HeatmapService()

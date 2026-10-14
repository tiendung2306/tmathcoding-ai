import asyncio
from fastapi import HTTPException

from app.core.time_ranges import get_cutoff_date
from app.schemas.analytics import (
    StudentTagAnalyticsResponse,
    StudentTagAnalyticsSummary,
    TagMetricItem,
    TagSubmissionStat,
)
from app.services.source_gateway import SourceGateway


class TagAnalyticsService:
    @staticmethod
    async def _all_tags(source: SourceGateway, actor_profile_id: int):
        tags = []
        cursor = None
        seen: set[str] = set()
        catalog_version = None
        while True:
            page, _, not_modified = await source.list_tags(
                actor_profile_id=actor_profile_id, cursor=cursor, limit=100,
            )
            if not_modified or page is None:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn không trả danh sách tag.")
            if catalog_version is None:
                if page.catalog_version is None:
                    raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu phiên bản danh mục tag.")
                catalog_version = page.catalog_version
            elif page.catalog_version != catalog_version:
                raise HTTPException(409, "Danh mục dữ liệu đã thay đổi; hãy tải lại thống kê.")
            tags.extend(page.items)
            if not page.has_more:
                return tags, catalog_version
            cursor = page.next_cursor
            if not cursor or cursor in seen:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả phân trang tag không hợp lệ.")
            seen.add(cursor)

    @staticmethod
    async def get_student_tag_analytics(
        user_id: int,
        source: SourceGateway,
        time_range: str = "all",
        *,
        actor_profile_id: int,
    ) -> StudentTagAnalyticsResponse:
        # This first aggregate supplies the provider's reference clock. The
        # windowed request below uses the same anchor as the legacy dashboard.
        profile, initial, tag_result, catalog_result = await asyncio.gather(
            source.get_student(user_id, actor_profile_id=actor_profile_id),
            source.aggregate_students([user_id], actor_profile_id=actor_profile_id,
                                      date_from=None, date_to=None, tag_groups=[],
                                      include_problem_facts=False),
            TagAnalyticsService._all_tags(source, actor_profile_id),
            source.get_analytics_catalog(actor_profile_id=actor_profile_id),
        )
        tags, tags_version = tag_result
        catalog, _, not_modified = catalog_result
        if not_modified or catalog is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn không trả danh mục analytics.")
        expected_version = catalog.catalog_version
        if tags_version != expected_version or initial.catalog_version != expected_version:
            raise HTTPException(409, "Danh mục dữ liệu đã thay đổi; hãy tải lại thống kê.")

        reference_now = initial.reference_now
        cutoff = get_cutoff_date(time_range, reference_now) if reference_now is not None else None
        aggregate = initial
        if cutoff is not None:
            aggregate = await source.aggregate_students(
                [user_id], actor_profile_id=actor_profile_id,
                date_from=cutoff, date_to=None, tag_groups=[], include_problem_facts=False,
            )
            if aggregate.catalog_version != expected_version:
                raise HTTPException(409, "Danh mục dữ liệu đã thay đổi; hãy tải lại thống kê.")
            if aggregate.reference_now != reference_now:
                raise HTTPException(409, "Mốc dữ liệu đã thay đổi; hãy tải lại thống kê.")
        student_aggregate = next(
            (item for item in aggregate.students if item.profile_id == user_id), None,
        )
        if student_aggregate is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")

        tag_stats = {item.tag_id: item for item in student_aggregate.tag_stats}
        catalog_counts = {item.tag_id: item.distinct_problem_count for item in catalog.tag_problem_counts}
        tag_items: list[TagMetricItem] = []

        for tag in tags:
            stat = tag_stats.get(tag.tag_id)
            total_problems = catalog_counts.get(tag.tag_id, 0)
            solved_problems = stat.solved_unique_count if stat else 0
            completion_rate = round(solved_problems / total_problems * 100.0, 1) if total_problems else 0.0

            if total_problems <= 3:
                tag_weight = "small"
            elif total_problems >= 10:
                tag_weight = "large"
            else:
                tag_weight = "medium"

            verdicts = dict(stat.verdict_counts) if stat else {}
            if "UNKNOWN" in verdicts:
                verdicts["OTHER"] = verdicts.get("OTHER", 0) + verdicts.pop("UNKNOWN")
            ac_count = verdicts.get("AC", 0)
            wa_count = verdicts.get("WA", 0)
            tle_count = verdicts.get("TLE", 0)
            other_count = sum(count for key, count in verdicts.items() if key not in {"AC", "WA", "TLE"})
            total_submissions = ac_count + wa_count + tle_count + other_count
            ac_rate = round(ac_count / total_submissions * 100.0, 1) if total_submissions else 0.0
            wa_rate = round(wa_count / total_submissions * 100.0, 1) if total_submissions else 0.0
            tle_rate = round(tle_count / total_submissions * 100.0, 1) if total_submissions else 0.0

            primary_error = None
            if tle_count > wa_count and tle_count > 0:
                primary_error = "TLE"
            elif wa_count > 0:
                primary_error = "WA"

            submissions_stat = TagSubmissionStat(
                total_submissions=total_submissions,
                ac_count=ac_count,
                wa_count=wa_count,
                tle_count=tle_count,
                other_count=other_count,
                ac_rate=ac_rate,
                wa_rate=wa_rate,
                tle_rate=tle_rate,
                primary_error=primary_error,
            )

            if completion_rate >= 70.0:
                status = "MASTERED"
            elif total_submissions >= 3 and (wa_rate >= 50.0 or tle_rate >= 50.0):
                status = "NEEDS_IMPROVEMENT"
            elif solved_problems > 0 or total_submissions > 0:
                status = "PRACTICING"
            else:
                status = "UNATTEMPTED"

            tag_items.append(TagMetricItem(
                tag_id=tag.tag_id,
                key=tag.key or f"T{tag.tag_id}",
                name=tag.title or tag.key or f"Topic {tag.tag_id}",
                total_problems=total_problems,
                ac_problems=solved_problems,
                completion_rate=completion_rate,
                tag_weight=tag_weight,
                submissions_stat=submissions_stat,
                status=status,
            ))

        total_submissions_period = student_aggregate.total_submissions
        summary = StudentTagAnalyticsSummary(
            total_problems_in_system=catalog.tagged_problem_count,
            total_solved_unique=student_aggregate.solved_unique_count,
            total_submissions_7d=total_submissions_period,
            time_range=time_range,
            total_submissions_period=total_submissions_period,
        )
        return StudentTagAnalyticsResponse(
            user_id=user_id,
            student_name=profile.name or f"User {user_id}",
            time_range=time_range,
            summary=summary,
            tags=tag_items,
        )


tag_analytics_service = TagAnalyticsService()

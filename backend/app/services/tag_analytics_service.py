from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from fastapi import HTTPException

from app.models.dmoj import JudgeSubmission, JudgeProblem, JudgeProblemTypes, JudgeProblemtype, JudgeProfile
from app.schemas.analytics import (
    TagSubmissionStat,
    TagMetricItem,
    StudentTagAnalyticsSummary,
    StudentTagAnalyticsResponse
)

class TagAnalyticsService:
    @staticmethod
    async def get_student_tag_analytics(user_id: int, db: AsyncSession) -> StudentTagAnalyticsResponse:
        # 1. Fetch Profile
        prof_stmt = select(JudgeProfile).where(JudgeProfile.id == user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        student_name = profile.name if profile else f"User {user_id}"

        # 2. Query Total Problems in System per Tag
        total_problems_stmt = (
            select(
                JudgeProblemTypes.problemtype_id,
                func.count(JudgeProblemTypes.problem_id).label("total_cnt")
            )
            .group_by(JudgeProblemTypes.problemtype_id)
        )
        total_res = await db.execute(total_problems_stmt)
        total_problems_map: Dict[int, int] = {row.problemtype_id: row.total_cnt for row in total_res.all()}

        # 3. Query Unique AC Solved Problems by Student per Tag (All-Time)
        solved_stmt = (
            select(
                JudgeProblemTypes.problemtype_id,
                func.count(func.distinct(JudgeSubmission.problem_id)).label("ac_cnt")
            )
            .join(JudgeSubmission, JudgeSubmission.problem_id == JudgeProblemTypes.problem_id)
            .where(JudgeSubmission.user_id == user_id, JudgeSubmission.result == "AC")
            .group_by(JudgeProblemTypes.problemtype_id)
        )
        solved_res = await db.execute(solved_stmt)
        solved_problems_map: Dict[int, int] = {row.problemtype_id: row.ac_cnt for row in solved_res.all()}

        # 4. Query 7-Day Submissions Breakdown per Tag
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        sub_7d_stmt = (
            select(
                JudgeProblemTypes.problemtype_id,
                JudgeSubmission.result,
                func.count(JudgeSubmission.id).label("sub_cnt")
            )
            .join(JudgeSubmission, JudgeSubmission.problem_id == JudgeProblemTypes.problem_id)
            .where(
                JudgeSubmission.user_id == user_id,
                JudgeSubmission.date >= seven_days_ago
            )
            .group_by(JudgeProblemTypes.problemtype_id, JudgeSubmission.result)
        )
        sub_7d_res = await db.execute(sub_7d_stmt)
        
        # Structure 7d sub data: {tag_id: {'AC': x, 'WA': y, 'TLE': z, ...}}
        sub_7d_map: Dict[int, Dict[str, int]] = {}
        total_submissions_7d = 0
        for row in sub_7d_res.all():
            tag_id = row.problemtype_id
            verdict = row.result or "OTHER"
            cnt = row.sub_cnt
            total_submissions_7d += cnt

            if tag_id not in sub_7d_map:
                sub_7d_map[tag_id] = {}
            sub_7d_map[tag_id][verdict] = sub_7d_map[tag_id].get(verdict, 0) + cnt

        # 5. Fetch all 99 topics
        topics_stmt = select(JudgeProblemtype).order_by(JudgeProblemtype.id)
        topics_res = await db.execute(topics_stmt)
        all_topics = topics_res.scalars().all()

        tag_items: List[TagMetricItem] = []
        total_solved_unique_system = sum(solved_problems_map.values())
        total_problems_in_system = sum(total_problems_map.values())

        for t in all_topics:
            t_id = t.id
            tot_p = total_problems_map.get(t_id, 0)
            ac_p = solved_problems_map.get(t_id, 0)
            comp_rate = round((ac_p / tot_p * 100.0), 1) if tot_p > 0 else 0.0

            # Weight classification
            if tot_p <= 3:
                tag_weight = "small"
            elif tot_p >= 10:
                tag_weight = "large"
            else:
                tag_weight = "medium"

            # 7d submission stats
            verdicts = sub_7d_map.get(t_id, {})
            ac_c = verdicts.get("AC", 0)
            wa_c = verdicts.get("WA", 0)
            tle_c = verdicts.get("TLE", 0)
            other_c = sum(v for k, v in verdicts.items() if k not in ["AC", "WA", "TLE"])
            tot_sub = ac_c + wa_c + tle_c + other_c

            ac_rate = round((ac_c / tot_sub * 100.0), 1) if tot_sub > 0 else 0.0
            wa_rate = round((wa_c / tot_sub * 100.0), 1) if tot_sub > 0 else 0.0
            tle_rate = round((tle_c / tot_sub * 100.0), 1) if tot_sub > 0 else 0.0

            primary_err = None
            if tle_c > wa_c and tle_c > 0:
                primary_err = "TLE"
            elif wa_c > 0:
                primary_err = "WA"

            stat_obj = TagSubmissionStat(
                total_submissions=tot_sub,
                ac_count=ac_c,
                wa_count=wa_c,
                tle_count=tle_c,
                other_count=other_c,
                ac_rate=ac_rate,
                wa_rate=wa_rate,
                tle_rate=tle_rate,
                primary_error=primary_err
            )

            # Determine Tag Status
            if comp_rate >= 70.0:
                status = "MASTERED"
            elif tot_sub >= 3 and (wa_rate >= 50.0 or tle_rate >= 50.0):
                status = "NEEDS_IMPROVEMENT"
            elif ac_p > 0 or tot_sub > 0:
                status = "PRACTICING"
            else:
                status = "UNATTEMPTED"

            tag_items.append(
                TagMetricItem(
                    tag_id=t_id,
                    key=t.name or f"T{t_id}",
                    name=t.full_name or t.name or f"Topic {t_id}",
                    total_problems=tot_p,
                    ac_problems=ac_p,
                    completion_rate=comp_rate,
                    tag_weight=tag_weight,
                    submissions_stat=stat_obj,
                    status=status
                )
            )

        summary_obj = StudentTagAnalyticsSummary(
            total_problems_in_system=total_problems_in_system,
            total_solved_unique=total_solved_unique_system,
            total_submissions_7d=total_submissions_7d
        )

        return StudentTagAnalyticsResponse(
            user_id=user_id,
            student_name=student_name,
            summary=summary_obj,
            tags=tag_items
        )

tag_analytics_service = TagAnalyticsService()

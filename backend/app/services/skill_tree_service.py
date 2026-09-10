from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.dmoj import JudgeSubmission, JudgeProblemTypes, JudgeProblemtype, JudgeProfile
from app.schemas.student import SkillTreeResponse, SkillTreeNode, AlgorithmRadar
from app.services.algorithm_competency_service import algorithm_competency_service
from fastapi import HTTPException

class SkillTreeService:
    @staticmethod
    async def get_student_skill_tree(
        user_id: int,
        db: AsyncSession,
        time_range: str = "all"
    ) -> SkillTreeResponse:
        # Fetch profile
        prof_stmt = select(JudgeProfile).where(JudgeProfile.id == user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        student_name = (profile.name or f"User {user_id}") if profile else f"User {user_id}"

        # Xác định cutoff date theo mốc thời gian
        ref_now = await algorithm_competency_service.get_reference_now(db)
        cutoff_date = algorithm_competency_service.get_cutoff_date(time_range, ref_now)

        # Fetch solved problems by topic in the selected time range
        stmt = (
            select(
                JudgeProblemTypes.problemtype_id,
                func.count(func.distinct(JudgeSubmission.problem_id)).label("ac_count")
            )
            .join(JudgeSubmission, JudgeSubmission.problem_id == JudgeProblemTypes.problem_id)
            .where(JudgeSubmission.user_id == user_id, JudgeSubmission.result == "AC")
        )
        if cutoff_date:
            stmt = stmt.where(JudgeSubmission.date >= cutoff_date)

        stmt = stmt.group_by(JudgeProblemTypes.problemtype_id)
        res = await db.execute(stmt)
        topic_ac_map = {row.problemtype_id: row.ac_count for row in res.all()}

        # Fetch all 99 topics
        topics_stmt = select(JudgeProblemtype).order_by(JudgeProblemtype.id)
        topics_res = await db.execute(topics_stmt)
        all_topics = topics_res.scalars().all()

        # Benchmark mục tiêu theo mốc thời gian
        benchmark_target = 10.0
        if time_range == "7d":
            benchmark_target = 2.0
        elif time_range == "30d":
            benchmark_target = 4.0
        elif time_range == "1y":
            benchmark_target = 8.0

        nodes = []
        for t in all_topics:
            ac_count = topic_ac_map.get(t.id, 0)
            mastery = min(100.0, (ac_count / benchmark_target) * 100.0)
            
            status = "LOCKED"
            if mastery >= 75.0:
                status = "GREEN"
            elif mastery >= 25.0:
                status = "YELLOW"
            elif ac_count > 0:
                status = "RED"
                
            nodes.append(
                SkillTreeNode(
                    topic_id=t.id,
                    key=t.name or f"T{t.id}",
                    name=t.full_name or t.name or f"Topic {t.id}",
                    category="Chủ đề",
                    mastery_score=round(mastery, 1),
                    status=status
                )
            )

        # Tính điểm Radar 8 Trụ cột Thuật toán thật theo mốc thời gian
        radar = await algorithm_competency_service.get_student_radar(user_id, time_range, db)

        return SkillTreeResponse(
            user_id=user_id,
            student_name=student_name,
            time_range=time_range,
            bloom_radar=radar,
            skill_tree_nodes=nodes
        )

skill_tree_service = SkillTreeService()

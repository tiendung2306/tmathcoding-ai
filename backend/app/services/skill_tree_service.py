from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.dmoj import JudgeSubmission, JudgeProblem, JudgeProblemTypes, JudgeProblemtype, JudgeProfile
from app.schemas.student import SkillTreeResponse, SkillTreeNode, BloomRadar
from fastapi import HTTPException

class SkillTreeService:
    @staticmethod
    async def get_student_skill_tree(user_id: int, db: AsyncSession) -> SkillTreeResponse:
        # Fetch profile
        prof_stmt = select(JudgeProfile).where(JudgeProfile.id == user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        student_name = profile.name if profile else f"User {user_id}"

        # Fetch solved problems by topic
        stmt = (
            select(
                JudgeProblemTypes.problemtype_id,
                func.count(func.distinct(JudgeSubmission.problem_id)).label("ac_count")
            )
            .join(JudgeSubmission, JudgeSubmission.problem_id == JudgeProblemTypes.problem_id)
            .where(JudgeSubmission.user_id == user_id, JudgeSubmission.result == "AC")
            .group_by(JudgeProblemTypes.problemtype_id)
        )
        res = await db.execute(stmt)
        topic_ac_map = {row.problemtype_id: row.ac_count for row in res.all()}

        # Fetch all 99 topics
        topics_stmt = select(JudgeProblemtype).order_by(JudgeProblemtype.id)
        topics_res = await db.execute(topics_stmt)
        all_topics = topics_res.scalars().all()

        nodes = []
        for t in all_topics:
            ac_count = topic_ac_map.get(t.id, 0)
            mastery = min(100.0, (ac_count / 10.0) * 100.0)  # Standardized benchmark 10 ACs = 100%
            
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

        # Bloom Radar default scores
        radar = BloomRadar(
            A_Nho=85.0 if len(topic_ac_map) > 0 else 0.0,
            B_Hieu=70.0 if len(topic_ac_map) > 2 else 0.0,
            C_VanDung=50.0 if len(topic_ac_map) > 5 else 0.0,
            D_PhanTich=30.0 if len(topic_ac_map) > 10 else 0.0,
            E_DanhGia=10.0 if len(topic_ac_map) > 15 else 0.0,
            F_DacBiet=0.0
        )

        return SkillTreeResponse(
            user_id=user_id,
            student_name=student_name,
            bloom_radar=radar,
            skill_tree_nodes=nodes
        )

skill_tree_service = SkillTreeService()

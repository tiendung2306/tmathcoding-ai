from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.dmoj import JudgeSubmission, JudgeProblem, JudgeProblemTypes, JudgeProblemtype, JudgeProfile
from app.schemas.student import SkillTreeResponse, SkillTreeNode, BloomRadar

# Mapping Bloom theo dữ liệu THẬT của tmath (bảng judge_problemgroup):
# 4=A(Nhớ), 5=B(Hiểu), 6=C(Vận dụng), 7=D(Phân tích), 8=E(Đánh giá), 13=F(Đặc biệt).
BLOOM_FIELD_MAP: Dict[int, str] = {
    4: "A_Nho",
    5: "B_Hieu",
    6: "C_VanDung",
    7: "D_PhanTich",
    8: "E_DanhGia",
    13: "F_DacBiet",
}


class SkillTreeService:
    @staticmethod
    async def _get_bloom_totals(db: AsyncSession) -> Dict[int, int]:
        """Đếm tổng số bài tập duy nhất theo từng mức Bloom trong toàn hệ thống."""
        stmt = (
            select(JudgeProblem.group_id, func.count(func.distinct(JudgeProblem.id)))
            .where(JudgeProblem.group_id.in_(list(BLOOM_FIELD_MAP.keys())))
            .group_by(JudgeProblem.group_id)
        )
        res = await db.execute(stmt)
        return {row[0]: row[1] for row in res.all()}

    @staticmethod
    async def _get_student_bloom_ac(user_id: int, db: AsyncSession) -> Dict[int, int]:
        """Đếm số bài tập AC duy nhất của học sinh theo từng mức Bloom."""
        stmt = (
            select(
                JudgeProblem.group_id,
                func.count(func.distinct(JudgeSubmission.problem_id))
            )
            .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
            .where(
                JudgeSubmission.user_id == user_id,
                JudgeSubmission.result == "AC",
                JudgeProblem.group_id.in_(list(BLOOM_FIELD_MAP.keys()))
            )
            .group_by(JudgeProblem.group_id)
        )
        res = await db.execute(stmt)
        return {row[0]: row[1] for row in res.all()}

    @staticmethod
    async def get_student_skill_tree(user_id: int, db: AsyncSession) -> SkillTreeResponse:
        # Fetch profile
        prof_stmt = select(JudgeProfile).where(JudgeProfile.id == user_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        # name có thể NULL trong DB thật -> guard để Pydantic không crash 500
        student_name = (profile.name or f"User {user_id}") if profile else f"User {user_id}"

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

        # Tính toán điểm Bloom Radar thật từ DB (khớp cách tính của Heatmap phía giáo viên)
        bloom_totals = await SkillTreeService._get_bloom_totals(db)
        student_bloom_ac = await SkillTreeService._get_student_bloom_ac(user_id, db)

        radar_scores = {}
        for group_id, field_name in BLOOM_FIELD_MAP.items():
            total = bloom_totals.get(group_id, 0)
            ac = student_bloom_ac.get(group_id, 0)
            score = round((ac / total) * 100.0, 1) if total > 0 else 0.0
            radar_scores[field_name] = min(100.0, score)

        radar = BloomRadar(**radar_scores)

        return SkillTreeResponse(
            user_id=user_id,
            student_name=student_name,
            bloom_radar=radar,
            skill_tree_nodes=nodes
        )


skill_tree_service = SkillTreeService()

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models.dmoj import (
    JudgeSubmission,
    JudgeProblem,
    JudgeProfile,
    JudgeOrganization,
    JudgeProfileOrganizations,
    AuthUser,
)
from app.schemas.teacher import (
    ClassHeatmapResponse,
    HeatmapStudentRow,
    StudentBloomScore,
    StudentDetailResponse,
    StudentDetailSummary,
    ClassStudentItem,
)

from app.services.algorithm_competency_service import (
    algorithm_competency_service,
    PILLAR_KEYS,
)

# Mapping Bloom theo dữ liệu THẬT của tmath (bảng judge_problemgroup):
# (4,"01","Mức độ A - Nhớ") ... (13,"mucdoF","Mức độ F - Đặc biệt")
BLOOM_GROUP_MAP: Dict[int, str] = {4: "A", 5: "B", 6: "C", 7: "D", 8: "E", 13: "F"}
BLOOM_ORDER: List[str] = ["A", "B", "C", "D", "E", "F"]
BLOOM_LABELS: Dict[str, str] = {
    "A": "Bloom A (Nhớ)",
    "B": "Bloom B (Hiểu)",
    "C": "Bloom C (Vận dụng)",
    "D": "Bloom D (Phân tích)",
    "E": "Bloom E (Đánh giá)",
    "F": "Bloom F (Đặc biệt)",
}

PILLAR_DISPLAY_LABELS: Dict[str, str] = {
    "quy_hoach_dong": "Quy hoạch động (DP)",
    "cau_truc_du_lieu": "Cấu trúc dữ liệu (DS)",
    "xu_ly_xau": "Xử lý xâu",
    "ham_co_ban": "Hàm & Cơ bản",
    "toan_hoc": "Toán học & Số học",
    "hinh_hoc": "Hình học tính toán",
    "do_thi": "Lý thuyết đồ thị",
    "tham_lam": "Thuật toán tham lam",
}
STUCK_THRESHOLD = 8  # >= 8 lượt nộp sai trên cùng 1 bài trong 24h
INACTIVE_DAYS = 7    # > 7 ngày không nộp bài


class HeatmapService:
    """F2.1: Class Performance Heatmap 2D (điểm Bloom) + F2.2: Student Detail."""

    @staticmethod
    async def _get_bloom_totals(db: AsyncSession) -> Dict[str, int]:
        """Tổng số bài tập theo từng mức Bloom trong hệ thống."""
        stmt = (
            select(JudgeProblem.group_id, func.count(func.distinct(JudgeProblem.id)))
            .where(JudgeProblem.group_id.in_(list(BLOOM_GROUP_MAP.keys())))
            .group_by(JudgeProblem.group_id)
        )
        res = await db.execute(stmt)
        return {BLOOM_GROUP_MAP[row.group_id]: row[1] for row in res.all()}

    @staticmethod
    async def _get_member_ids(db: AsyncSession, org_id: int) -> List[int]:
        stmt = select(JudgeProfileOrganizations.profile_id).where(
            JudgeProfileOrganizations.organization_id == org_id
        )
        res = await db.execute(stmt)
        return [row[0] for row in res.all()]

    @staticmethod
    async def _get_ac_counts_by_bloom(db: AsyncSession, member_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """Số bài AC duy nhất của từng học sinh theo từng mức Bloom: {user_id: {bloom: count}}."""
        if not member_ids:
            return {}
        stmt = (
            select(
                JudgeSubmission.user_id,
                JudgeProblem.group_id,
                func.count(func.distinct(JudgeSubmission.problem_id)),
            )
            .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
            .where(
                JudgeSubmission.user_id.in_(member_ids),
                JudgeSubmission.result == "AC",
                JudgeProblem.group_id.in_(list(BLOOM_GROUP_MAP.keys())),
            )
            .group_by(JudgeSubmission.user_id, JudgeProblem.group_id)
        )
        res = await db.execute(stmt)
        out: Dict[int, Dict[str, int]] = {}
        for row in res.all():
            out.setdefault(row.user_id, {})[BLOOM_GROUP_MAP[row.group_id]] = row[2]
        return out

    @staticmethod
    async def _get_alerts(
        db: AsyncSession, member_ids: List[int]
    ) -> Tuple[Dict[int, List[str]], Dict[int, Optional[str]]]:
        """Cảnh báo thật từ lịch sử nộp bài:
        - INACTIVE: không nộp bài nào trong INACTIVE_DAYS ngày gần nhất
        - STUCK: >= STUCK_THRESHOLD lượt nộp sai trên CÙNG 1 bài trong 24h qua"""
        alerts: Dict[int, List[str]] = {uid: [] for uid in member_ids}
        last_sub: Dict[int, Optional[str]] = {uid: None for uid in member_ids}
        if not member_ids:
            return alerts, last_sub

        stmt = (
            select(JudgeSubmission.user_id, func.max(JudgeSubmission.date))
            .where(JudgeSubmission.user_id.in_(member_ids))
            .group_by(JudgeSubmission.user_id)
        )
        res = await db.execute(stmt)
        now = datetime.utcnow()
        for uid, last_date in res.all():
            if last_date:
                last_sub[uid] = last_date.isoformat()
                if now - last_date > timedelta(days=INACTIVE_DAYS):
                    alerts[uid].append("INACTIVE")
        for uid in member_ids:
            if last_sub[uid] is None:
                alerts[uid].append("INACTIVE")

        stuck_stmt = (
            select(JudgeSubmission.user_id)
            .where(
                JudgeSubmission.user_id.in_(member_ids),
                JudgeSubmission.date >= now - timedelta(days=1),
                JudgeSubmission.result != "AC",
            )
            .group_by(JudgeSubmission.user_id, JudgeSubmission.problem_id)
            .having(func.count(JudgeSubmission.id) >= STUCK_THRESHOLD)
        )
        res = await db.execute(stuck_stmt)
        for uid in res.all():
            if "STUCK" not in alerts[uid[0]]:
                alerts[uid[0]].append("STUCK")

        return alerts, last_sub

    @staticmethod
    def _has_gap_alert(ac_by_bloom: Dict[str, int], bloom_totals: Dict[str, int]) -> bool:
        """GAP - hổng nền tảng: đã AC được bài ở mức Bloom cao hơn nhưng mức NGAY DƯỚI
        vẫn 0 AC (và mức dưới còn bài tập để làm)."""
        for i in range(1, len(BLOOM_ORDER)):
            higher, lower = BLOOM_ORDER[i], BLOOM_ORDER[i - 1]
            if (
                ac_by_bloom.get(higher, 0) > 0
                and bloom_totals.get(lower, 0) > 0
                and ac_by_bloom.get(lower, 0) == 0
            ):
                return True
        return False

    @staticmethod
    async def get_class_heatmap(org_id: int, db: AsyncSession) -> ClassHeatmapResponse:
        """F2.1: Heatmap 2D của lớp: điểm Bloom = (bài AC duy nhất / tổng bài mức đó) * 100."""
        org = (
            await db.execute(select(JudgeOrganization).where(JudgeOrganization.id == org_id))
        ).scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {org_id} not found.")

        member_ids = await HeatmapService._get_member_ids(db, org_id)
        profiles: Dict[int, str] = {}
        if member_ids:
            res = await db.execute(
                select(JudgeProfile.id, JudgeProfile.name)
                .where(JudgeProfile.id.in_(member_ids))
                .order_by(JudgeProfile.id)
            )
            profiles = {row.id: (row.name or f"User {row.id}") for row in res.all()}

        bloom_totals = await HeatmapService._get_bloom_totals(db)
        ac_map = await HeatmapService._get_ac_counts_by_bloom(db, member_ids)
        alerts, _ = await HeatmapService._get_alerts(db, member_ids)

        columns = [BLOOM_LABELS[b] for b in BLOOM_ORDER]
        rows: List[HeatmapStudentRow] = []
        col_sums = [0.0] * len(columns)

        for uid in sorted(profiles.keys()):
            ac_by_bloom = ac_map.get(uid, {})
            scores: List[float] = []
            for idx, bloom in enumerate(BLOOM_ORDER):
                total = bloom_totals.get(bloom, 0)
                ac = ac_by_bloom.get(bloom, 0)
                score = round(ac / total * 100.0, 1) if total > 0 else 0.0
                scores.append(score)
                col_sums[idx] += score

            student_alerts = alerts.get(uid, [])
            if HeatmapService._has_gap_alert(ac_by_bloom, bloom_totals) and "GAP" not in student_alerts:
                student_alerts.append("GAP")

            rows.append(
                HeatmapStudentRow(
                    user_id=uid,
                    student_name=profiles[uid],
                    scores=scores,
                    alerts=student_alerts,
                )
            )

        n = len(rows)
        averages = [round(s / n, 1) if n > 0 else 0.0 for s in col_sums]

        return ClassHeatmapResponse(
            organization_id=org_id,
            organization_name=org.name or f"Lớp #{org_id}",
            columns=columns,
            students=rows,
            class_averages=averages,
        )

    @staticmethod
    async def get_student_detail(student_id: int, db: AsyncSession, time_range: str = "all") -> StudentDetailResponse:
        """F2.2: Chi tiết học sinh: profile + lớp học + điểm năng lực 8 trụ cột thuật toán + cảnh báo + thống kê."""
        profile = (
            await db.execute(select(JudgeProfile).where(JudgeProfile.id == student_id))
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Student {student_id} not found.")

        username: Optional[str] = None
        if profile.user_id:
            username = (
                await db.execute(select(AuthUser.username).where(AuthUser.id == profile.user_id))
            ).scalar_one_or_none()

        orgs_res = await db.execute(
            select(JudgeOrganization.name)
            .join(JudgeProfileOrganizations, JudgeProfileOrganizations.organization_id == JudgeOrganization.id)
            .where(JudgeProfileOrganizations.profile_id == student_id)
            .order_by(JudgeOrganization.id)
        )
        organizations = [row[0] for row in orgs_res.all()]

        alerts, last_sub = await HeatmapService._get_alerts(db, [student_id])

        # Tính điểm năng lực 8 trụ cột thuật toán theo mốc thời gian
        radar = await algorithm_competency_service.get_student_radar(student_id, time_range, db)
        bloom_scores = [
            StudentBloomScore(
                group_id=idx + 1,
                label=PILLAR_DISPLAY_LABELS.get(k, k),
                score=getattr(radar, k, 0.0)
            )
            for idx, k in enumerate(PILLAR_KEYS)
        ]

        total_problems = (
            await db.execute(select(func.count(func.distinct(JudgeProblem.id))))
        ).scalar_one() or 0

        ref_now = await algorithm_competency_service.get_reference_now(db)
        cutoff = algorithm_competency_service.get_cutoff_date(time_range, ref_now)

        solved_stmt = select(func.count(func.distinct(JudgeSubmission.problem_id))).where(
            JudgeSubmission.user_id == student_id,
            JudgeSubmission.result == "AC"
        )
        if cutoff:
            solved_stmt = solved_stmt.where(JudgeSubmission.date >= cutoff)
        solved = (await db.execute(solved_stmt)).scalar_one() or 0

        subs_period_stmt = select(func.count(JudgeSubmission.id)).where(JudgeSubmission.user_id == student_id)
        if cutoff:
            subs_period_stmt = subs_period_stmt.where(JudgeSubmission.date >= cutoff)
        subs_period = (await db.execute(subs_period_stmt)).scalar_one() or 0

        return StudentDetailResponse(
            user_id=student_id,
            name=profile.name or f"User {student_id}",
            username=username or f"user_{student_id}",
            time_range=time_range,
            points=profile.points or 0.0,
            performance_points=profile.performance_points or 0.0,
            problem_count=profile.problem_count or 0,
            display_rank=profile.display_rank or "user",
            organizations=organizations,
            bloom_scores=bloom_scores,
            alerts=alerts[student_id],
            last_submission_at=last_sub[student_id],
            summary=StudentDetailSummary(
                total_problems_in_system=total_problems,
                total_solved_unique=solved,
                total_submissions_7d=subs_period,
                time_range=time_range,
                total_submissions_period=subs_period,
            ),
        )

    @staticmethod
    async def get_class_students(org_id: int, db: AsyncSession) -> List[ClassStudentItem]:
        """Danh sách học sinh thuộc lớp org_id kèm điểm, xếp hạng, cảnh báo và thời gian nộp gần nhất."""
        org = (
            await db.execute(select(JudgeOrganization).where(JudgeOrganization.id == org_id))
        ).scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {org_id} not found.")

        member_ids = await HeatmapService._get_member_ids(db, org_id)
        if not member_ids:
            return []

        stmt = (
            select(
                JudgeProfile.id,
                JudgeProfile.name,
                AuthUser.username,
                JudgeProfile.points,
                JudgeProfile.problem_count,
                JudgeProfile.display_rank,
            )
            .outerjoin(AuthUser, AuthUser.id == JudgeProfile.user_id)
            .where(JudgeProfile.id.in_(member_ids))
            .order_by(JudgeProfile.points.desc())
        )
        res = await db.execute(stmt)
        rows = res.all()

        alerts, last_sub = await HeatmapService._get_alerts(db, member_ids)

        return [
            ClassStudentItem(
                user_id=r[0],
                name=r[1] or f"User {r[0]}",
                username=r[2] or f"user_{r[0]}",
                points=round(r[3] or 0.0, 1),
                problem_count=r[4] or 0,
                display_rank=r[5] or "user",
                alerts=alerts.get(r[0], []),
                last_submission_at=last_sub.get(r[0]),
            )
            for r in rows
        ]


heatmap_service = HeatmapService()

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models.dmoj import (
    JudgeSubmission,
    JudgeProblem,
    JudgeProblemTypes,
    JudgeProfile,
    JudgeOrganization,
    JudgeProfileOrganizations,
    JudgeSubmissionsource,
    AuthUser,
)
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


class AlgorithmCompetencyService:
    """Quản lý và tính toán năng lực 8 Trụ cột Thuật toán kết hợp lọc theo Mốc thời gian."""

    @staticmethod
    async def get_reference_now(db: AsyncSession) -> datetime:
        """Xác định mốc thời gian hiện tại tham chiếu (neo theo bài nộp mới nhất trong DB hoặc thời gian thực)."""
        stmt = select(func.max(JudgeSubmission.date))
        latest_date = (await db.execute(stmt)).scalar_one_or_none()
        return latest_date or datetime.utcnow()

    @staticmethod
    def get_cutoff_date(time_range: str, ref_now: datetime) -> Optional[datetime]:
        """Tính ngày bắt đầu (cutoff date) từ mốc thời gian."""
        if time_range == "1d":
            return ref_now - timedelta(days=1)
        elif time_range == "7d":
            return ref_now - timedelta(days=7)
        elif time_range == "30d":
            return ref_now - timedelta(days=30)
        elif time_range == "1y":
            return ref_now - timedelta(days=365)
        return None  # 'all' -> toàn bộ quá trình

    @staticmethod
    def get_target_benchmark(pillar_key: str, time_range: str) -> int:
        pillar = ALGORITHM_PILLARS.get(pillar_key, {})
        key = f"target_{time_range}" if time_range in ["1d", "7d", "30d", "1y"] else "target_all"
        return pillar.get(key, 20)

    @staticmethod
    async def get_ac_counts_by_pillars(
        user_ids: List[int],
        cutoff_date: Optional[datetime],
        db: AsyncSession
    ) -> Dict[int, Dict[str, int]]:
        """Đếm số bài toán AC duy nhất của mỗi học sinh trong từng chuyên đề thuật toán."""
        if not user_ids:
            return {}

        # Tạo ánh xạ ngược từ tag_id sang pillar_key
        tag_to_pillar: Dict[int, str] = {}
        for p_key, meta in ALGORITHM_PILLARS.items():
            for t_id in meta["tag_ids"]:
                tag_to_pillar[t_id] = p_key

        all_tag_ids = list(tag_to_pillar.keys())

        stmt = (
            select(
                JudgeSubmission.user_id,
                JudgeProblemTypes.problemtype_id,
                JudgeSubmission.problem_id
            )
            .join(JudgeProblemTypes, JudgeProblemTypes.problem_id == JudgeSubmission.problem_id)
            .where(
                JudgeSubmission.user_id.in_(user_ids),
                JudgeSubmission.result == "AC",
                JudgeProblemTypes.problemtype_id.in_(all_tag_ids),
            )
        )
        if cutoff_date:
            stmt = stmt.where(JudgeSubmission.date >= cutoff_date)

        res = await db.execute(stmt)
        
        # Gom nhóm bài toán duy nhất theo {user_id: {pillar_key: set(problem_id)}}
        user_pillar_problems: Dict[int, Dict[str, set]] = {uid: {k: set() for k in PILLAR_KEYS} for uid in user_ids}
        for uid, tag_id, prob_id in res.all():
            p_key = tag_to_pillar.get(tag_id)
            if p_key and uid in user_pillar_problems:
                user_pillar_problems[uid][p_key].add(prob_id)

        # Chuyển thành số lượng
        return {
            uid: {k: len(probs) for k, probs in pillars.items()}
            for uid, pillars in user_pillar_problems.items()
        }

    @staticmethod
    async def get_student_radar(
        user_id: int,
        time_range: str,
        db: AsyncSession
    ) -> AlgorithmRadar:
        """Tính điểm Radar 8 trục bát giác cho 1 học sinh theo mô hình 4 thành phần đa chiều."""
        ref_now = await AlgorithmCompetencyService.get_reference_now(db)
        cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, ref_now)

        tag_to_pillar: Dict[int, str] = {}
        for p_key, meta in ALGORITHM_PILLARS.items():
            for t_id in meta["tag_ids"]:
                tag_to_pillar[t_id] = p_key
        all_tag_ids = list(tag_to_pillar.keys())

        # 1. Truy vấn toàn bộ submissions của học sinh trong các chuyên đề
        stmt = (
            select(
                JudgeSubmission.id,
                JudgeSubmission.problem_id,
                JudgeSubmission.result,
                JudgeSubmission.time,
                JudgeSubmission.memory,
                JudgeSubmission.date,
                JudgeProblem.group_id,
                JudgeProblem.time_limit,
                JudgeProblem.memory_limit,
                JudgeProblemTypes.problemtype_id,
            )
            .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
            .join(JudgeProblemTypes, JudgeProblemTypes.problem_id == JudgeSubmission.problem_id)
            .where(
                JudgeSubmission.user_id == user_id,
                JudgeProblemTypes.problemtype_id.in_(all_tag_ids),
            )
            .order_by(JudgeSubmission.date.asc())
        )
        if cutoff:
            stmt = stmt.where(JudgeSubmission.date >= cutoff)

        sub_rows = (await db.execute(stmt)).all()

        # 2. Gom nhóm theo pillar
        pillar_subs: Dict[str, List[Dict[str, Any]]] = {k: [] for k in PILLAR_KEYS}
        pillar_problems: Dict[str, Dict[int, Dict[str, Any]]] = {k: {} for k in PILLAR_KEYS}
        pillar_ac_sub_ids: Dict[str, List[int]] = {k: [] for k in PILLAR_KEYS}

        for row in sub_rows:
            p_key = tag_to_pillar.get(row[9])
            if not p_key:
                continue

            sub_item = {
                "id": row[0],
                "problem_id": row[1],
                "result": row[2],
                "time": row[3] or 0.0,
                "memory": row[4] or 0.0,
                "date": row[5],
                "group_id": row[6],
                "time_limit": row[7] or 1.0,
                "memory_limit": row[8] or 256000,
            }
            pillar_subs[p_key].append(sub_item)

            pid = sub_item["problem_id"]
            if pid not in pillar_problems[p_key]:
                pillar_problems[p_key][pid] = {
                    "group_id": sub_item["group_id"],
                    "time_limit": sub_item["time_limit"],
                    "memory_limit": sub_item["memory_limit"],
                    "attempts": 0,
                    "is_ac": False,
                    "ac_time": 0.0,
                    "ac_sub_id": None,
                    "fail_before_ac": 0,
                }

            prob_stat = pillar_problems[p_key][pid]
            prob_stat["attempts"] += 1
            if sub_item["result"] == "AC":
                if not prob_stat["is_ac"]:
                    prob_stat["is_ac"] = True
                    prob_stat["ac_time"] = sub_item["time"]
                    prob_stat["ac_sub_id"] = sub_item["id"]
                    pillar_ac_sub_ids[p_key].append(sub_item["id"])
            elif not prob_stat["is_ac"]:
                prob_stat["fail_before_ac"] += 1

        # 3. Lấy mẫu mã nguồn cho các bài AC tiêu biểu (tối đa 3 bài mỗi pillar)
        all_sample_ids: List[int] = []
        for k in PILLAR_KEYS:
            all_sample_ids.extend(pillar_ac_sub_ids[k][-3:])

        sources_map: Dict[int, str] = {}
        if all_sample_ids:
            src_stmt = select(JudgeSubmissionsource.submission_id, JudgeSubmissionsource.source).where(
                JudgeSubmissionsource.submission_id.in_(all_sample_ids)
            )
            for sid, src in (await db.execute(src_stmt)).all():
                sources_map[sid] = src or ""

        # 4. Chấm điểm từng pillar qua CompetencyEvaluator
        scores: Dict[str, float] = {}
        breakdown_dict: Dict[str, PillarBreakdownItem] = {}

        for k in PILLAR_KEYS:
            sample_sources = [
                sources_map[sid] for sid in pillar_ac_sub_ids[k][-3:] if sid in sources_map
            ]
            eval_res = CompetencyEvaluator.evaluate_pillar(
                pillar_key=k,
                time_range=time_range,
                submissions=pillar_subs[k],
                problems_map=pillar_problems[k],
                sample_sources=sample_sources,
            )
            scores[k] = eval_res["score"]
            breakdown_dict[k] = PillarBreakdownItem(
                score=eval_res["score"],
                base_score=eval_res["base_score"],
                precision_mod=eval_res["precision_mod"],
                efficiency_mod=eval_res["efficiency_mod"],
                code_quality_mod=eval_res["code_quality_mod"],
                ac_count=eval_res["ac_count"],
                total_subs=eval_res["total_subs"],
                avg_time_ratio=eval_res["avg_time_ratio"],
                breakdown_items=eval_res["breakdown_items"],
            )

        return AlgorithmRadar(
            time_range=time_range,
            quy_hoach_dong=scores["quy_hoach_dong"],
            cau_truc_du_lieu=scores["cau_truc_du_lieu"],
            xu_ly_xau=scores["xu_ly_xau"],
            ham_co_ban=scores["ham_co_ban"],
            toan_hoc=scores["toan_hoc"],
            hinh_hoc=scores["hinh_hoc"],
            do_thi=scores["do_thi"],
            tham_lam=scores["tham_lam"],
            breakdown=breakdown_dict,
        )

    @staticmethod
    async def get_class_competency_heatmap(
        org_id: int,
        time_range: str,
        db: AsyncSession
    ) -> ClassHeatmapResponse:
        """Tính ma trận 8 cột năng lực thuật toán cho cả lớp theo mốc thời gian."""
        org = (
            await db.execute(select(JudgeOrganization).where(JudgeOrganization.id == org_id))
        ).scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {org_id} not found.")

        # Lấy danh sách thành viên trong lớp
        m_stmt = select(JudgeProfileOrganizations.profile_id).where(
            JudgeProfileOrganizations.organization_id == org_id
        )
        member_ids = [r[0] for r in (await db.execute(m_stmt)).all()]
        if not member_ids:
            return ClassHeatmapResponse(
                organization_id=org_id,
                organization_name=org.name or f"Lớp #{org_id}",
                time_range=time_range,
                columns=PILLAR_COLUMNS,
                students=[],
                class_averages=[0.0] * len(PILLAR_COLUMNS),
            )

        # Lấy profile names
        p_stmt = (
            select(JudgeProfile.id, JudgeProfile.name)
            .where(JudgeProfile.id.in_(member_ids))
            .order_by(JudgeProfile.id)
        )
        profiles = {r.id: (r.name or f"User {r.id}") for r in (await db.execute(p_stmt)).all()}

        ref_now = await AlgorithmCompetencyService.get_reference_now(db)
        cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, ref_now)
        ac_map = await AlgorithmCompetencyService.get_ac_counts_by_pillars(member_ids, cutoff, db)

        # Cảnh báo nộp bài gần nhất
        alerts_map: Dict[int, List[str]] = {uid: [] for uid in member_ids}
        last_sub_stmt = (
            select(JudgeSubmission.user_id, func.max(JudgeSubmission.date))
            .where(JudgeSubmission.user_id.in_(member_ids))
            .group_by(JudgeSubmission.user_id)
        )
        for uid, last_dt in (await db.execute(last_sub_stmt)).all():
            if last_dt and (ref_now - last_dt > timedelta(days=7)):
                alerts_map[uid].append("INACTIVE")

        col_sums = [0.0] * len(PILLAR_KEYS)
        rows: List[HeatmapStudentRow] = []

        for uid in sorted(profiles.keys()):
            u_ac = ac_map.get(uid, {})
            scores: List[float] = []
            for idx, k in enumerate(PILLAR_KEYS):
                target = AlgorithmCompetencyService.get_target_benchmark(k, time_range)
                score = min(100.0, round((u_ac.get(k, 0) / target) * 100.0, 1)) if target > 0 else 0.0
                scores.append(score)
                col_sums[idx] += score

            # Cảnh báo lệch chuyên đề: Đồ thị/Quy hoạch động >= 40 nhưng Hàm cơ bản == 0
            student_alerts = list(alerts_map.get(uid, []))
            if (u_ac.get("quy_hoach_dong", 0) >= 3 or u_ac.get("do_thi", 0) >= 3) and u_ac.get("ham_co_ban", 0) == 0:
                if "GAP" not in student_alerts:
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
            time_range=time_range,
            columns=PILLAR_COLUMNS,
            students=rows,
            class_averages=averages,
        )


algorithm_competency_service = AlgorithmCompetencyService()

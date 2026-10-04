from math import ceil

from fastapi import HTTPException
from sqlalchemy import select, func, case, or_

from app.models.dmoj import JudgeProfile, JudgeProblem, JudgeProblemtype, JudgeProblemTypes, JudgeSubmission
from app.services.algorithm_competency_service import AlgorithmCompetencyService


async def require_profile(source, user_id):
    if (await source.execute(select(JudgeProfile.id).where(JudgeProfile.id == user_id))).scalar_one_or_none() is None:
        raise HTTPException(404, "Không tìm thấy học sinh.")


async def submissions_in_range(source, user_id, time_range):
    query = select(JudgeSubmission).where(JudgeSubmission.user_id == user_id)
    reference = await AlgorithmCompetencyService.get_reference_now(source)
    cutoff = AlgorithmCompetencyService.get_cutoff_date(time_range, reference)
    return query.where(JudgeSubmission.date >= cutoff) if cutoff else query


async def tag_problems(source, tag_id, user_id, time_range="all", status="all", q="", page=1, page_size=20):
    await require_profile(source, user_id)
    if (await source.execute(select(JudgeProblemtype.id).where(JudgeProblemtype.id == tag_id))).scalar_one_or_none() is None:
        raise HTTPException(404, "Không tìm thấy dạng bài.")
    sub = (await submissions_in_range(source, user_id, time_range)).subquery()
    stats = select(sub.c.problem_id, func.count().label("attempts"),
        func.max(case((sub.c.result == "AC", 1), else_=0)).label("solved"),
        func.max(sub.c.date).label("last_submission_at")).group_by(sub.c.problem_id).subquery()
    tagged = select(JudgeProblemTypes.problem_id).where(JudgeProblemTypes.problemtype_id == tag_id).distinct()
    base = select(JudgeProblem.id, JudgeProblem.code, JudgeProblem.name.label("title"),
        func.coalesce(stats.c.attempts, 0).label("attempts"), func.coalesce(stats.c.solved, 0).label("solved"),
        stats.c.last_submission_at).outerjoin(stats, stats.c.problem_id == JudgeProblem.id).where(JudgeProblem.id.in_(tagged))
    if q.strip():
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        base = base.where(or_(JudgeProblem.code.ilike(term, escape="\\"), JudgeProblem.name.ilike(term, escape="\\")))
    if status == "ac":
        base = base.where(stats.c.solved == 1)
    elif status == "attempted":
        base = base.where(stats.c.attempts > 0, stats.c.solved == 0)
    elif status == "unattempted":
        base = base.where(stats.c.problem_id.is_(None))
    total = (await source.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    total_pages = max(1, ceil(total / page_size))
    page = min(page, total_pages)
    rows = (await source.execute(base.order_by(JudgeProblem.code, JudgeProblem.id).offset((page - 1) * page_size).limit(page_size))).mappings().all()
    return {"items": [{**row, "solved": bool(row["solved"])} for row in rows],
            "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


async def problem_detail(source, problem_id, user_id, time_range="all", page=1, page_size=10):
    await require_profile(source, user_id)
    problem = (await source.execute(select(JudgeProblem).where(JudgeProblem.id == problem_id))).scalar_one_or_none()
    if problem is None:
        raise HTTPException(404, "Không tìm thấy bài toán.")
    base = (await submissions_in_range(source, user_id, time_range)).where(JudgeSubmission.problem_id == problem_id)
    total = (await source.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    total_pages = max(1, ceil(total / page_size))
    page = min(page, total_pages)
    rows = (await source.execute(base.order_by(JudgeSubmission.date.desc(), JudgeSubmission.id.desc())
        .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"id": problem.id, "code": problem.code, "title": problem.name,
        "description": problem.description or "", "time_limit": problem.time_limit, "memory_limit": problem.memory_limit,
        "submissions": {"items": [{"id": s.id, "date": s.date, "result": s.result or s.status,
            "points": s.points, "time": s.time, "memory": s.memory} for s in rows],
            "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}}

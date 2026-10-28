from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from app.core.dashboard_auth import require_admin
from app.core.dashboard_database import get_dashboard_db
from app.models.scoring import ScoringItem, ScoringPair, ScoringProfile, ScoringRun
from app.scoring.policy import default_policy
from app.scoring.service import leaderboard, run_data, state
from app.services.source_gateway import get_source_gateway

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/state")
async def get_state(db=Depends(get_dashboard_db)):
    current = await state(db)
    rows = (await db.execute(select(ScoringRun).order_by(ScoringRun.created_at.desc()).limit(30))).scalars()
    active = await db.get(ScoringRun, current.active_run_id) if current.active_run_id else None
    return {"revision": current.revision, "policy": default_policy().model_dump(mode="json"),
            "active": run_data(active) if active else None, "runs": [run_data(row) for row in rows]}


@router.get("/runs/{run_id}/items")
async def list_items(run_id: str, q: str = Query("", max_length=128),
                     grade: str = Query("", pattern="^([A-F]|unclassified)?$"),
                     page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100),
                     db=Depends(get_dashboard_db)):
    run = await db.get(ScoringRun, run_id)
    if run is None or run.status not in ("READY", "PUBLISHED"):
        raise HTTPException(409, "Lượt tính điểm chưa sẵn sàng để xem.")
    conditions = [ScoringItem.run_id == run_id]
    if grade:
        conditions.append(ScoringItem.grade.is_(None) if grade == "unclassified" else ScoringItem.grade == grade)
    if q.strip():
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(or_(ScoringItem.code.ilike(term, escape="\\"),
                              ScoringItem.title.ilike(term, escape="\\")))
    total = (await db.execute(select(func.count()).select_from(ScoringItem).where(*conditions))).scalar_one()
    rows = (await db.execute(select(ScoringItem).where(*conditions).order_by(ScoringItem.problem_id)
        .offset((page - 1) * page_size).limit(page_size))).scalars()
    return {"total": total, "page": page, "total_pages": (total + page_size - 1) // page_size,
            "items": [{key: getattr(row, key) for key in ("problem_id", "code", "title", "grade", "points",
                       "difficulty", "attempted", "solved", "method")} for row in rows]}


@router.get("/leaderboard")
async def get_leaderboard(page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
                          q: str = Query("", max_length=128), db=Depends(get_dashboard_db)):
    return await leaderboard(db, page, page_size, q)


@router.get("/students/{profile_id}")
async def get_student_score(profile_id: int, page: int = Query(1, ge=1),
                            db=Depends(get_dashboard_db), source=Depends(get_source_gateway),
                            admin=Depends(require_admin)):
    await source.get_student(profile_id, actor_profile_id=admin.source_profile_id)
    current = await state(db)
    if current.active_run_id is None:
        return None
    student = await db.get(ScoringProfile, (current.active_run_id, profile_id))
    if student is None:
        return {"ready": False}
    run = await db.get(ScoringRun, current.active_run_id)
    rows = (await db.execute(select(ScoringItem).join(ScoringPair,
        (ScoringPair.run_id == ScoringItem.run_id) & (ScoringPair.problem_id == ScoringItem.problem_id))
        .where(ScoringItem.run_id == current.active_run_id, ScoringPair.profile_id == profile_id,
               ScoringPair.has_ac.is_(True)).order_by(ScoringItem.problem_id)
        .offset((page - 1) * 30).limit(30))).scalars()
    return {"ready": True, "run_id": run.id, "as_of": run.source_as_of,
        "points": student.total_points, "solved_count": student.solved_count,
        "unscored_count": student.unscored_count, "page": page,
        "total_pages": (student.solved_count + 29) // 30,
        "items": [{"problem_id": row.problem_id, "code": row.code, "title": row.title,
                   "grade": row.grade, "points": row.points} for row in rows]}

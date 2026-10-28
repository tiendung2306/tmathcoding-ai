import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case, func, insert, literal, or_, select, update

from app.core.time import utc_now
from app.models.scoring import ScoringItem, ScoringPair, ScoringProfile, ScoringRun, ScoringState
from .policy import Policy, default_policy


async def state(db, lock=False):
    query = select(ScoringState).where(ScoringState.id == 1)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise HTTPException(503, "Chưa có schema điểm; hãy chạy migration.")
    return row


def run_data(row):
    return {key: getattr(row, key) for key in ("id", "kind", "status", "actor_id", "policy_revision",
        "base_run_id", "points_run_id", "created_at", "completed_at", "published_at", "source_as_of",
        "progress", "error", "diagnostics")}


async def enqueue(db, actor_id, kind="calibrate", restore_id=None):
    current = await state(db, lock=True)
    busy = (await db.execute(select(ScoringRun.id).where(
        ScoringRun.status.in_(("QUEUED", "PROCESSING"))).limit(1))).scalar_one_or_none()
    if busy:
        raise HTTPException(409, "Một tác vụ điểm đang chạy.")
    active = await db.get(ScoringRun, current.active_run_id) if current.active_run_id else None
    points_run_id = restore_id or current.active_run_id
    reference = await db.get(ScoringRun, points_run_id) if points_run_id else None
    if kind != "calibrate" and (reference is None or reference.published_at is None):
        raise HTTPException(409, "Chưa có bảng điểm đã công bố để cập nhật/khôi phục.")
    policy = default_policy().model_dump(mode="json")
    row = ScoringRun(id=uuid.uuid4().hex, kind=kind, status="QUEUED", actor_id=actor_id,
        policy_revision=current.revision, policy=policy, base_run_id=active.id if active else None,
        points_run_id=points_run_id, progress="Đang chờ worker")
    db.add(row)
    await db.commit()
    return run_data(row)


async def publish(db, run_id, source, actor_id):
    current = await state(db, lock=True)
    run = await db.get(ScoringRun, run_id)
    if run is None:
        raise HTTPException(404, "Không tìm thấy lượt tính điểm.")
    if current.active_run_id == run_id:
        return run_data(run)
    if run.status != "READY" or run.base_run_id != current.active_run_id:
        raise HTTPException(409, "Đề xuất không còn khớp bảng đang dùng. Hãy tính lại.")
    if Policy.model_validate(run.policy).model_dump() != default_policy().model_dump():
        raise HTTPException(409, "Lượt tính không dùng quy tắc điểm cố định hiện tại. Hãy tính lại.")
    missing = (await db.execute(select(func.count()).select_from(ScoringItem).where(
        ScoringItem.run_id == run.id, ScoringItem.points.is_(None)))).scalar_one()
    if missing:
        raise HTTPException(409, "Bảng cũ còn thiếu điểm mặc định. Hãy cập nhật điểm trước khi công bố.")
    if run.kind == "calibrate" and run.policy_revision != current.revision:
        raise HTTPException(409, "Cấu hình đã đổi. Hãy tính lại.")
    catalog, _, _ = await source.get_analytics_catalog(actor_profile_id=actor_id)
    if catalog is None or catalog.catalog_version != run.manifest["catalog_version"]:
        raise HTTPException(409, "Danh mục nguồn đã đổi. Hãy tính lại trước khi công bố.")
    run.status = "PUBLISHED"
    run.published_at = utc_now()
    run.progress = "Đã công bố"
    current.active_run_id = run.id
    await db.commit()
    return run_data(run)


async def leaderboard(db, page=1, page_size=24, q="", run_id=None, sort="points_desc"):
    current = await state(db)
    if run_id is not None and run_id != current.active_run_id:
        raise HTTPException(409, "Bảng điểm đã cập nhật. Hãy tải lại từ trang đầu.")
    active = current.active_run_id
    if active is None:
        return None
    ranked = select(ScoringProfile,
        func.rank().over(order_by=ScoringProfile.total_points.desc()).label("rank"))\
        .where(ScoringProfile.run_id == active).subquery()
    condition = []
    if q.strip():
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        condition = [or_(ranked.c.name.ilike(term, escape="\\"),
                         ranked.c.username.ilike(term, escape="\\"))]
    total = (await db.execute(select(func.count()).select_from(ranked).where(*condition))).scalar_one()
    ordering = {
        "points_desc": ranked.c.total_points.desc(),
        "points_asc": ranked.c.total_points.asc(),
        "name": ranked.c.name.asc(),
        "name_desc": ranked.c.name.desc(),
    }[sort]
    rows = (await db.execute(select(ranked).where(*condition).order_by(
        ordering, ranked.c.profile_id).offset((page - 1) * page_size).limit(page_size))).mappings().all()
    run = await db.get(ScoringRun, active)
    return {"items": [{"user_id": row["profile_id"], "name": row["name"], "username": row["username"],
        "points": row["total_points"], "problem_count": row["solved_count"], "rank": row["rank"],
        "unscored_count": row["unscored_count"]} for row in rows], "total": total, "page": page,
        "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
        "score_run_id": active, "score_as_of": run.source_as_of, "score_metric": "achievement"}


async def overlay_scores(db, rows):
    current = await state(db)
    if not current.active_run_id or not rows:
        return rows
    totals = {row.profile_id: row for row in (await db.execute(select(ScoringProfile).where(
        ScoringProfile.run_id == current.active_run_id,
        ScoringProfile.profile_id.in_([item.user_id for item in rows])))).scalars()}
    for item in rows:
        score = totals.get(item.user_id)
        if score is not None:
            item.source_points = item.points
            item.points = score.total_points
            item.unscored_count = score.unscored_count
            item.score_metric = "achievement"
    return rows


async def reprice_active(db, source, actor_id):
    """Build a complete generation from the existing immutable AC snapshot."""
    current = await state(db)
    if not current.active_run_id:
        raise HTTPException(409, "Chưa có bảng điểm để cập nhật.")
    original = await db.get(ScoringRun, current.active_run_id)
    policy = default_policy()
    run_id = uuid.uuid4().hex
    row = ScoringRun(id=run_id, kind="refresh", status="BUILDING", actor_id=actor_id,
        policy_revision=current.revision, policy=policy.model_dump(mode="json"),
        base_run_id=original.id, points_run_id=original.id, manifest=original.manifest,
        source_as_of=original.source_as_of, progress="Đang cập nhật điểm mặc định")
    db.add(row)
    await db.commit()
    item = ScoringItem.__table__
    initial = case({grade: band.initial for grade, band in policy.bands.items()}, value=item.c.grade,
                   else_=policy.unclassified_points)
    points = case((item.c.grade.is_(None), policy.unclassified_points),
                  else_=func.coalesce(item.c.points, initial))
    item_fields = [column.name for column in item.columns]
    replacements = {"run_id": literal(run_id), "points": points,
                    "method": case((item.c.grade.is_(None), "DEFAULT"), else_=item.c.method)}
    await db.execute(insert(item).from_select(item_fields,
        select(*(replacements.get(name, item.c[name]) for name in item_fields)).where(item.c.run_id == original.id)))
    pair = ScoringPair.__table__
    pair_fields = [column.name for column in pair.columns]
    await db.execute(insert(pair).from_select(pair_fields,
        select(*(literal(run_id) if name == "run_id" else pair.c[name] for name in pair_fields))
        .where(pair.c.run_id == original.id)))
    totals = select(pair.c.profile_id, func.sum(item.c.points).label("points"), func.count().label("solved"))\
        .select_from(pair.join(item, (pair.c.run_id == item.c.run_id) & (pair.c.problem_id == item.c.problem_id)))\
        .where(pair.c.run_id == run_id, pair.c.has_ac.is_(True)).group_by(pair.c.profile_id).subquery()
    profile = ScoringProfile.__table__
    await db.execute(insert(profile).from_select(
        ["run_id", "profile_id", "name", "username", "total_points", "solved_count", "unscored_count"],
        select(literal(run_id), profile.c.profile_id, profile.c.name, profile.c.username,
            func.coalesce(totals.c.points, 0), func.coalesce(totals.c.solved, 0), literal(0))
        .select_from(profile.outerjoin(totals, totals.c.profile_id == profile.c.profile_id))
        .where(profile.c.run_id == original.id)))
    row.status, row.completed_at, row.progress = "READY", utc_now(), "Đã cập nhật đầy đủ điểm"
    row.diagnostics = {**(original.diagnostics or {}), "partial": False,
                       "unclassified_points": policy.unclassified_points}
    row.diagnostics = {**row.diagnostics, "total_points": int((await db.execute(
        select(func.coalesce(func.sum(ScoringProfile.total_points), 0))
        .where(ScoringProfile.run_id == run_id))).scalar_one())}
    await db.commit()
    return await publish(db, run_id, source, actor_id)

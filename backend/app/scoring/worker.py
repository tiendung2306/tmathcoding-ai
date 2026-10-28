"""Durable snapshot jobs; run outside the web server with python -m app.scoring.worker."""
import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select, update

from app.core.dashboard_database import DashboardSessionLocal, dashboard_database
from app.core.time import utc_now
from app.models.scoring import ScoringItem, ScoringPair, ScoringProfile, ScoringRun, ScoringState
from app.services.source_gateway import get_source_gateway_client, close_source_gateway
from .policy import Policy, default_policy, source_grade
from .service import enqueue, publish, state

logger = logging.getLogger(__name__)


def parse_date(value):
    if value is None:
        return None
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return date.astimezone(timezone.utc).replace(tzinfo=None) if date.tzinfo else date


async def guard(db, run_id, token):
    claimed = await db.execute(update(ScoringRun).where(ScoringRun.id == run_id,
        ScoringRun.lease_token == token, ScoringRun.status == "PROCESSING").values(
            lease_until=utc_now() + timedelta(minutes=3)))
    if claimed.rowcount != 1:
        raise RuntimeError("Worker đã mất quyền xử lý tác vụ.")


async def claim():
    async with DashboardSessionLocal() as db:
        await state(db, lock=True)
        expired = await db.execute(update(ScoringRun).where(ScoringRun.status == "PROCESSING",
            ScoringRun.lease_until < utc_now()).values(status="FAILED", error="Worker bị gián đoạn. Chạy lại tác vụ để lấy snapshot mới."))
        row = (await db.execute(select(ScoringRun).where(ScoringRun.status == "QUEUED")
            .order_by(ScoringRun.created_at).limit(1).with_for_update())).scalar_one_or_none()
        if row is None:
            await db.commit()
            return None
        row.status, row.lease_token = "PROCESSING", uuid.uuid4().hex
        row.lease_until = utc_now() + timedelta(minutes=3)
        data = {key: getattr(row, key) for key in ("id", "lease_token", "actor_id", "kind", "policy", "points_run_id")}
        await db.commit()
        return data


async def heartbeat(run_id, token):
    while True:
        await asyncio.sleep(15)
        async with DashboardSessionLocal() as db:
            await guard(db, run_id, token)
            await db.commit()


async def execute(job):
    run_id, token, actor = job["id"], job["lease_token"], job["actor_id"]
    policy = Policy.model_validate(job["policy"])
    if policy.model_dump() != default_policy().model_dump():
        raise ValueError("Lượt tính không dùng quy tắc điểm cố định hiện tại.")
    source = get_source_gateway_client()
    manifest = await source.scoring_snapshot(actor_profile_id=actor)
    as_of = datetime.fromtimestamp(manifest["created_at"], timezone.utc).replace(tzinfo=None)
    previous = {}
    async with DashboardSessionLocal() as db:
        if job["points_run_id"]:
            previous = {item.problem_id: {"grade": item.grade, "points": item.points} for item in
                (await db.execute(select(ScoringItem).where(ScoringItem.run_id == job["points_run_id"]))).scalars()}
        await guard(db, run_id, token)
        await db.execute(update(ScoringRun).where(ScoringRun.id == run_id).values(
            manifest=manifest, source_as_of=as_of, progress="Đang đồng bộ snapshot nguồn"))
        await db.commit()
    items, pairs, profiles = [], [], []
    for section in ("problems", "profiles", "pairs"):
        digest, count = hashlib.sha256(), 0
        info = manifest["sections"][section]
        for page_number in range(info["pages"]):
            page = await source.scoring_snapshot_page(manifest["snapshot_id"], section, page_number,
                                                      actor_profile_id=actor)
            if page["snapshot_id"] != manifest["snapshot_id"] or page["page"] != page_number:
                raise ValueError("Provider trả sai trang snapshot.")
            raw = json.dumps(page["items"], ensure_ascii=False, separators=(",", ":")).encode()
            if hashlib.sha256(raw).hexdigest() != page["sha256"]:
                raise ValueError("Checksum trang nguồn không khớp.")
            digest.update(raw)
            count += len(page["items"])
            batch = []
            for value in page["items"]:
                if section == "problems":
                    pid = value["problem_id"]
                    grade = source_grade(value["group_id"])
                    row = {"run_id": run_id, "problem_id": pid, "code": value["code"] or str(pid),
                           "title": (value["title"] or value["code"] or str(pid))[:512],
                           "source_group_id": value["group_id"], "grade": grade,
                           "points": policy.unclassified_points if grade is None else None,
                           "method": "DEFAULT" if grade is None else "PROVISIONAL",
                           "attempted": 0, "solved": 0}
                    items.append(row)
                elif section == "profiles":
                    uid = value["profile_id"]
                    row = {"run_id": run_id, "profile_id": uid,
                           "name": (value["name"] or value["username"] or str(uid))[:255],
                           "username": (value["username"] or f"user_{uid}")[:150],
                           "total_points": 0, "solved_count": 0, "unscored_count": 0}
                    profiles.append(row)
                else:
                    row = {"run_id": run_id, "profile_id": value["profile_id"],
                           "problem_id": value["problem_id"], "has_ac": bool(value["has_ac"]),
                           "first_ac_at": parse_date(value["first_ac_at"])}
                    pairs.append(row)
                batch.append(row)
            model = {"problems": ScoringItem, "profiles": ScoringProfile, "pairs": ScoringPair}[section]
            async with DashboardSessionLocal() as db:
                await guard(db, run_id, token)
                if batch:
                    await db.execute(insert(model), batch)
                await db.execute(update(ScoringRun).where(ScoringRun.id == run_id).values(
                    progress=f"Đồng bộ {section}: {count}/{info['count']}"))
                await db.commit()
        if count != info["count"] or digest.hexdigest() != info["sha256"]:
            raise ValueError("Manifest snapshot không khớp dữ liệu nhận được.")
    if len({item["problem_id"] for item in items}) != len(items):
        raise ValueError("Trùng ID bài trong snapshot.")
    if job["kind"] == "calibrate":
        from .calibration import calibrate
        estimates, diagnostics = await asyncio.to_thread(calibrate, items, pairs, policy, previous)
        by_id = {item["problem_id"]: item for item in estimates}
        for item in items:
            item.update(by_id.get(item["problem_id"], {}))
    else:
        for item in items:
            old = previous.get(item["problem_id"])
            if item["grade"] is None:
                continue
            band = policy.bands[item["grade"]]
            if (old and old["grade"] == item["grade"] and old["points"] is not None
                    and band.minimum <= old["points"] <= band.maximum):
                item["points"], item["method"] = old["points"], "RETAINED"
            else:
                item["points"], item["method"] = band.initial, "PROVISIONAL"
        diagnostics = {"model": "published-points-refresh", "observations": len(pairs)}
    by_problem = {item["problem_id"]: item for item in items}
    by_profile = {item["profile_id"]: item for item in profiles}
    for item in items:
        item["attempted"], item["solved"] = 0, 0
    for pair in pairs:
        item = by_problem.get(pair["problem_id"])
        student = by_profile.get(pair["profile_id"])
        if item is None or student is None:
            raise ValueError("Snapshot tham chiếu profile hoặc bài không tồn tại.")
        item["attempted"] += 1
        if pair["has_ac"]:
            item["solved"] += 1
            student["solved_count"] += 1
            if item["points"] is None:
                raise ValueError("Bài chưa được cấp điểm mặc định.")
            student["total_points"] += item["points"]
    diagnostics.update({"problems": len(items), "profiles": len(profiles), "pairs": len(pairs),
        "unclassified": sum(item["grade"] is None for item in items),
        "total_points": sum(item["total_points"] for item in profiles),
        "partial": False})
    for model, rows, keys in ((ScoringItem, items, ("run_id", "problem_id")),
                              (ScoringProfile, profiles, ("run_id", "profile_id"))):
        # Replace only this unpublished generation; readers still use the active pointer.
        async with DashboardSessionLocal() as db:
            await guard(db, run_id, token)
            await db.execute(delete(model).where(model.run_id == run_id))
            for start in range(0, len(rows), 1000):
                await db.execute(insert(model), rows[start:start + 1000])
            await db.commit()
    async with DashboardSessionLocal() as db:
        await guard(db, run_id, token)
        oracle = (await db.execute(select(func.coalesce(func.sum(ScoringItem.points), 0))
            .join(ScoringPair, (ScoringPair.run_id == ScoringItem.run_id) &
                  (ScoringPair.problem_id == ScoringItem.problem_id))
            .where(ScoringItem.run_id == run_id, ScoringPair.has_ac.is_(True)))).scalar_one()
        stored = (await db.execute(select(func.coalesce(func.sum(ScoringProfile.total_points), 0))
            .where(ScoringProfile.run_id == run_id))).scalar_one()
        if int(oracle) != int(stored) or int(stored) != diagnostics["total_points"]:
            raise ValueError("Tổng điểm không khớp phép đối soát độc lập trong DB.")
        await db.execute(update(ScoringRun).where(ScoringRun.id == run_id).values(status="READY",
            completed_at=utc_now(), diagnostics=diagnostics, progress="Đã tính xong, chờ công bố"))
        await db.commit()
        if job["kind"] == "refresh":
            await publish(db, run_id, source, actor)


async def main():
    while True:
        job = await claim()
        if job is None:
            await asyncio.sleep(3)
            continue
        task = asyncio.create_task(heartbeat(job["id"], job["lease_token"]))
        try:
            await asyncio.wait_for(execute(job), timeout=1800)
        except Exception as exc:
            logger.exception("Scoring job failed: %s", job["id"])
            async with DashboardSessionLocal() as db:
                await db.execute(update(ScoringRun).where(ScoringRun.id == job["id"],
                    ScoringRun.lease_token == job["lease_token"], ScoringRun.status.in_(("PROCESSING", "READY")))
                    .values(status="FAILED", error=str(exc)[:2000], progress="Tác vụ thất bại"))
                await db.commit()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

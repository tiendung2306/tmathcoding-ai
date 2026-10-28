"""Bounded, frozen file pages for the local read-only scoring provider."""
import hashlib
import json
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import case, func, select

from .models import problem, profile, submission, user

_root = Path(tempfile.mkdtemp(prefix="tmath-scoring-"))
_lock = threading.Lock()
TTL = 3600
PAGE_SIZE = 1000
FINAL_RESULTS = ("AC", "WA", "TLE", "MLE", "RTE", "OLE", "IR", "CE", "AB", "SC")


def build_snapshot(db, actor_id, catalog_version):
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "Một snapshot điểm đang được tạo. Hãy thử lại.")
    directory = _root / uuid.uuid4().hex
    try:
        for child in _root.iterdir():
            if child.is_dir() and time.time() - child.stat().st_mtime > TTL:
                shutil.rmtree(child)
        if len(list(_root.iterdir())) >= 8:
            raise HTTPException(429, "Đã đạt giới hạn snapshot local; chờ snapshot cũ hết hạn.")
        directory.mkdir()
        manifest = {"snapshot_id": directory.name, "actor_id": actor_id,
                    "catalog_version": catalog_version, "created_at": time.time(), "sections": {}}
        queries = {
            "problems": select(problem.c.id.label("problem_id"), problem.c.code,
                               problem.c.name.label("title"), problem.c.group_id).order_by(problem.c.id),
            "profiles": select(profile.c.id.label("profile_id"), profile.c.name, user.c.username)
                .select_from(profile.outerjoin(user, user.c.id == profile.c.user_id)).order_by(profile.c.id),
            "pairs": select(submission.c.user_id.label("profile_id"), submission.c.problem_id,
                func.max(case((submission.c.result == "AC", 1), else_=0)).label("has_ac"),
                func.min(case((submission.c.result == "AC", submission.c.date))).label("first_ac_at"))
                .select_from(submission.join(problem, problem.c.id == submission.c.problem_id)
                             .join(profile, profile.c.id == submission.c.user_id))
                .where(submission.c.result.in_(FINAL_RESULTS),
                       func.coalesce(submission.c.status, "D").not_in(("QU", "P", "G", "IE")))
                .group_by(submission.c.user_id, submission.c.problem_id)
                .order_by(submission.c.user_id, submission.c.problem_id),
        }
        for section, query in queries.items():
            count, pages, digest = 0, 0, hashlib.sha256()
            result = db.execute(query.execution_options(yield_per=PAGE_SIZE)).mappings()
            for partition in result.partitions(PAGE_SIZE):
                items = [dict(row) for row in partition]
                raw = json.dumps(items, ensure_ascii=False, default=str, separators=(",", ":")).encode()
                (directory / f"{section}-{pages}.json").write_bytes(raw)
                digest.update(raw)
                count += len(items)
                pages += 1
            manifest["sections"][section] = {"count": count, "pages": pages, "sha256": digest.hexdigest()}
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest
    except Exception:
        if directory.exists():
            shutil.rmtree(directory)
        raise
    finally:
        _lock.release()


def read_page(snapshot_id, section, page, actor_id):
    if len(snapshot_id) != 32 or any(char not in "0123456789abcdef" for char in snapshot_id):
        raise HTTPException(404, "Không tìm thấy snapshot.")
    directory = _root / snapshot_id
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(409, "Snapshot hết hạn hoặc provider đã khởi động lại.")
    if manifest["actor_id"] != actor_id:
        raise HTTPException(403, "Snapshot thuộc phạm vi khác.")
    if time.time() - manifest["created_at"] > TTL:
        raise HTTPException(409, "Snapshot đã hết hạn.")
    info = manifest["sections"].get(section)
    if info is None or page < 0 or page >= info["pages"]:
        raise HTTPException(404, "Trang snapshot không tồn tại.")
    raw = (directory / f"{section}-{page}.json").read_bytes()
    return {"snapshot_id": snapshot_id, "section": section, "page": page,
            "items": json.loads(raw), "sha256": hashlib.sha256(raw).hexdigest()}

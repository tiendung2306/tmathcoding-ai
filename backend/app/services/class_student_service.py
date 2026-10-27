import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.services.source_gateway import SourceGateway, SourceStudent

_CACHE_TTL_SECONDS = 60
_CACHE_MAX_ENTRIES = 128


@dataclass
class _RosterCache:
    updated_at: float
    students: list[SourceStudent] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_roster_cache: OrderedDict[tuple[int, int], _RosterCache] = OrderedDict()


def _get_cache(key: tuple[int, int], now: float) -> _RosterCache:
    expired = [
        cache_key for cache_key, entry in _roster_cache.items()
        if now - entry.updated_at >= _CACHE_TTL_SECONDS
    ]
    for cache_key in expired:
        _roster_cache.pop(cache_key, None)

    entry = _roster_cache.pop(key, None)
    if entry is None:
        entry = _RosterCache(updated_at=now)
    entry.updated_at = now
    _roster_cache[key] = entry
    while len(_roster_cache) > _CACHE_MAX_ENTRIES:
        _roster_cache.popitem(last=False)
    return entry


async def get_class_students(
    source: SourceGateway, class_id: int, actor_profile_id: int,
) -> list[SourceStudent]:
    """Return a short-lived cached class roster, loading source cursor pages once."""
    cache = _get_cache((actor_profile_id, class_id), time.monotonic())
    async with cache.lock:
        if cache.students is not None:
            return cache.students

        students: list[SourceStudent] = []
        cursor = None
        seen_cursors: set[str] = set()
        retried_stale_cursor = False
        while True:
            try:
                page = await source.list_class_students(
                    class_id, actor_profile_id=actor_profile_id,
                    cursor=cursor, limit=100,
                )
            except HTTPException as exc:
                if exc.status_code != 409 or not students or retried_stale_cursor:
                    raise
                students.clear()
                cursor = None
                seen_cursors.clear()
                retried_stale_cursor = True
                continue

            students.extend(page.items)
            if not page.has_more:
                cache.students = students
                return students
            cursor = page.next_cursor
            if not cursor or cursor in seen_cursors:
                raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang lớp không hợp lệ.")
            seen_cursors.add(cursor)

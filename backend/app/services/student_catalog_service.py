import asyncio
import inspect
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.schemas.teacher import StudentPage, StudentSearchItem
from app.services.source_gateway import SourceGateway, SourcePage, SourceStudent

_STUDENT_CACHE_TTL_SECONDS = 60
_STUDENT_CACHE_MAX_ENTRIES = 128


@dataclass
class _StudentPageCache:
    updated_at: float
    pages: dict[int, SourcePage[SourceStudent]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_student_cache: OrderedDict[tuple[int, int, str, int], _StudentPageCache] = OrderedDict()


def _get_page_cache(key: tuple[int, int, str, int], now: float) -> _StudentPageCache:
    expired = [
        cache_key for cache_key, value in _student_cache.items()
        if now - value.updated_at >= _STUDENT_CACHE_TTL_SECONDS
    ]
    for cache_key in expired:
        _student_cache.pop(cache_key, None)

    cache = _student_cache.pop(key, None)
    if cache is None:
        cache = _StudentPageCache(updated_at=now)
    cache.updated_at = now
    _student_cache[key] = cache
    while len(_student_cache) > _STUDENT_CACHE_MAX_ENTRIES:
        _student_cache.popitem(last=False)
    return cache


async def _fetch_source_page(
    gateway: SourceGateway,
    teacher_id: int,
    actor: int,
    query: str | None,
    page: int,
    page_size: int,
    cache: _StudentPageCache,
) -> tuple[int, SourcePage[SourceStudent]]:
    cached_page = cache.pages.get(page)
    if cached_page is not None:
        return page, cached_page

    earlier_pages = [number for number in cache.pages if number < page]
    current_page = max(earlier_pages, default=0)
    cursor = cache.pages[current_page].next_cursor if current_page else None
    next_page = current_page + 1
    seen_cursors: set[str] = set()
    last_result: SourcePage[SourceStudent] | None = None

    while next_page <= page:
        if next_page > 1 and not cursor:
            break
        if cursor:
            if cursor in seen_cursors:
                raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
            seen_cursors.add(cursor)
        last_result = await gateway.list_students(
            teacher_id,
            actor_profile_id=actor,
            q=query,
            cursor=cursor,
            limit=page_size,
            sort="points_desc",
        )
        cache.pages[next_page] = last_result
        if not last_result.has_more:
            break
        cursor = last_result.next_cursor
        if next_page == page:
            break
        next_page += 1

    if page in cache.pages:
        return page, cache.pages[page]
    if last_result is not None:
        actual_page = max(cache.pages)
        return actual_page, last_result
    raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn không trả được trang học sinh.")


async def get_student_page(
    gateway: SourceGateway, teacher_id: int, page: int, page_size: int, q: str,
    actor_profile_id: int | None = None,
) -> StudentPage:
    actor = actor_profile_id or teacher_id
    query = q.strip() or None
    if "sort" not in inspect.signature(gateway.list_students).parameters:
        return await _get_legacy_student_page(gateway, teacher_id, actor, page, page_size, query)

    cache_key = (actor, teacher_id, query or "", page_size)
    cache = _get_page_cache(cache_key, time.monotonic())

    async with cache.lock:
        try:
            target_page, result = await _fetch_source_page(
                gateway, teacher_id, actor, query, page, page_size, cache,
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            cache.pages.clear()
            target_page, result = await _fetch_source_page(
                gateway, teacher_id, actor, query, page, page_size, cache,
            )

    items: list[StudentSearchItem] = []
    for item in result.items:
        if item.rank is None:
            raise HTTPException(
                status_code=502,
                detail="Dịch vụ dữ liệu nguồn chưa trả thứ hạng toàn cục của học sinh.",
            )
        items.append(StudentSearchItem(
            user_id=item.profile_id,
            name=item.name or f"Học sinh #{item.profile_id}",
            username=item.username or f"user_{item.profile_id}",
            points=item.points,
            problem_count=item.problem_count,
            avatar_url=item.avatar_url,
            rank=item.rank,
        ))

    total_pages = (result.total + page_size - 1) // page_size
    return StudentPage(
        items=items,
        total=result.total,
        page=target_page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def _get_legacy_student_page(
    gateway: SourceGateway,
    teacher_id: int,
    actor: int,
    page: int,
    page_size: int,
    query: str | None,
) -> StudentPage:
    """Keep older in-process SourceGateway adapters working during contract rollout."""
    result = await gateway.list_students(
        teacher_id, actor_profile_id=actor, q=None, cursor=None, limit=100,
    )
    students = list(result.items)
    seen_cursors: set[str] = set()
    while result.has_more:
        if not result.next_cursor or result.next_cursor in seen_cursors:
            raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
        seen_cursors.add(result.next_cursor)
        result = await gateway.list_students(
            teacher_id, actor_profile_id=actor, q=None, cursor=result.next_cursor, limit=100,
        )
        students.extend(result.items)

    students.sort(key=lambda item: (-item.points, item.profile_id))
    ranks = {item.profile_id: index + 1 for index, item in enumerate(students)}
    if query:
        term = query.casefold()
        students = [item for item in students if term in " ".join((
            item.name or "", item.username or "", str(item.profile_id),
        )).casefold()]
    total = len(students)
    total_pages = (total + page_size - 1) // page_size
    target_page = min(page, max(1, total_pages))
    start = (target_page - 1) * page_size
    return StudentPage(
        items=[StudentSearchItem(
            user_id=item.profile_id,
            name=item.name or f"Học sinh #{item.profile_id}",
            username=item.username or f"user_{item.profile_id}",
            points=item.points,
            problem_count=item.problem_count,
            avatar_url=item.avatar_url,
            rank=ranks[item.profile_id],
        ) for item in students[start:start + page_size]],
        total=total,
        page=target_page,
        page_size=page_size,
        total_pages=total_pages,
    )

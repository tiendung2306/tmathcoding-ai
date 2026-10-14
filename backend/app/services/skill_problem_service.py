from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import HTTPException

from app.services.source_gateway import SourceGateway

PAGE_LIMIT = 100
MAX_CURSOR_PAGES = 100
TIME_RANGE_DAYS = {"1d": 1, "7d": 7, "30d": 30, "1y": 365}
VALID_TIME_RANGES = {"all", *TIME_RANGE_DAYS}
VALID_STATUSES = {"all", "ac", "attempted", "unattempted"}


def _actor_id(user_id: int, actor_profile_id: int | None) -> int:
    return actor_profile_id if actor_profile_id is not None else user_id


def _validate_page(page: int, page_size: int, *, max_page_size: int) -> None:
    if page < 1:
        raise HTTPException(422, "Trang phải bắt đầu từ 1.")
    if page_size < 1 or page_size > max_page_size:
        raise HTTPException(422, f"Số bản ghi mỗi trang phải nằm trong khoảng 1 đến {max_page_size}.")


def _normalize_reference_now(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _cutoff(time_range: str, reference_now: datetime | None) -> datetime | None:
    if time_range not in VALID_TIME_RANGES:
        raise HTTPException(422, "Khoảng thời gian không hợp lệ.")
    days = TIME_RANGE_DAYS.get(time_range)
    return reference_now - timedelta(days=days) if days and reference_now is not None else None


async def _get_student(gateway: SourceGateway, profile_id: int, actor_id: int) -> None:
    try:
        await gateway.get_student(profile_id, actor_profile_id=actor_id)
    except HTTPException as exc:
        # Source self-access can be valid even when the profile has no class membership.
        # The aggregate/submission provider endpoint still checks profile existence and scope.
        if exc.status_code != 404 or actor_id != profile_id:
            raise


async def _reference_now(gateway: SourceGateway, profile_id: int, actor_id: int) -> datetime | None:
    aggregate = await gateway.aggregate_students([profile_id], actor_profile_id=actor_id)
    return _normalize_reference_now(aggregate.reference_now)


async def _collect_pages(fetch, *, max_pages: int = MAX_CURSOR_PAGES, with_version: bool = False):
    items = []
    cursor = None
    seen_cursors: set[str] = set()
    version = None
    version_seen = False
    for _ in range(max_pages):
        result = await fetch(cursor)
        current_version = getattr(result, "catalog_version", None)
        if with_version and current_version is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu phiên bản danh mục.")
        if current_version is not None:
            if version_seen and current_version != version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
            version, version_seen = current_version, True
        items.extend(result.items)
        if not result.has_more:
            return (items, version) if with_version else items
        if not result.next_cursor or result.next_cursor == cursor:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor phân trang không hợp lệ.")
        if result.next_cursor in seen_cursors:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor phân trang lặp.")
        seen_cursors.add(result.next_cursor)
        cursor = result.next_cursor
    raise HTTPException(422, "Kết quả vượt giới hạn 100 trang con trỏ; thu hẹp bộ lọc.")


async def _student_problem_facts(gateway: SourceGateway, profile_id: int, actor_id: int,
                                 date_from: datetime | None):
    return await _collect_pages(lambda cursor: gateway.list_student_problem_facts(
        profile_id, actor_profile_id=actor_id, date_from=date_from,
        date_to=None, cursor=cursor, limit=PAGE_LIMIT,
    ), with_version=True)


async def _get_reference_and_facts(gateway: SourceGateway, profile_id: int, actor_id: int,
                                   time_range: str):
    if time_range == "all":
        try:
            aggregate = await gateway.aggregate_students(
                [profile_id], actor_profile_id=actor_id, include_problem_facts=True,
            )
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            aggregate = await gateway.aggregate_students([profile_id], actor_profile_id=actor_id)
    else:
        aggregate = await gateway.aggregate_students([profile_id], actor_profile_id=actor_id)
    reference = _normalize_reference_now(aggregate.reference_now)
    cutoff = _cutoff(time_range, reference)
    if time_range == "all":
        embedded = aggregate.students[0].problem_facts if aggregate.students else []
        if embedded is not None:
            if aggregate.catalog_version is None:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu phiên bản danh mục.")
            return reference, cutoff, embedded, aggregate.catalog_version
    facts, version = await _student_problem_facts(gateway, profile_id, actor_id, cutoff)
    return reference, cutoff, facts, version


async def _tag_items(gateway: SourceGateway, actor_id: int, tag_id: int, q: str):
    tags, tag_version = await _collect_pages(
        lambda cursor: _get_tag_page(gateway, actor_id, cursor), with_version=True,
    )
    if not any(tag.tag_id == tag_id for tag in tags):
        raise HTTPException(404, "Không tìm thấy dạng bài.")
    problems, problem_version = await _collect_pages(lambda cursor: gateway.list_problems(
        actor_profile_id=actor_id, cursor=cursor, after_id=None, limit=PAGE_LIMIT,
        q=q.strip() or None, tag_id=tag_id, fields="summary",
    ), with_version=True)
    if tag_version is not None and problem_version is not None and tag_version != problem_version:
        raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
    return problems, problem_version or tag_version


async def _get_tag_page(gateway: SourceGateway, actor_id: int, cursor: str | None):
    page, _etag, not_modified = await gateway.list_tags(
        actor_profile_id=actor_id, cursor=cursor, limit=PAGE_LIMIT,
    )
    if not_modified or page is None:
        raise HTTPException(502, "Dịch vụ dữ liệu nguồn không trả danh sách dạng bài.")
    return page


async def tag_problems(
    gateway: SourceGateway, tag_id: int, user_id: int, time_range: str = "all",
    status: str = "all", q: str = "", page: int = 1, page_size: int = 20, *,
    actor_profile_id: int | None = None,
):
    _validate_page(page, page_size, max_page_size=50)
    if time_range not in VALID_TIME_RANGES:
        raise HTTPException(422, "Khoảng thời gian không hợp lệ.")
    if status not in VALID_STATUSES:
        raise HTTPException(422, "Trạng thái lọc không hợp lệ.")
    actor_id = _actor_id(user_id, actor_profile_id)
    await _get_student(gateway, user_id, actor_id)
    _reference, _cutoff_date, facts, facts_version = await _get_reference_and_facts(
        gateway, user_id, actor_id, time_range,
    )
    # Catalog requests are query-bound; q and tag filtering happen at the provider before paging.
    catalog, catalog_version = await _tag_items(gateway, actor_id, tag_id, q or "")
    if facts_version is not None and catalog_version is not None and facts_version != catalog_version:
        raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải; hãy thử lại.")
    facts_by_problem = {fact.problem_id: fact for fact in facts}
    items = []
    for problem in catalog:
        fact = facts_by_problem.get(problem.problem_id)
        attempts = fact.attempt_count if fact else 0
        solved = bool(fact and fact.ac_count > 0)
        if status == "ac" and not solved:
            continue
        if status == "attempted" and (attempts == 0 or solved):
            continue
        if status == "unattempted" and attempts > 0:
            continue
        items.append({
            "id": problem.problem_id, "code": problem.code, "title": problem.title or problem.name or "",
            "attempts": attempts, "solved": solved,
            "last_submission_at": fact.last_submission_at if fact else None,
        })
    items.sort(key=lambda item: ((item["code"] or "").casefold(), item["id"]))
    total = len(items)
    total_pages = max(1, ceil(total / page_size))
    page = min(page, total_pages)
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages}


async def problem_detail(
    gateway: SourceGateway, problem_id: int, user_id: int, time_range: str = "all",
    page: int = 1, page_size: int = 10, *, actor_profile_id: int | None = None,
):
    _validate_page(page, page_size, max_page_size=100)
    if time_range not in VALID_TIME_RANGES:
        raise HTTPException(422, "Khoảng thời gian không hợp lệ.")
    actor_id = _actor_id(user_id, actor_profile_id)
    await _get_student(gateway, user_id, actor_id)
    reference = await _reference_now(gateway, user_id, actor_id)
    cutoff = _cutoff(time_range, reference)
    problem = await gateway.get_problem(problem_id, actor_profile_id=actor_id)

    first_page = await gateway.list_student_submissions(
        user_id, actor_profile_id=actor_id, date_from=cutoff, date_to=None,
        result=None, only_with_source=None, problem_id=problem_id,
        cursor=None, limit=page_size, sort="desc",
    )
    total = first_page.total or 0
    total_pages = max(1, ceil(total / page_size))
    effective_page = min(page, total_pages)
    if effective_page > MAX_CURSOR_PAGES:
        raise HTTPException(422, "Trang vượt giới hạn phân trang; hãy dùng trang gần hơn.")
    current = first_page
    cursor = None
    seen_cursors: set[str] = set()
    for page_number in range(1, effective_page):
        if not current.has_more or not current.next_cursor:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn dừng phân trang sớm.")
        cursor = current.next_cursor
        if cursor in seen_cursors:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor phân trang lặp.")
        seen_cursors.add(cursor)
        current = await gateway.list_student_submissions(
            user_id, actor_profile_id=actor_id, date_from=cutoff, date_to=None,
            result=None, only_with_source=None, problem_id=problem_id,
            cursor=cursor, limit=page_size, sort="desc",
        )

    submissions = [{
        "id": item.submission_id, "date": item.submitted_at,
        "result": item.result or item.status, "points": item.points,
        "time": item.time, "memory": item.memory,
    } for item in current.items]
    return {
        "id": problem.problem_id, "code": problem.code,
        "title": problem.title or problem.name or (problem.code or f"Problem {problem_id}"),
        "description": problem.description or "", "time_limit": problem.time_limit,
        "memory_limit": problem.memory_limit,
        "submissions": {"items": submissions, "total": total, "page": effective_page,
                        "page_size": page_size, "total_pages": total_pages},
    }

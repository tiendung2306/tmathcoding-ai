from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_preferences import ClassStar
from app.models.virtual_class import VirtualClassSession
from app.schemas.teacher import ClassManager, ClassPage, ClassSummary
from app.services.source_gateway import SourceClass, SourceGateway


def _year_label(item: SourceClass) -> str | None:
    year = item.school_year
    if year is None or year.start is None or year.finish is None:
        return None
    return f"{year.start.year}-{year.finish.year}"


def _as_datetime(value: datetime | None) -> datetime | None:
    return value


async def get_class_page(
    gateway: SourceGateway,
    teacher_id: int,
    page: int,
    page_size: int,
    q: str,
    sort_by: str,
    sort_order: str,
    config_db: AsyncSession,
    starred_only: bool = False,
    actor_profile_id: int | None = None,
) -> ClassPage:
    star_owner_profile_id = actor_profile_id or teacher_id
    star_rows = (await config_db.execute(
        select(ClassStar.organization_id, ClassStar.starred_at)
        .where(ClassStar.owner_profile_id == star_owner_profile_id)
        .order_by(ClassStar.starred_at.desc(), ClassStar.organization_id.asc())
    )).all()
    stars = {row.organization_id: row.starred_at for row in star_rows}
    active_ids = list((await config_db.execute(
        select(VirtualClassSession.org_id).where(VirtualClassSession.end_time.is_(None))
        .distinct().order_by(VirtualClassSession.org_id.asc())
    )).scalars().all())
    sort = "created_at" if sort_by == "creation_date" else sort_by
    actor = actor_profile_id or teacher_id

    async def source_page(cursor: str | None):
        return await gateway.list_classes(
            teacher_id, actor_profile_id=actor, q=q.strip() or None, cursor=cursor,
            limit=page_size, sort=sort, order=sort_order,
            virtual_active_class_ids=active_ids, starred_class_ids=list(stars),
        )

    first = await source_page(None)
    total = first.total
    total_pages = (total + page_size - 1) // page_size
    target_page = min(page, max(1, total_pages))

    if starred_only:
        # The upstream query applies permission, ordering, and cursoring; collect in that
        # order before filtering stars so pagination never slices an incomplete subset.
        classes = list(first.items)
        cursor = first.next_cursor
        has_more = first.has_more
        seen_cursors: set[str] = set()
        while has_more:
            if not cursor or cursor in seen_cursors:
                raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
            seen_cursors.add(cursor)
            result = await source_page(cursor)
            classes.extend(result.items)
            cursor, has_more = result.next_cursor, result.has_more
        classes = [item for item in classes if item.class_id in stars]
        total = len(classes)
        total_pages = (total + page_size - 1) // page_size
        target_page = min(page, max(1, total_pages))
        chosen = classes[(target_page - 1) * page_size:target_page * page_size]
    else:
        result = first
        seen_cursors: set[str] = set()
        for _ in range(1, target_page):
            if not result.has_more:
                raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không đầy đủ.")
            if not result.next_cursor or result.next_cursor in seen_cursors:
                raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
            seen_cursors.add(result.next_cursor)
            result = await source_page(result.next_cursor)
        chosen = result.items

    return ClassPage(
        items=[ClassSummary(
            id=item.class_id,
            name=(item.name or f"Lớp {item.class_id}"),
            member_count=item.member_count,
            school_year=_year_label(item),
            managers=[ClassManager(id=manager.profile_id, name=manager.name) for manager in item.managers],
            creation_date=_as_datetime(item.created_at),
            is_active=item.class_id in active_ids,
            has_active_contest=item.has_active_contest,
            starred_at=stars.get(item.class_id),
        ) for item in chosen],
        total=total, page=target_page, page_size=page_size, total_pages=total_pages,
    )

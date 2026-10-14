from app.schemas.teacher import StudentPage, StudentSearchItem
from fastapi import HTTPException
from app.services.source_gateway import SourceGateway


async def get_student_page(
    gateway: SourceGateway, teacher_id: int, page: int, page_size: int, q: str,
    actor_profile_id: int | None = None,
) -> StudentPage:
    actor = actor_profile_id or teacher_id
    result = await gateway.list_students(
        teacher_id, actor_profile_id=actor, q=q.strip() or None, cursor=None, limit=page_size,
    )
    total_pages = (result.total + page_size - 1) // page_size
    target_page = min(page, max(1, total_pages))
    seen_cursors: set[str] = set()
    for _ in range(1, target_page):
        if not result.has_more:
            raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không đầy đủ.")
        if not result.next_cursor or result.next_cursor in seen_cursors:
            raise HTTPException(status_code=502, detail="Dịch vụ dữ liệu nguồn trả phân trang không hợp lệ.")
        seen_cursors.add(result.next_cursor)
        result = await gateway.list_students(
            teacher_id, actor_profile_id=actor, q=q.strip() or None,
            cursor=result.next_cursor, limit=page_size,
        )
    return StudentPage(
        items=[StudentSearchItem(
            user_id=item.profile_id, name=item.name or f"Học sinh #{item.profile_id}",
            username=item.username or f"user_{item.profile_id}", points=item.points,
            problem_count=item.problem_count,
        ) for item in result.items],
        total=result.total, page=target_page, page_size=page_size, total_pages=total_pages,
    )

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dashboard_database import get_dashboard_db
from app.schemas.teacher import (
    ContestOrganization,
    StudentSearchItem,
    StudentPage,
    ClassHeatmapResponse,
    StudentDetailResponse,
    ClassStudentItem,
)
from app.schemas.analytics import StudentTagAnalyticsResponse
from app.services.tag_analytics_service import tag_analytics_service
from app.services.heatmap_service import heatmap_service
from app.services.algorithm_competency_service import algorithm_competency_service
from app.services.student_catalog_service import get_student_page
from app.services.class_access import get_visible_class
from app.services.contest_access import get_visible_contest
from app.services.class_student_service import get_class_students as load_class_students
from app.services.source_gateway import SourceContest, SourceContestPage, SourceGateway, get_source_gateway
from app.core.auth import get_current_user

router = APIRouter()


def _target_profile_id(requested: int | None, actor) -> int:
    if requested is None:
        return actor.profile_id
    if requested != actor.profile_id and not actor.is_super_admin:
        raise HTTPException(403, "Bạn không có quyền truy cập hồ sơ nguồn này.")
    return requested


@router.get("/classes/{org_id}")
async def get_class_context(
    org_id: int,
    teacher_id: int | None = Query(None, ge=1),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    _target_profile_id(teacher_id, actor)
    organization = await get_visible_class(source, org_id, actor.profile_id)
    return {"id": organization.class_id, "name": organization.name}

@router.get("/contest-organizations", response_model=list[ContestOrganization])
async def get_contest_organizations(
    teacher_id: int | None = Query(None, ge=1),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    target = _target_profile_id(teacher_id, actor)
    items = []
    cursor = None
    seen_cursors: set[str] = set()
    while True:
        page = await source.list_classes(
            target, actor_profile_id=actor.profile_id, q=None, cursor=cursor,
            limit=100, sort="name", order="asc",
            virtual_active_class_ids=[], starred_class_ids=[],
        )
        items.extend(ContestOrganization(id=item.class_id, name=item.name or f"Lớp {item.class_id}")
                     for item in page.items)
        if not page.has_more:
            return items
        cursor = page.next_cursor
        if not cursor or cursor in seen_cursors:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor tổ chức không hợp lệ.")
        seen_cursors.add(cursor)


@router.get("/my-contests", response_model=SourceContestPage)
async def get_teacher_contests(
    teacher_id: int | None = Query(None, ge=1),
    state: str = Query("all", pattern="^(active|ended|all)$"),
    q: str = Query("", max_length=128),
    cursor: str | None = Query(None),
    limit: int = Query(24, ge=1, le=100),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    target = _target_profile_id(teacher_id, actor)
    return await source.list_teacher_contests(
        target, actor_profile_id=actor.profile_id, state=state, at=None,
        cursor=cursor, limit=limit, q=q.strip() or None,
    )


@router.get("/my-contests/{contest_id}", response_model=SourceContest)
async def get_teacher_contest(
    contest_id: int,
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    return await get_visible_contest(source, contest_id, actor.profile_id)

@router.get("/my-students", response_model=StudentPage)
async def get_teacher_students(
    teacher_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    q: str = Query("", max_length=128),
    sort: str = Query("points_desc", pattern="^(points_desc|points_asc|name|name_desc)$"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    target = _target_profile_id(teacher_id, actor)
    return await get_student_page(source, target, page, page_size, q, actor_profile_id=actor.profile_id, sort=sort)


@router.get("/students/search", response_model=list[StudentSearchItem])
async def search_students(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm tên học sinh"),
    teacher_id: int | None = Query(None, ge=1),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Find students visible to the acting source profile."""
    target = _target_profile_id(teacher_id, actor)
    res = await source.list_students(target, actor_profile_id=actor.profile_id, q=q, limit=10)
    return [
        StudentSearchItem(
            user_id=p.profile_id,
            name=p.name or f"User {p.profile_id}",
            username=p.username or f"user_{p.profile_id}",
            points=p.points,
            problem_count=p.problem_count,
        )
        for p in res.items
    ]

@router.get("/students/{student_id}")
async def get_student_context(
    student_id: int,
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    profile = await source.get_student(student_id, actor_profile_id=actor.profile_id)
    return {"id": profile.profile_id, "name": profile.name or f"Học sinh #{profile.profile_id}"}


@router.get("/class/{org_id}/heatmap", response_model=ClassHeatmapResponse)
async def get_class_heatmap(
    org_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """F2.1: Heatmap 2D năng lực lớp học theo 8 chuyên đề thuật toán cốt lõi."""
    return await algorithm_competency_service.get_class_competency_heatmap(
        org_id, time_range, source, dashboard_db, actor_profile_id=actor.profile_id,
    )

@router.get("/students/{student_id}/detail", response_model=StudentDetailResponse)
async def get_student_detail(
    student_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """F2.2: Xem chi tiết học sinh: profile, lớp học, năng lực 8 chuyên đề thuật toán, cảnh báo, thống kê."""
    return await heatmap_service.get_student_detail(
        student_id, source, time_range=time_range, dashboard_db=dashboard_db, actor_profile_id=actor.profile_id,
    )

@router.get("/students/{student_id}/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_managed_student_tag_analytics(
    student_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Tag analytics của 1 học sinh theo mốc thời gian (dùng cho chế độ xem chi tiết mở rộng)."""
    return await tag_analytics_service.get_student_tag_analytics(
        student_id, source, time_range=time_range, actor_profile_id=actor.profile_id,
    )

@router.get("/classes/{org_id}/students", response_model=list[ClassStudentItem])
async def get_class_students(
    org_id: int,
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Danh sách học sinh hiện thuộc lớp theo dữ liệu nguồn."""
    students = await load_class_students(source, org_id, actor.profile_id)
    return [ClassStudentItem(
        user_id=item.profile_id,
        name=item.name or f"Học sinh #{item.profile_id}",
        username=item.username or f"user_{item.profile_id}",
        avatar_url=item.avatar_url,
        points=item.points,
        problem_count=item.problem_count,
        display_rank=item.display_rank,
    ) for item in students]

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.core.database import get_db
from app.core.dashboard_database import get_dashboard_db
from app.core.config_database import get_config_db
from app.models.dmoj import (
    JudgeProfile,
    AuthUser,
)
from app.schemas.teacher import (
    ClassPage,
    ClassStarResponse,
    ClassSortField,
    SortOrder,
    StudentSearchItem,
    ClassHeatmapResponse,
    StudentDetailResponse,
    ClassStudentItem,
)
from app.schemas.analytics import StudentTagAnalyticsResponse
from app.services.tag_analytics_service import tag_analytics_service
from app.services.heatmap_service import heatmap_service
from app.services.algorithm_competency_service import algorithm_competency_service
from app.services.class_catalog_service import get_class_page
from app.services.class_preferences_service import set_class_star
from app.services.class_access import get_visible_class

router = APIRouter()


@router.get("/classes/{org_id}")
async def get_class_context(
    org_id: int,
    teacher_id: int = Query(2, ge=1),
    db: AsyncSession = Depends(get_db),
):
    organization = await get_visible_class(db, org_id, teacher_id)
    return {"id": organization.id, "name": organization.name}

# ==============================================================================
# LƯU Ý TÍCH HỢP (INTEGRATION NOTE):
# Đây là dịch vụ Standalone Microservice. Khi tích hợp vào Monolith chính,
# thay `teacher_id` query bằng Dependency xác thực Session/JWT của giáo viên
# và kiểm tra quyền quản lý lớp trước khi trả dữ liệu học sinh.
# ==============================================================================

@router.get("/my-classes", response_model=ClassPage)
async def get_teacher_classes(
    teacher_id: int = Query(2, description="Profile ID của Giáo viên (Mặc định 2 khi test độc lập)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    q: str = Query("", max_length=128),
    sort_by: ClassSortField = Query("creation_date"),
    sort_order: SortOrder = Query("desc"),
    starred_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    config_db: AsyncSession = Depends(get_config_db),
):
    """F2.1: Danh sách lớp giáo viên QUẢN LÝ (judge_organization_admins) kèm số học sinh thật.
    Super Admin (judge_profile.super_admin=1) xem được toàn bộ tổ chức (SDD §3)."""
    return await get_class_page(db, teacher_id, page, page_size, q, sort_by, sort_order, config_db, starred_only)


@router.put("/classes/{org_id}/star", response_model=ClassStarResponse)
async def star_class(
    org_id: int,
    teacher_id: int = Query(2, ge=1),
    db: AsyncSession = Depends(get_db),
    config_db: AsyncSession = Depends(get_config_db),
):
    return await set_class_star(db, config_db, teacher_id, org_id, True)


@router.delete("/classes/{org_id}/star", response_model=ClassStarResponse)
async def unstar_class(
    org_id: int,
    teacher_id: int = Query(2, ge=1),
    db: AsyncSession = Depends(get_db),
    config_db: AsyncSession = Depends(get_config_db),
):
    return await set_class_star(db, config_db, teacher_id, org_id, False)

@router.get("/students/search", response_model=list[StudentSearchItem])
async def search_students(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm tên học sinh"),
    db: AsyncSession = Depends(get_db)
):
    """F2.2: Tìm học sinh theo TÊN (judge_profile.name) hoặc USERNAME thật (auth_user.username)."""
    stmt = (
        select(JudgeProfile, AuthUser.username)
        .outerjoin(AuthUser, AuthUser.id == JudgeProfile.user_id)
        .where(
            or_(
                JudgeProfile.name.like(f"%{q}%"),
                AuthUser.username.like(f"%{q}%"),
            )
        )
        .limit(10)
    )
    res = await db.execute(stmt)
    return [
        StudentSearchItem(
            user_id=p.id,
            name=p.name or f"User {p.id}",
            username=username or f"user_{p.id}",
            points=p.points or 0.0,
            problem_count=p.problem_count or 0,
        )
        for p, username in res.all()
    ]

@router.get("/students/{student_id}")
async def get_student_context(student_id: int, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(JudgeProfile).where(
        JudgeProfile.id == student_id
    ))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")
    return {"id": profile.id, "name": profile.name or f"Học sinh #{profile.id}"}


@router.get("/class/{org_id}/heatmap", response_model=ClassHeatmapResponse)
async def get_class_heatmap(
    org_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    db: AsyncSession = Depends(get_db),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """F2.1: Heatmap 2D năng lực lớp học theo 8 chuyên đề thuật toán cốt lõi."""
    return await algorithm_competency_service.get_class_competency_heatmap(org_id, time_range, db, dashboard_db)

@router.get("/students/{student_id}/detail", response_model=StudentDetailResponse)
async def get_student_detail(
    student_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    db: AsyncSession = Depends(get_db),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """F2.2: Xem chi tiết học sinh: profile, lớp học, năng lực 8 chuyên đề thuật toán, cảnh báo, thống kê."""
    return await heatmap_service.get_student_detail(student_id, db, time_range=time_range, dashboard_db=dashboard_db)

@router.get("/students/{student_id}/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_managed_student_tag_analytics(
    student_id: int,
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    db: AsyncSession = Depends(get_db)
):
    """Tag analytics của 1 học sinh theo mốc thời gian (dùng cho chế độ xem chi tiết mở rộng)."""
    return await tag_analytics_service.get_student_tag_analytics(student_id, db, time_range=time_range)

@router.get("/classes/{org_id}/students", response_model=list[ClassStudentItem])
async def get_class_students(
    org_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Danh sách học sinh của một lớp học kèm điểm, xếp hạng, cảnh báo và thời gian nộp bài gần nhất."""
    return await heatmap_service.get_class_students(org_id, db)

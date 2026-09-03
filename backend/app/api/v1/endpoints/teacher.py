from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.models.dmoj import (
    JudgeOrganization,
    JudgeProfile,
    JudgeProfileOrganizations,
    JudgeOrganizationAdmins,
    AuthUser,
)
from app.schemas.teacher import (
    ClassSummary,
    StudentSearchItem,
    ClassHeatmapResponse,
    StudentDetailResponse,
)
from app.schemas.analytics import StudentTagAnalyticsResponse
from app.services.tag_analytics_service import tag_analytics_service
from app.services.heatmap_service import heatmap_service

router = APIRouter()

# ==============================================================================
# LƯU Ý TÍCH HỢP (INTEGRATION NOTE):
# Đây là dịch vụ Standalone Microservice. Khi tích hợp vào Monolith chính,
# thay `teacher_id` query bằng Dependency xác thực Session/JWT của giáo viên
# và kiểm tra quyền quản lý lớp trước khi trả dữ liệu học sinh.
# ==============================================================================

@router.get("/my-classes", response_model=list[ClassSummary])
async def get_teacher_classes(
    teacher_id: int = Query(2, description="Profile ID của Giáo viên (Mặc định 2 khi test độc lập)"),
    db: AsyncSession = Depends(get_db)
):
    """F2.1: Danh sách lớp giáo viên QUẢN LÝ (judge_organization_admins) kèm số học sinh thật.
    Super Admin (judge_profile.super_admin=1) xem được toàn bộ tổ chức (SDD §3)."""
    # Kiểm tra super admin
    profile = (
        await db.execute(select(JudgeProfile).where(JudgeProfile.id == teacher_id))
    ).scalar_one_or_none()
    is_super_admin = bool(profile and profile.super_admin)

    member_count_sq = (
        select(func.count(JudgeProfileOrganizations.id))
        .where(JudgeProfileOrganizations.organization_id == JudgeOrganization.id)
        .correlate(JudgeOrganization)
        .scalar_subquery()
    )

    if is_super_admin:
        stmt = (
            select(JudgeOrganization.id, JudgeOrganization.name, member_count_sq)
            .order_by(JudgeOrganization.id)
            .limit(100)
        )
    else:
        stmt = (
            select(JudgeOrganization.id, JudgeOrganization.name, member_count_sq)
            .join(JudgeOrganizationAdmins, JudgeOrganizationAdmins.organization_id == JudgeOrganization.id)
            .where(JudgeOrganizationAdmins.profile_id == teacher_id)
            .order_by(JudgeOrganization.id)
            .limit(100)
        )

    res = await db.execute(stmt)
    return [
        ClassSummary(
            id=row.id,
            name=row.name or f"Lớp {row.id}",
            member_count=row[2] or 0,
        )
        for row in res.all()
    ]

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

@router.get("/class/{org_id}/heatmap", response_model=ClassHeatmapResponse)
async def get_class_heatmap(
    org_id: int,
    db: AsyncSession = Depends(get_db)
):
    """F2.1: Heatmap 2D năng lực lớp học — điểm Bloom thật + cảnh báo STUCK/GAP/INACTIVE."""
    return await heatmap_service.get_class_heatmap(org_id, db)

@router.get("/students/{student_id}/detail", response_model=StudentDetailResponse)
async def get_student_detail(
    student_id: int,
    db: AsyncSession = Depends(get_db)
):
    """F2.2: Xem chi tiết học sinh — profile, lớp học, điểm Bloom, cảnh báo, thống kê."""
    return await heatmap_service.get_student_detail(student_id, db)

@router.get("/students/{student_id}/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_managed_student_tag_analytics(
    student_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Tag analytics của 1 học sinh (dùng cho chế độ xem chi tiết mở rộng)."""
    return await tag_analytics_service.get_student_tag_analytics(student_id, db)

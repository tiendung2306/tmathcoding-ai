from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.core.database import get_db
from app.models.dmoj import JudgeOrganization, JudgeProfile
from app.schemas.teacher import ClassSummary, StudentSearchItem, ClassHeatmapResponse, HeatmapStudentRow
from app.schemas.analytics import StudentTagAnalyticsResponse
from app.services.tag_analytics_service import tag_analytics_service

router = APIRouter()

@router.get("/my-classes", response_model=list[ClassSummary])
async def get_teacher_classes(
    teacher_id: int = Query(2, description="Profile ID của Giáo viên (Mặc định 2 khi test độc lập)"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch classes managed by teacher."""
    stmt = select(JudgeOrganization).limit(20)
    res = await db.execute(stmt)
    orgs = res.scalars().all()
    
    return [
        ClassSummary(id=o.id, name=o.name or f"Class {o.id}", member_count=50)
        for o in orgs
    ]

@router.get("/students/search", response_model=list[StudentSearchItem])
async def search_students(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm tên học sinh"),
    db: AsyncSession = Depends(get_db)
):
    """Search students by name or username."""
    stmt = select(JudgeProfile).where(
        or_(
            JudgeProfile.name.like(f"%{q}%"),
            JudgeProfile.display_rank.like(f"%{q}%")
        )
    ).limit(10)
    res = await db.execute(stmt)
    profiles = res.scalars().all()

    return [
        StudentSearchItem(
            user_id=p.id,
            name=p.name or f"User {p.id}",
            username=f"student_{p.id}",
            points=p.points or 0.0,
            problem_count=p.problem_count or 0
        )
        for p in profiles
    ]

@router.get("/class/{org_id}/heatmap", response_model=ClassHeatmapResponse)
async def get_class_heatmap(
    org_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Fetch 2D Class Performance Heatmap for a class."""
    cols = ["Bloom A (Nhớ)", "Bloom B (Hiểu)", "Bloom C (Vận dụng)", "Bloom D (Phân tích)", "Bloom E (Đánh giá)"]
    
    students = [
        HeatmapStudentRow(user_id=101, student_name="Nguyễn Văn A", scores=[95.0, 80.0, 60.0, 30.0, 0.0], alerts=[]),
        HeatmapStudentRow(user_id=102, student_name="Trần Thị B", scores=[90.0, 75.0, 20.0, 10.0, 0.0], alerts=["STUCK"]),
        HeatmapStudentRow(user_id=103, student_name="Lê Hoàng C", scores=[40.0, 20.0, 0.0, 0.0, 0.0], alerts=["INACTIVE"])
    ]

    return ClassHeatmapResponse(
        organization_id=org_id,
        organization_name=f"Lớp học #{org_id}",
        columns=cols,
        students=students,
        class_averages=[75.0, 58.3, 26.6, 13.3, 0.0]
    )

@router.get("/students/{student_id}/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_managed_student_tag_analytics(
    student_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Fetch tag analytics for a student."""
    return await tag_analytics_service.get_student_tag_analytics(student_id, db)

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.student import SkillTreeResponse, FailedSubmissionItem, SubmissionDetailResponse
from app.schemas.ai import CodeDoctorRequest, CodeDoctorResponse
from app.schemas.jobs import JobCreateResponse
from app.schemas.analytics import StudentTagAnalyticsResponse, AICommentaryResponse
from app.services.skill_tree_service import skill_tree_service
from app.services.code_doctor_service import code_doctor_service
from app.services.tag_analytics_service import tag_analytics_service
from app.services.tag_ai_service import tag_ai_service

router = APIRouter()

# ==============================================================================
# LƯU Ý TÍCH HỢP (INTEGRATION NOTE):
# Đây là dịch vụ Standalone Microservice phát triển độc lập cho tmath AI.
# Khi tích hợp vào Nền tảng Monolith chính, thay thế tham số `user_id`
# bằng Dependency xác thực Session/JWT (vd: `current_user = Depends(get_current_user)`).
# ==============================================================================

@router.get("/skill-tree", response_model=SkillTreeResponse)
async def get_student_skill_tree(
    user_id: int = Query(1, description="ID của học sinh cần xem (Mặc định 1 khi test độc lập)"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch 99-Node Skill Tree & Bloom Radar for a student."""
    return await skill_tree_service.get_student_skill_tree(user_id, db)

@router.post("/code-doctor/diagnose", response_model=JobCreateResponse)
async def diagnose_code(
    req: CodeDoctorRequest,
):
    """Request Socratic AI Code Doctor diagnosis for a failed submission.
    Returns immediately with a job_id (in ~10ms) or cached result (in ~1ms).
    """
    return await code_doctor_service.diagnose_submission_async(
        req.submission_id, force_refresh=req.force_refresh
    )

@router.get("/submissions/failed", response_model=List[FailedSubmissionItem])
async def get_failed_submissions(
    user_id: int = Query(1, description="ID của học sinh cần xem danh sách bài nộp lỗi (Mặc định 1 khi test độc lập)"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng bài nộp lỗi tối đa"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch recent failed submissions (with source code) for Socratic Code Doctor diagnosis."""
    return await code_doctor_service.get_failed_submissions(user_id, db, limit=limit)

@router.get("/submissions/{submission_id}/detail", response_model=SubmissionDetailResponse)
async def get_submission_detail(
    submission_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Fetch full submission details: problem statement, source code, and test case breakdown."""
    return await code_doctor_service.get_submission_detail(submission_id, db)


@router.get("/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_student_tag_analytics(
    user_id: int = Query(1, description="ID của học sinh cần xem thống kê Tag (Mặc định 1 khi test độc lập)"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch tag completion metrics and 7-day submission statistics for a student."""
    return await tag_analytics_service.get_student_tag_analytics(user_id, db)

@router.get("/analytics/ai-commentary", response_model=AICommentaryResponse)
async def get_student_ai_commentary(
    user_id: int = Query(1, description="ID của học sinh cần nhận xét AI (Mặc định 1 khi test độc lập)"),
    force_refresh: bool = Query(False, description="Set True để ép LLM sinh nhận xét mới"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch daily personalized AI commentary and recommendations for a student."""
    return await tag_ai_service.get_daily_ai_commentary(user_id, db, force_refresh=force_refresh)

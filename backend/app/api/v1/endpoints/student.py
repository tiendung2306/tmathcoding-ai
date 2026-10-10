from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.dmoj import JudgeSubmission, JudgeProblem
from app.schemas.student import (
    SkillTreeResponse,
    StudentRecentSubmission,
    FailedSubmissionItem,
    SubmissionDetailResponse,
)
from app.schemas.ai import CodeDoctorRequest, CodeDoctorResponse
from app.schemas.jobs import JobCreateResponse
from app.schemas.analytics import StudentTagAnalyticsResponse, AICommentaryResponse
from app.services.skill_tree_service import skill_tree_service
from app.core.dashboard_database import get_dashboard_db
from app.services.code_doctor_service import code_doctor_service
from app.services.tag_analytics_service import tag_analytics_service
from app.services.tag_ai_service import tag_ai_service

router = APIRouter()


@router.get("/skill-tags/{tag_id}/problems")
async def get_tag_problems(
    tag_id: int, user_id: int = Query(..., gt=0),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$"),
    status: str = Query("all", pattern="^(all|ac|attempted|unattempted)$"),
    q: str = Query("", max_length=200), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    from app.services.skill_problem_service import tag_problems
    return await tag_problems(db, tag_id, user_id, time_range, status, q, page, page_size)


@router.get("/skill-problems/{problem_id}")
async def get_skill_problem(
    problem_id: int, user_id: int = Query(..., gt=0),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$"),
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    from app.services.skill_problem_service import problem_detail
    return await problem_detail(db, problem_id, user_id, time_range, page, page_size)

# ==============================================================================
# LƯU Ý TÍCH HỢP (INTEGRATION NOTE):
# Đây là dịch vụ Standalone Microservice phát triển độc lập cho tmath AI.
# Khi tích hợp vào Nền tảng Monolith chính, thay thế tham số `user_id`
# bằng Dependency xác thực Session/JWT (vd: `current_user = Depends(get_current_user)`).
# ==============================================================================

@router.get("/skill-tree", response_model=SkillTreeResponse)
async def get_student_skill_tree(
    user_id: int = Query(1, description="ID của học sinh cần xem (Mặc định 1 khi test độc lập)"),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    db: AsyncSession = Depends(get_db),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """Fetch 99-Node Skill Tree & 8-Pillar Algorithm Radar for a student according to time_range."""
    return await skill_tree_service.get_student_skill_tree(user_id, db, time_range=time_range, dashboard_db=dashboard_db)

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
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    db: AsyncSession = Depends(get_db)
):
    """Fetch tag completion metrics and submission statistics for a student according to time_range."""
    return await tag_analytics_service.get_student_tag_analytics(user_id, db, time_range=time_range)

@router.get("/analytics/ai-commentary", response_model=AICommentaryResponse | None)
async def get_student_ai_commentary(
    user_id: int = Query(1, description="ID của học sinh cần nhận xét AI (Mặc định 1 khi test độc lập)"),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    force_refresh: bool = Query(False, description="Set True để ép LLM sinh nhận xét mới"),
    db: AsyncSession = Depends(get_db)
):
    """Read today's cached commentary; generate only when explicitly requested."""
    if not force_refresh:
        return await tag_ai_service.get_cached_daily_ai_commentary(user_id, time_range=time_range)
    return await tag_ai_service.get_daily_ai_commentary(user_id, db, time_range=time_range, force_refresh=True)

@router.get("/submissions/recent", response_model=list[StudentRecentSubmission])
async def get_student_recent_submissions(
    user_id: int = Query(..., description="ID của học sinh cần xem bài nộp"),
    only_failed: bool = Query(False, description="Chỉ lấy bài nộp không đạt AC"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng bài nộp"),
    db: AsyncSession = Depends(get_db)
):
    """Danh sách bài nộp gần đây của học sinh (phục vụ chọn bài nộp cho Code Doctor)."""
    stmt = (
        select(
            JudgeSubmission.id,
            JudgeSubmission.date,
            JudgeSubmission.result,
            JudgeSubmission.points,
            JudgeProblem.id.label("problem_id"),
            JudgeProblem.code.label("problem_code"),
            JudgeProblem.name.label("problem_name"),
        )
        .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
        .where(JudgeSubmission.user_id == user_id)
    )
    if only_failed:
        stmt = stmt.where(JudgeSubmission.result != "AC")

    stmt = stmt.order_by(JudgeSubmission.date.desc()).limit(limit)
    res = await db.execute(stmt)

    return [
        StudentRecentSubmission(
            id=row.id,
            date=row.date.isoformat() if row.date else "",
            result=row.result or "UNK",
            points=float(row.points or 0.0),
            problem_id=row.problem_id,
            problem_code=row.problem_code or "",
            problem_name=row.problem_name or f"Bài toán #{row.problem_id}",
        )
        for row in res.all()
    ]

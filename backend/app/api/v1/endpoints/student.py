from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.schemas.student import (
    SkillTreeResponse,
    StudentRecentSubmission,
    StudentSubmissionHistoryItem,
    StudentSubmissionHistoryPage,
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
from app.services.source_gateway import SourceGateway, get_source_gateway

router = APIRouter()


@router.get("/skill-tags/{tag_id}/problems")
async def get_tag_problems(
    tag_id: int, user_id: int = Query(..., gt=0),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$"),
    status: str = Query("all", pattern="^(all|ac|attempted|unattempted)$"),
    q: str = Query("", max_length=200), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    from app.services.skill_problem_service import tag_problems
    return await tag_problems(source, tag_id, user_id, time_range, status, q, page, page_size,
                              actor_profile_id=actor.profile_id)


@router.get("/skill-problems/{problem_id}")
async def get_skill_problem(
    problem_id: int, user_id: int = Query(..., gt=0),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$"),
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=30),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    from app.services.skill_problem_service import problem_detail
    return await problem_detail(source, problem_id, user_id, time_range, page, page_size,
                                actor_profile_id=actor.profile_id)

@router.get("/skill-tree", response_model=SkillTreeResponse)
async def get_student_skill_tree(
    user_id: int = Query(1, gt=0, description="ID của học sinh cần xem"),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
    dashboard_db: AsyncSession = Depends(get_dashboard_db)
):
    """Fetch 99-Node Skill Tree & 8-Pillar Algorithm Radar for a student according to time_range."""
    return await skill_tree_service.get_student_skill_tree(
        user_id, source, time_range=time_range, dashboard_db=dashboard_db, actor_profile_id=actor.profile_id,
    )

@router.post("/code-doctor/diagnose", response_model=JobCreateResponse)
async def diagnose_code(
    req: CodeDoctorRequest,
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Request Socratic AI Code Doctor diagnosis for a failed submission.
    Returns immediately with a job_id (in ~10ms) or cached result (in ~1ms).
    """
    return await code_doctor_service.diagnose_submission_async(
        req.submission_id, source, actor.profile_id, force_refresh=req.force_refresh
    )

@router.get("/submissions/failed", response_model=List[FailedSubmissionItem])
async def get_failed_submissions(
    user_id: int = Query(1, gt=0, description="ID của học sinh cần xem danh sách bài nộp lỗi"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng bài nộp lỗi tối đa"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Fetch recent failed submissions (with source code) for Socratic Code Doctor diagnosis."""
    return await code_doctor_service.get_failed_submissions(
        user_id, source, actor.profile_id, limit=limit,
    )

@router.get("/submissions/{submission_id}/detail", response_model=SubmissionDetailResponse)
async def get_submission_detail(
    submission_id: int,
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Fetch full submission details: problem statement, source code, and test case breakdown."""
    return await code_doctor_service.get_submission_detail(
        submission_id, source, actor.profile_id,
    )


@router.get("/analytics/tags", response_model=StudentTagAnalyticsResponse)
async def get_student_tag_analytics(
    user_id: int = Query(1, gt=0, description="ID của học sinh cần xem thống kê Tag"),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Fetch tag completion metrics and submission statistics for a student according to time_range."""
    return await tag_analytics_service.get_student_tag_analytics(
        user_id, source, time_range=time_range, actor_profile_id=actor.profile_id,
    )

@router.get("/analytics/ai-commentary", response_model=AICommentaryResponse | None)
async def get_student_ai_commentary(
    user_id: int = Query(1, gt=0, description="ID của học sinh cần nhận xét AI"),
    time_range: str = Query("all", pattern="^(1d|7d|30d|1y|all)$", description="Mốc thời gian đánh giá (7d, 30d, 1y, all)"),
    force_refresh: bool = Query(False, description="Set True để ép LLM sinh nhận xét mới"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Read today's cached commentary; generate only when explicitly requested."""
    if not force_refresh:
        await source.get_student(user_id, actor_profile_id=actor.profile_id)
        return await tag_ai_service.get_cached_daily_ai_commentary(user_id, time_range=time_range)
    return await tag_ai_service.get_daily_ai_commentary(
        user_id, source, time_range=time_range, force_refresh=True,
        actor_profile_id=actor.profile_id,
    )

@router.get("/submissions/recent", response_model=list[StudentRecentSubmission])
async def get_student_recent_submissions(
    user_id: int = Query(..., gt=0, description="ID của học sinh cần xem bài nộp"),
    only_failed: bool = Query(False, description="Chỉ lấy bài nộp không đạt AC"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng bài nộp"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Danh sách bài nộp gần đây của học sinh (phục vụ chọn bài nộp cho Code Doctor)."""
    page = await source.list_student_submissions(
        user_id, actor_profile_id=actor.profile_id,
        exclude_result="AC" if only_failed else None,
        limit=limit, sort="desc",
    )
    return [
        StudentRecentSubmission(
            id=item.submission_id,
            date=item.submitted_at.isoformat() if item.submitted_at else "",
            result=item.result or "UNK",
            points=float(item.points or 0.0),
            problem_id=item.problem_id,
            problem_code=item.problem_code or "",
            problem_name=item.problem_title or f"Bài toán #{item.problem_id}",
        )
        for item in page.items
    ]


@router.get("/submissions/history", response_model=StudentSubmissionHistoryPage)
async def get_student_submission_history(
    user_id: int = Query(..., gt=0, description="ID của học sinh cần xem lịch sử bài nộp"),
    cursor: str | None = Query(None),
    result: str | None = Query(None, min_length=1, max_length=16),
    period: str = Query("all", pattern="^(1d|7d|30d|1y|all)$"),
    page_size: int = Query(24, ge=1, le=100),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Lịch sử bài nộp có lọc và phân trang theo cursor của Source API."""
    date_to = datetime.now(timezone.utc) if period != "all" else None
    days = {"1d": 1, "7d": 7, "30d": 30, "1y": 365}.get(period)
    date_from = date_to - timedelta(days=days) if date_to and days else None
    page = await source.list_student_submissions(
        user_id, actor_profile_id=actor.profile_id, date_from=date_from, date_to=date_to,
        result=result, cursor=cursor, limit=page_size, sort="desc",
    )
    return StudentSubmissionHistoryPage(
        items=[StudentSubmissionHistoryItem(
            submission_id=item.submission_id,
            problem_id=item.problem_id,
            problem_code=item.problem_code or "",
            problem_name=item.problem_title or f"Bài toán #{item.problem_id}",
            language=(item.language.common_name or item.language.name or item.language.key)
            if item.language else None,
            result=item.result,
            status=item.status,
            date=item.submitted_at.isoformat(),
            points=item.points,
            time=item.time,
            memory=item.memory,
            has_source=item.has_source,
        ) for item in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
        total=page.total,
        page_size=page_size,
        as_of=page.as_of,
    )

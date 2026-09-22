import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.dmoj import JudgeSubmission, JudgeProfile, AuthUser, JudgeProblem, JudgeProfileOrganizations
from app.models.virtual_class import VirtualClassSession
from app.schemas.virtual_class import (
    LiveSubmissionItem, VirtualClassStatus, LiveSubmissionsResponse,
    VirtualClassSessionItem, VirtualClassSessionListResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{org_id}/sessions", response_model=VirtualClassSessionListResponse)
async def get_virtual_class_sessions(
    org_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách tất cả các phiên học ảo của một lớp."""
    stmt = (
        select(VirtualClassSession)
        .where(VirtualClassSession.org_id == org_id)
        .order_by(desc(VirtualClassSession.start_time))
    )
    res = await db.execute(stmt)
    sessions = res.scalars().all()
    
    session_items = []
    active_session = None
    
    for s in sessions:
        item = VirtualClassSessionItem(
            id=s.id,
            org_id=s.org_id,
            name=s.name or f"Phiên học {s.start_time.strftime('%d/%m/%Y %H:%M')}",
            start_time=s.start_time,
            end_time=s.end_time
        )
        session_items.append(item)
        if s.end_time is None:
            active_session = item
            
    return VirtualClassSessionListResponse(
        sessions=session_items,
        active_session=active_session
    )

@router.post("/{org_id}/start", response_model=VirtualClassSessionItem)
async def start_virtual_class(
    org_id: int,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Bắt đầu một phiên học ảo mới."""
    # Check if there is an active session
    stmt = select(VirtualClassSession).where(
        VirtualClassSession.org_id == org_id,
        VirtualClassSession.end_time.is_(None)
    )
    res = await db.execute(stmt)
    active = res.scalar_one_or_none()
    
    if active:
        raise HTTPException(status_code=400, detail="Đang có một phiên học diễn ra. Không thể tạo phiên mới.")
        
    new_session = VirtualClassSession(
        org_id=org_id,
        name=name,
        start_time=datetime.utcnow()
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    
    return VirtualClassSessionItem(
        id=new_session.id,
        org_id=new_session.org_id,
        name=new_session.name or f"Phiên học {new_session.start_time.strftime('%d/%m/%Y %H:%M')}",
        start_time=new_session.start_time,
        end_time=new_session.end_time
    )

@router.post("/sessions/{session_id}/stop", response_model=VirtualClassSessionItem)
async def stop_virtual_class(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Kết thúc một phiên học ảo."""
    stmt = select(VirtualClassSession).where(VirtualClassSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên học.")
        
    if session.end_time is None:
        session.end_time = datetime.utcnow()
        await db.commit()
        await db.refresh(session)
        
    return VirtualClassSessionItem(
        id=session.id,
        org_id=session.org_id,
        name=session.name or f"Phiên học {session.start_time.strftime('%d/%m/%Y %H:%M')}",
        start_time=session.start_time,
        end_time=session.end_time
    )

@router.get("/sessions/{session_id}/live-submissions", response_model=LiveSubmissionsResponse)
async def get_live_submissions(
    session_id: int,
    since_id: int = Query(0, description="Lấy các submission có ID lớn hơn ID này"),
    limit: int = Query(50, description="Số lượng tối đa trả về"),
    db: AsyncSession = Depends(get_db)
):
    """Polling API: Lấy các bài nộp trong một phiên học cụ thể."""
    stmt_sess = select(VirtualClassSession).where(VirtualClassSession.id == session_id)
    res_sess = await db.execute(stmt_sess)
    session = res_sess.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    # Lấy các submission của học sinh thuộc tổ chức này trong thời gian session
    org_member_sq = (
        select(JudgeProfileOrganizations.profile_id)
        .where(JudgeProfileOrganizations.organization_id == session.org_id)
        .scalar_subquery()
    )

    stmt = (
        select(JudgeSubmission, JudgeProfile, AuthUser, JudgeProblem)
        .join(JudgeProfile, JudgeProfile.id == JudgeSubmission.user_id)
        .outerjoin(AuthUser, AuthUser.id == JudgeProfile.user_id)
        .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
        .where(JudgeSubmission.id > since_id)
        .where(JudgeSubmission.date >= session.start_time)
        .where(JudgeProfile.id.in_(org_member_sq))
    )
    
    if session.end_time:
        stmt = stmt.where(JudgeSubmission.date <= session.end_time)
        
    stmt = stmt.order_by(desc(JudgeSubmission.id)).limit(limit)

    res = await db.execute(stmt)
    rows = res.all()

    submissions = []
    max_id = since_id

    for sub, profile, auth_user, problem in reversed(rows): 
        ai_flags = {}
        if sub.result != "AC":
            ai_flags["has_error"] = True

        name = profile.name
        if not name and auth_user:
            name = auth_user.first_name + " " + auth_user.last_name
        if not name or name.strip() == "":
            name = f"User {profile.id}"

        submissions.append(LiveSubmissionItem(
            id=sub.id,
            user_id=profile.id,
            user_name=name,
            problem_id=problem.id,
            problem_name=problem.name,
            date=sub.date,
            result=sub.result,
            points=sub.points,
            time=sub.time,
            memory=sub.memory,
            source=None,
            ai_flags=ai_flags
        ))
        if sub.id > max_id:
            max_id = sub.id

    return LiveSubmissionsResponse(submissions=submissions, last_id=max_id)

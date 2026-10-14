import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.dashboard_database import get_dashboard_db
from app.core.time import utc_now
from app.models.virtual_class import VirtualClassSession
from app.schemas.virtual_class import (
    LiveSubmissionItem, LiveSubmissionEvent, VirtualClassStatus, LiveSubmissionsResponse,
    VirtualClassSessionItem, VirtualClassSessionListResponse, VirtualClassSessionDetail
)
from app.services.class_access import get_visible_class
from app.services.source_gateway import SourceGateway, get_source_gateway
from app.core.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sessions/{session_id}", response_model=VirtualClassSessionDetail)
async def get_virtual_class_session(
    session_id: int,
    db: AsyncSession = Depends(get_dashboard_db),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    session = (await db.execute(select(VirtualClassSession).where(
        VirtualClassSession.id == session_id
    ))).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên học.")
    organization = await get_visible_class(source, session.org_id, actor.profile_id)
    return VirtualClassSessionDetail(
        id=session.id, org_id=session.org_id,
        name=session.name or f"Phiên học {session.start_time.strftime('%d/%m/%Y %H:%M')}",
        start_time=session.start_time, end_time=session.end_time,
        class_name=organization.name or f"Lớp #{organization.class_id}",
    )

@router.get("/{org_id}/sessions", response_model=VirtualClassSessionListResponse)
async def get_virtual_class_sessions(
    org_id: int,
    db: AsyncSession = Depends(get_dashboard_db),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Lấy danh sách tất cả các phiên học ảo của một lớp."""
    await get_visible_class(source, org_id, actor.profile_id)
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
    db: AsyncSession = Depends(get_dashboard_db),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Bắt đầu một phiên học ảo mới."""
    await get_visible_class(source, org_id, actor.profile_id)
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
        start_time=utc_now()
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
    db: AsyncSession = Depends(get_dashboard_db),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Kết thúc một phiên học ảo."""
    stmt = select(VirtualClassSession).where(VirtualClassSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên học.")

    await get_visible_class(source, session.org_id, actor.profile_id)
        
    if session.end_time is None:
        session.end_time = utc_now()
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
    cursor: Optional[str] = Query(None, description="Cursor sự kiện trả về từ lần polling trước"),
    limit: int = Query(100, ge=1, le=100),
    dashboard_db: AsyncSession = Depends(get_dashboard_db),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Đọc snapshot hoặc các thay đổi bài nộp của phiên học."""
    stmt_sess = select(VirtualClassSession).where(VirtualClassSession.id == session_id)
    res_sess = await dashboard_db.execute(stmt_sess)
    session = res_sess.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    await get_visible_class(source, session.org_id, actor.profile_id)
        
    if cursor is not None:
        page = await source.list_class_submission_changes(
            session.org_id, actor_profile_id=actor.profile_id, cursor=cursor,
            date_from=session.start_time, date_to=session.end_time, limit=limit,
        )
        events = [
            LiveSubmissionEvent(
                kind=event.kind,
                submission_id=event.submission_id,
                record=_live_item(event.record) if event.record is not None else None,
            )
            for event in page.events
        ]
        return LiveSubmissionsResponse(
            events=events, cursor=page.next_cursor,
            high_watermark=page.high_watermark, snapshot=False,
            is_active=session.end_time is None,
        )

    # The first page's high_watermark is an atomic handoff to the changes feed.
    upstream_cursor: str | None = None
    pinned_watermark: str | None = None
    snapshot_items: list[LiveSubmissionItem] = []
    seen_cursors: set[str] = set()
    while True:
        page = await source.list_class_submissions(
            session.org_id, actor_profile_id=actor.profile_id,
            date_from=session.start_time, date_to=session.end_time,
            cursor=upstream_cursor, limit=limit,
        )
        if pinned_watermark is None:
            pinned_watermark = page.high_watermark
        elif page.high_watermark != pinned_watermark:
            raise HTTPException(409, "Snapshot bài nộp đã thay đổi. Hãy tải lại phiên.")
        snapshot_items.extend(_live_item(item) for item in page.items)
        if not page.has_more:
            break
        next_cursor = page.next_cursor
        if not next_cursor or next_cursor in seen_cursors:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor phân trang không hợp lệ.")
        seen_cursors.add(next_cursor)
        upstream_cursor = next_cursor

    if pinned_watermark is None:
        raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu high watermark cho snapshot.")
    return LiveSubmissionsResponse(
        events=[LiveSubmissionEvent(kind="created", submission_id=item.id, record=item)
                for item in snapshot_items],
        cursor=pinned_watermark, high_watermark=None, snapshot=True,
        is_active=session.end_time is None,
    )


def _live_item(item) -> LiveSubmissionItem:
    return LiveSubmissionItem(
        id=item.submission_id,
        user_id=item.profile_id,
        user_name=item.student_name or f"User {item.profile_id}",
        problem_id=item.problem_id,
        problem_name=item.problem_title or item.problem_code or f"Bài #{item.problem_id}",
        date=item.submitted_at,
        result=item.result or item.status or "?",
        points=item.points or 0,
        time=item.time,
        memory=item.memory,
        source=None,
        ai_flags={"has_error": item.result not in (None, "AC")},
    )

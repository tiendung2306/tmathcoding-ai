import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Header, Request

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.dashboard_database import get_dashboard_db
from app.schemas.skill_config import SkillConfigWrite, SkillDocument, SkillProposalReview
from app.services import skill_config_service as service


async def get_skill_user(x_user_id: int | None = Header(None, alias="X-User-ID"), source=Depends(get_db)):
    return await get_current_user(x_user_id=x_user_id if x_user_id is not None else settings.DASHBOARD_ADMIN_PROFILE_ID, db=source)


async def require_admin(user=Depends(get_skill_user)):
    if not user.super_admin:
        raise HTTPException(403, "Chỉ quản trị viên được cấu hình cây kỹ năng.")
    return user


router = APIRouter(dependencies=[Depends(require_admin)])
_inferences = {}
_cancelled_runs = {}


@router.get("")
async def get_configuration(source=Depends(get_db), dashboard=Depends(get_dashboard_db)):
    return await service.state(dashboard, source)


@router.put("")
async def save_configuration(payload: SkillConfigWrite, user=Depends(require_admin), source=Depends(get_db), dashboard=Depends(get_dashboard_db)):
    return await service.write(dashboard, source, payload.revision, payload.document, user.id, True)


@router.post("/suggest")
async def suggest(document: SkillDocument, request: Request, source=Depends(get_db), run_id: str | None = None, dashboard=Depends(get_dashboard_db)):
    if run_id is not None and (not run_id or len(run_id) > 64):
        raise HTTPException(422, "ID lượt AI không hợp lệ.")
    if run_id in _cancelled_runs:
        raise HTTPException(499, "Đã dừng yêu cầu phân loại AI.")
    if run_id in _inferences:
        raise HTTPException(409, "Lượt AI đang xử lý.")
    inference = asyncio.create_task(service.suggest(document, source))
    if run_id:
        _inferences[run_id] = inference
    async def watch_disconnect():
        while not await request.is_disconnected():
            await asyncio.sleep(0.25)
    watcher = asyncio.create_task(watch_disconnect())
    try:
        completed, _ = await asyncio.wait([inference, watcher], return_when=asyncio.FIRST_COMPLETED)
        if watcher in completed:
            raise HTTPException(499, "Đã dừng yêu cầu phân loại AI.")
        try:
            result = await inference
            result["proposals"] = await service.store_proposals(dashboard, document, result["suggestions"])
            return result
        except asyncio.CancelledError:
            if run_id in _cancelled_runs:
                raise HTTPException(499, "Đã dừng yêu cầu phân loại AI.")
            raise
    finally:
        watcher.cancel()
        inference.cancel()
        await asyncio.gather(watcher, inference, return_exceptions=True)
        if run_id and _inferences.get(run_id) is inference:
            _inferences.pop(run_id, None)


@router.delete("/suggest/{run_id}")
async def cancel_suggestion(run_id: str):
    if not run_id or len(run_id) > 64:
        raise HTTPException(422, "ID lượt AI không hợp lệ.")
    now = time.monotonic()
    for key, created in list(_cancelled_runs.items()):
        if now - created > 240 or len(_cancelled_runs) >= 1000:
            _cancelled_runs.pop(key, None)
    _cancelled_runs[run_id] = now
    task = _inferences.get(run_id)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    return {"cancelled": True}


@router.patch("/proposals")
async def review_proposals(payload: SkillProposalReview, user=Depends(require_admin), source=Depends(get_db), dashboard=Depends(get_dashboard_db)):
    return await service.review_proposals(dashboard, source, payload, user.id)

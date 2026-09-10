import logging
from fastapi import APIRouter, HTTPException
from app.schemas.jobs import JobStatusResponse
from app.core.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Fetch status, progress, and result of an asynchronous LLM job.

    Includes automatic lazy recovery for zombie tasks exceeding deadlines.
    """
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' không tồn tại hoặc đã hết hạn lưu trữ (24h)."
        )
    return job

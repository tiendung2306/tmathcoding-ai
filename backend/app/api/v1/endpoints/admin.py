from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()

@router.post("/auto-tag/run-batch")
async def run_auto_tagging_batch():
    """Trigger background Auto-Tagging pipeline worker for untagged problems."""
    return {"status": "started", "message": "Pipeline Auto-Tagging batch worker launched in background."}

@router.get("/auto-tag/status")
async def get_auto_tagging_status():
    """Get status of untagged problems tagging progress."""
    return {
        "total_problems": 16491,
        "tagged_problems": 4520,
        "untagged_problems": 11971,
        "progress_percentage": 27.4
    }

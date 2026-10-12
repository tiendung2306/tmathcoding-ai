from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.dashboard_auth import require_account

from app.core.database import get_db
from app.models.dmoj import JudgeProfile

async def get_current_user(
    account=Depends(require_account),
    db: AsyncSession = Depends(get_db)
) -> JudgeProfile:
    """Resolve the source profile linked to the authenticated dashboard account."""
    target_id = account.source_profile_id
    if target_id is None:
        raise HTTPException(status_code=403, detail="Tài khoản chưa gắn với hồ sơ nguồn.")

    stmt = select(JudgeProfile).where(JudgeProfile.id == target_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated or profile not found."
        )

    return profile

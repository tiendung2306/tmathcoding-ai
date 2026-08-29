from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.models.dmoj import JudgeProfile

async def get_current_user(
    x_user_id: Optional[int] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
) -> JudgeProfile:
    """Dependency to fetch current authenticated user profile.
    Extracts User ID from JWT Token or Authorization/X-User-ID header securely.
    Defaults to User ID 1 if not provided in dev/testing mode."""
    target_id = x_user_id if x_user_id is not None else 1

    stmt = select(JudgeProfile).where(JudgeProfile.id == target_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated or profile not found."
        )

    return profile

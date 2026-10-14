from fastapi import Depends, HTTPException, status
from app.core.dashboard_auth import require_account
from app.services.source_gateway import SourceAccess, SourceGateway, get_source_gateway

async def get_current_user(
    account=Depends(require_account),
    source: SourceGateway = Depends(get_source_gateway),
) -> SourceAccess:
    """Resolve the source profile linked to the authenticated dashboard account."""
    target_id = account.source_profile_id
    if target_id is None:
        raise HTTPException(status_code=403, detail="Tài khoản chưa gắn với hồ sơ nguồn.")

    profile = await source.get_access(target_id, actor_profile_id=target_id)
    if not profile.exists or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated or profile not found."
        )

    return profile

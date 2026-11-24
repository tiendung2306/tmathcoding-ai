import asyncio
import hashlib
import hmac
import secrets
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dashboard_database import get_dashboard_db
from app.core.time import utc_now
from app.models.auth import DashboardAccount, DashboardAuthSession
from app.services.source_gateway import SourceAccess, SourceGateway, get_source_gateway

COOKIE_NAME = "tmath_session"
_ACCESS_CACHE_MAX_ENTRIES = 64
_access_cache: dict[tuple[int, int], tuple[float, SourceAccess]] = {}
SESSION_DAYS = 7
password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(password_hasher.hash, password)


async def verify_password(password: str, stored: str) -> bool:
    try:
        return await asyncio.to_thread(password_hasher.verify, stored, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def csrf_for_token(token: str) -> str:
    return token_hash("csrf:" + token)


async def create_session(db: AsyncSession, account: DashboardAccount) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    await db.execute(delete(DashboardAuthSession).where(DashboardAuthSession.expires_at <= utc_now()))
    db.add(DashboardAuthSession(
        token_hash=token_hash(token), account_id=account.id,
        expires_at=utc_now() + timedelta(days=SESSION_DAYS), created_at=utc_now(),
    ))
    await db.commit()
    return token, csrf_for_token(token)


async def current_auth(request: Request, db: AsyncSession = Depends(get_dashboard_db)) -> tuple[DashboardAccount, DashboardAuthSession]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    row = (await db.execute(
        select(DashboardAccount, DashboardAuthSession)
        .join(DashboardAuthSession, DashboardAuthSession.account_id == DashboardAccount.id)
        .where(DashboardAuthSession.token_hash == token_hash(token), DashboardAuthSession.expires_at > utc_now())
    )).one_or_none()
    if row is None:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn.")
    account, session = row
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(csrf, csrf_for_token(token)):
            raise HTTPException(403, "Yêu cầu thiếu mã xác thực.", headers={"X-Auth-Error": "csrf_invalid"})
    return account, session


async def require_account(auth=Depends(current_auth)) -> DashboardAccount:
    return auth[0]


def reset_access_cache() -> None:
    _access_cache.clear()


async def source_access(request: Request, source: SourceGateway, profile_id: int) -> SourceAccess:
    """Resolve the linked source profile once per request and briefly across requests.

    Every dashboard request needs this check; without reuse each request paid one or
    more extra Source API round trips. Only granted access is cached, so a newly
    granted profile is never denied from cache, and revocation takes effect within
    SOURCE_ACCESS_CACHE_SECONDS (0 disables the cross-request cache).
    """
    cached = getattr(request.state, "source_access", None)
    if isinstance(cached, SourceAccess) and cached.profile_id == profile_id:
        return cached
    ttl = settings.SOURCE_ACCESS_CACHE_SECONDS
    key = (id(source), profile_id)
    now = time.monotonic()
    hit = _access_cache.get(key)
    if ttl > 0 and hit is not None and now - hit[0] < ttl:
        profile = hit[1]
    else:
        profile = await source.get_access(profile_id, actor_profile_id=profile_id)
        if ttl > 0 and profile.exists and profile.is_active:
            _access_cache[key] = (now, profile)
            while len(_access_cache) > _ACCESS_CACHE_MAX_ENTRIES:
                _access_cache.pop(next(iter(_access_cache)))
        else:
            _access_cache.pop(key, None)
    request.state.source_access = profile
    return profile


async def require_admin(request: Request,
                        account: DashboardAccount = Depends(require_account),
                        source: SourceGateway = Depends(get_source_gateway)) -> DashboardAccount:
    if account.role != "admin" or account.admin_slot != 1:
        raise HTTPException(403, "Chỉ quản trị viên được truy cập khu vực này.")
    if account.source_profile_id is None:
        raise HTTPException(403, "Quyền quản trị nguồn không còn hợp lệ.")
    profile = await source_access(request, source, account.source_profile_id)
    if not profile.exists or not profile.is_active or not profile.is_super_admin:
        raise HTTPException(403, "Quyền quản trị nguồn không còn hợp lệ.")
    return account

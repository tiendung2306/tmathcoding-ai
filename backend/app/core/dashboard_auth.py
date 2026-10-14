import asyncio
import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashboard_database import get_dashboard_db
from app.core.time import utc_now
from app.models.auth import DashboardAccount, DashboardAuthSession
from app.services.source_gateway import SourceGateway, get_source_gateway

COOKIE_NAME = "tmath_session"
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


async def require_admin(account: DashboardAccount = Depends(require_account),
                        source: SourceGateway = Depends(get_source_gateway)) -> DashboardAccount:
    if account.role != "admin" or account.admin_slot != 1:
        raise HTTPException(403, "Chỉ quản trị viên được truy cập khu vực này.")
    if account.source_profile_id is None:
        raise HTTPException(403, "Quyền quản trị nguồn không còn hợp lệ.")
    profile = await source.get_access(account.source_profile_id, actor_profile_id=account.source_profile_id)
    if not profile.exists or not profile.is_active or not profile.is_super_admin:
        raise HTTPException(403, "Quyền quản trị nguồn không còn hợp lệ.")
    return account

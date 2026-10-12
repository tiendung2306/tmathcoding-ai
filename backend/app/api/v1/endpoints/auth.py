import hashlib
import math

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dashboard_auth import (
    COOKIE_NAME, SESSION_DAYS, create_session, csrf_for_token, current_auth,
    verify_password,
)
from app.core.dashboard_database import get_dashboard_db
from app.core.redis import get_redis_client
from app.core.time import utc_now
from app.models.auth import DashboardAccount

router = APIRouter()


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


def account_data(account: DashboardAccount, csrf: str, expires_in: int) -> dict:
    return {
        "id": account.id,
        "username": account.username,
        "role": account.role,
        "has_source_profile": account.source_profile_id is not None,
        "csrf_token": csrf,
        "expires_in": expires_in,
    }


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, path="/",
        httponly=True, secure=settings.AUTH_COOKIE_SECURE, samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/") and origin not in settings.CORS_ORIGINS:
        raise HTTPException(403, "Nguồn yêu cầu không hợp lệ.")


async def login_limit(request: Request, username: str) -> tuple[object, str]:
    redis = get_redis_client()
    if redis is None:
        raise HTTPException(503, "Đăng nhập tạm thời không khả dụng.")
    client_ip = request.client.host if request.client else "unknown"
    key = "auth:login:" + hashlib.sha256(f"{client_ip}:{username}".encode()).hexdigest()
    ip_key = "auth:login:ip:" + hashlib.sha256(client_ip.encode()).hexdigest()
    try:
        attempts = await redis.incr(key)
        if attempts == 1:
            await redis.expire(key, 900)
        ip_attempts = await redis.incr(ip_key)
        if ip_attempts == 1:
            await redis.expire(ip_key, 900)
    except Exception:
        raise HTTPException(503, "Đăng nhập tạm thời không khả dụng.") from None
    if attempts > 5 or ip_attempts > 50:
        raise HTTPException(429, "Thử lại sau 15 phút.")
    return redis, key


@router.post("/login")
async def login(credentials: Credentials, request: Request, response: Response,
                db: AsyncSession = Depends(get_dashboard_db)):
    check_origin(request)
    username = credentials.username.strip().lower()
    redis, key = await login_limit(request, username)
    account = (await db.execute(select(DashboardAccount).where(DashboardAccount.username == username))).scalar_one_or_none()
    if account is None or not await verify_password(credentials.password, account.password_hash):
        raise HTTPException(401, "Tên tài khoản hoặc mật khẩu không đúng.")
    await redis.delete(key)
    token, csrf = await create_session(db, account)
    set_session_cookie(response, token)
    return account_data(account, csrf, SESSION_DAYS * 86400)


@router.get("/me")
async def me(request: Request, response: Response, auth=Depends(current_auth)):
    response.headers["Cache-Control"] = "no-store"
    expires_in = max(0, math.ceil((auth[1].expires_at - utc_now()).total_seconds()))
    return account_data(auth[0], csrf_for_token(request.cookies[COOKIE_NAME]), expires_in)


@router.post("/logout")
async def logout(request: Request, response: Response, auth=Depends(current_auth),
                 db: AsyncSession = Depends(get_dashboard_db)):
    check_origin(request)
    await db.delete(auth[1])
    await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}

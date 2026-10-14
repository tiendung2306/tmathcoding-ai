import unittest
from datetime import timedelta
from unittest.mock import patch

import httpx
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints import auth as auth_endpoint
from app.core.config import settings
from app.core.dashboard_auth import require_admin, password_hasher
from app.core.dashboard_database import get_dashboard_db
from app.services.source_gateway import SourceAccess, get_source_gateway
from app.core.time import utc_now
from app.models.auth import DashboardAccount, DashboardAuthSession


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def delete(self, instance):
        self.session.delete(instance)

    def add(self, instance):
        self.session.add(instance)


class FakeRedis:
    def __init__(self):
        self.counters = {}

    async def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key, seconds):
        return True

    async def delete(self, key):
        self.counters.pop(key, None)


class FakeSourceGateway:
    def __init__(self):
        self.admin_active = True
        self.admin_super_admin = True

    async def get_access(self, profile_id, *, actor_profile_id):
        return SourceAccess(
            profile_id=profile_id, exists=True, is_active=self.admin_active,
            is_super_admin=self.admin_super_admin, roles=["admin"],
        )


class DashboardAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        DashboardAccount.__table__.create(self.engine)
        DashboardAuthSession.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.session.add(DashboardAccount(
            username="admin", password_hash=password_hasher.hash("test-only-password"), role="admin",
            admin_slot=1, source_profile_id=2,
        ))
        self.session.commit()
        self.db = AsyncSessionAdapter(self.session)
        self.source_api = FakeSourceGateway()
        self.redis = FakeRedis()
        self.app = FastAPI()
        self.app.include_router(auth_endpoint.router, prefix="/auth")

        @self.app.get("/protected")
        async def protected(_=Depends(require_admin)):
            return {"ok": True}

        async def dashboard():
            yield self.db
        async def source_gateway():
            return self.source_api

        self.app.dependency_overrides[get_dashboard_db] = dashboard
        self.app.dependency_overrides[get_source_gateway] = source_gateway
        self.cookie_patch = patch.object(settings, "AUTH_COOKIE_SECURE", False)
        self.redis_patch = patch.object(auth_endpoint, "get_redis_client", return_value=self.redis)
        self.cookie_patch.start()
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()
        self.cookie_patch.stop()
        self.session.close()
        self.engine.dispose()

    async def test_login_grants_admin_access_and_logout(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            self.assertEqual((await client.get("/protected")).status_code, 401)
            self.assertEqual((await client.post("/auth/register", json={"username": "x", "password": "abcdefgh"})).status_code, 404)
            self.assertEqual((await client.post("/auth/login", json={"username": "admin", "password": "wrong"})).status_code, 401)
            response = await client.post("/auth/login", json={"username": "admin", "password": "test-only-password"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("httponly", response.headers["set-cookie"].lower())
            csrf = response.json()["csrf_token"]
            self.assertNotIn("must_change_password", response.json())
            self.assertEqual((await client.post("/auth/change-password", headers={"X-CSRF-Token": csrf},
                                                json={"current_password": "test-only-password", "new_password": "new-password-123"})).status_code, 404)
            self.assertEqual((await client.get("/protected")).status_code, 200)
            self.source_api.admin_active = False
            self.assertEqual((await client.get("/protected")).status_code, 403)
            self.assertEqual((await client.post("/auth/logout", headers={"X-CSRF-Token": csrf})).status_code, 200)
            self.assertEqual((await client.get("/auth/me")).status_code, 401)

    async def test_login_rate_limit_and_origin(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            self.assertEqual((await client.post("/auth/login", headers={"Origin": "https://bad.example"},
                                               json={"username": "admin", "password": "test-only-password"})).status_code, 403)
            for _ in range(5):
                self.assertEqual((await client.post("/auth/login", json={"username": "admin", "password": "wrong"})).status_code, 401)
            self.assertEqual((await client.post("/auth/login", json={"username": "admin", "password": "test-only-password"})).status_code, 429)

    async def test_rotated_cookie_rejects_old_csrf_before_logout(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            credentials = {"username": "admin", "password": "test-only-password"}
            first = await client.post("/auth/login", json=credentials)
            second = await client.post("/auth/login", json=credentials)
            self.assertNotEqual(first.json()["csrf_token"], second.json()["csrf_token"])
            rejected = await client.post("/auth/logout", headers={"X-CSRF-Token": first.json()["csrf_token"]})
            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(rejected.headers["X-Auth-Error"], "csrf_invalid")
            current = await client.get("/auth/me")
            self.assertEqual(current.status_code, 200)
            self.assertEqual(current.json()["csrf_token"], second.json()["csrf_token"])
            self.assertEqual((await client.post("/auth/logout", headers={"X-CSRF-Token": current.json()["csrf_token"]})).status_code, 200)

    async def test_session_remaining_time_and_expiry(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            login = await client.post("/auth/login", json={"username": "admin", "password": "test-only-password"})
            self.assertGreater(login.json()["expires_in"], 0)
            session = self.session.query(DashboardAuthSession).one()
            session.expires_at = utc_now() + timedelta(seconds=30)
            self.session.commit()
            current = await client.get("/auth/me")
            self.assertGreater(current.json()["expires_in"], 0)
            self.assertLessEqual(current.json()["expires_in"], 30)
            session.expires_at = utc_now() - timedelta(seconds=1)
            self.session.commit()
            self.assertEqual((await client.get("/auth/me")).status_code, 401)
            self.assertEqual((await client.get("/protected")).status_code, 401)

    async def test_permission_denial_does_not_use_csrf_error_code(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            await client.post("/auth/login", json={"username": "admin", "password": "test-only-password"})
            self.source_api.admin_super_admin = False
            response = await client.get("/protected")
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("X-Auth-Error", response.headers)

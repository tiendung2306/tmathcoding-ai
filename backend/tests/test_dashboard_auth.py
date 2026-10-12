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
from app.core.database import get_db
from app.core.time import utc_now
from app.models.auth import DashboardAccount, DashboardAuthSession
from app.models.dmoj import JudgeProfile
from db_fixtures import create_source_tables


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
        self.source_engine = create_engine("sqlite://")
        create_source_tables(self.source_engine, JudgeProfile)
        self.source_session = Session(self.source_engine)
        self.source_session.add(JudgeProfile(id=2, super_admin=1))
        self.source_session.commit()
        self.source = AsyncSessionAdapter(self.source_session)
        self.redis = FakeRedis()
        self.app = FastAPI()
        self.app.include_router(auth_endpoint.router, prefix="/auth")

        @self.app.get("/protected")
        async def protected(_=Depends(require_admin)):
            return {"ok": True}

        async def dashboard():
            yield self.db
        async def source():
            yield self.source

        self.app.dependency_overrides[get_dashboard_db] = dashboard
        self.app.dependency_overrides[get_db] = source
        self.cookie_patch = patch.object(settings, "AUTH_COOKIE_SECURE", False)
        self.redis_patch = patch.object(auth_endpoint, "get_redis_client", return_value=self.redis)
        self.cookie_patch.start()
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()
        self.cookie_patch.stop()
        self.session.close()
        self.engine.dispose()
        self.source_session.close()
        self.source_engine.dispose()

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
            self.source_session.get(JudgeProfile, 2).super_admin = 0
            self.source_session.commit()
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
            self.source_session.get(JudgeProfile, 2).super_admin = 0
            self.source_session.commit()
            response = await client.get("/protected")
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("X-Auth-Error", response.headers)

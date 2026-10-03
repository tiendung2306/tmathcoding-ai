import unittest
from datetime import date, datetime, timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.api.v1.endpoints.teacher import router
from app.api.v1.endpoints.virtual_class import router as virtual_router
from app.core.database import get_db
from app.core.config import Settings
from app.core.config_database import get_config_db
from app.models.class_preferences import ClassStar
from app.models.dmoj import (
    AuthUser, JudgeOrganization, JudgeOrganizationAdmins,
    JudgeProfile, JudgeProfileOrganizations, JudgeSchoolYear,
)
from app.models.virtual_class import VirtualClassSession
from app.services.class_catalog_service import get_class_page
from app.services.class_preferences_service import set_class_star
from fastapi import HTTPException
from pydantic import ValidationError
from db_fixtures import create_source_tables


class AsyncTestSession:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def get_bind(self):
        return self.session.get_bind()

    async def commit(self):
        self.session.commit()

    def add(self, value):
        self.session.add(value)

    async def refresh(self, value):
        self.session.refresh(value)


class ClassCatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        tables = [AuthUser, JudgeProfile, JudgeSchoolYear, JudgeOrganization, JudgeOrganizationAdmins,
                  JudgeProfileOrganizations]
        for model in tables:
            model.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.db = AsyncTestSession(self.session)
        self.config_engine = create_engine("sqlite://")
        ClassStar.__table__.create(self.config_engine)
        VirtualClassSession.__table__.create(self.config_engine)
        self.config_session = Session(self.config_engine)
        self.config_db = AsyncTestSession(self.config_session)
        self.session.execute(insert(AuthUser), [
            {"id": i, "username": f"user{i}"} for i in (2, 3, 4)
        ])
        self.session.execute(insert(JudgeProfile), [
            {"id": i, "user_id": i, "super_admin": int(i == 2)} for i in (2, 3, 4)
        ])
        self.session.execute(insert(JudgeOrganization), [
            {"id": i, "name": f"Lớp {i:03d}", "slug": f"class{i}",
             "creation_date": datetime(2020, 1, 1) + timedelta(days=i),
             "is_hidden": int(i == 130), "is_open": 0}
            for i in range(1, 131)
        ])
        self.session.execute(insert(JudgeProfileOrganizations), [
            {"profile_id": 3, "organization_id": 1},
            {"profile_id": 4, "organization_id": 1},
            {"profile_id": 3, "organization_id": 2},
        ])
        self.session.execute(insert(JudgeOrganizationAdmins), [
            {"profile_id": 3, "organization_id": 1},
            {"profile_id": 3, "organization_id": 1},
            {"profile_id": 3, "organization_id": 130},
        ])
        self.config_session.execute(insert(VirtualClassSession), [
            {"org_id": 10, "start_time": datetime(2026, 1, 2), "end_time": None},
            {"org_id": 11, "start_time": datetime(2026, 1, 1), "end_time": datetime(2026, 1, 5)},
            {"org_id": 11, "start_time": datetime(2025, 1, 1), "end_time": datetime(2025, 1, 2)},
            {"org_id": 12, "start_time": datetime(2026, 1, 3), "end_time": datetime(2026, 1, 4)},
        ])
        self.session.commit()
        self.config_session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.config_session.close()
        self.config_engine.dispose()

    async def fetch(self, **kwargs):
        params = dict(teacher_id=2, page=1, page_size=24, q="",
                      sort_by="creation_date", sort_order="desc", config_db=self.config_db)
        params.update(kwargs)
        return await get_class_page(self.db, **params)

    async def test_all_classes_are_accessible_across_pages(self):
        ids = []
        for page in range(1, 7):
            result = await self.fetch(page=page)
            self.assertEqual(result.total, 130)
            self.assertEqual(result.total_pages, 6)
            ids.extend(item.id for item in result.items)
        self.assertEqual(ids, list(range(130, 0, -1)))
        self.assertEqual(len(set(ids)), 130)

    async def test_creation_name_and_id_both_directions(self):
        for field in ("creation_date", "name", "id"):
            for direction in ("asc", "desc"):
                with self.subTest(field=field, direction=direction):
                    result = await self.fetch(sort_by=field, sort_order=direction)
                    expected = list(range(1, 25)) if direction == "asc" else list(range(130, 106, -1))
                    self.assertEqual([item.id for item in result.items], expected)

    async def test_member_counts_and_empty_classes(self):
        descending = await self.fetch(sort_by="member_count", sort_order="desc")
        self.assertEqual([(item.id, item.member_count) for item in descending.items[:3]],
                         [(1, 2), (2, 1), (3, 0)])
        ascending = await self.fetch(sort_by="member_count", sort_order="asc")
        self.assertEqual([item.id for item in ascending.items[:3]], [3, 4, 5])
        self.assertTrue(all(item.member_count == 0 for item in ascending.items))

    async def test_school_year_and_managers_do_not_duplicate_members(self):
        self.session.add(JudgeSchoolYear(id=1, start=date(2026, 6, 8), finish=date(2027, 6, 1)))
        self.session.get(JudgeOrganization, 1).year_id = 1
        self.session.get(JudgeOrganization, 2).year_id = 999
        self.session.get(JudgeProfile, 3).name = "Nguyễn Văn A"
        self.session.add(JudgeOrganizationAdmins(profile_id=4, organization_id=1))
        self.config_session.execute(insert(VirtualClassSession), [
            {"org_id": 1, "start_time": datetime(2026, 1, 1), "end_time": None},
            {"org_id": 1, "start_time": datetime(2026, 1, 2), "end_time": None},
        ])
        self.session.commit()
        self.config_session.commit()
        first = (await self.fetch(q="Lớp 001")).items[0]
        self.assertEqual((first.member_count, first.school_year), (2, "2026-2027"))
        self.assertEqual([(manager.id, manager.name) for manager in first.managers],
                         [(3, "Nguyễn Văn A"), (4, "user4")])
        self.assertEqual(first.last_session_at, datetime(2026, 1, 2))
        missing = (await self.fetch(q="Lớp 002")).items[0]
        self.assertIsNone(missing.school_year)
        self.assertEqual(missing.managers, [])
        result = await self.fetch(page_size=100)
        self.assertEqual(result.total, 130)
        self.assertEqual(len({item.id for item in result.items}), 100)

    async def test_latest_session_aggregates_and_nulls_last_both_directions(self):
        for direction, expected in (("asc", [10, 12, 11]), ("desc", [11, 12, 10])):
            result = await self.fetch(sort_by="last_session_at", sort_order=direction)
            self.assertEqual([item.id for item in result.items[:3]], expected)
            self.assertTrue(all(item.last_session_at is None for item in result.items[3:]))
            self.assertEqual(result.total, 130)
            ended = next(item for item in result.items if item.id == 11)
            self.assertEqual(ended.last_session_at, datetime(2026, 1, 5))

    async def test_permission_scope_counts_and_no_duplicate_rows(self):
        result = await self.fetch(teacher_id=3)
        self.assertEqual(result.total, 2)
        self.assertEqual([item.id for item in result.items], [130, 1])
        unknown = await self.fetch(teacher_id=999)
        self.assertEqual(unknown.total, 0)
        self.assertEqual(unknown.items, [])

    async def test_search_before_paging_and_counts_match_permissions(self):
        result = await self.fetch(q="  130  ")
        self.assertEqual(result.total, 1)
        self.assertEqual([item.id for item in result.items], [130])
        result = await self.fetch(teacher_id=3, q="Lớp 002")
        self.assertEqual(result.total, 0)

    async def test_search_wildcards_are_literal(self):
        for q in ("%", "_", "' OR 1=1 --"):
            with self.subTest(q=q):
                result = await self.fetch(q=q)
                self.assertEqual(result.total, 0)
        organization = self.session.get(JudgeOrganization, 130)
        organization.name = "100%_literal"
        self.session.commit()
        result = await self.fetch(q="%_")
        self.assertEqual([item.id for item in result.items], [130])

    async def test_page_bounds_and_empty_result(self):
        result = await self.fetch(page=999)
        self.assertEqual(result.page, 6)
        self.assertEqual(len(result.items), 10)
        result = await self.fetch(page=999, q="does-not-exist")
        self.assertEqual((result.page, result.total, result.total_pages), (1, 0, 0))

    async def test_ties_have_stable_order_and_missing_creation_date_is_last(self):
        for i in (1, 2):
            self.session.get(JudgeOrganization, i).creation_date = datetime(2030, 1, 1)
        self.session.get(JudgeOrganization, 130).creation_date = None
        self.session.commit()
        result = await self.fetch()
        self.assertEqual([item.id for item in result.items[:2]], [1, 2])
        for direction in ("asc", "desc"):
            result = await self.fetch(page=2, page_size=100, sort_order=direction)
            self.assertEqual(result.items[-1].id, 130)

    async def test_api_contract_and_invalid_parameters(self):
        app = FastAPI()
        app.include_router(router, prefix="/teacher")

        async def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        async def override_config_db():
            yield self.config_db
        app.dependency_overrides[get_config_db] = override_config_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/teacher/my-classes")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual((body["total"], body["page_size"]), (130, 24))
            self.assertEqual(body["items"][0]["id"], 130)
            for field in ("creation_date", "name", "member_count", "id", "last_session_at"):
                for order in ("asc", "desc"):
                    response = await client.get("/teacher/my-classes", params={"sort_by": field, "sort_order": order})
                    self.assertEqual(response.status_code, 200)
            for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101},
                           {"sort_by": "unknown"}, {"sort_order": "unknown"}, {"q": "x" * 129},
                           {"starred_only": "invalid"}):
                with self.subTest(params=params):
                    response = await client.get("/teacher/my-classes", params=params)
                    self.assertEqual(response.status_code, 422)

            response = await client.put("/teacher/classes/1/star")
            self.assertEqual(response.status_code, 200)
            timestamp = response.json()["starred_at"]
            response = await client.put("/teacher/classes/1/star")
            self.assertEqual(response.json()["starred_at"], timestamp)
            response = await client.get("/teacher/my-classes", params={"starred_only": True})
            self.assertEqual(response.json()["total"], 1)
            self.assertEqual(response.json()["items"][0]["id"], 1)
            for _ in range(2):
                response = await client.delete("/teacher/classes/1/star")
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.json()["starred_at"])

    async def test_virtual_class_lifecycle_uses_dashboard_and_live_reads_source(self):
        from app.models.dmoj import JudgeProblem, JudgeSubmission
        create_source_tables(self.engine, JudgeProblem, JudgeSubmission)
        app = FastAPI()
        app.include_router(virtual_router, prefix="/virtual-class")
        async def source():
            yield self.db
        async def dashboard():
            yield self.config_db
        app.dependency_overrides[get_db] = source
        app.dependency_overrides[get_config_db] = dashboard
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            self.assertEqual((await client.post("/virtual-class/999/start")).status_code, 404)
            response = await client.post("/virtual-class/130/start", params={"name": "Test session"})
            self.assertEqual(response.status_code, 200)
            session_id = response.json()["id"]
            self.assertEqual((await client.post("/virtual-class/130/start")).status_code, 400)
            listing = (await client.get("/virtual-class/130/sessions")).json()
            self.assertEqual(listing["active_session"]["id"], session_id)
            live = await client.get(f"/virtual-class/sessions/{session_id}/live-submissions")
            self.assertEqual(live.status_code, 200)
            self.assertEqual(live.json()["submissions"], [])
            for _ in range(2):
                response = await client.post(f"/virtual-class/sessions/{session_id}/stop")
                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.json()["end_time"])
        self.assertNotIn(VirtualClassSession.__tablename__, JudgeOrganization.metadata.tables)

    async def test_stars_pin_before_paging_in_timestamp_order_for_every_sort(self):
        first = datetime(2026, 1, 1)
        last = first + timedelta(microseconds=1)
        self.config_session.execute(insert(ClassStar), [
            {"owner_profile_id": 2, "organization_id": 1, "starred_at": first},
            {"owner_profile_id": 2, "organization_id": 2, "starred_at": last},
            {"owner_profile_id": 3, "organization_id": 130, "starred_at": last},
        ])
        self.config_session.commit()
        for field in ("creation_date", "name", "member_count", "id", "last_session_at"):
            for order in ("asc", "desc"):
                result = await self.fetch(sort_by=field, sort_order=order, page_size=1)
                self.assertEqual(result.items[0].id, 2)
                self.assertEqual(result.items[0].starred_at, last)
                result = await self.fetch(sort_by=field, sort_order=order, page_size=1, page=2)
                self.assertEqual(result.items[0].id, 1)
        ids = []
        for page in range(1, 7):
            ids.extend(item.id for item in (await self.fetch(page=page)).items)
        self.assertEqual(len(set(ids)), 130)
        self.assertEqual(ids[:2], [2, 1])
        self.assertEqual([item.id for item in (await self.fetch(teacher_id=3)).items], [130, 1])

    async def test_star_filter_respects_owner_search_and_visibility(self):
        for owner, org in ((2, 1), (2, 130), (3, 1), (3, 2)):
            self.config_session.add(ClassStar(owner_profile_id=owner, organization_id=org))
        self.config_session.commit()
        result = await self.fetch(starred_only=True, q="130")
        self.assertEqual((result.total, result.items[0].id), (1, 130))
        result = await self.fetch(starred_only=True, teacher_id=3)
        self.assertEqual((result.total, result.items[0].id), (1, 1))
        result = await self.fetch(starred_only=True, teacher_id=4)
        self.assertEqual((result.total, result.total_pages, result.items), (0, 0, []))

    async def test_star_mutations_are_idempotent_isolated_and_check_permissions(self):
        async def change(owner, org, starred):
            return await set_class_star(self.db, self.config_db, owner, org, starred)
        first = await change(2, 1, True)
        self.assertIsNotNone(first.starred_at)
        self.assertEqual((await change(2, 1, True)).starred_at, first.starred_at)
        await change(3, 1, True)
        self.assertIsNone((await change(2, 1, False)).starred_at)
        self.assertIsNone((await change(2, 1, False)).starred_at)
        self.assertIsNotNone(self.config_session.get(ClassStar, (3, 1)).starred_at)
        self.assertGreater((await change(2, 1, True)).starred_at, first.starred_at)
        for owner, org, status in ((3, 2, 404), (4, 1, 404), (999, 1, 403), (2, 999, 404)):
            for starred in (True, False):
                with self.assertRaises(HTTPException) as error:
                    await change(owner, org, starred)
                self.assertEqual(error.exception.status_code, status)
        self.assertEqual(self.session.query(JudgeOrganization).count(), 130)
        self.assertNotIn("class_star", JudgeOrganization.metadata.tables)

    def test_config_database_name_is_safe_and_separate(self):
        values = dict(PROJECT_NAME="test", SOURCE_DB_HOST="localhost", SOURCE_DB_USER="test",
                      SOURCE_DB_PASSWORD="test", SOURCE_DB_NAME="dmoj", DASHBOARD_DB_HOST="dashboard",
                      DASHBOARD_DB_USER="app", DASHBOARD_DB_PASSWORD="test", _env_file=None)
        self.assertEqual(Settings(**values).CONFIG_MYSQL_DB, "tmath_dashboard")
        for name in ("dmoj", "DMOJ", "bad`name", "bad-name", "a" * 65):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Settings(**values, CONFIG_MYSQL_DB=name)
        self.assertEqual(Settings(**values, CONFIG_MYSQL_DB="service_config").CONFIG_MYSQL_DB,
                         "service_config")


if __name__ == "__main__":
    unittest.main()

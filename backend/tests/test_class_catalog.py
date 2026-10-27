import unittest
from datetime import date, datetime, timedelta
from hashlib import md5

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.api.v1.endpoints.teacher import router
from app.api.v1.endpoints.virtual_class import router as virtual_router
from app.core.config import Settings
from app.core.config_database import get_config_db
from app.services.source_gateway import (
    SourceAccess, SourceClass, SourceManager, SourcePage, SourceSchoolYear,
    SourceStudent, SourceSubmission, SourceSubmissionPage, SourceSubmissionChange,
    SourceSubmissionChangesPage, get_source_gateway,
)
from app.core.auth import get_current_user
from app.models.dmoj import (
    AuthUser, JudgeOrganization, JudgeOrganizationAdmins,
    JudgeProfile, JudgeProfileOrganizations, JudgeSchoolYear, JudgeSubmission,
)
from app.models.virtual_class import VirtualClassSession
from app.services.student_catalog_service import get_student_page
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


class FakeSourceGateway:
    """A source API double whose page order is the provider's complete-set order."""

    def __init__(self, source_db):
        self.db = source_db
        self.active_contest_ids = set()
        self.observed_actors = []

    def _visible_class_ids(self, actor_profile_id):
        profile = self.db.get(JudgeProfile, actor_profile_id)
        if profile is None:
            return []
        if profile.super_admin:
            return [row.id for row in self.db.query(JudgeOrganization.id).order_by(JudgeOrganization.id)]
        return sorted({row.organization_id for row in self.db.query(JudgeOrganizationAdmins.organization_id)
                       .filter_by(profile_id=actor_profile_id)})

    def _class(self, class_id):
        row = self.db.get(JudgeOrganization, class_id)
        if row is None:
            return None
        year = self.db.get(JudgeSchoolYear, row.year_id) if row.year_id else None
        managers = []
        for manager_id, in self.db.query(JudgeOrganizationAdmins.profile_id).filter_by(organization_id=class_id).distinct().order_by(JudgeOrganizationAdmins.profile_id):
            profile = self.db.get(JudgeProfile, manager_id)
            user = self.db.get(AuthUser, profile.user_id) if profile and profile.user_id else None
            managers.append(SourceManager(
                profile_id=manager_id,
                name=(profile.name or "").strip() or (user.username if user else None) or f"Profile {manager_id}",
            ))
        member_count = self.db.query(JudgeProfileOrganizations).filter_by(organization_id=class_id).count()
        return SourceClass(
            class_id=row.id, name=row.name, school_year=(SourceSchoolYear(start=year.start, finish=year.finish) if year and year.start and year.finish else None),
            created_at=row.creation_date, member_count=member_count, managers=managers,
            has_active_contest=row.id in self.active_contest_ids,
            active_contest_ids=([900 + row.id] if row.id in self.active_contest_ids else []),
        )

    async def get_access(self, profile_id, *, actor_profile_id):
        profile = self.db.get(JudgeProfile, profile_id)
        return SourceAccess(profile_id=profile_id, exists=profile is not None, is_active=profile is not None,
                            is_super_admin=bool(profile and profile.super_admin), roles=[])

    async def list_classes(self, profile_id, *, actor_profile_id, q=None, cursor=None, limit=24,
                           sort="created_at", order="desc", virtual_active_class_ids=None,
                           starred_class_ids=None):
        self.observed_actors.append(actor_profile_id)
        classes = [self._class(class_id) for class_id in self._visible_class_ids(profile_id)]
        classes = [item for item in classes if item is not None]
        if q:
            term = q.casefold()
            classes = [item for item in classes if term in (item.name or "").casefold() or term in str(item.class_id)]
        virtual_rank = {value: index for index, value in enumerate(virtual_active_class_ids or [])}
        starred_rank = {value: index for index, value in enumerate(starred_class_ids or [])}
        values = {
            "created_at": lambda item: item.created_at,
            "name": lambda item: (item.name or "").casefold(),
            "member_count": lambda item: item.member_count,
            "id": lambda item: item.class_id,
        }
        contests = [item for item in classes if item.has_active_contest]
        contests.sort(key=lambda item: item.class_id)
        active = sorted((item for item in classes if not item.has_active_contest and item.class_id in virtual_rank),
                        key=lambda item: virtual_rank[item.class_id])
        starred = sorted((item for item in classes if not item.has_active_contest and item.class_id not in virtual_rank and item.class_id in starred_rank),
                         key=lambda item: starred_rank[item.class_id])
        rest = [item for item in classes if not item.has_active_contest and item.class_id not in virtual_rank and item.class_id not in starred_rank]
        if sort == "created_at":
            present = [item for item in rest if values[sort](item) is not None]
            absent = [item for item in rest if values[sort](item) is None]
            present.sort(key=lambda item: item.class_id)
            present.sort(key=lambda item: values[sort](item), reverse=order == "desc")
            absent.sort(key=lambda item: item.class_id)
            rest = present + absent
        else:
            rest.sort(key=lambda item: item.class_id)
            rest.sort(key=lambda item: values[sort](item), reverse=order == "desc")
        classes = contests + active + starred + rest
        total = len(classes)
        offset = int(cursor or 0)
        items = classes[offset:offset + limit]
        next_offset = offset + len(items)
        return SourcePage[SourceClass](items=items, next_cursor=str(next_offset) if next_offset < total else None,
                                       has_more=next_offset < total, total=total, as_of=datetime.now().astimezone())

    async def get_class(self, class_id, *, actor_profile_id):
        self.observed_actors.append(actor_profile_id)
        if self.db.get(JudgeProfile, actor_profile_id) is None:
            raise HTTPException(403, "No source profile")
        if class_id not in self._visible_class_ids(actor_profile_id):
            raise HTTPException(404, "Class not found")
        return self._class(class_id)

    def _student(self, profile_id):
        profile = self.db.get(JudgeProfile, profile_id)
        user = self.db.get(AuthUser, profile.user_id) if profile and profile.user_id else None
        return SourceStudent(profile_id=profile.id, name=profile.name, username=user.username if user else None,
                             points=profile.points or 0, problem_count=profile.problem_count or 0,
                             display_rank=profile.display_rank or "user",
                             avatar_url=(f"https://www.gravatar.com/avatar/{md5(user.email.strip().lower().encode()).hexdigest()}?d=identicon&s=200"
                                         if user and user.email and user.email.strip() else None))

    async def list_students(self, profile_id, *, actor_profile_id, q=None, cursor=None, limit=24):
        allowed = set(self._visible_class_ids(profile_id))
        student_ids = {row.profile_id for row in self.db.query(JudgeProfileOrganizations.profile_id)
                       .filter(JudgeProfileOrganizations.organization_id.in_(allowed or [-1]))}
        students = [self._student(student_id) for student_id in student_ids]
        if q:
            term = q.casefold()
            students = [item for item in students if term in (item.name or "").casefold() or
                        term in (item.username or "").casefold() or term in str(item.profile_id)]
        students.sort(key=lambda item: ((item.name or f"Học sinh #{item.profile_id}").casefold(), item.profile_id))
        total = len(students)
        offset = int(cursor or 0)
        items = students[offset:offset + limit]
        next_offset = offset + len(items)
        return SourcePage[SourceStudent](items=items, next_cursor=str(next_offset) if next_offset < total else None,
                                         has_more=next_offset < total, total=total, as_of=datetime.now().astimezone())

    async def list_class_students(self, class_id, *, actor_profile_id, cursor=None, limit=100):
        await self.get_class(class_id, actor_profile_id=actor_profile_id)
        ids = [row.profile_id for row in self.db.query(JudgeProfileOrganizations.profile_id)
               .filter_by(organization_id=class_id).order_by(JudgeProfileOrganizations.profile_id)]
        items = [self._student(student_id) for student_id in ids]
        offset = int(cursor or 0)
        selected = items[offset:offset + limit]
        next_offset = offset + len(selected)
        has_more = next_offset < len(items)
        return SourcePage[SourceStudent](items=selected, next_cursor=str(next_offset) if has_more else None,
                                         has_more=has_more, total=len(items), as_of=datetime.now().astimezone())

    async def get_student(self, profile_id, *, actor_profile_id):
        profile = self.db.get(JudgeProfile, profile_id)
        if profile is None:
            raise HTTPException(404, "Student not found")
        visible_students = await self.list_students(actor_profile_id, actor_profile_id=actor_profile_id, limit=100)
        if profile_id not in {item.profile_id for item in visible_students.items}:
            raise HTTPException(404, "Student not found")
        return self._student(profile_id)


class TeacherOrganizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        tables = [AuthUser, JudgeProfile, JudgeSchoolYear, JudgeOrganization, JudgeOrganizationAdmins,
                  JudgeProfileOrganizations]
        for model in tables:
            model.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.db = AsyncTestSession(self.session)
        self.config_engine = create_engine("sqlite://")
        VirtualClassSession.__table__.create(self.config_engine)
        self.config_session = Session(self.config_engine)
        self.config_db = AsyncTestSession(self.config_session)
        self.gateway = FakeSourceGateway(self.session)
        self.actor = SourceAccess(profile_id=2, exists=True, is_active=True, is_super_admin=True)
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

    def override_source_dependencies(self, app):
        async def source_gateway():
            return self.gateway
        async def current_user():
            return self.actor
        app.dependency_overrides[get_source_gateway] = source_gateway
        app.dependency_overrides[get_current_user] = current_user

    async def test_student_list_is_distinct_and_respects_managed_classes(self):
        all_students = await get_student_page(self.gateway, 2, 1, 24, "")
        self.assertEqual([item.user_id for item in all_students.items], [3, 4])
        managed_students = await get_student_page(self.gateway, 3, 1, 24, "")
        self.assertEqual([item.user_id for item in managed_students.items], [3, 4])
        self.assertEqual((await get_student_page(self.gateway, 4, 1, 24, "")).total, 0)
        searched = await get_student_page(self.gateway, 2, 1, 24, "user4")
        self.assertEqual([item.user_id for item in searched.items], [4])

    async def test_student_sort_directions_with_legacy_gateway(self):
        self.session.get(JudgeProfile, 3).points = 20
        self.session.get(JudgeProfile, 4).points = 5
        self.session.commit()
        expected = {
            "name": [3, 4],
            "name_desc": [4, 3],
            "points_desc": [3, 4],
            "points_asc": [4, 3],
        }
        for sort, ids in expected.items():
            with self.subTest(sort=sort):
                result = await get_student_page(self.gateway, 2, 1, 24, "", sort=sort)
                self.assertEqual([item.user_id for item in result.items], ids)
                self.assertEqual({item.user_id: item.rank for item in result.items}, {3: 1, 4: 2})

    async def test_student_without_name_uses_profile_id(self):
        self.session.get(JudgeProfile, 4).name = None
        self.session.commit()
        page = await get_student_page(self.gateway, 2, 1, 24, "")
        self.assertEqual(next(item for item in page.items if item.user_id == 4).name, "4")

    async def test_api_contract_and_invalid_parameters(self):
        app = FastAPI()
        app.include_router(router, prefix="/teacher")
        self.override_source_dependencies(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            students = await client.get("/teacher/my-students")
            self.assertEqual(students.status_code, 200)
            self.assertEqual([item["user_id"] for item in students.json()["items"]], [3, 4])

    async def test_class_students_use_source_url_without_exposing_email(self):
        create_source_tables(self.engine, JudgeSubmission)
        self.session.get(AuthUser, 3).email = " student@example.com "
        self.session.commit()
        app = FastAPI()
        app.include_router(router, prefix="/teacher")

        self.override_source_dependencies(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/teacher/classes/1/students")

        self.assertEqual(response.status_code, 200)
        students = {student["user_id"]: student for student in response.json()}
        expected_hash = md5(b"student@example.com").hexdigest()
        self.assertEqual(students[3]["avatar_url"], f"https://www.gravatar.com/avatar/{expected_hash}?d=identicon&s=200")
        self.assertNotIn("email", students[3])
        self.assertIsNone(students[4]["avatar_url"])

    async def test_class_students_follow_all_source_cursors(self):
        self.session.execute(insert(AuthUser), [
            {"id": i, "username": f"bulk{i}"} for i in range(1000, 1201)
        ])
        self.session.execute(insert(JudgeProfile), [
            {"id": i, "user_id": i, "super_admin": 0} for i in range(1000, 1201)
        ])
        self.session.execute(insert(JudgeProfileOrganizations), [
            {"profile_id": i, "organization_id": 1} for i in range(1000, 1201)
        ])
        self.session.commit()
        app = FastAPI()
        app.include_router(router, prefix="/teacher")
        self.override_source_dependencies(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/teacher/classes/1/students")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 203)

    async def test_class_students_reject_repeated_upstream_cursor(self):
        async def repeated_cursor(class_id, *, actor_profile_id, cursor=None, limit=100):
            return SourcePage[SourceStudent](
                items=[SourceStudent(profile_id=3, name="Alice", username="alice")],
                next_cursor="same-cursor", has_more=True, total=2,
                as_of=datetime.now().astimezone(),
            )

        self.gateway.list_class_students = repeated_cursor
        app = FastAPI()
        app.include_router(router, prefix="/teacher")
        self.override_source_dependencies(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/teacher/classes/1/students")
        self.assertEqual(response.status_code, 502)

    async def test_virtual_class_lifecycle_uses_dashboard_and_live_reads_source(self):
        app = FastAPI()
        app.include_router(virtual_router, prefix="/virtual-class")
        async def dashboard():
            yield self.config_db
        app.dependency_overrides[get_config_db] = dashboard
        self.override_source_dependencies(app)
        submission = SourceSubmission(
            submission_id=41, profile_id=3, student_name="Alice", problem_id=7,
            problem_title="Sum", result="AC", points=100,
            submitted_at=datetime(2026, 10, 12, 0, 0),
        )
        page_calls = []
        async def class_submissions(class_id, *, actor_profile_id, date_from=None, date_to=None,
                                   after_submission_id=None, cursor=None, limit=100):
            page_calls.append((class_id, actor_profile_id, cursor))
            if cursor is None:
                first_page = [submission.model_copy(update={"submission_id": 1000 + i}) for i in range(100)]
                return SourceSubmissionPage(items=first_page, next_cursor="page-2", has_more=True,
                    total=101, high_watermark="opaque-hwm", max_submission_id=1099,
                    as_of=datetime(2026, 10, 12))
            return SourceSubmissionPage(items=[submission], next_cursor=None, has_more=False,
                total=101, high_watermark="opaque-hwm", max_submission_id=1099,
                as_of=datetime(2026, 10, 12))
        changes_calls = []
        async def changes(class_id, *, actor_profile_id, cursor=None, date_from=None, date_to=None, limit=100):
            changes_calls.append((class_id, actor_profile_id, cursor))
            return SourceSubmissionChangesPage(events=[
                SourceSubmissionChange(event_id=1, kind="updated", submission_id=41,
                    version=2, changed_at=datetime(2026, 10, 12, 0, 1), record=submission.model_copy(update={"result": "WA"})),
                SourceSubmissionChange(event_id=2, kind="deleted", submission_id=40,
                    version=3, changed_at=datetime(2026, 10, 12, 0, 2), record=None),
                SourceSubmissionChange(event_id=3, kind="created", submission_id=42,
                    version=1, changed_at=datetime(2026, 10, 12, 0, 3),
                    record=submission.model_copy(update={"submission_id": 42, "result": "TLE"})),
            ], next_cursor="opaque-next", has_more=False, high_watermark=2,
                as_of=datetime(2026, 10, 12, 0, 2))
        self.gateway.list_class_submissions = class_submissions
        self.gateway.list_class_submission_changes = changes
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
            self.assertEqual(len(live.json()["events"]), 101)
            self.assertEqual(live.json()["events"][-1]["record"]["id"], 41)
            self.assertTrue(live.json()["snapshot"])
            self.assertEqual(live.json()["cursor"], "opaque-hwm")
            self.assertTrue(live.json()['is_active'])
            changes_response = await client.get(
                f"/virtual-class/sessions/{session_id}/live-submissions", params={"cursor": "opaque-hwm"})
            self.assertEqual(changes_response.status_code, 200)
            self.assertEqual([event["kind"] for event in changes_response.json()["events"]], ["updated", "deleted", "created"])
            self.assertEqual(changes_response.json()["events"][0]["record"]["result"], "WA")
            self.assertIsNone(changes_response.json()["events"][1]["record"])
            self.assertEqual(changes_response.json()["events"][2]["record"]["id"], 42)
            self.assertEqual(changes_response.json()["cursor"], "opaque-next")
            self.assertEqual(page_calls, [(130, 2, None), (130, 2, "page-2")])
            self.assertEqual(changes_calls, [(130, 2, "opaque-hwm")])
            self.actor = SourceAccess(profile_id=4, exists=True, is_active=True, is_super_admin=False)
            denied_poll = await client.get(
                f"/virtual-class/sessions/{session_id}/live-submissions", params={"cursor": "opaque-next"})
            self.assertEqual(denied_poll.status_code, 404)
            self.assertEqual((await client.post(f"/virtual-class/sessions/{session_id}/stop")).status_code, 404)
            self.assertIsNone(self.config_session.get(VirtualClassSession, session_id).end_time)
            self.actor = SourceAccess(profile_id=2, exists=True, is_active=True, is_super_admin=True)
            for _ in range(2):
                response = await client.post(f"/virtual-class/sessions/{session_id}/stop")
                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.json()["end_time"])
            live = await client.get(f"/virtual-class/sessions/{session_id}/live-submissions")
            self.assertFalse(live.json()['is_active'])
        self.assertNotIn(VirtualClassSession.__tablename__, JudgeOrganization.metadata.tables)

    async def test_direct_class_and_session_urls_enforce_class_visibility(self):
        app = FastAPI()
        app.include_router(router, prefix="/teacher")
        app.include_router(virtual_router, prefix="/virtual-class")

        async def dashboard():
            yield self.config_db
        app.dependency_overrides[get_config_db] = dashboard
        self.override_source_dependencies(app)
        session = self.config_session.query(VirtualClassSession).filter_by(org_id=11).first()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get('/teacher/classes/1', params={'teacher_id': 3})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'id': 1, 'name': 'Lớp 001'})
            self.assertEqual((await client.get('/teacher/classes/2', params={'teacher_id': 3})).status_code, 200)
            self.assertEqual((await client.get('/teacher/classes/999')).status_code, 404)
            response = await client.get('/teacher/students/3')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['id'], 3)
            self.assertTrue(response.json()['name'])
            self.assertEqual((await client.get('/teacher/students/999')).status_code, 404)
            response = await client.get('/teacher/students/search', params={'q': 'khong-khop-ten'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])
            response = await client.get(f'/virtual-class/sessions/{session.id}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['class_name'], 'Lớp 011')
            self.assertEqual(response.json()['org_id'], 11)
            self.assertIsNotNone(response.json()['end_time'])
            self.assertEqual((await client.get('/virtual-class/sessions/999')).status_code, 404)
            self.actor = SourceAccess(profile_id=3, exists=True, is_active=True, is_super_admin=False)
            self.assertEqual((await client.get('/teacher/classes/1')).status_code, 200)
            self.assertEqual(self.gateway.observed_actors[-1], 3)
            self.assertEqual((await client.get('/teacher/classes/2')).status_code, 404)
            self.assertEqual((await client.get(f'/virtual-class/sessions/{session.id}')).status_code, 404)

    def test_config_database_name_is_safe_and_separate(self):
        values = dict(PROJECT_NAME="test", DASHBOARD_DB_HOST="dashboard",
                      DASHBOARD_DB_USER="app", DASHBOARD_DB_PASSWORD="test", _env_file=None)
        self.assertEqual(Settings(**values).CONFIG_MYSQL_DB, "tmath_dashboard")
        for name in ("bad`name", "bad-name", "a" * 65):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Settings(**values, CONFIG_MYSQL_DB=name)
        self.assertEqual(Settings(**values, CONFIG_MYSQL_DB="service_config").CONFIG_MYSQL_DB,
                         "service_config")


if __name__ == "__main__":
    unittest.main()

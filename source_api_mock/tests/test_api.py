import os
import time
import unittest
from datetime import date, datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from source_api_mock.main import app, get_db
from source_api_mock.models import (
    contest, contest_author, contest_curator, contest_organization, metadata,
    language, organization, organization_admin, problem, profile, profile_organization,
    problem_group, problem_type, problem_type_catalog, school_year, submission,
    submission_source, submission_testcase, user,
)
from source_api_mock.main import _change_last_id, _change_logs, _change_snapshots, _change_versions
from source_api_mock import main as source_main


class SourceAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        _change_snapshots.clear()
        _change_logs.clear()
        _change_last_id.clear()
        _change_versions.clear()
        source_main._change_markers.clear()
        source_main._change_last_reconciled.clear()
        with self.engine.begin() as conn:
            for table in reversed(metadata.sorted_tables):
                conn.execute(table.delete())
            conn.execute(insert(user), [
                {"id": 20, "username": "teacher", "is_active": 1},
                {"id": 21, "username": "alice", "is_active": 1},
                {"id": 22, "username": "bob", "is_active": 0},
            ])
            conn.execute(insert(profile), [
                {"id": 2, "user_id": 20, "name": "Teacher", "points": 0, "problem_count": 0, "display_rank": "teacher", "super_admin": 0},
                {"id": 3, "user_id": 21, "name": "Alice", "points": 12.5, "problem_count": 4, "display_rank": "user", "super_admin": 0},
                {"id": 4, "user_id": 22, "name": "Bob", "points": 3, "problem_count": 1, "display_rank": "user", "super_admin": 0},
                {"id": 9, "user_id": None, "name": "Admin", "points": 0, "problem_count": 0, "display_rank": "admin", "super_admin": 1},
                {"id": 5, "user_id": None, "name": "No class", "points": 0, "problem_count": 0, "display_rank": "user", "super_admin": 0},
                {"id": 6, "user_id": 999, "name": "Missing user", "points": 0, "problem_count": 0, "display_rank": "user", "super_admin": 0},
            ])
            conn.execute(insert(school_year), [{"id": 1, "start": date(2025, 1, 1), "finish": date(2025, 12, 31)}])
            conn.execute(insert(organization), [
                {"id": 11, "name": "Beta", "creation_date": datetime(2025, 2, 1, 10), "year_id": 1, "is_hidden": 0},
                {"id": 12, "name": "Alpha", "creation_date": datetime(2025, 1, 1, 10), "year_id": 1, "is_hidden": 0},
                {"id": 13, "name": "Hidden", "creation_date": None, "year_id": None, "is_hidden": 1},
                {"id": 14, "name": "No date", "creation_date": None, "year_id": None, "is_hidden": 0},
            ])
            conn.execute(insert(organization_admin), [
                {"id": 1, "profile_id": 2, "organization_id": 11},
                {"id": 2, "profile_id": 2, "organization_id": 12},
                {"id": 3, "profile_id": 2, "organization_id": 14},
            ])
            conn.execute(insert(profile_organization), [
                {"id": 1, "profile_id": 3, "organization_id": 11},
                {"id": 2, "profile_id": 3, "organization_id": 12},
                {"id": 3, "profile_id": 4, "organization_id": 12},
            ])
            conn.execute(insert(problem), [
                {"id": 201, "code": "P201", "name": "Problem 201", "description": "Statement", "time_limit": 1.5, "memory_limit": 256000, "points": 100.0, "is_public": 1, "is_organization_private": 0, "classes_id": None, "group_id": 4, "version_update": 12},
                {"id": 202, "code": "P202", "name": "Problem 202", "description": None, "time_limit": 2.0, "memory_limit": 512000, "points": 50.0, "is_public": 1, "is_organization_private": 0, "classes_id": None, "group_id": 5, "version_update": None},
                {"id": 203, "code": "P203", "name": None, "description": None, "time_limit": 1.0, "memory_limit": 128000, "points": 25.0, "is_public": 1, "is_organization_private": 0, "classes_id": None, "group_id": None, "version_update": 7},
                {"id": 204, "code": "P204", "name": "Private problem", "description": "Private statement", "time_limit": 1.0, "memory_limit": 128000, "points": 25.0, "is_public": 0, "is_organization_private": 1, "classes_id": None, "group_id": None, "version_update": 8},
            ])
            conn.execute(insert(problem_type_catalog), [
                {"id": 14, "name": "algebra", "full_name": "Algebra", "priority": 1},
                {"id": 31, "name": "number", "full_name": "Number theory", "priority": 2},
            ])
            conn.execute(insert(problem_group), [
                {"id": 4, "name": "basics", "full_name": "Basics"},
                {"id": 5, "name": "advanced", "full_name": "Advanced"},
            ])
            conn.execute(insert(problem_type), [
                {"id": 1, "problem_id": 201, "problemtype_id": 14},
                {"id": 2, "problem_id": 201, "problemtype_id": 31},
                {"id": 3, "problem_id": 203, "problemtype_id": 31},
            ])
            conn.execute(insert(language), [
                {"id": 1, "key": "py3", "name": "Python 3", "common_name": "Python"},
            ])
            conn.execute(insert(submission), [
                {"id": 501, "date": datetime(2026, 6, 1, 10), "judged_date": datetime(2026, 6, 1, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 1024, "points": 0, "status": "IE", "result": "WA", "error": None, "user_id": 3, "problem_id": 201, "language_id": 1},
                {"id": 502, "date": datetime(2026, 6, 1, 10), "judged_date": datetime(2026, 6, 1, 10, 2), "rejudged_date": None, "version_update": "1", "time": 0.2, "memory": 2048, "points": 100, "status": "D", "result": "AC", "error": None, "user_id": 3, "problem_id": 202, "language_id": 1},
                {"id": 503, "date": datetime(2026, 6, 2, 10), "judged_date": datetime(2026, 6, 2, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.3, "memory": 3072, "points": 50, "status": "D", "result": "AC", "error": None, "user_id": 4, "problem_id": 201, "language_id": 1},
            ])
            conn.execute(insert(submission_source), [
                {"id": 701, "submission_id": 501, "source": "print('hello')"},
                {"id": 702, "submission_id": 502, "source": "print('accepted 202')"},
                {"id": 703, "submission_id": 503, "source": "print('accepted 201')"},
            ])
            conn.execute(insert(submission_testcase), [{"id": 801, "case": 1, "status": "WA", "time": 0.1, "memory": 1024, "points": 0, "total": 100, "batch": None, "feedback": "Wrong", "extended_feedback": "Expected 2", "output": "1", "submission_id": 501}])
            conn.execute(insert(contest), [
                {"id": 101, "key": "ACTIVE", "name": "Active contest", "start_time": datetime(2025, 1, 1), "end_time": datetime(2030, 1, 1), "is_visible": 1, "is_private": 0, "is_organization_private": 0, "is_public_contest": 1, "version_update": 1},
                {"id": 102, "key": "ENDED", "name": "Ended contest", "start_time": datetime(2024, 1, 1), "end_time": datetime(2024, 1, 2), "is_visible": 1, "is_private": 0, "is_organization_private": 0, "is_public_contest": 0, "version_update": 2},
                {"id": 103, "key": "MULTI", "name": "Multi class", "start_time": datetime(2027, 1, 1), "end_time": datetime(2027, 1, 2), "is_visible": 1, "is_private": 0, "is_organization_private": 0, "is_public_contest": 1, "version_update": 3},
                {"id": 104, "key": "HIDDEN", "name": "Hidden contest", "start_time": datetime(2025, 1, 1), "end_time": datetime(2030, 1, 1), "is_visible": 0, "is_private": 1, "is_organization_private": 0, "is_public_contest": 0, "version_update": 4},
                {"id": 105, "key": "AUTHOR", "name": "Author only", "start_time": datetime(2024, 1, 1), "end_time": datetime(2024, 1, 2), "is_visible": 0, "is_private": 1, "is_organization_private": 0, "is_public_contest": 0, "version_update": 5},
                {"id": 106, "key": "CURATOR", "name": "Curator contest", "start_time": datetime(2025, 1, 1), "end_time": datetime(2030, 1, 1), "is_visible": 0, "is_private": 1, "is_organization_private": 0, "is_public_contest": 0, "version_update": 6},
            ])
            conn.execute(insert(contest_organization), [
                {"contest_id": 101, "organization_id": 11},
                {"contest_id": 102, "organization_id": 12},
                {"contest_id": 103, "organization_id": 11},
                {"contest_id": 103, "organization_id": 12},
                {"contest_id": 104, "organization_id": 12},
            ])
            conn.execute(insert(contest_author), [{"contest_id": 105, "profile_id": 2}])
            conn.execute(insert(contest_curator), [{"contest_id": 106, "profile_id": 2}])
        os.environ["SOURCE_API_TOKEN"] = "test-service-token"
        os.environ["SOURCE_API_ALLOWED_ACTORS"] = "2,9"
        os.environ["SOURCE_API_SOURCE_ACTORS"] = "2"
        os.environ["SOURCE_API_TESTCASE_ACTORS"] = "2"

        def override_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def headers(self, actor="2", token="test-service-token"):
        return {"Authorization": f"Bearer {token}", "X-Actor-Profile-Id": actor, "X-Request-Id": "req-test"}

    def test_auth_requires_service_token_and_mapped_actor(self):
        path = "/integration/v1/profiles/2/access"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers={"Authorization": "Basic abc"}).status_code, 401)
        self.assertEqual(self.client.get(path, headers={"Authorization": "Bearer"}).status_code, 401)
        self.assertEqual(self.client.get(path, headers=self.headers(actor="999")).status_code, 403)
        self.assertEqual(self.client.get(path, headers=self.headers(actor="2", token="wrong")).status_code, 401)

    def test_scoring_snapshot_scope_deduplication_and_freeze(self):
        from source_api_mock.scoring import _root
        import shutil
        for directory in _root.iterdir():
            shutil.rmtree(directory)
        path = "/integration/v1/scoring/snapshots"
        self.assertEqual(self.client.post(path, headers=self.headers()).status_code, 403)
        with self.engine.begin() as connection:
            connection.execute(insert(submission), [{"id": 504, "date": datetime(2026, 6, 3),
                "user_id": 3, "problem_id": 202, "result": "WA", "status": "D"}])
        response = self.client.post(path, headers=self.headers(actor="9"))
        self.assertEqual(response.status_code, 200, response.text)
        manifest = response.json()
        self.assertEqual(manifest["sections"]["pairs"]["count"], 2)
        self.assertEqual(manifest["sections"]["profiles"]["count"], 6)
        page_path = f"{path}/{manifest['snapshot_id']}/pairs"
        page = self.client.get(page_path, headers=self.headers(actor="9")).json()
        self.assertEqual([(r["profile_id"], r["problem_id"], r["has_ac"]) for r in page["items"]],
                         [(3, 202, 1), (4, 201, 1)])
        with self.engine.begin() as connection:
            connection.execute(update(submission).where(submission.c.id == 502).values(result="WA"))
        self.assertEqual(self.client.get(page_path, headers=self.headers(actor="9")).json(), page)
        self.assertEqual(self.client.get(page_path, headers=self.headers()).status_code, 403)

    def test_local_wildcard_mapping_and_source_scopes_keep_resource_acl(self):
        os.environ["SOURCE_API_ALLOWED_ACTORS"] = "*"
        os.environ["SOURCE_API_SOURCE_ACTORS"] = "*"
        os.environ["SOURCE_API_TESTCASE_ACTORS"] = "*"
        self.assertEqual(
            self.client.get("/integration/v1/submissions/501?include=source,testcases", headers=self.headers(actor="2")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/integration/v1/submissions/501?include=source", headers=self.headers(actor="5")).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/integration/v1/profiles/2/access", headers=self.headers(actor="999", token="wrong-token")).status_code,
            401,
        )
    def test_validation_errors_use_contract_envelope_and_request_id(self):
        response = self.client.get(
            "/integration/v1/teachers/2/students?limit=101",
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {
            "code": "validation_error",
            "message": "Request validation failed",
            "request_id": "req-test",
        })

    def test_openapi_documents_error_envelopes_and_retry_after(self):
        document = self.client.get("/integration/v1/openapi.json").json()
        paths = document["paths"]
        scheme = document["components"]["securitySchemes"]["SourceServiceBearer"]
        self.assertEqual(scheme, {"type": "http", "scheme": "bearer"})
        expected = {
            ("/integration/v1/profiles/{profile_id}/access", "get"): {"401", "403", "422", "429", "500", "502", "503"},
            ("/integration/v1/teachers/{profile_id}/classes/query", "post"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/classes/{class_id}", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/teachers/{profile_id}/students", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/classes/{class_id}/students", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/students/{profile_id}", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/teachers/{profile_id}/contests", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/classes/{class_id}/contests", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/students/{profile_id}/submissions", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/classes/{class_id}/submissions", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/classes/{class_id}/submission-changes", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/submissions/{submission_id}", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/problems/{problem_id}", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/problems/{problem_id}/accepted-samples", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/students/{profile_id}/submission-samples", "get"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/tags", "get"): {"401", "403", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/problems", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/problem-groups", "get"): {"401", "403", "409", "422", "429", "500", "502", "503"},
            ("/integration/v1/analytics/catalog", "get"): {"401", "403", "422", "429", "500", "502", "503"},
            ("/integration/v1/analytics/students/aggregate", "post"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/analytics/students/alerts", "post"): {"401", "403", "404", "422", "429", "500", "502", "503"},
            ("/integration/v1/students/{profile_id}/problem-facts", "get"): {"401", "403", "404", "409", "422", "429", "500", "502", "503"},
        }
        for (path, method), statuses in expected.items():
            with self.subTest(path=path, method=method):
                operation = paths[path][method]
                self.assertEqual(operation["security"], [{"SourceServiceBearer": []}])
                self.assertNotIn("Authorization", {p["name"] for p in operation.get("parameters", [])})
                responses = operation["responses"]
                self.assertTrue(statuses.issubset(responses))
                for status in statuses:
                    schema = responses[status]["content"]["application/json"]["schema"]
                    self.assertEqual(schema["$ref"], "#/components/schemas/APIError")
                self.assertIn("Retry-After", responses["429"]["headers"])
        for path in ("/integration/v1/tags", "/integration/v1/analytics/catalog"):
            operation = paths[path]["get"]
            self.assertIn("ETag", operation["responses"]["200"]["headers"])
            self.assertIn("ETag", operation["responses"]["304"]["headers"])
        error_schema = document["components"]["schemas"]["APIError"]["properties"]
        self.assertEqual(set(error_schema), {"code", "message", "request_id"})

    def test_access_and_teacher_scope(self):
        response = self.client.get("/integration/v1/profiles/2/access", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["teacher"])
        self.assertFalse(response.json()["is_super_admin"])
        self.assertEqual(self.client.get("/integration/v1/profiles/3/access", headers=self.headers()).status_code, 403)

    def test_classes_filter_before_cursor_pagination_and_sort(self):
        path = "/integration/v1/teachers/2/classes/query"
        first = self.client.post(path, headers=self.headers(), json={"limit": 1, "sort": "name", "order": "asc"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["items"][0]["class_id"], 11)
        self.assertTrue(first.json()["has_more"])
        second = self.client.post(path, headers=self.headers(), json={"limit": 1, "cursor": first.json()["next_cursor"]})
        self.assertEqual(second.json()["items"][0]["class_id"], 12)
        self.assertEqual(second.json()["total"], 3)
        self.assertFalse(second.json()["items"][0]["has_active_contest"])

    def test_contest_priority_precedes_requested_sort_and_null_dates_stay_last(self):
        path = "/integration/v1/teachers/2/classes/query"
        response = self.client.post(path, headers=self.headers(), json={"limit": 1, "sort": "name", "order": "asc"})
        self.assertEqual(response.status_code, 200)
        first = response.json()["items"][0]
        self.assertEqual(first["class_id"], 11)  # Active-contest priority puts Beta before Alpha.
        self.assertTrue(first["has_active_contest"])
        self.assertEqual(first["active_contest_ids"], [101])
        for direction in ("asc", "desc"):
            page = self.client.post(path, headers=self.headers(), json={"limit": 10, "sort": "created_at", "order": direction})
            ids = [item["class_id"] for item in page.json()["items"]]
            self.assertEqual(ids[-1], 14)

    def test_contest_routes_filter_state_class_mapping_and_author_curator(self):
        base = "/integration/v1/teachers/2/contests"
        active = self.client.get(base, params={"state": "active", "at": "2026-06-01T00:00:00Z"}, headers=self.headers())
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual({item["contest_id"] for item in active.json()["items"]}, {101, 106})
        self.assertEqual(next(item for item in active.json()["items"] if item["contest_id"] == 101)["class_ids"], [11])
        active_public = next(item for item in active.json()["items"] if item["contest_id"] == 101)
        self.assertTrue(active_public["is_public"])
        curator = next(item for item in active.json()["items"] if item["contest_id"] == 106)
        self.assertEqual(curator["class_ids"], [])
        self.assertIsNone(curator["updated_at"])
        ended = self.client.get(base, params={"state": "ended", "at": "2026-06-01T00:00:00Z"}, headers=self.headers())
        self.assertEqual({item["contest_id"] for item in ended.json()["items"]}, {102, 105})
        class_contests = self.client.get("/integration/v1/classes/11/contests", params={"at": "2026-06-01T00:00:00Z"}, headers=self.headers())
        self.assertEqual({item["contest_id"] for item in class_contests.json()["items"]}, {101, 103})
        multi = next(item for item in class_contests.json()["items"] if item["contest_id"] == 103)
        self.assertEqual(multi["class_ids"], [11, 12])
        hidden = self.client.get("/integration/v1/classes/12/contests", params={"state": "active", "at": "2026-06-01T00:00:00Z"}, headers=self.headers())
        self.assertEqual(hidden.json()["items"], [])
        first_page = self.client.get(base, params={"state": "active", "at": "2026-06-01T00:00:00Z", "limit": 1}, headers=self.headers()).json()
        next_page = self.client.get(base, params={"state": "active", "at": "2026-06-01T00:00:00Z", "limit": 1,
                                                   "cursor": first_page["next_cursor"]}, headers=self.headers())
        self.assertEqual(next_page.json()["items"][0]["contest_id"], 106)
        stale_scope = self.client.get(base, params={"state": "ended", "at": "2026-06-01T00:00:00Z", "limit": 1,
                                                    "cursor": first_page["next_cursor"]}, headers=self.headers())
        self.assertEqual(stale_scope.status_code, 409)

    def test_cursor_is_bound_to_filter_and_snapshot(self):
        path = "/integration/v1/teachers/2/classes/query"
        first = self.client.post(path, headers=self.headers(), json={"limit": 1, "sort": "name"}).json()
        cursor = first["next_cursor"]
        changed_filter = self.client.post(path, headers=self.headers(), json={"limit": 1, "sort": "id", "cursor": cursor})
        self.assertEqual(changed_filter.status_code, 409)
        with self.engine.begin() as conn:
            conn.execute(update(organization).where(organization.c.id == 12).values(name="Changed"))
        changed_data = self.client.post(path, headers=self.headers(), json={"limit": 1, "sort": "name", "cursor": cursor})
        self.assertEqual(changed_data.status_code, 409)

    def test_search_wildcards_are_literal_for_class_ids_and_students(self):
        classes = self.client.post("/integration/v1/teachers/2/classes/query", headers=self.headers(),
                                   json={"q": "1%", "limit": 100})
        self.assertEqual(classes.status_code, 200)
        self.assertEqual(classes.json()["total"], 0)
        students = self.client.get("/integration/v1/teachers/2/students", params={"q": "%"}, headers=self.headers())
        self.assertEqual(students.status_code, 200)
        self.assertEqual(students.json()["total"], 0)
        empty_params = self.client.get("/integration/v1/teachers/2/students", params={"q": "", "cursor": ""}, headers=self.headers())
        self.assertEqual(empty_params.status_code, 200)
        self.assertEqual(empty_params.json()["total"], 2)

    def test_students_are_deduplicated_and_out_of_scope_hidden(self):
        response = self.client.get("/integration/v1/teachers/2/students?limit=1", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(response.json()["items"][0]["profile_id"], 3)
        student = self.client.get("/integration/v1/students/3", headers=self.headers())
        self.assertEqual([c["class_id"] for c in student.json()["classes"]], [11, 12])
        self.assertEqual(self.client.get("/integration/v1/students/9", headers=self.headers()).status_code, 404)
        self.assertEqual(self.client.get("/integration/v1/profiles/6/access", headers=self.headers(actor="9")).json()["is_active"], False)
        superadmin_students = self.client.get("/integration/v1/teachers/9/students", headers=self.headers(actor="9"))
        self.assertEqual(superadmin_students.json()["total"], 2)
        self.assertNotIn(5, {item["profile_id"] for item in superadmin_students.json()["items"]})

    def test_student_sort_directions_keep_global_rank(self):
        path = "/integration/v1/teachers/2/students"
        expected = {
            "name": ([3, 4], [None, None]),
            "name_desc": ([4, 3], [None, None]),
            "points_desc": ([3, 4], [1, 2]),
            "points_asc": ([4, 3], [2, 1]),
        }
        for sort, (ids, ranks) in expected.items():
            with self.subTest(sort=sort):
                first = self.client.get(path, params={"sort": sort, "limit": 1}, headers=self.headers())
                self.assertEqual(first.status_code, 200)
                second = self.client.get(path, params={"sort": sort, "limit": 1,
                                                       "cursor": first.json()["next_cursor"]}, headers=self.headers())
                self.assertEqual(second.status_code, 200)
                items = first.json()["items"] + second.json()["items"]
                self.assertEqual([item["profile_id"] for item in items], ids)
                self.assertEqual([item["rank"] for item in items], ranks)

    def test_student_without_name_uses_profile_id(self):
        with self.engine.begin() as conn:
            conn.execute(update(profile).where(profile.c.id == 4).values(name=None))
        response = self.client.get("/integration/v1/teachers/2/students", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(next(item for item in response.json()["items"] if item["profile_id"] == 4)["name"], "4")

    def test_tag_problem_pools_only_include_visible_problems(self):
        path = "/integration/v1/analytics/tag-problem-pools"
        response = self.client.get(path, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["catalog_version"])
        self.assertEqual(payload["tag_problem_ids"]["14"], [201])
        self.assertEqual(payload["tag_problem_ids"]["31"], [201, 203])

    def test_class_students_and_contests(self):
        response = self.client.get("/integration/v1/classes/11/students", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["items"][0]["avatar_url"])
        self.assertEqual(self.client.get("/integration/v1/classes/12", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.get("/integration/v1/classes/13", headers=self.headers()).status_code, 404)
        self.assertEqual(self.client.get("/integration/v1/classes/14", headers=self.headers()).status_code, 200)

    def test_student_submission_filters_paging_permissions_and_source_scope(self):
        path = "/integration/v1/students/3/submissions"
        first = self.client.get(path, params={"result": "WA", "only_with_source": "true", "limit": 1}, headers=self.headers())
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["total"], 1)
        item = first.json()["items"][0]
        self.assertEqual(item["submission_id"], 501)
        self.assertEqual(item["problem_title"], "Problem 201")
        self.assertEqual(item["language"]["key"], "py3")
        page_one = self.client.get(path, params={"limit": 1, "sort": "desc"}, headers=self.headers()).json()
        self.assertEqual(page_one["items"][0]["submission_id"], 502)
        page_two = self.client.get(path, params={"limit": 1, "sort": "desc", "cursor": page_one["next_cursor"]}, headers=self.headers())
        self.assertEqual(page_two.status_code, 200, page_two.text)
        self.assertEqual(page_two.json()["items"][0]["submission_id"], 501)
        failed = self.client.get(path, params={"exclude_result": "AC", "limit": 1}, headers=self.headers())
        self.assertEqual(failed.status_code, 200, failed.text)
        self.assertEqual(failed.json()["total"], 1)
        self.assertEqual(failed.json()["items"][0]["result"], "WA")
        boundary = self.client.get(path, params={"to": "2026-06-01T10:00:00Z"}, headers=self.headers())
        self.assertEqual(boundary.json()["total"], 0)
        self.assertEqual(self.client.get("/integration/v1/students/5/submissions", headers=self.headers()).status_code, 404)
        actor_without_source = self.headers(actor="9")
        self.assertEqual(self.client.get("/integration/v1/submissions/501", headers=actor_without_source).status_code, 200)
        self.assertEqual(self.client.get("/integration/v1/submissions/501?include=source", headers=actor_without_source).status_code, 403)
        self.assertEqual(self.client.get("/integration/v1/submissions/501?include=testcases", headers=actor_without_source).status_code, 403)
        allowed = self.client.get("/integration/v1/submissions/501?include=source,testcases", headers=self.headers())
        self.assertEqual(allowed.json()["source_code"], "print('hello')")
        self.assertEqual(allowed.json()["testcases"][0]["feedback"], "Expected 2")
        self.assertEqual(self.client.get("/integration/v1/submissions/599", headers=self.headers()).status_code, 404)

    def test_accepted_and_student_submission_samples_are_scoped_and_bounded(self):
        with self.engine.begin() as conn:
            conn.execute(insert(submission), [
                {"id": 504, "date": datetime(2026, 6, 3, 10), "judged_date": datetime(2026, 6, 3, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.15, "memory": 1536, "points": 100, "status": "D", "result": "AC", "error": None, "user_id": 3, "problem_id": 201, "language_id": 1},
                {"id": 505, "date": datetime(2026, 6, 2, 10), "judged_date": datetime(2026, 6, 2, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.2, "memory": 2048, "points": 80, "status": "D", "result": "AC", "error": None, "user_id": 3, "problem_id": 201, "language_id": 1},
                {"id": 506, "date": datetime(2026, 6, 4, 10), "judged_date": datetime(2026, 6, 4, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 100, "points": 100, "status": "D", "result": "AC", "error": None, "user_id": 3, "problem_id": 201, "language_id": 1},
                {"id": 507, "date": datetime(2026, 6, 5, 10), "judged_date": datetime(2026, 6, 5, 10, 1), "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 100, "points": 100, "status": "D", "result": "AC", "error": None, "user_id": 3, "problem_id": 204, "language_id": 1},
            ])
            conn.execute(insert(submission_source), [
                {"id": 704, "submission_id": 504, "source": "print('accepted 201 v2')"},
                {"id": 705, "submission_id": 505, "source": "print('accepted 201 v1')"},
                {"id": 706, "submission_id": 506, "source": None},
                {"id": 707, "submission_id": 507, "source": "private code"},
            ])
            conn.execute(insert(problem_type), [{"id": 5, "problem_id": 204, "problemtype_id": 14}])
        accepted_path = "/integration/v1/problems/201/accepted-samples"
        accepted = self.client.get(accepted_path, params={"limit": 1}, headers=self.headers())
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual([item["submission_id"] for item in accepted.json()["items"]], [504])
        self.assertEqual(accepted.json()["items"][0]["source_code"], "print('accepted 201 v2')")
        self.assertEqual(self.client.get(accepted_path, headers=self.headers(actor="9")).status_code, 403)
        self.assertEqual(self.client.get("/integration/v1/problems/204/accepted-samples", headers=self.headers()).status_code, 404)
        self.assertEqual(self.client.get(accepted_path, params={"limit": 4}, headers=self.headers()).status_code, 422)

        path = "/integration/v1/students/3/submission-samples"
        params = [("tag_ids", "14"), ("tag_ids", "31"), ("per_group_limit", "1")]
        samples = self.client.get(path, params=params, headers=self.headers())
        self.assertEqual(samples.status_code, 200, samples.text)
        self.assertEqual([item["submission_id"] for item in samples.json()["items"]], [504])
        self.assertEqual(samples.json()["items"][0]["tag_ids"], [14, 31])
        self.assertNotIn("private code", [item["source_code"] for item in samples.json()["items"]])
        self.assertEqual(samples.json()["items"][0]["problem_time_limit"], 1.5)
        before_latest = self.client.get(path, params=params + [("to", "2026-06-03T10:00:00Z")], headers=self.headers())
        self.assertEqual(before_latest.status_code, 200, before_latest.text)
        self.assertEqual([item["submission_id"] for item in before_latest.json()["items"]], [505])
        self.assertEqual(self.client.get(path, params=params, headers=self.headers(actor="9")).status_code, 403)

    def test_batch_student_alerts_detect_stuck_and_keep_request_scope(self):
        with self.engine.begin() as conn:
            conn.execute(insert(submission), [
                {"id": sid, "date": datetime(2026, 6, 4, 10, 0, sid - 600), "judged_date": None,
                 "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 100,
                 "points": 0, "status": "D", "result": "WA", "error": None,
                 "user_id": 3, "problem_id": 201, "language_id": 1}
                for sid in range(600, 608)
            ] + [{
                "id": sid, "date": datetime(2026, 6, 4, 11, 0, sid - 610), "judged_date": None,
                "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 100,
                "points": 0, "status": "D", "result": "WA", "error": None,
                "user_id": 4, "problem_id": 204, "language_id": 1,
            } for sid in range(610, 618)] + [{
                "id": 618, "date": datetime(2026, 6, 4, 23), "judged_date": None,
                "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 100,
                "points": 0, "status": "D", "result": "WA", "error": None,
                "user_id": 3, "problem_id": 204, "language_id": 1,
            }])
        response = self.client.post("/integration/v1/analytics/students/alerts", json={
            "profile_ids": [3, 4], "at": "2026-06-05T10:00:00Z",
        }, headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        by_profile = {item["profile_id"]: item for item in response.json()["items"]}
        self.assertTrue(by_profile[3]["has_stuck_problem"])
        self.assertFalse(by_profile[4]["has_stuck_problem"])
        self.assertEqual(by_profile[3]["last_submission_at"], "2026-06-04T10:00:07Z")
        self.assertEqual(by_profile[4]["last_submission_at"], "2026-06-02T10:00:00Z")
        self.assertEqual(response.json()["reference_now"], "2026-06-04T10:00:07Z")
        denied = self.client.post("/integration/v1/analytics/students/alerts", json={
            "profile_ids": [3, 5], "at": "2026-06-05T10:00:00Z",
        }, headers=self.headers())
        self.assertEqual(denied.status_code, 404)
        oversized = self.client.post("/integration/v1/analytics/students/alerts", json={
            "profile_ids": list(range(1, 102)), "at": "2026-06-05T10:00:00Z",
        }, headers=self.headers())
        self.assertEqual(oversized.status_code, 422)

    def test_class_submission_handoff_and_changes_detect_late_update_delete(self):
        path = "/integration/v1/classes/11/submissions"
        first = self.client.get(path, params={"limit": 1}, headers=self.headers())
        self.assertEqual(first.status_code, 200, first.text)
        first_page = first.json()
        self.assertTrue(first_page["next_cursor"])
        self.assertTrue(first_page["high_watermark"])
        self.assertEqual(first_page["items"][0]["submission_id"], 502)
        boundary = self.client.get(path, params={"to": "2026-06-01T10:00:00Z"}, headers=self.headers())
        self.assertEqual(boundary.json()["total"], 0)
        second = self.client.get(path, params={"limit": 1, "cursor": first_page["next_cursor"]}, headers=self.headers())
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["items"][0]["submission_id"], 501)
        self.assertEqual(second.json()["high_watermark"], first_page["high_watermark"])
        no_changes = self.client.get("/integration/v1/classes/11/submission-changes",
                                     params={"cursor": first_page["high_watermark"]}, headers=self.headers())
        self.assertEqual(no_changes.status_code, 200)
        self.assertEqual(no_changes.json()["events"], [])

        with self.engine.begin() as conn:
            conn.execute(insert(submission), {
                "id": 504, "date": datetime(2025, 1, 1), "judged_date": datetime(2025, 1, 1, 1),
                "rejudged_date": None, "version_update": "1", "time": 0.3, "memory": 3000,
                "points": 0, "status": "IE", "result": "WA", "error": None,
                "user_id": 3, "problem_id": 201, "language_id": 1,
            })
            conn.execute(update(submission).where(submission.c.id == 501).values(
                result="AC", status="D", points=100,
            ))
            conn.execute(submission.delete().where(submission.c.id == 502))
        stale_list_page = self.client.get(path, params={"limit": 1, "cursor": first_page["next_cursor"]}, headers=self.headers())
        self.assertEqual(stale_list_page.status_code, 409)

        changes_path = "/integration/v1/classes/11/submission-changes"
        cursor = first_page["high_watermark"]
        events = []
        while True:
            page = self.client.get(changes_path, params={"cursor": cursor, "limit": 1}, headers=self.headers())
            self.assertEqual(page.status_code, 200, page.text)
            payload = page.json()
            events.extend(payload["events"])
            if not payload["has_more"]:
                break
            cursor = payload["next_cursor"]
        by_id = {event["submission_id"]: event for event in events}
        self.assertEqual({event["kind"] for event in events}, {"created", "updated", "deleted"})
        self.assertEqual(by_id[504]["kind"], "created")
        self.assertEqual(by_id[504]["record"]["submitted_at"], "2025-01-01T00:00:00Z")
        self.assertEqual(by_id[501]["kind"], "updated")
        self.assertEqual(by_id[501]["record"]["result"], "AC")
        self.assertEqual(by_id[501]["record"]["submitted_at"], "2026-06-01T10:00:00Z")
        self.assertEqual(by_id[502]["kind"], "deleted")
        self.assertIsNone(by_id[502]["record"])

    def test_invalid_class_cursors_fail_before_submission_scan(self):
        with patch.object(source_main, "submission_rows", side_effect=AssertionError("full submission scan")), \
             patch.object(source_main, "_class_submission_metadata", side_effect=AssertionError("metadata scan")):
            tampered_list = self.client.get(
                "/integration/v1/classes/11/submissions?cursor=bad-cursor", headers=self.headers(),
            )
            tampered_changes = self.client.get(
                "/integration/v1/classes/11/submission-changes?cursor=bad-cursor", headers=self.headers(),
            )
        self.assertEqual(tampered_list.status_code, 409)
        self.assertEqual(tampered_changes.status_code, 409)

    def test_unchanged_change_poll_skips_full_metadata_and_payload_scan(self):
        snapshot = self.client.get("/integration/v1/classes/11/submissions?limit=2", headers=self.headers())
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        with patch.object(source_main, "submission_rows", side_effect=AssertionError("payload scan")), \
             patch.object(source_main, "_class_submission_metadata", side_effect=AssertionError("metadata scan")):
            response = self.client.get(
                "/integration/v1/classes/11/submission-changes",
                params={"cursor": snapshot.json()["high_watermark"]}, headers=self.headers(),
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["events"], [])

    def test_periodic_reconciliation_finds_unmarked_verdict_change_and_delete(self):
        snapshot = self.client.get("/integration/v1/classes/11/submissions?limit=2", headers=self.headers())
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        watermark = snapshot.json()["high_watermark"]
        marker = source_main._change_markers[11]
        with self.engine.begin() as conn:
            conn.execute(update(submission).where(submission.c.id == 501).values(result="AC", status="D"))
            conn.execute(submission.delete().where(submission.c.id == 502))
        source_main._change_last_reconciled[11] = time.monotonic() - 11
        with patch.object(source_main, "_class_submission_marker", return_value=marker):
            response = self.client.get(
                "/integration/v1/classes/11/submission-changes",
                params={"cursor": watermark, "limit": 100}, headers=self.headers(),
            )
        self.assertEqual(response.status_code, 200, response.text)
        by_id = {event["submission_id"]: event for event in response.json()["events"]}
        self.assertEqual(by_id[501]["kind"], "updated")
        self.assertEqual(by_id[501]["record"]["result"], "AC")
        self.assertEqual(by_id[502]["kind"], "deleted")
        self.assertIsNone(by_id[502]["record"])

    def test_initial_change_cursor_emits_current_snapshot_and_problem_detail(self):
        response = self.client.get("/integration/v1/classes/11/submission-changes?limit=1", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"][0]["kind"], "created")
        self.assertTrue(response.json()["has_more"])
        self.assertTrue(response.json()["next_cursor"])
        detail = self.client.get("/integration/v1/problems/201", headers=self.headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["code"], "P201")
        self.assertEqual(detail.json()["title"], "Problem 201")
        self.assertEqual(detail.json()["tag_ids"], [14, 31])
        self.assertIsNone(detail.json()["updated_at"])
        self.assertEqual(detail.json()["version"], 12)
        unnamed = self.client.get("/integration/v1/problems/203", headers=self.headers())
        self.assertEqual(unnamed.status_code, 200)
        self.assertEqual(unnamed.json()["title"], "P203")
        private_teacher = self.client.get("/integration/v1/problems/204", headers=self.headers("2"))
        self.assertEqual(private_teacher.status_code, 404)
        private_admin = self.client.get("/integration/v1/problems/204", headers=self.headers("9"))
        self.assertEqual(private_admin.status_code, 200)
        self.assertEqual(private_admin.json()["description"], "Private statement")
        boundary = self.client.get("/integration/v1/classes/12/submissions?to=2026-06-02T10:00:00Z", headers=self.headers())
        self.assertEqual(boundary.status_code, 200)
        boundary_changes = self.client.get(
            "/integration/v1/classes/12/submission-changes",
            params={"cursor": boundary.json()["high_watermark"], "to": "2026-06-02T10:00:00Z"},
            headers=self.headers(),
        )
        self.assertEqual(boundary_changes.status_code, 200)
        self.assertEqual(boundary_changes.json()["events"], [])

    def test_class_page_cursor_fails_closed_after_mock_process_epoch_changes(self):
        path = "/integration/v1/classes/11/submissions"
        first = self.client.get(path, params={"limit": 1}, headers=self.headers()).json()
        original_epoch = source_main._change_epoch
        try:
            source_main._change_epoch = "new-process-epoch"
            response = self.client.get(path, params={"limit": 1, "cursor": first["next_cursor"]}, headers=self.headers())
            self.assertEqual(response.status_code, 409)
        finally:
            source_main._change_epoch = original_epoch

    def test_class_submission_paging_exceeds_one_hundred_pages_without_loss(self):
        rows = [{
            "id": submission_id, "date": datetime(2026, 6, 1, 10), "judged_date": datetime(2026, 6, 1, 10, 1),
            "rejudged_date": None, "version_update": "1", "time": 0.1, "memory": 1024,
            "points": 0, "status": "IE", "result": "WA", "error": None,
            "user_id": 3, "problem_id": 201, "language_id": 1,
        } for submission_id in range(1000, 1102)]
        with self.engine.begin() as conn:
            conn.execute(insert(submission), rows)
        path = "/integration/v1/classes/11/submissions"
        ids = []
        cursor = None
        watermark = None
        for _ in range(105):
            params = {"limit": 1}
            if cursor:
                params["cursor"] = cursor
            response = self.client.get(path, params=params, headers=self.headers())
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            ids.extend(item["submission_id"] for item in payload["items"])
            if watermark is None:
                watermark = payload["high_watermark"]
            self.assertEqual(payload["high_watermark"], watermark)
            if not payload["has_more"]:
                break
            cursor = payload["next_cursor"]
        self.assertEqual(len(ids), 104)
        self.assertEqual(len(set(ids)), len(ids))

    def test_catalog_routes_paginate_filter_and_return_etags(self):
        tag_path = "/integration/v1/tags"
        first = self.client.get(tag_path, params={"limit": 1}, headers=self.headers())
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.headers.get("ETag"))
        self.assertEqual(first.json()["items"][0]["tag_id"], 14)
        self.assertEqual(first.json()["total"], 2)
        cached = self.client.get(tag_path, params={"limit": 1},
                                 headers={**self.headers(), "If-None-Match": first.headers["ETag"]})
        self.assertEqual(cached.status_code, 304)
        stale_cursor = self.client.get(tag_path, params={"limit": 1, "cursor": "invalid"},
                                       headers={**self.headers(), "If-None-Match": first.headers["ETag"]})
        self.assertEqual(stale_cursor.status_code, 409)
        next_page = self.client.get(tag_path, params={"limit": 1, "cursor": first.json()["next_cursor"]},
                                    headers=self.headers())
        self.assertEqual([item["tag_id"] for item in next_page.json()["items"]], [31])

        problems = self.client.get("/integration/v1/problems", params={"limit": 1}, headers=self.headers())
        self.assertEqual(problems.status_code, 200, problems.text)
        next_problems = self.client.get("/integration/v1/problems", params={
            "limit": 1, "cursor": problems.json()["next_cursor"],
        }, headers=self.headers())
        self.assertEqual(next_problems.json()["total"], problems.json()["total"])
        tagged = self.client.get("/integration/v1/problems", params={"tag_id": 14}, headers=self.headers())
        self.assertEqual(tagged.json()["total"], 1)
        for literal in ("%", "_", "\\\\"):
            wildcard = self.client.get("/integration/v1/problems", params={"q": literal}, headers=self.headers())
            self.assertEqual(wildcard.status_code, 200, wildcard.text)
            self.assertEqual(wildcard.json()["total"], 0)
        selected = self.client.get("/integration/v1/problems", params=[("ids", "201"), ("ids", "203"), ("fields", "summary")], headers=self.headers())
        self.assertEqual([row["problem_id"] for row in selected.json()["items"]], [201, 203])
        self.assertNotIn("description", selected.json()["items"][0])
        groups = self.client.get("/integration/v1/problem-groups", headers=self.headers())
        self.assertEqual(groups.status_code, 200, groups.text)
        self.assertEqual([item["group_id"] for item in groups.json()["items"]], [4, 5])

    def test_catalog_counts_distinct_problems_and_etag_tracks_unversioned_edits(self):
        path = "/integration/v1/analytics/catalog"
        initial = self.client.get(path, headers=self.headers())
        self.assertEqual(initial.status_code, 200, initial.text)
        body = initial.json()
        self.assertEqual(body["total_problem_count"], 3)
        self.assertEqual(body["tagged_problem_count"], 2)
        algebra = next(item for item in body["tag_problem_counts"] if item["tag_id"] == 14)
        self.assertEqual(algebra["distinct_problem_count"], 1)
        self.assertEqual(algebra["example_titles"], ["Problem 201"])
        unnamed_tag = self.client.get("/integration/v1/problems?tag_id=31", headers=self.headers())
        self.assertEqual(unnamed_tag.status_code, 200, unnamed_tag.text)
        self.assertEqual([item["title"] for item in unnamed_tag.json()["items"]], ["Problem 201", "P203"])
        number_theory = next(item for item in body["tag_problem_counts"] if item["tag_id"] == 31)
        self.assertEqual(number_theory["distinct_problem_count"], 2)
        self.assertEqual(number_theory["example_titles"], ["P203", "Problem 201"])
        etag = initial.headers["ETag"]
        not_modified = self.client.get(path, headers={**self.headers(), "If-None-Match": etag})
        self.assertEqual(not_modified.status_code, 304)
        with self.engine.begin() as conn:
            conn.execute(update(problem).where(problem.c.id == 201).values(name="Renamed", version_update=12))
        changed = self.client.get(path, headers=self.headers())
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertNotEqual(changed.headers["ETag"], etag)
        self.assertEqual(changed.json()["tag_problem_counts"][0]["example_titles"], ["Renamed"])

    def test_catalog_visibility_hides_private_rows_and_rejects_stale_cursor(self):
        first = self.client.get("/integration/v1/problems", params={"limit": 1}, headers=self.headers())
        self.assertEqual(first.json()["total"], 3)
        private = self.client.get("/integration/v1/problems", params={"ids": 204}, headers=self.headers())
        self.assertEqual(private.json()["items"], [])
        admin = self.client.get("/integration/v1/problems", params={"ids": 204}, headers=self.headers("9"))
        self.assertEqual(admin.json()["items"][0]["problem_id"], 204)
        with self.engine.begin() as conn:
            conn.execute(update(problem).where(problem.c.id == 203).values(name="New title", version_update=7))
        stale = self.client.get("/integration/v1/problems", params={"limit": 1, "cursor": first.json()["next_cursor"]},
                                headers=self.headers())
        self.assertEqual(stale.status_code, 409)

    def test_problem_cursor_without_after_id_pages_to_end_without_duplicates(self):
        with self.engine.begin() as conn:
            conn.execute(insert(problem), [
                {
                    "id": problem_id, "code": f"P{problem_id}", "name": f"Problem {problem_id}",
                    "description": None, "time_limit": 1.0, "memory_limit": 128000,
                    "points": 10.0, "is_public": 1, "is_organization_private": 0,
                    "classes_id": None, "group_id": None, "version_update": 1,
                }
                for problem_id in range(300, 550)
            ])

        params = {"limit": 100, "fields": "summary"}
        seen_ids, seen_cursors, page_count = [], set(), 0
        while True:
            response = self.client.get("/integration/v1/problems", params=params, headers=self.headers())
            self.assertEqual(response.status_code, 200, response.text)
            page = response.json()
            page_count += 1
            seen_ids.extend(item["problem_id"] for item in page["items"])
            if not page["has_more"]:
                self.assertIsNone(page["next_cursor"])
                break
            cursor = page["next_cursor"]
            self.assertTrue(cursor)
            self.assertNotIn(cursor, seen_cursors)
            seen_cursors.add(cursor)
            params = {"limit": 100, "fields": "summary", "cursor": cursor}

        self.assertEqual(page_count, 3)
        self.assertEqual(len(seen_ids), 253)
        self.assertEqual(len(seen_ids), len(set(seen_ids)))
        self.assertEqual(seen_ids, sorted(seen_ids))

    def test_problem_cursor_preserves_explicit_after_id_anchor(self):
        with self.engine.begin() as conn:
            conn.execute(insert(problem), [
                {
                    "id": problem_id, "code": f"P{problem_id}", "name": f"Problem {problem_id}",
                    "description": None, "time_limit": 1.0, "memory_limit": 128000,
                    "points": 10.0, "is_public": 1, "is_organization_private": 0,
                    "classes_id": None, "group_id": None, "version_update": 1,
                }
                for problem_id in range(300, 550)
            ])

        params = {"after_id": 350, "limit": 100, "fields": "summary"}
        seen_ids, page_totals = [], []
        while True:
            response = self.client.get("/integration/v1/problems", params=params, headers=self.headers())
            self.assertEqual(response.status_code, 200, response.text)
            page = response.json()
            page_totals.append(page["total"])
            seen_ids.extend(item["problem_id"] for item in page["items"])
            if not page["has_more"]:
                break
            params = {"cursor": page["next_cursor"], "limit": 100, "fields": "summary"}

        self.assertEqual(seen_ids, list(range(351, 550)))
        self.assertEqual(len(seen_ids), len(set(seen_ids)))
        self.assertEqual(page_totals, [page_totals[0]] * len(page_totals))

    def test_student_aggregate_filters_and_counts_multitag_union_distinct(self):
        response = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": [3, 4], "from": "2026-06-01T10:00:00Z", "to": "2026-06-02T10:00:00Z",
            "tag_groups": [{"key": "overlap", "tag_ids": [14, 31, 14]}],
            "include_problem_facts": True,
        })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["reference_now"], "2026-06-02T10:00:00Z")
        self.assertTrue(payload["catalog_version"])
        alice = payload["students"][0]
        self.assertEqual(alice["profile_id"], 3)
        self.assertEqual(alice["total_submissions"], 2)
        self.assertEqual(alice["solved_unique_count"], 1)
        self.assertEqual(alice["verdict_counts"], {"WA": 1, "AC": 1})
        tag14 = next(item for item in alice["tag_stats"] if item["tag_id"] == 14)
        self.assertEqual(tag14["problem_count"], 1)
        self.assertEqual(tag14["attempted_unique_count"], 1)
        self.assertEqual(tag14["solved_unique_count"], 0)
        requested = alice["requested_group_stats"][0]
        self.assertEqual(requested, {"key": "overlap", "attempted_unique_count": 1, "solved_unique_count": 0})
        self.assertEqual(len(alice["problem_facts"]), 2)
        fact_by_id = {item["problem_id"]: item for item in alice["problem_facts"]}
        self.assertEqual(fact_by_id[202]["first_ac_time"], 0.2)
        self.assertEqual(fact_by_id[202]["problem_time_limit"], 2.0)
        self.assertEqual(fact_by_id[202]["problem_memory_limit"], 512000)
        self.assertEqual(fact_by_id[202]["rapid_failure_pair_count"], 0)
        self.assertEqual(payload["students"][1]["problem_facts"], [])
        self.assertEqual(payload["students"][1]["total_submissions"], 0)  # Bob's submission is exactly `to`.

    def test_student_aggregate_permission_preflight_and_empty_student(self):
        with patch.object(source_main, "_load_student_fact_data", side_effect=AssertionError("must check scope first")):
            forbidden = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
                "profile_ids": [3, 5],
            })
        self.assertEqual(forbidden.status_code, 404)
        duplicate = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": [3, 3],
        })
        self.assertEqual(duplicate.status_code, 422)
        with self.engine.begin() as conn:
            conn.execute(insert(profile), [{"id": 7, "user_id": None, "name": "Empty student", "points": 0,
                                             "problem_count": 0, "display_rank": "user", "super_admin": 0}])
            conn.execute(insert(profile_organization), [{"id": 4, "profile_id": 7, "organization_id": 11}])
        empty = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": [7], "include_problem_facts": True,
        })
        self.assertEqual(empty.status_code, 200, empty.text)
        item = empty.json()["students"][0]
        self.assertEqual(item["total_submissions"], 0)
        self.assertEqual(item["problem_facts"], [])
        self.assertIsNone(item["last_submission_at"])
        self.assertEqual(empty.json()["reference_now"], "2026-06-02T10:00:00Z")

    def test_problem_facts_cursor_pagination_half_open_range_and_snapshot_conflict(self):
        path = "/integration/v1/students/3/problem-facts"
        first = self.client.get(path, params={"from": "2026-06-01T10:00:00Z", "to": "2026-06-02T10:00:00Z", "limit": 1},
                                headers=self.headers())
        self.assertEqual(first.status_code, 200, first.text)
        payload = first.json()
        self.assertEqual(payload["total"], 2)
        fact = payload["items"][0]
        self.assertEqual(fact["problem_id"], 201)
        self.assertEqual(fact["tag_ids"], [14, 31])
        self.assertEqual(fact["attempt_count"], 1)
        self.assertEqual(fact["verdict_counts"], {"WA": 1})
        self.assertTrue(payload["has_more"])
        with self.engine.begin() as conn:
            conn.execute(update(submission).where(submission.c.id == 501).values(result="AC", status="D", points=100))
        stale = self.client.get(path, params={"from": "2026-06-01T10:00:00Z", "to": "2026-06-02T10:00:00Z",
                                               "limit": 1, "cursor": payload["next_cursor"]}, headers=self.headers())
        self.assertEqual(stale.status_code, 409)
        changed = self.client.get(path, params={"from": "2026-06-01T10:00:00Z", "to": "2026-06-02T10:00:00Z"},
                                  headers=self.headers())
        self.assertEqual(changed.status_code, 200, changed.text)
        updated = changed.json()["items"][0]
        self.assertEqual(updated["ac_count"], 1)
        self.assertEqual(updated["failed_before_first_ac_count"], 0)
        self.assertEqual(updated["first_ac_submission_id"], 501)
        outside = self.client.get(path, params={"to": "2026-06-02T10:00:00Z"}, headers=self.headers())
        self.assertEqual(outside.status_code, 200)
        self.assertEqual(outside.json()["total"], 2)

    def test_student_aggregate_problem_fact_cap_uses_paged_endpoint(self):
        with patch.object(source_main, "_distinct_student_problem_count", return_value=1001), \
             patch.object(source_main, "_load_student_fact_data", side_effect=AssertionError("must cap before materializing")):
            response = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
                "profile_ids": [3], "include_problem_facts": True,
            })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "validation_error")

    def test_student_aggregate_accepts_one_hundred_scoped_profiles(self):
        profile_ids = list(range(1000, 1100))
        with self.engine.begin() as conn:
            conn.execute(insert(profile), [{
                "id": profile_id, "user_id": None, "name": f"Student {profile_id}",
                "points": 0, "problem_count": 0, "display_rank": "user", "super_admin": 0,
            } for profile_id in profile_ids])
            conn.execute(insert(profile_organization), [{
                "id": 100 + index, "profile_id": profile_id, "organization_id": 11,
            } for index, profile_id in enumerate(profile_ids)])
        response = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": profile_ids,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["students"]), 100)
        self.assertTrue(all(item["total_submissions"] == 0 for item in response.json()["students"]))

    def test_student_analytics_excludes_private_problem_data_for_non_admin(self):
        with self.engine.begin() as conn:
            conn.execute(insert(submission), [{
                "id": 504, "date": datetime(2026, 6, 3, 10), "judged_date": datetime(2026, 6, 3, 10, 1),
                "rejudged_date": None, "version_update": "1", "time": 1.0, "memory": 1024,
                "points": 0, "status": "D", "result": "WA", "error": None,
                "user_id": 3, "problem_id": 204, "language_id": 1,
            }])
        aggregate = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": [3], "include_problem_facts": True,
        })
        self.assertEqual(aggregate.status_code, 200, aggregate.text)
        student = aggregate.json()["students"][0]
        self.assertEqual(aggregate.json()["reference_now"], "2026-06-02T10:00:00Z")
        self.assertEqual(student["total_submissions"], 2)
        self.assertNotIn(204, [fact["problem_id"] for fact in student["problem_facts"]])
        facts = self.client.get("/integration/v1/students/3/problem-facts", headers=self.headers())
        self.assertEqual(facts.status_code, 200)
        self.assertNotIn(204, [fact["problem_id"] for fact in facts.json()["items"]])

    def test_student_aggregate_rejects_duplicate_group_keys(self):
        response = self.client.post("/integration/v1/analytics/students/aggregate", headers=self.headers(), json={
            "profile_ids": [3],
            "tag_groups": [{"key": "same", "tag_ids": [14]}, {"key": "same", "tag_ids": [31]}],
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()

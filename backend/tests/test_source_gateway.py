import unittest
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request

from app.services.source_gateway import HttpSourceGateway, get_source_gateway


class SourceGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_alerts_and_submission_samples_use_scoped_gateway_routes(self):
        requests = []

        async def handle(request: httpx.Request):
            requests.append(request)
            if request.url.path.endswith("/analytics/students/alerts"):
                return httpx.Response(200, json={
                    "items": [{"profile_id": 9, "last_submission_at": "2026-10-12T00:00:00Z",
                               "has_stuck_problem": True}],
                    "as_of": "2026-10-13T00:00:00Z", "reference_now": "2026-10-12T00:00:00Z",
                })
            if request.url.path.endswith("submission-samples"):
                return httpx.Response(200, json={"items": [{
                    "submission_id": 4, "problem_id": 8, "tag_ids": [14],
                    "submitted_at": "2026-10-12T00:00:00Z", "time": 0.2, "memory": 20,
                    "problem_time_limit": 1, "problem_memory_limit": 256,
                    "language_key": "CPP17", "source_code": "int main(){}",
                }], "as_of": "2026-10-13T00:00:00Z"})
            return httpx.Response(200, json={"items": [{
                "submission_id": 5, "language_key": "CPP17", "source_code": "int main(){}",
                "points": 100, "time": 0.1, "memory": 12,
                "submitted_at": "2026-10-12T00:00:00Z",
            }], "as_of": "2026-10-13T00:00:00Z"})

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            at = datetime(2026, 10, 13, tzinfo=timezone.utc)
            alerts = await gateway.get_student_alerts([9], actor_profile_id=7, at=at)
            samples = await gateway.list_student_submission_samples(
                9, actor_profile_id=7, date_from=at - timedelta(days=7),
                tag_ids=[14, 31], per_group_limit=3,
            )
            accepted = await gateway.get_problem_accepted_samples(8, actor_profile_id=7)
            empty = await gateway.get_student_alerts([], actor_profile_id=7, at=at)
        finally:
            await client.aclose()

        self.assertTrue(alerts.items[0].has_stuck_problem)
        self.assertEqual(samples.items[0].source_code, "int main(){}")
        self.assertEqual(samples.items[0].problem_memory_limit, 256)
        self.assertEqual(accepted.items[0].submission_id, 5)
        self.assertEqual(empty.items, [])
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[0].headers["Authorization"], "Bearer token")
        self.assertEqual(requests[0].headers["X-Actor-Profile-Id"], "7")
        self.assertEqual(requests[0].read().decode(), '{"profile_ids":[9],"at":"2026-10-13T00:00:00Z"}')
        self.assertEqual(requests[1].url.params.get_list("tag_ids"), ["14", "31"])
        self.assertEqual(requests[1].url.params["from"], "2026-10-06T00:00:00Z")
        self.assertEqual(requests[2].url.path, "/integration/v1/problems/8/accepted-samples")

    async def test_submission_routes_parse_dtos_and_opaque_cursors(self):
        seen = []

        def submission(submission_id=41):
            return {
                "submission_id": submission_id, "profile_id": 9, "student_name": "Ada",
                "problem_id": 3, "problem_code": "SUM", "problem_title": "Sum",
                "language_id": 7, "language": {"id": 7, "key": "py", "name": "Python",
                                                  "common_name": "Python"},
                "result": "AC", "status": "AC", "points": 100, "time": 0.02,
                "memory": 1024, "submitted_at": "2026-10-12T00:00:00Z",
                "has_source": True, "version": "3", "updated_at": "2026-10-12T00:00:02Z",
            }

        async def handle(request: httpx.Request):
            seen.append((request.url.path, dict(request.url.params)))
            if request.url.path.endswith("submission-changes"):
                return httpx.Response(200, json={
                    "events": [{"event_id": 5, "kind": "updated", "submission_id": 41,
                                "version": 3, "changed_at": "2026-10-12T00:00:02Z",
                                "record": submission()}],
                    "next_cursor": "event-next", "has_more": False,
                    "high_watermark": 5, "as_of": "2026-10-12T00:00:03Z",
                })
            if request.url.path.endswith("/submissions/41"):
                return httpx.Response(200, json={**submission(), "source_code": "print(1)", "testcases": []})
            if request.url.path.endswith("/problems/3"):
                return httpx.Response(200, json={"problem_id": 3, "code": "SUM", "title": "Sum",
                    "name": "Sum", "tag_ids": [2], "updated_at": "2026-10-12T00:00:00Z",
                    "version": 7})
            return httpx.Response(200, json={
                "items": [submission()], "next_cursor": "page-next", "has_more": True,
                "total": 120, "high_watermark": "watermark", "max_submission_id": 41,
                "as_of": "2026-10-12T00:00:03Z",
            })

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            student_page = await gateway.list_student_submissions(
                9, actor_profile_id=9, date_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
                result="AC", only_with_source=True, problem_id=3, exclude_result="WA",
                cursor="s-next", limit=25,
                sort="desc",
            )
            class_page = await gateway.list_class_submissions(31, actor_profile_id=9,
                                                               cursor="c-next", limit=100)
            changes = await gateway.list_class_submission_changes(31, actor_profile_id=9,
                                                                   cursor="opaque-watermark")
            detail = await gateway.get_submission(41, actor_profile_id=9,
                                                  include_source=True, include_testcases=True)
            problem = await gateway.get_problem(3, actor_profile_id=9)
        finally:
            await client.aclose()

        self.assertEqual(student_page.items[0].language.common_name, "Python")
        self.assertEqual(student_page.items[0].submission_id, 41)
        self.assertEqual(student_page.high_watermark, "watermark")
        self.assertEqual(class_page.next_cursor, "page-next")
        self.assertEqual(changes.events[0].kind, "updated")
        self.assertEqual(changes.next_cursor, "event-next")
        self.assertEqual(detail.source_code, "print(1)")
        self.assertEqual(problem.title, "Sum")
        self.assertEqual(problem.tag_ids, [2])
        self.assertEqual(problem.version, 7)
        self.assertEqual(seen[0][0], "/integration/v1/students/9/submissions")
        self.assertEqual(seen[0][1]["from"], "2026-10-01T00:00:00+00:00")
        self.assertEqual(seen[0][1]["sort"], "desc")
        self.assertEqual(seen[0][1]["exclude_result"], "WA")
        self.assertEqual(seen[1][0], "/integration/v1/classes/31/submissions")
        self.assertEqual(seen[2][0], "/integration/v1/classes/31/submission-changes")
        self.assertEqual(seen[2][1]["cursor"], "opaque-watermark")
        self.assertEqual(seen[3][1]["include"], "source,testcases")

    async def test_class_query_uses_integration_prefix_and_actor_header(self):
        requests = []

        async def handle(request: httpx.Request):
            requests.append(request)
            return httpx.Response(200, json={
                "items": [{
                    "class_id": 31, "name": "Lớp 7A",
                    "school_year": {"start": "2025-01-01", "finish": "2026-12-31"},
                    "created_at": None, "member_count": 12, "managers": [],
                    "has_active_contest": True, "active_contest_ids": [81], "updated_at": None,
                }],
                "next_cursor": "opaque-next", "has_more": True, "total": 29,
                "as_of": "2026-10-12T00:00:00Z",
            })

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "service-token", client=client)
        try:
            result = await gateway.list_classes(
                9, actor_profile_id=9, q="7A", cursor="opaque-current", limit=24,
                sort="created_at", order="desc", virtual_active_class_ids=[31], starred_class_ids=[4, 31],
            )
        finally:
            await client.aclose()

        request = requests[0]
        self.assertEqual(request.url.path, "/integration/v1/teachers/9/classes/query")
        self.assertEqual(request.headers["Authorization"], "Bearer service-token")
        self.assertEqual(request.headers["X-Actor-Profile-Id"], "9")
        self.assertTrue(request.headers["X-Request-Id"])
        self.assertEqual(request.read().decode(), '{"q":"7A","cursor":"opaque-current","limit":24,"sort":"created_at","order":"desc","virtual_active_class_ids":[31],"starred_class_ids":[4,31]}')
        self.assertEqual(result.items[0].class_id, 31)
        self.assertEqual(result.items[0].school_year.start.isoformat(), "2025-01-01")
        self.assertTrue(result.items[0].has_active_contest)
        self.assertEqual(result.next_cursor, "opaque-next")
        self.assertEqual(result.total, 29)

    async def test_api_403_is_preserved(self):
        async def handle(_request: httpx.Request):
            return httpx.Response(403, json={"code": "forbidden"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            with self.assertRaises(HTTPException) as error:
                await gateway.get_class(100, actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 403)
        finally:
            await client.aclose()

    async def test_malformed_upstream_json_and_schema_map_to_safe_502(self):
        async def handle(request: httpx.Request):
            if request.url.path.endswith("/malformed-json"):
                return httpx.Response(200, content=b"{")
            return httpx.Response(200, json={"unexpected": "shape"})

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            with self.assertRaises(HTTPException) as schema_error:
                await gateway.get_class(31, actor_profile_id=9)
            self.assertEqual(schema_error.exception.status_code, 502)
            self.assertEqual(schema_error.exception.detail,
                             "Dịch vụ dữ liệu nguồn trả dữ liệu không đúng hợp đồng.")
            with self.assertRaises(HTTPException) as json_error:
                await gateway._request("GET", "malformed-json", actor_profile_id=9)
            self.assertEqual(json_error.exception.status_code, 502)
            self.assertEqual(json_error.exception.detail,
                             "Dịch vụ dữ liệu nguồn trả nội dung JSON không hợp lệ.")
        finally:
            await client.aclose()

    async def test_expired_cursor_is_reported_as_conflict(self):
        async def handle(_request: httpx.Request):
            return httpx.Response(409, json={"code": "cursor_expired"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            with self.assertRaises(HTTPException) as error:
                await gateway.list_students(9, actor_profile_id=9, cursor="expired")
            self.assertEqual(error.exception.status_code, 409)
            self.assertIn("Cursor", error.exception.detail)
        finally:
            await client.aclose()

    async def test_rate_limit_preserves_retry_after(self):
        delays = []

        async def fake_sleep(delay: float):
            delays.append(delay)

        async def handle(_request: httpx.Request):
            return httpx.Response(429, headers={"Retry-After": "30"}, json={"code": "rate_limited"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway(
            "https://source.example/integration/v1", "token", client=client,
            sleep=fake_sleep, max_retry_after_seconds=5,
        )
        try:
            with self.assertRaises(HTTPException) as error:
                await gateway.get_class(31, actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 429)
            self.assertEqual(error.exception.headers["Retry-After"], "30")
            self.assertEqual(delays, [5, 5])
        finally:
            await client.aclose()

    async def test_http_date_retry_after_uses_injected_clock(self):
        delays = []

        async def fake_sleep(delay: float):
            delays.append(delay)

        async def handle(_request: httpx.Request):
            return httpx.Response(429, headers={"Retry-After": "Thu, 01 Jan 2026 00:00:03 GMT"},
                                  json={"code": "rate_limited"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway(
            "https://source.example/integration/v1", "token", client=client,
            sleep=fake_sleep, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        try:
            with self.assertRaises(HTTPException):
                await gateway.get_class(31, actor_profile_id=9)
            self.assertEqual(delays, [3, 3])
        finally:
            await client.aclose()

    async def test_persistent_source_server_errors_map_to_bad_gateway(self):
        attempts = 0
        delays = []

        async def fake_sleep(delay: float):
            delays.append(delay)

        async def handle(_request: httpx.Request):
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, json={"code": "unavailable"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client,
                                    sleep=fake_sleep)
        try:
            with self.assertRaises(HTTPException) as error:
                await gateway.get_class(31, actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 502)
            self.assertEqual(attempts, 3)
            self.assertEqual(delays, [0.1, 0.2])
        finally:
            await client.aclose()

    async def test_non_retryable_source_errors_are_not_retried(self):
        attempts = 0
        status_code = 409

        async def handle(_request: httpx.Request):
            nonlocal attempts
            attempts += 1
            return httpx.Response(status_code, json={"code": "source_error"})

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            for expected in (401, 403, 404, 409, 422):
                status_code = expected
                attempts = 0
                with self.assertRaises(HTTPException) as error:
                    await gateway.get_class(31, actor_profile_id=9)
                self.assertEqual(error.exception.status_code, expected)
                self.assertEqual(attempts, 1)
        finally:
            await client.aclose()

    async def test_contest_methods_use_teacher_and_class_contract_paths(self):
        paths = []

        async def handle(request: httpx.Request):
            paths.append((request.url.path, dict(request.url.params)))
            return httpx.Response(200, json={
                "items": [], "next_cursor": None, "has_more": False,
                "as_of": "2026-10-12T00:00:00Z",
            })

        client = httpx.AsyncClient(
            base_url="https://source.example/integration/v1/",
            transport=httpx.MockTransport(handle),
        )
        gateway = HttpSourceGateway("https://source.example/integration/v1", "token", client=client)
        try:
            teacher_page = await gateway.list_teacher_contests(
                9, actor_profile_id=9, state="active", cursor="c1", limit=10,
            )
            class_page = await gateway.list_class_contests(
                31, actor_profile_id=9, state="upcoming", limit=10,
            )
        finally:
            await client.aclose()

        self.assertEqual(paths[0][0], "/integration/v1/teachers/9/contests")
        self.assertEqual(paths[0][1], {"state": "active", "cursor": "c1", "limit": "10"})
        self.assertEqual(paths[1][0], "/integration/v1/classes/31/contests")
        self.assertEqual(paths[1][1], {"state": "upcoming", "limit": "10"})
        self.assertFalse(teacher_page.has_more)
        self.assertFalse(class_page.items)

    async def test_fastapi_state_gateway_override_is_used(self):
        sentinel = object()
        app = FastAPI()
        app.state.source_gateway = sentinel
        request = Request({"type": "http", "app": app, "headers": [], "query_string": b""})
        self.assertIs(get_source_gateway(request), sentinel)

    async def test_catalog_methods_serialize_filters_and_bulk_ids_in_one_request(self):
        seen = []

        async def handle(request: httpx.Request):
            seen.append(request)
            if request.url.path.endswith("/tags"):
                return httpx.Response(200, headers={"ETag": '"tags-v1"'}, json={
                    "items": [{"tag_id": 2, "key": "dp", "title": "Dynamic programming",
                               "updated_at": None}],
                    "next_cursor": "tags-next", "has_more": True, "total": 8,
                    "catalog_version": "v1", "as_of": "2026-10-13T00:00:00Z",
                })
            if request.url.path.endswith("/problems"):
                return httpx.Response(200, json={
                    "items": [{"problem_id": 3, "code": "SUM", "title": "Sum", "description": None,
                               "points": 100, "time_limit": 1, "memory_limit": 65536,
                               "group_id": 4, "tag_ids": [2], "updated_at": None, "version": 1}],
                    "next_cursor": "problems-next", "has_more": False, "total": 1,
                    "catalog_version": "v1", "as_of": "2026-10-13T00:00:00Z",
                })
            return httpx.Response(200, json={
                "items": [{"group_id": 4, "key": "basics", "title": "Basics"}],
                "next_cursor": None, "has_more": False, "total": 1,
                "as_of": "2026-10-13T00:00:00Z",
            })

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "catalog-token", client=client)
        try:
            tags, etag, not_modified = await gateway.list_tags(
                actor_profile_id=9, cursor="opaque-tag-cursor", limit=30)
            problems = await gateway.list_problems(
                actor_profile_id=9, cursor="opaque-problem-cursor", limit=10,
                q="graph", tag_id=2, group_id=4, ids=[3, 7, 9], fields="summary")
            after_id_page = await gateway.list_problems(actor_profile_id=9, after_id=11, limit=10)
            groups = await gateway.list_problem_groups(
                actor_profile_id=9, cursor="opaque-group-cursor", limit=20)
        finally:
            await client.aclose()

        self.assertFalse(not_modified)
        self.assertEqual(etag, '"tags-v1"')
        self.assertEqual(tags.items[0].tag_id, 2)
        self.assertEqual(tags.next_cursor, "tags-next")
        self.assertEqual(problems.items[0].problem_id, 3)
        self.assertEqual(problems.items[0].tag_ids, [2])
        self.assertIsNone(problems.items[0].description)
        self.assertEqual(groups.items[0].key, "basics")
        # Metadata for multiple IDs is fetched in one bulk request, never one request per ID.
        problem_requests = [request for request in seen if request.url.path.endswith("/problems")
                            and request.url.params.get_list("ids")]
        self.assertEqual(len(problem_requests), 1)
        problem_request = problem_requests[0]
        self.assertEqual(problem_request.url.params.get_list("ids"), ["3", "7", "9"])
        self.assertEqual(problem_request.url.params["cursor"], "opaque-problem-cursor")
        after_id_requests = [request for request in seen if request.url.path.endswith("/problems")
                             and "after_id" in request.url.params]
        self.assertEqual(len(after_id_requests), 1)
        self.assertEqual(after_id_requests[0].url.params["after_id"], "11")
        self.assertIsNotNone(after_id_page)
        self.assertEqual(problem_request.url.params["q"], "graph")
        self.assertEqual(problem_request.url.params["tag_id"], "2")
        self.assertEqual(problem_request.url.params["group_id"], "4")
        self.assertEqual(problem_request.url.params["fields"], "summary")
        for request in seen:
            self.assertEqual(request.headers["Authorization"], "Bearer catalog-token")
            self.assertEqual(request.headers["X-Actor-Profile-Id"], "9")
            self.assertTrue(request.headers["X-Request-Id"])

    async def test_catalog_etag_304_and_malformed_response(self):
        seen = []
        mode = "not-modified"

        async def handle(request: httpx.Request):
            nonlocal mode
            seen.append(request)
            if mode == "not-modified":
                return httpx.Response(304, headers={"ETag": '"catalog-v4"'})
            if mode == "valid":
                return httpx.Response(200, headers={"ETag": '"catalog-v4"'}, json={
                    "catalog_version": "v4", "total_problem_count": 4, "tagged_problem_count": 3,
                    "tag_problem_counts": [{"tag_id": 2, "distinct_problem_count": 3,
                                            "example_titles": ["Sum"]}],
                    "group_problem_counts": [{"group_id": 4, "distinct_problem_count": 2}],
                    "as_of": "2026-10-13T00:00:00Z",
                })
            return httpx.Response(200, headers={"ETag": '"catalog-v4"'}, json={"catalog_version": "bad"})

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "catalog-token", client=client)
        try:
            catalog, etag, unchanged = await gateway.get_analytics_catalog(
                actor_profile_id=9, if_none_match='"catalog-v4"')
            self.assertIsNone(catalog)
            self.assertEqual(etag, '"catalog-v4"')
            self.assertTrue(unchanged)
            self.assertEqual(seen[0].headers["If-None-Match"], '"catalog-v4"')
            mode = "valid"
            catalog, etag, unchanged = await gateway.get_analytics_catalog(actor_profile_id=9)
            self.assertFalse(unchanged)
            self.assertEqual(etag, '"catalog-v4"')
            self.assertEqual(catalog.total_problem_count, 4)
            self.assertEqual(catalog.tagged_problem_count, 3)
            self.assertEqual(catalog.tag_problem_counts[0].example_titles, ["Sum"])
            mode = "malformed"
            with self.assertRaises(HTTPException) as error:
                await gateway.get_analytics_catalog(actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 502)
            self.assertEqual(error.exception.detail,
                             "Dịch vụ dữ liệu nguồn trả dữ liệu không đúng hợp đồng.")
        finally:
            await client.aclose()

    async def test_empty_problem_id_filter_does_not_fetch_catalog(self):
        calls = []

        async def handle(request: httpx.Request):
            calls.append(request)
            return httpx.Response(500)

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "catalog-token", client=client)
        try:
            page = await gateway.list_problems(actor_profile_id=9, ids=[])
        finally:
            await client.aclose()
        self.assertEqual(page.items, [])
        self.assertEqual(page.total, 0)
        self.assertFalse(page.has_more)
        self.assertEqual(calls, [])

    async def test_student_aggregate_serialization_dto_and_idempotent_retry(self):
        requests = []
        delays = []
        attempts = 0

        async def fake_sleep(delay: float):
            delays.append(delay)

        async def handle(request: httpx.Request):
            nonlocal attempts
            attempts += 1
            requests.append(request)
            if attempts == 1:
                return httpx.Response(503, json={"code": "temporary"})
            return httpx.Response(200, json={
                "students": [{
                    "profile_id": 9, "total_submissions": 7, "solved_unique_count": 2,
                    "last_submission_at": "2026-10-13T00:00:00Z", "verdict_counts": {"AC": 2, "WA": 5},
                    "tag_stats": [{"tag_id": 2, "problem_count": 3, "solved_unique_count": 1,
                                   "attempted_unique_count": 2, "verdict_counts": {"AC": 1, "WA": 2}}],
                    "group_stats": [{"group_id": 4, "solved_unique_count": 1}],
                    "requested_group_stats": [{"key": "dp", "solved_unique_count": 1,
                                                "attempted_unique_count": 2}],
                    "problem_facts": [{
                        "problem_id": 31, "tag_ids": [2], "group_id": 4, "attempt_count": 3,
                        "ac_count": 1, "first_ac_submission_id": 90,
                        "first_ac_at": "2026-10-12T23:00:00Z", "failed_before_first_ac_count": 2,
                        "best_ac_time": 0.03, "last_submission_at": "2026-10-13T00:00:00Z",
                        "verdict_counts": {"AC": 1, "WA": 2},
                    }],
                }],
                "as_of": "2026-10-13T00:00:01Z", "reference_now": "2026-10-13T00:00:00Z",
                "catalog_version": "catalog-7",
            })

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "analytics-token",
                                    client=client, sleep=fake_sleep)
        try:
            result = await gateway.aggregate_students(
                [9], actor_profile_id=9,
                date_from=datetime(2026, 10, 1, 3, tzinfo=timezone.utc),
                date_to=datetime(2026, 10, 14, 3, tzinfo=timezone.utc),
                tag_groups=[{"key": "dp", "tag_ids": [2, 8]}], include_problem_facts=True,
            )
        finally:
            await client.aclose()

        self.assertEqual(attempts, 2)
        self.assertEqual(delays, [0.1])
        self.assertEqual(result.reference_now, datetime(2026, 10, 13, tzinfo=timezone.utc))
        self.assertEqual(result.as_of, datetime(2026, 10, 13, 0, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(result.catalog_version, "catalog-7")
        self.assertEqual(result.students[0].tag_stats[0].verdict_counts["WA"], 2)
        self.assertEqual(result.students[0].problem_facts[0].first_ac_submission_id, 90)
        for request in requests:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/integration/v1/analytics/students/aggregate")
            self.assertEqual(request.headers["Authorization"], "Bearer analytics-token")
            self.assertEqual(request.headers["X-Actor-Profile-Id"], "9")
            self.assertTrue(request.headers["X-Request-Id"])
        payload = requests[1].read().decode()
        self.assertEqual(payload, '{"profile_ids":[9],"from":"2026-10-01T03:00:00Z","to":"2026-10-14T03:00:00Z","tag_groups":[{"key":"dp","tag_ids":[2,8]}],"include_problem_facts":true}')

    async def test_empty_aggregate_is_local_and_oversized_input_is_rejected(self):
        calls = []

        async def handle(request: httpx.Request):
            calls.append(request)
            return httpx.Response(500)

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "analytics-token", client=client)
        try:
            empty = await gateway.aggregate_students([], actor_profile_id=9)
            self.assertEqual(empty.students, [])
            self.assertIsNone(empty.as_of)
            self.assertIsNone(empty.reference_now)
            self.assertIsNone(empty.catalog_version)
            with self.assertRaises(HTTPException) as error:
                await gateway.aggregate_students(list(range(1, 102)), actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 422)
            with self.assertRaises(HTTPException) as duplicate_error:
                await gateway.aggregate_students([9, 9], actor_profile_id=9)
            self.assertEqual(duplicate_error.exception.status_code, 422)
            with self.assertRaises(HTTPException) as invalid_error:
                await gateway.aggregate_students([0], actor_profile_id=9)
            self.assertEqual(invalid_error.exception.status_code, 422)
        finally:
            await client.aclose()
        self.assertEqual(calls, [])

    async def test_problem_facts_pagination_auth_errors_and_malformed_payload(self):
        seen = []
        mode = "ok"

        async def handle(request: httpx.Request):
            nonlocal mode
            seen.append(request)
            if mode == "forbidden":
                return httpx.Response(403, json={"code": "forbidden"})
            if mode == "malformed":
                return httpx.Response(200, json={"items": [{"problem_id": "bad"}]})
            return httpx.Response(200, json={
                "items": [{"problem_id": 31, "tag_ids": [2], "group_id": 4,
                            "attempt_count": 2, "ac_count": 0, "first_ac_submission_id": None,
                            "first_ac_at": None, "failed_before_first_ac_count": 2,
                            "best_ac_time": None, "last_submission_at": "2026-10-13T00:00:00Z",
                            "verdict_counts": {"WA": 2}}],
                "next_cursor": "opaque-facts-next", "has_more": True, "total": 7,
                "as_of": "2026-10-13T00:00:01Z", "catalog_version": "catalog-7",
            })

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "analytics-token", client=client)
        try:
            page = await gateway.list_student_problem_facts(
                9, actor_profile_id=9,
                date_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
                date_to=datetime(2026, 10, 14, tzinfo=timezone.utc),
                cursor="opaque-current", limit=50,
            )
            self.assertEqual(page.items[0].problem_id, 31)
            self.assertEqual(page.next_cursor, "opaque-facts-next")
            self.assertTrue(page.has_more)
            self.assertEqual(page.catalog_version, "catalog-7")
            self.assertEqual(seen[0].url.params["from"], "2026-10-01T00:00:00Z")
            self.assertEqual(seen[0].url.params["to"], "2026-10-14T00:00:00Z")
            self.assertEqual(seen[0].url.params["cursor"], "opaque-current")
            self.assertEqual(seen[0].url.params["limit"], "50")
            self.assertEqual(seen[0].headers["Authorization"], "Bearer analytics-token")
            self.assertEqual(seen[0].headers["X-Actor-Profile-Id"], "9")
            mode = "forbidden"
            with self.assertRaises(HTTPException) as forbidden:
                await gateway.list_student_problem_facts(9, actor_profile_id=9)
            self.assertEqual(forbidden.exception.status_code, 403)
            mode = "malformed"
            with self.assertRaises(HTTPException) as malformed:
                await gateway.list_student_problem_facts(9, actor_profile_id=9)
            self.assertEqual(malformed.exception.status_code, 502)
        finally:
            await client.aclose()

    async def test_tag_etag_is_forwarded_and_provider_not_found_is_preserved(self):
        seen = []
        status = 200

        async def handle(request: httpx.Request):
            seen.append(request)
            if status == 404:
                return httpx.Response(404, json={"code": "not_found"})
            if request.headers.get("If-None-Match"):
                return httpx.Response(304, headers={"ETag": '"tag-v2"'})
            return httpx.Response(200, headers={"ETag": '"tag-v2"'}, json={
                "items": [{"tag_id": 14, "key": "algebra", "title": "Algebra"}],
                "catalog_version": "tag-v2", "next_cursor": None, "has_more": False,
                "total": 1, "as_of": "2026-10-13T00:00:00Z",
            })

        client = httpx.AsyncClient(base_url="https://source.example/integration/v1/",
                                   transport=httpx.MockTransport(handle))
        gateway = HttpSourceGateway("https://source.example/integration/v1", "catalog-token", client=client)
        try:
            page, etag, unchanged = await gateway.list_tags(
                actor_profile_id=9, if_none_match='"tag-v2"')
            self.assertIsNone(page)
            self.assertEqual(etag, '"tag-v2"')
            self.assertTrue(unchanged)
            self.assertEqual(seen[0].headers["If-None-Match"], '"tag-v2"')
            page, etag, unchanged = await gateway.list_tags(
                actor_profile_id=9, cursor="opaque-next", if_none_match='"tag-v2"')
            self.assertFalse(unchanged)
            self.assertEqual(page.items[0].tag_id, 14)
            self.assertNotIn("If-None-Match", seen[1].headers)
            status = 404
            with self.assertRaises(HTTPException) as error:
                await gateway.list_tags(actor_profile_id=9)
            self.assertEqual(error.exception.status_code, 404)
        finally:
            await client.aclose()

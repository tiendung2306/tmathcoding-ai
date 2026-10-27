"""HTTP boundary for source owned profile, class, and student data."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import uuid
from typing import Any, Awaitable, Callable, Literal, Protocol, runtime_checkable

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings


def _validate_source_response(model, payload):
    try:
        return model.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả dữ liệu không đúng hợp đồng.") from exc


def _utc_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class SourceAccess(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_id: int
    exists: bool
    is_active: bool
    is_super_admin: bool
    roles: list[str] = Field(default_factory=list)
    version: str | int | None = None
    as_of: datetime | None = None


class SourceSchoolYear(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: date | None = None
    finish: date | None = None


class SourceManager(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_id: int
    name: str


class SourceClass(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_id: int
    name: str | None = None
    school_year: SourceSchoolYear | None = None
    created_at: datetime | None = None
    member_count: int = 0
    managers: list[SourceManager] = Field(default_factory=list)
    has_active_contest: bool = False
    active_contest_ids: list[int] = Field(default_factory=list)
    updated_at: datetime | None = None


class SourceStudentClass(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_id: int
    name: str


class SourceStudent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_id: int
    name: str | None = None
    username: str | None = None
    points: float = 0
    rank: int | None = None
    problem_count: int = 0
    display_rank: str = "user"
    updated_at: datetime | None = None
    avatar_url: str | None = None
    joined_at: datetime | None = None
    performance_points: float | None = None
    classes: list[SourceStudentClass] = Field(default_factory=list)


class SourceContest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contest_id: int
    code: str
    title: str
    class_ids: list[int] = Field(default_factory=list)
    starts_at: datetime
    ends_at: datetime
    status: str
    is_public: bool
    updated_at: datetime | None = None


class SourceContestPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceContest]
    next_cursor: str | None = None
    has_more: bool = False
    as_of: datetime


class SourceLanguage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    key: str | None = None
    name: str | None = None
    common_name: str | None = None


class SourceTestcase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case: int | None = None
    status: str | None = None
    time: float | None = None
    memory: float | None = None
    points: float | None = None
    total: float | None = None
    feedback: str | None = None
    output: str | None = None


class SourceSubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submission_id: int
    profile_id: int
    student_name: str | None = None
    problem_id: int
    problem_code: str | None = None
    problem_title: str | None = None
    language_id: int | None = None
    language: SourceLanguage | None = None
    result: str | None = None
    status: str | None = None
    points: float | None = None
    time: float | None = None
    memory: float | None = None
    submitted_at: datetime
    has_source: bool = False
    version: str | None = None
    updated_at: datetime | None = None


class SourceSubmissionPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceSubmission]
    next_cursor: str | None = None
    has_more: bool = False
    total: int
    high_watermark: str | None = None
    max_submission_id: int | None = None
    as_of: datetime


class SourceSubmissionDetail(SourceSubmission):
    model_config = ConfigDict(extra="ignore")

    source_code: str | None = None
    testcases: list[SourceTestcase] = Field(default_factory=list)


class SourceSubmissionChange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: int
    kind: Literal["created", "updated", "deleted"]
    submission_id: int
    version: int
    changed_at: datetime
    record: SourceSubmission | None = None


class SourceSubmissionChangesPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: list[SourceSubmissionChange]
    next_cursor: str | None = None
    has_more: bool
    high_watermark: int
    as_of: datetime


class SourceProblem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem_id: int
    code: str | None = None
    title: str | None = None
    name: str | None = None
    description: str | None = None
    points: float | None = None
    time_limit: float | None = None
    memory_limit: int | None = None
    group_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    updated_at: datetime | None = None
    version: str | int | None = None


class SourceTag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tag_id: int
    key: str
    title: str
    updated_at: datetime | None = None


class SourceProblemGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    group_id: int
    key: str
    title: str


class SourceTagPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceTag]
    next_cursor: str | None = None
    has_more: bool = False
    catalog_version: str | int | None = None
    as_of: datetime | None = None


class SourceProblemGroupPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceProblemGroup]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
    as_of: datetime | None = None


class SourceProblemPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceProblem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None
    as_of: datetime | None = None
    catalog_version: str | int | None = None


class SourceTagProblemCount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tag_id: int
    distinct_problem_count: int
    example_titles: list[str] = Field(default_factory=list)


class SourceGroupProblemCount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    group_id: int
    distinct_problem_count: int


class SourceAnalyticsCatalog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    catalog_version: str | int
    total_problem_count: int
    tagged_problem_count: int
    tag_problem_counts: list[SourceTagProblemCount] = Field(default_factory=list)
    group_problem_counts: list[SourceGroupProblemCount] = Field(default_factory=list)
    as_of: datetime


class SourceTagGroupRequest(BaseModel):
    key: str
    tag_ids: list[int]


class SourceTagAggregateStat(BaseModel):
    tag_id: int
    problem_count: int
    solved_unique_count: int
    attempted_unique_count: int
    verdict_counts: dict[str, int]


class SourceGroupAggregateStat(BaseModel):
    group_id: int
    solved_unique_count: int


class SourceRequestedGroupAggregateStat(BaseModel):
    key: str
    solved_unique_count: int
    attempted_unique_count: int


class SourceProblemFact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem_id: int
    tag_ids: list[int]
    group_id: int | None
    attempt_count: int
    ac_count: int
    first_ac_submission_id: int | None
    first_ac_at: datetime | None
    failed_before_first_ac_count: int
    best_ac_time: float | None
    first_ac_time: float | None = None
    problem_time_limit: float | None = None
    problem_memory_limit: float | None = None
    rapid_failure_pair_count: int = 0
    last_submission_at: datetime
    verdict_counts: dict[str, int]


class SourceStudentAggregate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_id: int
    total_submissions: int
    solved_unique_count: int
    last_submission_at: datetime | None
    verdict_counts: dict[str, int]
    tag_stats: list[SourceTagAggregateStat]
    group_stats: list[SourceGroupAggregateStat]
    requested_group_stats: list[SourceRequestedGroupAggregateStat]
    problem_facts: list[SourceProblemFact] | None


class SourceStudentAggregateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    students: list[SourceStudentAggregate]
    as_of: datetime | None
    reference_now: datetime | None
    catalog_version: str | int | None


class SourceStudentAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile_id: int
    last_submission_at: datetime | None
    has_stuck_problem: bool


class SourceStudentAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceStudentAlert]
    as_of: datetime
    reference_now: datetime | None


class SourceStudentSubmissionSample(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submission_id: int
    problem_id: int
    tag_ids: list[int]
    submitted_at: datetime
    time: float | None = None
    memory: float | None = None
    problem_time_limit: float | None = None
    problem_memory_limit: float | None = None
    language_key: str | None = None
    source_code: str


class SourceStudentSubmissionSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceStudentSubmissionSample]
    as_of: datetime


class SourceAcceptedSample(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submission_id: int
    language_key: str | None = None
    source_code: str
    points: float | None = None
    time: float | None = None
    memory: float | None = None
    submitted_at: datetime


class SourceAcceptedSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceAcceptedSample]
    as_of: datetime


class SourceProblemFactsPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[SourceProblemFact]
    next_cursor: str | None
    has_more: bool
    total: int
    as_of: datetime
    catalog_version: str | int


class SourcePage[T](BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[T]
    next_cursor: str | None
    has_more: bool
    total: int
    as_of: datetime


@runtime_checkable
class SourceGateway(Protocol):
    async def get_access(self, profile_id: int, *, actor_profile_id: int) -> SourceAccess: ...
    async def list_classes(self, profile_id: int, *, actor_profile_id: int, q: str | None,
                           cursor: str | None, limit: int, sort: str, order: str,
                           virtual_active_class_ids: list[int], starred_class_ids: list[int]) -> SourcePage[SourceClass]: ...
    async def get_class(self, class_id: int, *, actor_profile_id: int) -> SourceClass: ...
    async def list_students(self, profile_id: int, *, actor_profile_id: int, q: str | None,
                            cursor: str | None, limit: int, sort: str = "name") -> SourcePage[SourceStudent]: ...
    async def list_class_students(self, class_id: int, *, actor_profile_id: int,
                                  cursor: str | None, limit: int) -> SourcePage[SourceStudent]: ...
    async def get_student(self, profile_id: int, *, actor_profile_id: int) -> SourceStudent: ...
    async def list_teacher_contests(self, profile_id: int, *, actor_profile_id: int, state: str,
                                    at: datetime | None, cursor: str | None, limit: int,
                                    q: str | None = None) -> SourceContestPage: ...
    async def get_teacher_contest(self, profile_id: int, contest_id: int, *, actor_profile_id: int) -> SourceContest: ...
    async def list_class_contests(self, class_id: int, *, actor_profile_id: int, state: str,
                                  at: datetime | None, cursor: str | None, limit: int) -> SourceContestPage: ...
    async def list_student_submissions(self, profile_id: int, *, actor_profile_id: int,
                                      date_from: datetime | None, date_to: datetime | None,
                                      result: str | None, only_with_source: bool | None,
                                      problem_id: int | None, exclude_result: str | None,
                                      cursor: str | None,
                                      limit: int, sort: str) -> SourceSubmissionPage: ...
    async def list_class_submissions(self, class_id: int, *, actor_profile_id: int,
                                     date_from: datetime | None, date_to: datetime | None,
                                     after_submission_id: int | None, cursor: str | None,
                                     limit: int) -> SourceSubmissionPage: ...
    async def list_class_submission_changes(self, class_id: int, *, actor_profile_id: int,
                                            cursor: str | None, date_from: datetime | None,
                                            date_to: datetime | None, limit: int) -> SourceSubmissionChangesPage: ...
    async def get_submission(self, submission_id: int, *, actor_profile_id: int,
                             include_source: bool, include_testcases: bool) -> SourceSubmissionDetail: ...
    async def get_problem(self, problem_id: int, *, actor_profile_id: int) -> SourceProblem: ...
    async def list_tags(self, *, actor_profile_id: int, cursor: str | None, limit: int,
                        if_none_match: str | None = None) -> tuple[SourceTagPage | None, str | None, bool]: ...
    async def list_problems(self, *, actor_profile_id: int, cursor: str | None, after_id: int | None,
                            limit: int, q: str | None = None, tag_id: int | None = None,
                            group_id: int | None = None, ids: list[int] | None = None,
                            fields: Literal["summary", "full"] = "summary") -> SourceProblemPage: ...
    async def list_problem_groups(self, *, actor_profile_id: int, cursor: str | None,
                                  limit: int) -> SourceProblemGroupPage: ...
    async def get_analytics_catalog(self, *, actor_profile_id: int, if_none_match: str | None = None
                                    ) -> tuple[SourceAnalyticsCatalog | None, str | None, bool]: ...
    async def aggregate_students(self, profile_ids: list[int], *, actor_profile_id: int,
                                 date_from: datetime | None, date_to: datetime | None,
                                 tag_groups: list[SourceTagGroupRequest],
                                 include_problem_facts: bool = False) -> SourceStudentAggregateResponse: ...
    async def list_student_problem_facts(self, profile_id: int, *, actor_profile_id: int,
                                         date_from: datetime | None, date_to: datetime | None,
                                         cursor: str | None, limit: int) -> SourceProblemFactsPage: ...
    async def get_student_alerts(self, profile_ids: list[int], *, actor_profile_id: int,
                                 at: datetime) -> SourceStudentAlertsResponse: ...
    async def list_student_submission_samples(self, profile_id: int, *, actor_profile_id: int,
                                              date_from: datetime | None, date_to: datetime | None,
                                              tag_ids: list[int], result: str = "AC",
                                              per_group_limit: int = 3) -> SourceStudentSubmissionSamplesResponse: ...
    async def get_problem_accepted_samples(self, problem_id: int, *, actor_profile_id: int,
                                           limit: int = 3) -> SourceAcceptedSamplesResponse: ...


class HttpSourceGateway:
    def __init__(self, base_url: str, token: str, timeout_seconds: float = 8.0,
                 client: httpx.AsyncClient | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 max_retries: int = 2, base_backoff_seconds: float = 0.1,
                 max_retry_after_seconds: float = 5.0):
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(timeout_seconds),
        )
        self._token = token
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(20)
        self._sleep = sleep
        self._clock = clock
        self._max_retries = max(0, max_retries)
        self._base_backoff_seconds = max(0.0, base_backoff_seconds)
        self._max_retry_after_seconds = max(0.0, max_retry_after_seconds)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _retry_after_seconds(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                now = self._clock()
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                seconds = (retry_at - now).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None
        return min(self._max_retry_after_seconds, max(0.0, seconds))

    def _backoff_seconds(self, retry_index: int) -> float:
        return min(self._max_retry_after_seconds, self._base_backoff_seconds * (2 ** retry_index))

    async def _request(self, method: str, path: str, *, actor_profile_id: int,
                       json: dict[str, Any] | None = None, params: dict[str, Any] | None = None,
                       idempotent: bool = False, extra_headers: dict[str, str] | None = None,
                       return_response: bool = False):
        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Actor-Profile-Id": str(actor_profile_id),
            "X-Request-Id": str(uuid.uuid4()),
        }
        if extra_headers:
            headers.update(extra_headers)
        method = method.upper()
        if params is not None:
            params = {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in params.items()
                if value is not None and value != ""
            }
        retryable = method in {"GET", "HEAD", "OPTIONS"} or method == "POST" and idempotent
        max_attempts = self._max_retries + 1 if retryable else 1
        async with self._semaphore:
            for attempt in range(max_attempts):
                try:
                    response = await self._client.request(method, path, json=json, params=params, headers=headers)
                except httpx.TimeoutException as exc:
                    if attempt + 1 < max_attempts:
                        await self._sleep(self._backoff_seconds(attempt))
                        continue
                    raise HTTPException(503, "Dịch vụ dữ liệu nguồn đang phản hồi chậm.") from exc
                except httpx.HTTPError as exc:
                    if attempt + 1 < max_attempts:
                        await self._sleep(self._backoff_seconds(attempt))
                        continue
                    raise HTTPException(502, "Không thể kết nối dịch vụ dữ liệu nguồn.") from exc
                is_retryable_status = response.status_code == 429 or response.status_code >= 500
                if retryable and is_retryable_status and attempt + 1 < max_attempts:
                    delay = self._retry_after_seconds(response.headers.get("Retry-After"))
                    await self._sleep(delay if delay is not None else self._backoff_seconds(attempt))
                    continue
                if response.status_code in (401, 403, 404, 409, 422, 429):
                    detail = {
                        401: "Dịch vụ dữ liệu nguồn từ chối xác thực.",
                        403: "Không có quyền truy cập dữ liệu nguồn.",
                        404: "Không tìm thấy dữ liệu nguồn.",
                        409: "Cursor dữ liệu nguồn hết hạn hoặc không còn hợp lệ.",
                        422: "Dữ liệu gửi đến dịch vụ nguồn không hợp lệ hoặc vượt giới hạn.",
                        429: "Dịch vụ dữ liệu nguồn đang giới hạn yêu cầu.",
                    }[response.status_code]
                    headers = {}
                    if response.status_code == 429 and response.headers.get("Retry-After"):
                        headers["Retry-After"] = response.headers["Retry-After"]
                    raise HTTPException(response.status_code, detail, headers=headers)
                if return_response:
                    if response.is_error:
                        raise HTTPException(502, "Dịch vụ dữ liệu nguồn gặp lỗi.")
                    return response
                if response.is_error:
                    raise HTTPException(502, "Dịch vụ dữ liệu nguồn gặp lỗi.")
                try:
                    return response.json()
                except (ValueError, TypeError) as exc:
                    raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả nội dung JSON không hợp lệ.") from exc
        raise HTTPException(502, "Dịch vụ dữ liệu nguồn gặp lỗi.")

    async def get_access(self, profile_id: int, *, actor_profile_id: int) -> SourceAccess:
        raw = await self._request("GET", f"profiles/{profile_id}/access", actor_profile_id=actor_profile_id)
        return _validate_source_response(SourceAccess, raw)

    async def list_classes(self, profile_id: int, *, actor_profile_id: int, q: str | None = None,
                           cursor: str | None = None, limit: int = 24, sort: str = "created_at",
                           order: str = "desc", virtual_active_class_ids: list[int] | None = None,
                           starred_class_ids: list[int] | None = None) -> SourcePage[SourceClass]:
        raw = await self._request("POST", f"teachers/{profile_id}/classes/query", actor_profile_id=actor_profile_id,
            json={"q": q or None, "cursor": cursor, "limit": limit, "sort": sort, "order": order,
                  "virtual_active_class_ids": virtual_active_class_ids or [], "starred_class_ids": starred_class_ids or []},
            idempotent=True)
        return _validate_source_response(SourcePage[SourceClass], raw)

    async def get_class(self, class_id: int, *, actor_profile_id: int) -> SourceClass:
        raw = await self._request("GET", f"classes/{class_id}", actor_profile_id=actor_profile_id)
        return _validate_source_response(SourceClass, raw)

    async def list_students(self, profile_id: int, *, actor_profile_id: int, q: str | None = None,
                            cursor: str | None = None, limit: int = 24,
                            sort: str = "name") -> SourcePage[SourceStudent]:
        raw = await self._request("GET", f"teachers/{profile_id}/students", actor_profile_id=actor_profile_id,
                                  params={"q": q or None, "cursor": cursor, "limit": limit, "sort": sort})
        return _validate_source_response(SourcePage[SourceStudent], raw)

    async def list_class_students(self, class_id: int, *, actor_profile_id: int,
                                  cursor: str | None = None, limit: int = 100) -> SourcePage[SourceStudent]:
        raw = await self._request("GET", f"classes/{class_id}/students", actor_profile_id=actor_profile_id,
                                  params={"cursor": cursor, "limit": limit})
        return _validate_source_response(SourcePage[SourceStudent], raw)

    async def get_student(self, profile_id: int, *, actor_profile_id: int) -> SourceStudent:
        raw = await self._request("GET", f"students/{profile_id}", actor_profile_id=actor_profile_id)
        return _validate_source_response(SourceStudent, raw)

    async def list_teacher_contests(self, profile_id: int, *, actor_profile_id: int, state: str = "all",
                                    at: datetime | None = None, cursor: str | None = None,
                                    limit: int = 24, q: str | None = None) -> SourceContestPage:
        params = {"state": state, "at": at, "cursor": cursor, "limit": limit,
                  "q": q or None}
        raw = await self._request("GET", f"teachers/{profile_id}/contests", actor_profile_id=actor_profile_id,
                                  params={key: value for key, value in params.items() if value is not None})
        return _validate_source_response(SourceContestPage, raw)

    async def get_teacher_contest(self, profile_id: int, contest_id: int, *, actor_profile_id: int) -> SourceContest:
        raw = await self._request("GET", f"teachers/{profile_id}/contests/{contest_id}",
                                  actor_profile_id=actor_profile_id)
        return _validate_source_response(SourceContest, raw)

    async def list_class_contests(self, class_id: int, *, actor_profile_id: int, state: str = "all",
                                  at: datetime | None = None, cursor: str | None = None,
                                  limit: int = 24) -> SourceContestPage:
        params = {"state": state, "at": at, "cursor": cursor, "limit": limit}
        raw = await self._request("GET", f"classes/{class_id}/contests", actor_profile_id=actor_profile_id,
                                  params={key: value for key, value in params.items() if value is not None})
        return _validate_source_response(SourceContestPage, raw)

    async def list_student_submissions(self, profile_id: int, *, actor_profile_id: int,
                                       date_from: datetime | None = None, date_to: datetime | None = None,
                                       result: str | None = None, only_with_source: bool | None = None,
                                       problem_id: int | None = None, exclude_result: str | None = None,
                                       cursor: str | None = None,
                                       limit: int = 50, sort: str = "desc") -> SourceSubmissionPage:
        params = {
            "from": date_from, "to": date_to, "result": result,
            "only_with_source": only_with_source, "problem_id": problem_id,
            "exclude_result": exclude_result,
            "cursor": cursor, "limit": limit, "sort": sort,
        }
        raw = await self._request("GET", f"students/{profile_id}/submissions", actor_profile_id=actor_profile_id,
                                  params={key: value for key, value in params.items() if value is not None})
        return _validate_source_response(SourceSubmissionPage, raw)

    async def list_class_submissions(self, class_id: int, *, actor_profile_id: int,
                                     date_from: datetime | None = None, date_to: datetime | None = None,
                                     after_submission_id: int | None = None, cursor: str | None = None,
                                     limit: int = 50) -> SourceSubmissionPage:
        params = {
            "from": date_from, "to": date_to, "after_submission_id": after_submission_id,
            "cursor": cursor, "limit": limit,
        }
        raw = await self._request("GET", f"classes/{class_id}/submissions", actor_profile_id=actor_profile_id,
                                  params={key: value for key, value in params.items() if value is not None})
        return _validate_source_response(SourceSubmissionPage, raw)

    async def list_class_submission_changes(self, class_id: int, *, actor_profile_id: int,
                                            cursor: str | None = None, date_from: datetime | None = None,
                                            date_to: datetime | None = None,
                                            limit: int = 100) -> SourceSubmissionChangesPage:
        params = {"cursor": cursor, "from": date_from, "to": date_to, "limit": limit}
        raw = await self._request("GET", f"classes/{class_id}/submission-changes",
                                  actor_profile_id=actor_profile_id,
                                  params={key: value for key, value in params.items() if value is not None})
        return _validate_source_response(SourceSubmissionChangesPage, raw)

    async def get_submission(self, submission_id: int, *, actor_profile_id: int,
                             include_source: bool = False,
                             include_testcases: bool = False) -> SourceSubmissionDetail:
        included = []
        if include_source:
            included.append("source")
        if include_testcases:
            included.append("testcases")
        params = {"include": ",".join(included)} if included else {}
        raw = await self._request("GET", f"submissions/{submission_id}", actor_profile_id=actor_profile_id,
                                  params=params)
        return _validate_source_response(SourceSubmissionDetail, raw)

    async def get_problem(self, problem_id: int, *, actor_profile_id: int) -> SourceProblem:
        raw = await self._request("GET", f"problems/{problem_id}", actor_profile_id=actor_profile_id)
        return _validate_source_response(SourceProblem, raw)

    async def list_tags(self, *, actor_profile_id: int, cursor: str | None = None, limit: int = 100,
                        if_none_match: str | None = None
                        ) -> tuple[SourceTagPage | None, str | None, bool]:
        headers = {"If-None-Match": if_none_match} if if_none_match and cursor is None else None
        response = await self._request("GET", "tags", actor_profile_id=actor_profile_id,
                                       params={"cursor": cursor, "limit": limit},
                                       extra_headers=headers, return_response=True)
        etag = response.headers.get("ETag")
        if response.status_code == 304:
            return None, etag, True
        try:
            raw = response.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả nội dung JSON không hợp lệ.") from exc
        return _validate_source_response(SourceTagPage, raw), etag, False

    async def list_problems(self, *, actor_profile_id: int, cursor: str | None = None,
                            after_id: int | None = None, limit: int = 100, q: str | None = None,
                            tag_id: int | None = None, group_id: int | None = None,
                            ids: list[int] | None = None,
                            fields: Literal["summary", "full"] = "summary") -> SourceProblemPage:
        params: dict[str, Any] = {
            "cursor": cursor, "after_id": after_id if cursor is None else None, "limit": limit, "q": q,
            "tag_id": tag_id, "group_id": group_id, "fields": fields,
        }
        if ids:
            params["ids"] = ids
        elif ids == []:
            # An explicitly empty ID filter means no matches; omitting it would
            # accidentally turn a bulk lookup into a full catalog request.
            return SourceProblemPage(items=[], next_cursor=None, has_more=False, total=0,
                                     as_of=datetime.now(timezone.utc))
        raw = await self._request("GET", "problems", actor_profile_id=actor_profile_id, params=params)
        return _validate_source_response(SourceProblemPage, raw)

    async def list_problem_groups(self, *, actor_profile_id: int, cursor: str | None = None,
                                  limit: int = 100) -> SourceProblemGroupPage:
        raw = await self._request("GET", "problem-groups", actor_profile_id=actor_profile_id,
                                  params={"cursor": cursor, "limit": limit})
        return _validate_source_response(SourceProblemGroupPage, raw)

    async def get_analytics_catalog(self, *, actor_profile_id: int, if_none_match: str | None = None
                                    ) -> tuple[SourceAnalyticsCatalog | None, str | None, bool]:
        headers = {"If-None-Match": if_none_match} if if_none_match else None
        response = await self._request("GET", "analytics/catalog", actor_profile_id=actor_profile_id,
                                       extra_headers=headers, return_response=True)
        etag = response.headers.get("ETag")
        if response.status_code == 304:
            return None, etag, True
        try:
            raw = response.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả nội dung JSON không hợp lệ.") from exc
        return _validate_source_response(SourceAnalyticsCatalog, raw), etag, False

    async def aggregate_students(self, profile_ids: list[int], *, actor_profile_id: int,
                                 date_from: datetime | None = None, date_to: datetime | None = None,
                                 tag_groups: list[SourceTagGroupRequest] | None = None,
                                 include_problem_facts: bool = False) -> SourceStudentAggregateResponse:
        if not profile_ids:
            return SourceStudentAggregateResponse(
                students=[], as_of=None, reference_now=None, catalog_version=None,
            )
        if len(profile_ids) > 100 or any(profile_id < 1 for profile_id in profile_ids):
            raise HTTPException(422, "Danh sách học sinh phải có tối đa 100 ID hợp lệ.")
        if len(set(profile_ids)) != len(profile_ids):
            raise HTTPException(422, "Danh sách học sinh không được lặp ID.")
        body = {
            "profile_ids": profile_ids,
            "from": _utc_z(date_from),
            "to": _utc_z(date_to),
            "tag_groups": [
                group.model_dump() if isinstance(group, SourceTagGroupRequest) else group
                for group in (tag_groups or [])
            ],
            "include_problem_facts": include_problem_facts,
        }
        raw = await self._request(
            "POST", "analytics/students/aggregate", actor_profile_id=actor_profile_id,
            json=body, idempotent=True,
        )
        return _validate_source_response(SourceStudentAggregateResponse, raw)

    async def list_student_problem_facts(self, profile_id: int, *, actor_profile_id: int,
                                         date_from: datetime | None = None,
                                         date_to: datetime | None = None,
                                         cursor: str | None = None,
                                         limit: int = 100) -> SourceProblemFactsPage:
        raw = await self._request(
            "GET", f"students/{profile_id}/problem-facts", actor_profile_id=actor_profile_id,
            params={"from": _utc_z(date_from), "to": _utc_z(date_to),
                    "cursor": cursor, "limit": limit},
        )
        return _validate_source_response(SourceProblemFactsPage, raw)

    async def get_student_alerts(self, profile_ids: list[int], *, actor_profile_id: int,
                                 at: datetime) -> SourceStudentAlertsResponse:
        if not profile_ids:
            return SourceStudentAlertsResponse(items=[], as_of=at, reference_now=at)
        if len(profile_ids) > 100 or any(profile_id < 1 for profile_id in profile_ids):
            raise HTTPException(422, "Danh sách học sinh phải có tối đa 100 ID hợp lệ.")
        if len(set(profile_ids)) != len(profile_ids):
            raise HTTPException(422, "Danh sách học sinh không được lặp ID.")
        raw = await self._request(
            "POST", "analytics/students/alerts", actor_profile_id=actor_profile_id,
            json={"profile_ids": profile_ids, "at": _utc_z(at)}, idempotent=True,
        )
        return _validate_source_response(SourceStudentAlertsResponse, raw)

    async def list_student_submission_samples(self, profile_id: int, *, actor_profile_id: int,
                                              date_from: datetime | None = None,
                                              date_to: datetime | None = None,
                                              tag_ids: list[int], result: str = "AC",
                                              per_group_limit: int = 3) -> SourceStudentSubmissionSamplesResponse:
        raw = await self._request(
            "GET", f"students/{profile_id}/submission-samples", actor_profile_id=actor_profile_id,
            params={"from": _utc_z(date_from), "to": _utc_z(date_to), "tag_ids": tag_ids,
                    "result": result, "per_group_limit": per_group_limit},
        )
        return _validate_source_response(SourceStudentSubmissionSamplesResponse, raw)

    async def get_problem_accepted_samples(self, problem_id: int, *, actor_profile_id: int,
                                           limit: int = 3) -> SourceAcceptedSamplesResponse:
        raw = await self._request(
            "GET", f"problems/{problem_id}/accepted-samples", actor_profile_id=actor_profile_id,
            params={"limit": limit},
        )
        return _validate_source_response(SourceAcceptedSamplesResponse, raw)


_source_gateway: HttpSourceGateway | None = None


def get_source_gateway_client() -> HttpSourceGateway:
    """Return the shared HTTP gateway for request handlers and background workers."""
    global _source_gateway
    if _source_gateway is None:
        base_url = getattr(settings, "SOURCE_API_BASE_URL", "")
        token = getattr(settings, "SOURCE_API_TOKEN", "")
        if not base_url or not token:
            raise RuntimeError("SOURCE_API_BASE_URL and SOURCE_API_TOKEN must be configured")
        _source_gateway = HttpSourceGateway(
            base_url, token, getattr(settings, "SOURCE_API_TIMEOUT_SECONDS", 8.0),
        )
    return _source_gateway


def get_source_gateway(request: Request) -> SourceGateway:
    """FastAPI dependency; app.state override supports isolated tests and deployments."""
    configured = getattr(request.app.state, "source_gateway", None)
    return configured if configured is not None else get_source_gateway_client()


async def close_source_gateway() -> None:
    global _source_gateway
    if _source_gateway is not None:
        await _source_gateway.close()
        _source_gateway = None

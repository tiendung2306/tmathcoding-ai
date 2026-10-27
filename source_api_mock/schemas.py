from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SchoolYear(APIModel):
    start: date
    finish: date


class Manager(APIModel):
    profile_id: int
    name: str


class ClassItem(APIModel):
    class_id: int
    name: str
    school_year: SchoolYear | None
    created_at: datetime | None
    member_count: int
    managers: list[Manager]
    has_active_contest: bool = False
    active_contest_ids: list[int] = Field(default_factory=list)
    updated_at: datetime | None = None


class StudentItem(APIModel):
    profile_id: int
    name: str
    username: str
    points: float
    rank: int | None = None
    problem_count: int
    display_rank: str
    updated_at: datetime | None = None


class ClassStudent(StudentItem):
    avatar_url: str | None = None
    joined_at: datetime | None = None


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
    has_more: bool
    total: int
    as_of: datetime


class TagItem(BaseModel):
    tag_id: int
    key: str
    title: str
    updated_at: datetime | None = None


class TagPage(BaseModel):
    items: list[TagItem]
    catalog_version: str
    next_cursor: str | None = None
    has_more: bool
    total: int
    as_of: datetime


class ProblemGroupItem(BaseModel):
    group_id: int
    key: str
    title: str


class ProblemGroupPage(BaseModel):
    items: list[ProblemGroupItem]
    catalog_version: str
    next_cursor: str | None = None
    has_more: bool
    total: int
    as_of: datetime


class ProblemPage(BaseModel):
    items: list[ProblemItem]
    catalog_version: str
    next_cursor: str | None = None
    has_more: bool
    total: int
    as_of: datetime


class TagProblemCount(BaseModel):
    tag_id: int
    distinct_problem_count: int
    example_titles: list[str]


class GroupProblemCount(BaseModel):
    group_id: int
    distinct_problem_count: int


class CatalogSummary(BaseModel):
    catalog_version: str
    total_problem_count: int
    tagged_problem_count: int
    tag_problem_counts: list[TagProblemCount]
    group_problem_counts: list[GroupProblemCount]
    as_of: datetime


class TagProblemPools(BaseModel):
    catalog_version: str
    tag_problem_ids: dict[int, list[int]]


class RequestedTagGroup(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    tag_ids: list[int] = Field(max_length=100)

    @field_validator("key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("key must not be blank")
        return value

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("tag_ids must be positive IDs")
        return values


class StudentAggregateRequest(BaseModel):
    profile_ids: list[int] = Field(min_length=1, max_length=100)
    from_at: datetime | None = Field(default=None, alias="from")
    to_at: datetime | None = Field(default=None, alias="to")
    tag_groups: list[RequestedTagGroup] = Field(default_factory=list, max_length=100)
    include_problem_facts: bool = False

    @model_validator(mode="after")
    def unique_group_keys(self):
        keys = [group.key for group in self.tag_groups]
        if len(set(keys)) != len(keys):
            raise ValueError("tag_groups keys must be unique")
        return self


class StudentTagStat(BaseModel):
    tag_id: int
    problem_count: int
    solved_unique_count: int
    attempted_unique_count: int
    verdict_counts: dict[str, int]


class StudentGroupStat(BaseModel):
    group_id: int
    solved_unique_count: int


class RequestedGroupStat(BaseModel):
    key: str
    solved_unique_count: int
    attempted_unique_count: int


class ProblemFact(BaseModel):
    problem_id: int
    tag_ids: list[int]
    group_id: int | None = None
    attempt_count: int
    ac_count: int
    first_ac_submission_id: int | None = None
    first_ac_at: datetime | None = None
    failed_before_first_ac_count: int
    best_ac_time: float | None = None
    first_ac_time: float | None = None
    problem_time_limit: float | None = None
    problem_memory_limit: int | None = None
    rapid_failure_pair_count: int = 0
    last_submission_at: datetime
    verdict_counts: dict[str, int]


class StudentAggregateItem(BaseModel):
    profile_id: int
    total_submissions: int
    solved_unique_count: int
    last_submission_at: datetime | None = None
    verdict_counts: dict[str, int]
    tag_stats: list[StudentTagStat]
    group_stats: list[StudentGroupStat]
    requested_group_stats: list[RequestedGroupStat]
    problem_facts: list[ProblemFact] | None = None


class StudentAggregateResponse(BaseModel):
    students: list[StudentAggregateItem]
    as_of: datetime
    reference_now: datetime | None = None
    catalog_version: str


class ProblemFactsPage(BaseModel):
    items: list[ProblemFact]
    next_cursor: str | None = None
    has_more: bool
    total: int
    as_of: datetime
    catalog_version: str


class Access(APIModel):
    profile_id: int
    exists: bool
    is_active: bool
    is_super_admin: bool
    roles: list[str]
    version: str | None = None
    as_of: datetime


class ClassQuery(BaseModel):
    q: str | None = None
    cursor: str | None = None
    limit: int = Field(default=24, ge=1, le=100)
    sort: str = Field(default="name", pattern="^(name|created_at|member_count|id)$")
    order: str = Field(default="asc", pattern="^(asc|desc)$")
    virtual_active_class_ids: list[int] = Field(default_factory=list)
    starred_class_ids: list[int] = Field(default_factory=list)


class LanguageItem(BaseModel):
    id: int
    key: str | None = None
    name: str | None = None
    common_name: str | None = None


class TestcaseItem(BaseModel):
    case: int | None = None
    status: str | None = None
    time: float | None = None
    memory: float | None = None
    points: float | None = None
    total: float | None = None
    feedback: str | None = None
    output: str | None = None


class SubmissionItem(BaseModel):
    submission_id: int
    profile_id: int
    student_name: str | None = None
    problem_id: int
    problem_code: str | None = None
    problem_title: str | None = None
    language_id: int | None = None
    language: LanguageItem | None = None
    result: str | None = None
    status: str | None = None
    points: float | None = None
    time: float | None = None
    memory: float | None = None
    submitted_at: datetime
    has_source: bool
    version: str | None = None
    updated_at: datetime | None = None


class SubmissionPage(BaseModel):
    items: list[SubmissionItem]
    next_cursor: str | None = None
    has_more: bool = False
    total: int
    high_watermark: str | None = None
    max_submission_id: int | None = None
    as_of: datetime


class SubmissionDetail(SubmissionItem):
    source_code: str | None = None
    testcases: list[TestcaseItem] = Field(default_factory=list)


class AcceptedSample(BaseModel):
    submission_id: int
    language_key: str | None = None
    source_code: str
    points: float | None = None
    time: float | None = None
    memory: float | None = None
    submitted_at: datetime


class AcceptedSamplesResponse(BaseModel):
    items: list[AcceptedSample]
    as_of: datetime


class StudentSubmissionSample(BaseModel):
    submission_id: int
    problem_id: int
    tag_ids: list[int]
    submitted_at: datetime
    time: float | None = None
    memory: float | None = None
    problem_time_limit: float | None = None
    problem_memory_limit: int | None = None
    language_key: str | None = None
    source_code: str


class StudentSubmissionSamplesResponse(BaseModel):
    items: list[StudentSubmissionSample]
    as_of: datetime


class StudentAlertItem(BaseModel):
    profile_id: int
    last_submission_at: datetime | None = None
    has_stuck_problem: bool


class StudentAlertsRequest(BaseModel):
    profile_ids: list[int] = Field(min_length=1, max_length=100)
    at: datetime


class StudentAlertsResponse(BaseModel):
    items: list[StudentAlertItem]
    as_of: datetime
    reference_now: datetime | None = None


class SubmissionChange(BaseModel):
    event_id: int
    kind: str
    submission_id: int
    version: int
    changed_at: datetime
    record: SubmissionItem | None = None


class SubmissionChangesPage(BaseModel):
    events: list[SubmissionChange]
    next_cursor: str | None = None
    has_more: bool
    high_watermark: int
    as_of: datetime


class ProblemItem(BaseModel):
    problem_id: int
    code: str | None = None
    title: str
    name: str | None = None
    description: str | None = None
    points: float | None = None
    time_limit: float | None = None
    memory_limit: int | None = None
    group_id: int | None = None
    is_public: bool
    tag_ids: list[int] = Field(default_factory=list)
    updated_at: datetime | None = None
    version: int | str | None = None


class ContestItem(BaseModel):
    contest_id: int
    code: str
    title: str
    class_ids: list[int]
    starts_at: datetime
    ends_at: datetime
    status: str
    is_public: bool
    updated_at: datetime | None = None
    version: int | str | None = None


class ContestPage(BaseModel):
    items: list[ContestItem]
    next_cursor: str | None = None
    has_more: bool = False
    as_of: datetime


class StudentClass(BaseModel):
    class_id: int
    name: str


class StudentDetail(StudentItem):
    classes: list[StudentClass]


class APIError(BaseModel):
    code: str
    message: str
    request_id: str | None = None

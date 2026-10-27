"""Standalone, read-only API mock for the tmathcoding source database."""
import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Integer, String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from .database import get_session_factory
from .models import (
    contest, contest_author, contest_curator, contest_organization,
    language, organization, organization_admin, problem, problem_group, problem_type,
    problem_type_catalog, profile, profile_organization, school_year, submission,
    submission_source, submission_testcase, user,
)
from .schemas import (
    APIError, Access, AcceptedSample, AcceptedSamplesResponse, CatalogSummary, ClassItem, ClassQuery, ClassStudent, ContestPage,
    GroupProblemCount, LanguageItem, Manager, Page, ProblemGroupItem, ProblemGroupPage,
    ProblemItem, ProblemPage, SchoolYear, StudentDetail, StudentItem, TagItem, TagPage,
    TagProblemCount, ProblemFact, ProblemFactsPage, RequestedGroupStat,
    StudentAggregateItem, StudentAggregateRequest, StudentAggregateResponse, ContestItem,
    StudentGroupStat, StudentTagStat,
    SubmissionChange, SubmissionChangesPage, SubmissionDetail, SubmissionItem,
    SubmissionPage, StudentSubmissionSample, StudentSubmissionSamplesResponse,
    StudentAlertsRequest, StudentAlertsResponse, StudentAlertItem, TestcaseItem,
)

app = FastAPI(title="tmathcoding Source API Mock", version="1.0.0", openapi_url="/integration/v1/openapi.json")
API_PREFIX = "/integration/v1"
logger = logging.getLogger(__name__)
source_bearer = HTTPBearer(scheme_name="SourceServiceBearer", auto_error=False)
_change_lock = threading.RLock()
_change_epoch = os.urandom(16).hex()
_change_snapshots: dict[int, dict[int, dict]] = {}
_change_logs: dict[int, list[dict]] = {}
_change_last_id: dict[int, int] = {}
_change_versions: dict[tuple[int, int], int] = {}
_change_markers: dict[int, tuple] = {}
_change_last_reconciled: dict[int, float] = {}
_change_log_limit = 20_000

ERROR_DESCRIPTIONS = {
    401: "Missing or invalid service token.",
    403: "Actor is not authorized for this resource.",
    404: "Resource does not exist or is outside the actor's visible scope.",
    409: "Cursor is expired or does not match the query snapshot.",
    422: "Request parameters or body failed validation.",
    429: "Request rate limit exceeded.",
    500: "Unexpected internal service error.",
    502: "Upstream source service failed.",
    503: "Source service is temporarily unavailable.",
}
ERROR_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "cursor_expired",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}


def error_responses(*statuses: int):
    responses = {}
    for status in statuses:
        response = {
            "model": APIError,
            "description": ERROR_DESCRIPTIONS[status],
            "content": {"application/json": {"example": {
                "code": ERROR_CODES[status],
                "message": ERROR_DESCRIPTIONS[status],
                "request_id": "req-example",
            }}},
        }
        if status == 429:
            response["headers"] = {
                "Retry-After": {
                    "description": "Seconds until another request may be made.",
                    "schema": {"type": "string", "example": "30"},
                },
            }
        responses[status] = response
    return responses


COMMON_ERROR_RESPONSES = error_responses(401, 403, 422, 429, 500, 502, 503)
ETAG_HEADERS = {
    "ETag": {"description": "Opaque version of the visible source catalog.",
             "schema": {"type": "string", "example": '"abc123"'}}
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def escaped_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_db():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def actor_profile_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(source_bearer),
    x_actor_profile_id: int | None = Header(default=None, alias="X-Actor-Profile-Id"),
) -> int:
    expected = os.getenv("SOURCE_API_TOKEN", "")
    provided = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    actor_mapping = os.getenv("SOURCE_API_ALLOWED_ACTORS", "")
    allowed = actor_mapping.strip() == "*" or (
        x_actor_profile_id is not None
        and x_actor_profile_id in {int(part) for part in actor_mapping.split(",") if part.strip().isdigit()}
    )
    if not expected or provided != expected:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Invalid service token"})
    if x_actor_profile_id is None or not allowed:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Actor is not mapped to this service token"})
    return x_actor_profile_id


def profile_row(db: Session, profile_id: int):
    return db.execute(select(profile).where(profile.c.id == profile_id)).mappings().first()


def is_super_admin(db: Session, profile_id: int) -> bool:
    row = profile_row(db, profile_id)
    return bool(row and row["super_admin"])


def require_actor_profile(db: Session, actor_id: int, requested_id: int):
    if actor_id != requested_id and not is_super_admin(db, actor_id):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Actor cannot act for this profile"})


def visible_class(db: Session, class_id: int, actor_id: int):
    stmt = select(organization).where(organization.c.id == class_id)
    if not is_super_admin(db, actor_id):
        stmt = stmt.where(select(organization_admin.c.id).where(
            organization_admin.c.organization_id == organization.c.id,
            organization_admin.c.profile_id == actor_id,
        ).exists())
    row = db.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Class not found"})
    return row


def cursor_secret() -> bytes:
    return os.getenv("SOURCE_API_CURSOR_SECRET", os.getenv("SOURCE_API_TOKEN", "local-cursor-secret")).encode()


def fingerprint(items) -> str:
    values = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items]
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def encode_cursor(offset: int, resource: str, scope: str, snapshot: str, **extra) -> str:
    payload = json.dumps({"offset": offset, "resource": resource, "scope": scope, "snapshot": snapshot,
                          "issued_at": int(time.time()), **extra},
                         sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(cursor_secret(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + b"." + signature).decode().rstrip("=")


def cursor_payload(cursor: str, resource: str, scope: str | None, snapshot: str | None = None) -> dict:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode() + b"=" * (-len(cursor) % 4))
        if len(decoded) < 34 or decoded[-33:-32] != b".":
            raise ValueError
        payload, signature = decoded[:-33], decoded[-32:]
        expected = hmac.new(cursor_secret(), payload, hashlib.sha256).digest()
        data = json.loads(payload)
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        if data["resource"] != resource or (scope is not None and data["scope"] != scope):
            raise ValueError
        if snapshot is not None and data["snapshot"] != snapshot:
            raise ValueError
        ttl = int(os.getenv("SOURCE_API_CURSOR_TTL_SECONDS", "900"))
        if int(time.time()) - int(data["issued_at"]) > ttl:
            raise ValueError
        return data
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, binascii.Error):
        raise HTTPException(status_code=409, detail={"code": "cursor_expired", "message": "Cursor expired or does not match this query"})


def cursor_offset(cursor: str | None, resource: str, scope: str, snapshot: str) -> int:
    if not cursor or not str(cursor).strip():
        return 0
    try:
        offset = int(cursor_payload(cursor, resource, scope, snapshot)["offset"])
        if offset < 0:
            raise ValueError
        return offset
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=409, detail={"code": "cursor_expired", "message": "Cursor expired or does not match this query"})


def page_result(items, total: int, offset: int, limit: int, resource: str, scope: str, snapshot: str):
    has_more = offset + len(items) < total
    next_cursor = encode_cursor(offset + len(items), resource, scope, snapshot) if has_more else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more, "total": total, "as_of": utc_now()}


def managed_class_ids(db: Session, actor_id: int):
    if is_super_admin(db, actor_id):
        return None
    return set(db.execute(select(organization_admin.c.organization_id).where(
        organization_admin.c.profile_id == actor_id
    )).scalars())


def student_visible(db: Session, student_id: int, actor_id: int) -> bool:
    if is_super_admin(db, actor_id):
        return db.execute(select(profile_organization.c.id).where(
            profile_organization.c.profile_id == student_id,
        ).limit(1)).first() is not None
    allowed_classes = managed_class_ids(db, actor_id) or set()
    return db.execute(select(profile_organization.c.id).where(
        profile_organization.c.profile_id == student_id,
        profile_organization.c.organization_id.in_(allowed_classes or [-1]),
    ).limit(1)).first() is not None


def submission_visible(db: Session, student_id: int, actor_id: int) -> bool:
    if student_id == actor_id or is_super_admin(db, actor_id):
        return True
    return student_visible(db, student_id, actor_id)


def source_scope_allows(actor_id: int) -> bool:
    configured = os.getenv("SOURCE_API_SOURCE_ACTORS", "")
    return configured.strip() == "*" or actor_id in {
        int(part) for part in configured.split(",") if part.strip().isdigit()
    }


def testcase_scope_allows(actor_id: int) -> bool:
    configured = os.getenv("SOURCE_API_TESTCASE_ACTORS")
    if configured is None or not configured.strip():
        return source_scope_allows(actor_id)
    return configured.strip() == "*" or actor_id in {
        int(part) for part in configured.split(",") if part.strip().isdigit()
    }


def submission_rows(db: Session, *, class_id: int | None = None, profile_id: int | None = None,
                    submission_id: int | None = None, submission_ids: list[int] | None = None,
                    from_at: datetime | None = None, to_at: datetime | None = None,
                    offset: int | None = None, limit: int | None = None,
                    class_order: bool = False, after_submission_id: int | None = None,
                    after_key: tuple[datetime, int] | None = None,
                    student_order: str | None = None, result: str | None = None,
                    exclude_result: str | None = None, problem_id: int | None = None,
                    only_with_source: bool = False):
    has_source = select(submission_source.c.id).where(
        submission_source.c.submission_id == submission.c.id,
    ).exists()
    stmt = select(
        submission.c.id.label("submission_id"), submission.c.user_id.label("profile_id"),
        profile.c.name.label("student_name"), submission.c.problem_id,
        problem.c.code.label("problem_code"), problem.c.name.label("problem_title"),
        submission.c.language_id, language.c.key.label("language_key"),
        language.c.name.label("language_name"), language.c.common_name.label("language_common_name"),
        submission.c.result, submission.c.status, submission.c.points, submission.c.time,
        submission.c.memory, submission.c.date.label("submitted_at"),
        submission.c.judged_date, submission.c.rejudged_date, submission.c.version_update,
        has_source.label("has_source"),
    ).select_from(
        submission.join(profile, profile.c.id == submission.c.user_id)
        .outerjoin(problem, problem.c.id == submission.c.problem_id)
        .outerjoin(language, language.c.id == submission.c.language_id)
    )
    if class_id is not None:
        stmt = stmt.join(profile_organization, profile_organization.c.profile_id == submission.c.user_id).where(
            profile_organization.c.organization_id == class_id,
        )
    if profile_id is not None:
        stmt = stmt.where(submission.c.user_id == profile_id)
    if result is not None:
        stmt = stmt.where(submission.c.result == result)
    if exclude_result is not None:
        stmt = stmt.where(or_(submission.c.result != exclude_result, submission.c.result.is_(None)))
    if problem_id is not None:
        stmt = stmt.where(submission.c.problem_id == problem_id)
    if only_with_source:
        stmt = stmt.where(has_source)
    if submission_id is not None:
        stmt = stmt.where(submission.c.id == submission_id)
    if submission_ids is not None:
        stmt = stmt.where(submission.c.id.in_(submission_ids or [-1]))
    if after_submission_id is not None:
        stmt = stmt.where(submission.c.id > after_submission_id)
    if after_key is not None:
        last_date = as_utc(after_key[0]).replace(tzinfo=None)
        stmt = stmt.where(or_(
            submission.c.date < last_date,
            and_(submission.c.date == last_date, submission.c.id < after_key[1]),
        ))
    if from_at is not None:
        stmt = stmt.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        stmt = stmt.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    if student_order is not None:
        ordering = submission.c.date.desc() if student_order == "desc" else submission.c.date.asc()
        tie_breaker = submission.c.id.desc() if student_order == "desc" else submission.c.id.asc()
        stmt = stmt.where(submission.c.date.is_not(None)).order_by(ordering, tie_breaker)
    elif class_order:
        stmt = stmt.order_by(submission.c.date.desc(), submission.c.id.desc())
    else:
        stmt = stmt.order_by(submission.c.id.asc())
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).mappings())


def submission_item(row, *, include_student_name: bool = False) -> dict:
    updated = row["rejudged_date"] or row["judged_date"]
    version = row["version_update"]
    if version is None and updated is not None:
        version = as_utc(updated).isoformat()
    item = {
        "submission_id": row["submission_id"],
        "profile_id": row["profile_id"],
        "problem_id": row["problem_id"],
        "problem_code": row["problem_code"],
        "problem_title": row["problem_title"],
        "language_id": row["language_id"],
        "language": ({
            "id": row["language_id"], "key": row["language_key"],
            "name": row["language_name"], "common_name": row["language_common_name"],
        } if row["language_id"] is not None else None),
        "result": row["result"], "status": row["status"],
        "points": float(row["points"]) if row["points"] is not None else None,
        "time": float(row["time"]) if row["time"] is not None else None,
        "memory": float(row["memory"]) if row["memory"] is not None else None,
        "submitted_at": as_utc(row["submitted_at"]),
        "has_source": bool(row["has_source"]),
        "version": str(version) if version is not None else None,
        "updated_at": as_utc(updated),
    }
    if include_student_name:
        item["student_name"] = row["student_name"] or f"Profile {row['profile_id']}"
    return item


def _within_dates(value: datetime, from_at: datetime | None, to_at: datetime | None) -> bool:
    timestamp = as_utc(value)
    return (from_at is None or timestamp >= as_utc(from_at)) and (to_at is None or timestamp < as_utc(to_at))


def _validated_dates(from_at: datetime | None, to_at: datetime | None):
    if from_at is not None and to_at is not None and as_utc(from_at) > as_utc(to_at):
        raise HTTPException(status_code=422, detail={
            "code": "validation_error", "message": "from must be earlier than or equal to to",
        })


def _date_filtered_items(rows, from_at: datetime | None, to_at: datetime | None, *, include_student_name=False):
    items = [submission_item(row, include_student_name=include_student_name) for row in rows
             if row["submitted_at"] is not None and _within_dates(row["submitted_at"], from_at, to_at)]
    return items


def _class_submission_marker(db: Session, class_id: int) -> tuple:
    stmt = select(
        func.count(submission.c.id), func.max(submission.c.id), func.sum(submission.c.id),
        func.sum(cast(submission.c.version_update, Integer)),
        func.sum(case((submission.c.result == "AC", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "WA", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "TLE", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "MLE", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "RTE", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "CE", submission.c.id), else_=0)),
        func.sum(case((submission.c.result == "IE", submission.c.id), else_=0)),
        func.sum(case((submission.c.status == "D", submission.c.id), else_=0)),
        func.sum(case((submission.c.status == "IE", submission.c.id), else_=0)),
        func.sum(submission.c.points), func.sum(submission.c.time), func.sum(submission.c.memory),
    ).select_from(submission.join(
        profile_organization, profile_organization.c.profile_id == submission.c.user_id,
    )).where(profile_organization.c.organization_id == class_id)
    values = db.execute(stmt).one()
    count, max_id, sum_ids, sum_versions = values[:4]
    return (
        int(count or 0), int(max_id) if max_id is not None else None,
        int(sum_ids or 0), int(sum_versions or 0),
        *(float(value or 0) for value in values[4:]),
    )


def _class_submission_metadata(db: Session, class_id: int) -> dict[int, dict]:
    stmt = select(
        submission.c.id.label("submission_id"), submission.c.date.label("submitted_at"),
        submission.c.version_update, submission.c.result, submission.c.status,
        submission.c.points, submission.c.time, submission.c.memory,
        submission.c.judged_date, submission.c.rejudged_date,
    ).select_from(submission.join(
        profile_organization, profile_organization.c.profile_id == submission.c.user_id,
    )).where(profile_organization.c.organization_id == class_id)
    return {
        row["submission_id"]: {
            "submitted_at": as_utc(row["submitted_at"]),
            "marker": (
                str(row["version_update"]), row["result"], row["status"],
                row["points"], row["time"], row["memory"],
                row["judged_date"], row["rejudged_date"],
            ),
        }
        for row in db.execute(stmt).mappings()
    }


def _class_submission_count(db: Session, class_id: int,
                            from_at: datetime | None = None,
                            to_at: datetime | None = None,
                            after_submission_id: int | None = None) -> int:
    stmt = select(func.count(submission.c.id)).select_from(submission.join(
        profile_organization, profile_organization.c.profile_id == submission.c.user_id,
    )).where(profile_organization.c.organization_id == class_id)
    if from_at is not None:
        stmt = stmt.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        stmt = stmt.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    if after_submission_id is not None:
        stmt = stmt.where(submission.c.id > after_submission_id)
    return int(db.execute(stmt).scalar_one() or 0)


def _student_submission_snapshot(
    db: Session, profile_id: int, *, from_at: datetime | None = None,
    to_at: datetime | None = None, result: str | None = None,
    exclude_result: str | None = None, problem_id: int | None = None,
    only_with_source: bool = False,
) -> tuple[int, tuple]:
    source_exists = select(submission_source.c.id).where(
        submission_source.c.submission_id == submission.c.id,
    ).exists()
    stmt = select(
        func.count(submission.c.id), func.max(submission.c.id), func.sum(submission.c.id),
        func.sum(submission.c.points), func.sum(submission.c.time), func.sum(submission.c.memory),
        func.min(submission.c.date), func.max(submission.c.date),
        func.max(submission.c.judged_date), func.max(submission.c.rejudged_date),
        func.max(submission.c.version_update),
        func.sum(case((submission.c.result == "AC", 1), else_=0)),
        func.sum(case((submission.c.result == "WA", 1), else_=0)),
        func.sum(case((submission.c.result == "TLE", 1), else_=0)),
        func.sum(case((submission.c.status == "D", 1), else_=0)),
        func.sum(case((submission.c.status == "IE", 1), else_=0)),
    ).where(submission.c.user_id == profile_id, submission.c.date.is_not(None))
    if from_at is not None:
        stmt = stmt.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        stmt = stmt.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    if result is not None:
        stmt = stmt.where(submission.c.result == result)
    if exclude_result is not None:
        stmt = stmt.where(or_(submission.c.result != exclude_result, submission.c.result.is_(None)))
    if problem_id is not None:
        stmt = stmt.where(submission.c.problem_id == problem_id)
    if only_with_source:
        stmt = stmt.where(source_exists)
    values = db.execute(stmt).one()
    total = int(values[0] or 0)
    return total, tuple(values[1:])


def _ensure_change_baseline(db: Session, class_id: int) -> int:
    if class_id not in _change_snapshots:
        metadata_rows = _class_submission_metadata(db, class_id)
        _change_snapshots[class_id] = {
            submission_id: {"record": None, **row}
            for submission_id, row in metadata_rows.items()
        }
        _change_markers[class_id] = _class_submission_marker(db, class_id)
        _change_last_reconciled[class_id] = time.monotonic()
        _change_logs.setdefault(class_id, [])
        _change_last_id.setdefault(class_id, 0)
    return _change_last_id.get(class_id, 0)


def _append_change(class_id: int, kind: str, submission_id: int,
                   record: dict | None, submitted_at: datetime | None):
    event_id = _change_last_id.get(class_id, 0) + 1
    _change_last_id[class_id] = event_id
    version = _change_versions.get((class_id, submission_id), 0) + 1
    _change_versions[(class_id, submission_id)] = version
    log = _change_logs.setdefault(class_id, [])
    log.append({
        "event_id": event_id, "kind": kind, "submission_id": submission_id,
        "version": version, "changed_at": utc_now(), "record": record,
        "submitted_at": submitted_at,
    })
    if len(log) > _change_log_limit:
        del log[:-_change_log_limit]


def _refresh_class_change_log(db: Session, class_id: int) -> int:
    _ensure_change_baseline(db, class_id)
    marker = _class_submission_marker(db, class_id)
    reconcile_interval = max(1, int(os.getenv("SOURCE_API_RECONCILE_INTERVAL_SECONDS", "10")))
    reconciliation_due = time.monotonic() - _change_last_reconciled.get(class_id, 0) >= reconcile_interval
    if marker == _change_markers.get(class_id) and not reconciliation_due:
        return _change_last_id.get(class_id, 0)

    previous = _change_snapshots[class_id]
    current_metadata = _class_submission_metadata(db, class_id)
    current_ids = set(current_metadata)
    previous_ids = set(previous)
    changed_ids = {
        submission_id for submission_id, current in current_metadata.items()
        if submission_id not in previous or current["marker"] != previous[submission_id]["marker"]
    }
    removed_ids = previous_ids - current_ids
    changed_rows = submission_rows(db, class_id=class_id, submission_ids=list(changed_ids)) if changed_ids else []
    records = {row["submission_id"]: submission_item(row, include_student_name=True) for row in changed_rows}

    for submission_id in sorted(changed_ids):
        metadata = current_metadata[submission_id]
        old = previous.get(submission_id)
        kind = "updated" if old is not None else "created"
        record = records.get(submission_id)
        if record is None:
            continue
        _append_change(class_id, kind, submission_id, record, metadata["submitted_at"])
        metadata["record"] = record
    for submission_id in sorted(removed_ids):
        old = previous[submission_id]
        _append_change(class_id, "deleted", submission_id, None, old.get("submitted_at"))
    for submission_id, metadata in current_metadata.items():
        if submission_id not in changed_ids:
            metadata["record"] = previous[submission_id].get("record")
    _change_snapshots[class_id] = current_metadata
    _change_markers[class_id] = marker
    _change_last_reconciled[class_id] = time.monotonic()
    return _change_last_id.get(class_id, 0)


def _change_scope(actor_id: int, class_id: int, from_at: datetime | None, to_at: datetime | None) -> str:
    return json.dumps({
        "actor_id": actor_id, "class_id": class_id,
        "from": as_utc(from_at).isoformat() if from_at else None,
        "to": as_utc(to_at).isoformat() if to_at else None,
        "epoch": _change_epoch,
    }, sort_keys=True, separators=(",", ":"))


def _encode_change_cursor(after_seq: int, through_seq: int, scope: str) -> str:
    payload = json.dumps({
        "resource": "class_submission_changes", "after_seq": after_seq,
        "through_seq": through_seq, "scope": scope, "issued_at": int(time.time()),
    }, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(cursor_secret(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + b"." + signature).decode().rstrip("=")


def _decode_change_cursor(cursor: str, scope: str) -> tuple[int, int]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode() + b"=" * (-len(cursor) % 4))
        if len(decoded) < 34 or decoded[-33:-32] != b".":
            raise ValueError
        payload, signature = decoded[:-33], decoded[-32:]
        data = json.loads(payload)
        expected = hmac.new(cursor_secret(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        if data["resource"] != "class_submission_changes" or data["scope"] != scope:
            raise ValueError
        if int(time.time()) - int(data["issued_at"]) > int(os.getenv("SOURCE_API_CURSOR_TTL_SECONDS", "900")):
            raise ValueError
        after_seq, through_seq = int(data["after_seq"]), int(data["through_seq"])
        if after_seq < 0 or through_seq < after_seq:
            raise ValueError
        return after_seq, through_seq
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, binascii.Error):
        raise HTTPException(status_code=409, detail={
            "code": "cursor_expired", "message": "Cursor expired or does not match this query",
        })


def _sync_class_change_log(class_id: int, items: list[dict]):
    current = {item["submission_id"]: item for item in items}
    previous = _change_snapshots.get(class_id)
    events: list[dict] = []
    if previous is None:
        events = [("created", submission_id, item) for submission_id, item in current.items()]
    else:
        for submission_id, item in current.items():
            old = previous.get(submission_id)
            if old is None:
                events.append(("created", submission_id, item))
            elif old["record"] is None or old["record"] != item:
                events.append(("updated", submission_id, item))
        for submission_id, old in previous.items():
            if submission_id not in current:
                events.append(("deleted", submission_id, None))
    for kind, submission_id, item in sorted(events, key=lambda e: e[1]):
        prior = previous.get(submission_id) if previous is not None else None
        submitted_at = item.get("submitted_at") if item else (
            (prior or {}).get("record") or {}
        ).get("submitted_at") or (prior or {}).get("submitted_at")
        event_kind = "created" if kind == "updated" and prior and prior.get("record") is None else kind
        _append_change(class_id, event_kind, submission_id, item, submitted_at)
    _change_snapshots[class_id] = {
        submission_id: {
            "record": item, "submitted_at": item.get("submitted_at"),
            "marker": (item.get("version"), item.get("updated_at"), None),
        }
        for submission_id, item in current.items()
    }
    log = _change_logs.setdefault(class_id, [])
    return _change_last_id.get(class_id, 0), log[0]["event_id"] if log else 1


def _change_cursor_floor(class_id: int) -> int:
    log = _change_logs.get(class_id, [])
    return log[0]["event_id"] if log else _change_last_id.get(class_id, 0) + 1


def _change_event_in_range(event: dict, from_at: datetime | None, to_at: datetime | None) -> bool:
    timestamp = event.get("submitted_at")
    if timestamp is None:
        return False
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return _within_dates(timestamp, from_at, to_at)


def student_item(row) -> dict:
    email = (row.get("email") or "").strip().lower()
    avatar_url = None
    if email:
        email_hash = hashlib.md5(email.encode("utf-8"), usedforsecurity=False).hexdigest()
        avatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=96"
    return {
        "profile_id": row["profile_id"], "name": (row["name"] or f"Profile {row['profile_id']}"),
        "username": row["username"] or f"user_{row['profile_id']}", "points": float(row["points"] or 0),
        "problem_count": int(row["problem_count"] or 0), "display_rank": row["display_rank"] or "user",
        "rank": row.get("rank"),
        "updated_at": None, "avatar_url": avatar_url,
    }


def contest_owner_ids(db: Session, profile_id: int) -> set[int]:
    authored = db.execute(select(contest_author.c.contest_id).where(contest_author.c.profile_id == profile_id)).scalars()
    curated = db.execute(select(contest_curator.c.contest_id).where(contest_curator.c.profile_id == profile_id)).scalars()
    return set(authored) | set(curated)


def contest_mappings(db: Session, contest_ids: list[int], class_scope: set[int] | None = None):
    if not contest_ids:
        return {}
    stmt = select(contest_organization.c.contest_id, contest_organization.c.organization_id).where(
        contest_organization.c.contest_id.in_(contest_ids)
    )
    if class_scope is not None:
        stmt = stmt.where(contest_organization.c.organization_id.in_(class_scope or {-1}))
    mapping = {}
    for contest_id, class_id in db.execute(stmt):
        mapping.setdefault(contest_id, []).append(class_id)
    return mapping


def contest_status(row, at: datetime) -> str:
    start, end, now = as_utc(row["start_time"]), as_utc(row["end_time"]), as_utc(at)
    if start is not None and end is not None and start <= now < end:
        return "active"
    if start is not None and start > now:
        return "upcoming"
    return "ended"


def active_contests_by_class(db: Session, class_ids: list[int], profile_id: int,
                             actor_id: int | None = None, at: datetime | None = None):
    if not class_ids:
        return {}
    now = as_utc(at or utc_now())
    rows = {row["id"]: row for row in db.execute(
        select(contest).join(contest_organization, contest_organization.c.contest_id == contest.c.id)
        .where(contest_organization.c.organization_id.in_(class_ids))
    ).mappings()}
    owners = contest_owner_ids(db, profile_id)
    visible_classes = {}
    for contest_id, class_id in db.execute(select(contest_organization.c.contest_id,
        contest_organization.c.organization_id).where(contest_organization.c.organization_id.in_(class_ids))):
        visible_classes.setdefault(contest_id, []).append(class_id)
    can_see_all = is_super_admin(db, actor_id if actor_id is not None else profile_id)
    by_class = {}
    for row in rows.values():
        # A teacher sees visible contests for managed classes and their own hidden contests.
        if not can_see_all and not row["is_visible"] and row["id"] not in owners:
            continue
        if contest_status(row, now) != "active":
            continue
        for class_id in visible_classes.get(row["id"], []):
            by_class.setdefault(class_id, []).append(row["id"])
    for ids in by_class.values():
        ids.sort()
    return by_class


def contest_item(row, class_ids: list[int], at: datetime):
    return {
        "contest_id": row["id"], "code": row["key"] or str(row["id"]),
        "title": row["name"] or row["key"] or f"Contest {row['id']}",
        "class_ids": class_ids, "starts_at": as_utc(row["start_time"]),
        "ends_at": as_utc(row["end_time"]), "status": contest_status(row, at),
        "is_public": bool(row["is_public_contest"]), "updated_at": None,
        "version": str(row["version_update"]) if row["version_update"] is not None else None,
    }


def paged_contests(items, cursor, limit, scope):
    snapshot = fingerprint(items)
    scope_json = json.dumps(scope, sort_keys=True, separators=(",", ":"))
    offset = cursor_offset(cursor, "contests", scope_json, snapshot)
    return page_result(items[offset:offset + limit], len(items), offset, limit,
                       "contests", scope_json, snapshot)


def teacher_contest_items(db: Session, profile_id: int, actor_id: int, state: str,
                          at: datetime, class_id: int | None = None,
                          q: str | None = None):
    all_access = is_super_admin(db, actor_id)
    owners = contest_owner_ids(db, profile_id)
    if all_access:
        class_scope = set(db.execute(select(organization.c.id)).scalars())
    else:
        class_scope = managed_class_ids(db, actor_id) or set()

    candidate_ids = None
    if class_id is not None:
        candidate_ids = set(db.execute(select(contest_organization.c.contest_id).where(
            contest_organization.c.organization_id == class_id,
        )).scalars())
    mapping_stmt = select(contest_organization.c.contest_id, contest_organization.c.organization_id).where(
        contest_organization.c.organization_id.in_(class_scope or {-1})
    )
    if candidate_ids is not None:
        mapping_stmt = mapping_stmt.where(contest_organization.c.contest_id.in_(candidate_ids or {-1}))
    mappings = {}
    for contest_id, mapped_class_id in db.execute(mapping_stmt):
        mappings.setdefault(contest_id, []).append(mapped_class_id)

    if all_access or candidate_ids is None:
        contest_stmt = select(contest)
        if candidate_ids is not None:
            contest_stmt = contest_stmt.where(contest.c.id.in_(candidate_ids or {-1}))
        rows = list(db.execute(contest_stmt).mappings())
    else:
        eligible_ids = (set(mappings) | owners) & (candidate_ids or set())
        if not eligible_ids:
            return []
        rows = list(db.execute(select(contest).where(contest.c.id.in_(eligible_ids))).mappings())

    result = []
    term = (q or "").strip().casefold()
    for row in rows:
        owned = row["id"] in owners
        if class_id is not None and not all_access and not row["is_visible"] and not owned:
            continue
        mapped_ids = mappings.get(row["id"], [])
        if class_id is not None and row["id"] not in candidate_ids:
            continue
        status = contest_status(row, at)
        if state != "all" and status != state:
            continue
        if term and term not in " ".join((row["name"] or "", row["key"] or "", str(row["id"]))).casefold():
            continue
        item = contest_item(row, sorted(set(mapped_ids)), at)
        result.append(item)
    result.sort(key=lambda item: (
        item["starts_at"] is not None,
        item["starts_at"] or datetime.min.replace(tzinfo=timezone.utc),
        item["contest_id"],
    ), reverse=True)
    return result


def teacher_contest_detail(db: Session, profile_id: int, actor_id: int, contest_id: int, at: datetime):
    row = db.execute(select(contest).where(contest.c.id == contest_id)).mappings().first()
    if row is None:
        raise HTTPException(404, {"code": "not_found", "message": "Contest not found"})

    all_access = is_super_admin(db, actor_id)
    class_scope = None if all_access else managed_class_ids(db, actor_id)
    mappings = contest_mappings(db, [contest_id], class_scope).get(contest_id, [])
    return contest_item(row, sorted(set(mappings)), at)


def list_students_query(db: Session, actor_id: int, class_id: int | None = None, q: str | None = None):
    stmt = select(
        profile.c.id.label("profile_id"), profile.c.name, user.c.username, profile.c.points,
        user.c.email, profile.c.problem_count, profile.c.display_rank,
    ).select_from(profile.outerjoin(user, user.c.id == profile.c.user_id))
    if class_id is not None:
        stmt = stmt.join(profile_organization, profile_organization.c.profile_id == profile.c.id).where(
            profile_organization.c.organization_id == class_id
        )
    else:
        stmt = stmt.join(profile_organization, profile_organization.c.profile_id == profile.c.id)
        if not is_super_admin(db, actor_id):
            class_ids = managed_class_ids(db, actor_id) or {-1}
            stmt = stmt.where(profile_organization.c.organization_id.in_(class_ids))
    if q and q.strip():
        term = f"%{escaped_like(q.strip())}%"
        stmt = stmt.where(or_(profile.c.name.ilike(term, escape="\\"), user.c.username.ilike(term, escape="\\"), cast(profile.c.id, String).ilike(term, escape="\\")))
    return stmt.distinct().order_by(profile.c.name.asc(), profile.c.id.asc())


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={**detail, "request_id": request.headers.get("X-Request-Id")})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "code": "validation_error",
        "message": "Request validation failed",
        "request_id": request.headers.get("X-Request-Id"),
    })


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled source API mock error", exc_info=exc)
    return JSONResponse(status_code=500, content={
        "code": "internal_error",
        "message": ERROR_DESCRIPTIONS[500],
        "request_id": request.headers.get("X-Request-Id"),
    })


@app.get(f"{API_PREFIX}/profiles/{{profile_id}}/access", response_model=Access,
         responses=COMMON_ERROR_RESPONSES)
def get_access(profile_id: int, db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    require_actor_profile(db, actor_id, profile_id)
    row = profile_row(db, profile_id)
    if row is None:
        return Access(profile_id=profile_id, exists=False, is_active=False, is_super_admin=False, roles=[], as_of=utc_now())
    user_active = db.execute(select(user.c.is_active).where(user.c.id == row["user_id"])).scalar_one_or_none()
    roles = []
    if row["super_admin"]:
        roles.append("super_admin")
    if db.execute(select(organization_admin.c.id).where(organization_admin.c.profile_id == profile_id).limit(1)).first():
        roles.append("teacher")
    active = bool(user_active) if row["user_id"] is not None else False
    return Access(profile_id=profile_id, exists=True, is_active=active, is_super_admin=bool(row["super_admin"]), roles=roles,
                  version=None, as_of=utc_now())


@app.post(f"{API_PREFIX}/teachers/{{profile_id}}/classes/query", response_model=Page[ClassItem],
          responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def query_classes(profile_id: int, body: ClassQuery, db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    require_actor_profile(db, actor_id, profile_id)
    owner = profile_row(db, profile_id)
    if owner is None:
        raise HTTPException(404, {"code": "not_found", "message": "Profile not found"})
    stmt = select(organization)
    if not owner["super_admin"]:
        stmt = stmt.where(select(organization_admin.c.id).where(
            organization_admin.c.organization_id == organization.c.id,
            organization_admin.c.profile_id == profile_id,
        ).exists())
    if body.q and body.q.strip():
        term = f"%{escaped_like(body.q.strip())}%"
        stmt = stmt.where(or_(organization.c.name.ilike(term, escape="\\"), cast(organization.c.id, String).ilike(term, escape="\\")))
    rows = list(db.execute(stmt).mappings())
    class_ids = [row["id"] for row in rows]
    active_contests = active_contests_by_class(db, class_ids, profile_id, actor_id)
    counts = dict(db.execute(select(profile_organization.c.organization_id, func.count(profile_organization.c.id))
        .where(profile_organization.c.organization_id.in_(class_ids or [-1])).group_by(profile_organization.c.organization_id)).all())
    year_ids = [row["year_id"] for row in rows if row["year_id"] is not None]
    years = {r["id"]: r for r in db.execute(select(school_year).where(school_year.c.id.in_(year_ids or [-1]))).mappings()}
    managers = {}
    for class_id, manager_id, manager_name, manager_username in db.execute(
        select(organization_admin.c.organization_id, profile.c.id, profile.c.name, user.c.username)
        .join(profile, profile.c.id == organization_admin.c.profile_id).outerjoin(user, user.c.id == profile.c.user_id)
        .where(organization_admin.c.organization_id.in_(class_ids or [-1])).distinct().order_by(profile.c.id)
    ).all():
        managers.setdefault(class_id, []).append(Manager(profile_id=manager_id, name=(manager_name or "").strip() or manager_username or f"Profile {manager_id}"))
    active = {value: index for index, value in enumerate(body.virtual_active_class_ids)}
    starred = {value: index for index, value in enumerate(body.starred_class_ids)}
    def sort_key(row):
        # Stable ties follow the requested field then source ID.
        val = counts.get(row["id"], 0) if body.sort == "member_count" else (row["name"] or "").casefold() if body.sort == "name" else row["creation_date"] if body.sort == "created_at" else row["id"]
        return (not bool(active_contests.get(row["id"])), row["id"] not in active,
                active.get(row["id"], 0), row["id"] not in starred,
                starred.get(row["id"], 0), val is None, val if body.order == "asc" else _Reverse(val), row["id"])
    rows.sort(key=sort_key)
    items = []
    for row in rows:
        year = years.get(row["year_id"])
        items.append(ClassItem(class_id=row["id"], name=row["name"] or f"Class {row['id']}",
            school_year=SchoolYear(start=year["start"], finish=year["finish"]) if year and year["start"] and year["finish"] else None,
            created_at=as_utc(row["creation_date"]), member_count=int(counts.get(row["id"], 0)), managers=managers.get(row["id"], []),
            has_active_contest=bool(active_contests.get(row["id"])),
            active_contest_ids=active_contests.get(row["id"], []), updated_at=None))
    scope = json.dumps({"profile_id": profile_id, "actor_id": actor_id, "q": body.q, "limit": body.limit, "sort": body.sort,
                        "order": body.order, "virtual_active_class_ids": body.virtual_active_class_ids,
                        "starred_class_ids": body.starred_class_ids}, sort_keys=True, separators=(",", ":"))
    snapshot = fingerprint(items)
    offset = cursor_offset(body.cursor, "teacher_classes", scope, snapshot)
    return page_result(items[offset:offset + body.limit], len(items), offset, body.limit,
                       "teacher_classes", scope, snapshot)


class _Reverse:
    """Reverse non-null ordering without assuming a field's concrete type."""
    def __init__(self, value): self.value = value
    def __lt__(self, other):
        if self.value is None or other.value is None:
            return self.value is None and other.value is not None
        return self.value > other.value
    def __eq__(self, other):
        return isinstance(other, _Reverse) and self.value == other.value


@app.get(f"{API_PREFIX}/classes/{{class_id}}", response_model=ClassItem,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def get_class(class_id: int, db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    row = visible_class(db, class_id, actor_id)
    body = ClassQuery(limit=100)
    # Reuse the query assembly so detail and list expose identical source fields.
    rows = query_classes(_profile_for_class(db, class_id, actor_id), body, db, actor_id)
    match = next((item for item in rows["items"] if item.class_id == class_id), None)
    if match is None:
        year = db.execute(select(school_year).where(school_year.c.id == row["year_id"])).mappings().first() if row["year_id"] else None
        count = db.execute(select(func.count(profile_organization.c.id)).where(profile_organization.c.organization_id == class_id)).scalar_one()
        mgrs = db.execute(select(organization_admin.c.profile_id, profile.c.name, user.c.username).join(profile, profile.c.id == organization_admin.c.profile_id).outerjoin(user, user.c.id == profile.c.user_id).where(organization_admin.c.organization_id == class_id)).all()
        active = active_contests_by_class(db, [class_id], actor_id, actor_id).get(class_id, [])
        match = ClassItem(class_id=class_id, name=row["name"] or f"Class {class_id}", school_year=SchoolYear(start=year["start"], finish=year["finish"]) if year and year["start"] and year["finish"] else None,
            created_at=as_utc(row["creation_date"]), member_count=count, managers=[Manager(profile_id=m[0], name=(m[1] or "").strip() or m[2] or f"Profile {m[0]}") for m in mgrs], has_active_contest=bool(active), active_contest_ids=active, updated_at=None)
    return match


def _profile_for_class(db: Session, class_id: int, actor_id: int):
    if is_super_admin(db, actor_id):
        return actor_id
    return actor_id


def _paged_students(db, profile_id, class_id, q, cursor, limit, class_view=False, actor_id=None, sort="name"):
    scope_actor = actor_id if actor_id is not None else profile_id
    q = q.strip() if q and q.strip() else None
    cursor = cursor.strip() if cursor and cursor.strip() else None
    stmt = list_students_query(db, profile_id, class_id, None if sort == "points_desc" else q)
    rows = list(db.execute(stmt).mappings())
    items = [student_item(row) for row in rows]
    if sort == "points_desc":
        items.sort(key=lambda item: (-item["points"], item["profile_id"]))
        for rank, item in enumerate(items, 1):
            item["rank"] = rank
        if q:
            term = q.casefold()
            items = [item for item in items if term in " ".join((
                item["name"], item["username"], str(item["profile_id"]),
            )).casefold()]
    if class_view:
        items = [{**item, "avatar_url": None, "joined_at": None} for item in items]
    scope = json.dumps({"actor_id": scope_actor, "profile_id": profile_id, "class_id": class_id, "q": q, "limit": limit,
                        "class_view": class_view, "sort": sort}, sort_keys=True, separators=(",", ":"))
    snapshot = fingerprint(items)
    offset = cursor_offset(cursor, "students", scope, snapshot)
    return page_result(items[offset:offset + limit], len(items), offset, limit, "students", scope, snapshot)


@app.get(f"{API_PREFIX}/teachers/{{profile_id}}/students", response_model=Page[StudentItem],
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def teacher_students(profile_id: int, q: str | None = None, cursor: str | None = None, limit: int = Query(24, ge=1, le=100), sort: str = Query("name", pattern="^(name|points_desc)$"), db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    require_actor_profile(db, actor_id, profile_id)
    if profile_row(db, profile_id) is None:
        raise HTTPException(404, {"code": "not_found", "message": "Profile not found"})
    return _paged_students(db, profile_id, None, q, cursor, limit, actor_id=actor_id, sort=sort)


@app.get(f"{API_PREFIX}/classes/{{class_id}}/students", response_model=Page[ClassStudent],
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def class_students(class_id: int, cursor: str | None = None, limit: int = Query(24, ge=1, le=100), db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    visible_class(db, class_id, actor_id)
    return _paged_students(db, actor_id, class_id, None, cursor, limit, True, actor_id=actor_id)


@app.get(f"{API_PREFIX}/students/{{profile_id}}", response_model=StudentDetail,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def get_student(profile_id: int, db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    row = db.execute(select(profile.c.id.label("profile_id"), profile.c.name, user.c.username, profile.c.points, profile.c.problem_count, profile.c.display_rank)
        .select_from(profile.outerjoin(user, user.c.id == profile.c.user_id)).where(profile.c.id == profile_id)).mappings().first()
    if row is None or not student_visible(db, profile_id, actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Student not found"})
    classes_stmt = select(organization.c.id.label("class_id"), organization.c.name).join(profile_organization, profile_organization.c.organization_id == organization.c.id).where(profile_organization.c.profile_id == profile_id)
    if not is_super_admin(db, actor_id):
        classes_stmt = classes_stmt.where(organization.c.id.in_(managed_class_ids(db, actor_id) or [-1]))
    classes = [{"class_id": r.class_id, "name": r.name or f"Class {r.class_id}"} for r in db.execute(classes_stmt.order_by(organization.c.id))]
    return {**student_item(row), "classes": classes}


@app.get(f"{API_PREFIX}/teachers/{{profile_id}}/contests", response_model=ContestPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def teacher_contests(profile_id: int, state: str = Query("all", pattern="^(active|upcoming|ended|all)$"), at: datetime | None = None, cursor: str | None = None, limit: int = Query(24, ge=1, le=100), q: str | None = Query(None, max_length=128), db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    require_actor_profile(db, actor_id, profile_id)
    if profile_row(db, profile_id) is None:
        raise HTTPException(404, {"code": "not_found", "message": "Profile not found"})
    evaluated_at = as_utc(at or utc_now())
    items = teacher_contest_items(db, profile_id, actor_id, state, evaluated_at, q=q)
    result = paged_contests(items, cursor, limit, {
        "endpoint": "teacher_contests", "profile_id": profile_id, "actor_id": actor_id,
        "state": state, "at": as_utc(at).isoformat() if at is not None else None,
        "limit": limit, "q": (q or "").strip(),
    })
    return result


@app.get(f"{API_PREFIX}/teachers/{{profile_id}}/contests/{{contest_id}}", response_model=ContestItem,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def teacher_contest_detail_route(
    profile_id: int,
    contest_id: int,
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    require_actor_profile(db, actor_id, profile_id)
    if profile_row(db, profile_id) is None:
        raise HTTPException(404, {"code": "not_found", "message": "Profile not found"})
    return teacher_contest_detail(db, profile_id, actor_id, contest_id, as_utc(utc_now()))


@app.get(f"{API_PREFIX}/classes/{{class_id}}/contests", response_model=ContestPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def class_contests(class_id: int, state: str = Query("all", pattern="^(active|upcoming|ended|all)$"), at: datetime | None = None, cursor: str | None = None, limit: int = Query(24, ge=1, le=100), db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    visible_class(db, class_id, actor_id)
    evaluated_at = as_utc(at or utc_now())
    items = teacher_contest_items(db, actor_id, actor_id, state, evaluated_at, class_id=class_id)
    return paged_contests(items, cursor, limit, {
        "endpoint": "class_contests", "class_id": class_id, "actor_id": actor_id,
        "state": state, "at": as_utc(at).isoformat() if at is not None else None, "limit": limit,
    })


def _date_scope(from_at: datetime | None, to_at: datetime | None) -> dict:
    return {
        "from": as_utc(from_at).isoformat() if from_at else None,
        "to": as_utc(to_at).isoformat() if to_at else None,
    }


def _submission_detail_payload(db: Session, row, actor_id: int, include: set[str]) -> dict:
    item = submission_item(row)
    source_code = None
    if "source" in include:
        if not source_scope_allows(actor_id):
            raise HTTPException(403, {"code": "forbidden", "message": "Source-code access is not granted"})
        source_row = db.execute(select(submission_source.c.source).where(
            submission_source.c.submission_id == row["submission_id"],
        )).first()
        source_code = source_row[0] if source_row else None
    cases = []
    if "testcases" in include:
        if not testcase_scope_allows(actor_id):
            raise HTTPException(403, {"code": "forbidden", "message": "Testcase access is not granted"})
        cases = [TestcaseItem(
            case=case.case, status=case.status, time=case.time, memory=case.memory,
            points=case.points, total=case.total, feedback=case.extended_feedback or case.feedback,
            output=case.output,
        ) for case in db.execute(select(submission_testcase)
            .where(submission_testcase.c.submission_id == row["submission_id"])
            .order_by(submission_testcase.c.case.asc(), submission_testcase.c.id.asc())).all()]
    return {**item, "source_code": source_code, "testcases": cases}


@app.get(f"{API_PREFIX}/students/{{profile_id}}/submissions", response_model=Page[SubmissionItem],
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def student_submissions(
    profile_id: int,
    from_at: datetime | None = Query(None, alias="from"),
    to_at: datetime | None = Query(None, alias="to"),
    result: str | None = None,
    exclude_result: str | None = None,
    only_with_source: bool = False,
    problem_id: int | None = Query(None, ge=1),
    cursor: str | None = None,
    limit: int = Query(24, ge=1, le=100),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(from_at, to_at)
    if cursor is not None and not str(cursor).strip():
        cursor = None
    if profile_row(db, profile_id) is None:
        raise HTTPException(404, {"code": "not_found", "message": "Profile not found"})
    if not submission_visible(db, profile_id, actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Student not found"})
    scope = json.dumps({
        "actor_id": actor_id, "profile_id": profile_id, **_date_scope(from_at, to_at),
        "result": result, "exclude_result": exclude_result,
        "only_with_source": only_with_source, "problem_id": problem_id,
        "sort": sort, "limit": limit,
    }, sort_keys=True, separators=(",", ":"))
    total, marker = _student_submission_snapshot(
        db, profile_id, from_at=from_at, to_at=to_at, result=result,
        exclude_result=exclude_result, problem_id=problem_id,
        only_with_source=only_with_source,
    )
    snapshot = fingerprint([marker])
    offset = cursor_offset(cursor, "student_submissions", scope, snapshot)
    rows = submission_rows(
        db, profile_id=profile_id, from_at=from_at, to_at=to_at,
        offset=offset, limit=limit, student_order=sort, result=result,
        exclude_result=exclude_result, problem_id=problem_id,
        only_with_source=only_with_source,
    )
    items = [submission_item(row) for row in rows]
    return page_result(items, total, offset, limit,
                       "student_submissions", scope, snapshot)


@app.get(f"{API_PREFIX}/classes/{{class_id}}/submissions", response_model=SubmissionPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def class_submissions(
    class_id: int,
    from_at: datetime | None = Query(None, alias="from"),
    to_at: datetime | None = Query(None, alias="to"),
    after_submission_id: int | None = Query(None, ge=0),
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(from_at, to_at)
    if cursor is not None and not str(cursor).strip():
        cursor = None
    if cursor is not None and after_submission_id is not None:
        raise HTTPException(422, {"code": "validation_error", "message": "Use cursor or after_submission_id, not both"})
    visible_class(db, class_id, actor_id)
    payload = None
    high_watermark = None
    id_cursor = after_submission_id
    snapshot_marker = None
    if cursor is not None:
        # Reject tampered, expired, and query-mismatched cursors before querying
        # the class submission set.
        payload = cursor_payload(cursor, "class_submissions", None)
        if payload.get("after_submission_id") is not None:
            if not isinstance(payload["after_submission_id"], int) or after_submission_id is not None:
                raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
            id_cursor = payload.get("last_submission_id")
            if not isinstance(id_cursor, int):
                raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
            after_submission_id = payload["after_submission_id"]
        scope = json.dumps({
            "actor_id": actor_id, "class_id": class_id, **_date_scope(from_at, to_at),
            "after_submission_id": after_submission_id, "limit": limit,
        }, sort_keys=True, separators=(",", ":"))
        if payload.get("scope") != scope:
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
        high_watermark = payload.get("high_watermark")
        if not isinstance(high_watermark, str):
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
        change_scope = _change_scope(actor_id, class_id, from_at, to_at)
        after_seq, through_seq = _decode_change_cursor(high_watermark, change_scope)
        with _change_lock:
            floor = _change_cursor_floor(class_id)
            latest = _change_last_id.get(class_id, 0)
            if after_seq < floor - 1 or through_seq < floor - 1 or through_seq > latest:
                raise HTTPException(409, {"code": "cursor_expired", "message": "Change feed history is unavailable"})
    else:
        scope = json.dumps({
            "actor_id": actor_id, "class_id": class_id, **_date_scope(from_at, to_at),
            "after_submission_id": after_submission_id, "limit": limit,
        }, sort_keys=True, separators=(",", ":"))
        with _change_lock:
            if class_id not in _change_snapshots:
                _ensure_change_baseline(db, class_id)
            else:
                _refresh_class_change_log(db, class_id)
            snapshot_marker = _change_markers[class_id]
            through_seq = _change_last_id.get(class_id, 0)
            high_watermark = _encode_change_cursor(
                through_seq, through_seq, _change_scope(actor_id, class_id, from_at, to_at),
            )

    if snapshot_marker is None:
        snapshot_marker = _class_submission_marker(db, class_id)
    snapshot = fingerprint([snapshot_marker])
    if payload is not None and payload.get("snapshot") != snapshot:
        raise HTTPException(409, {"code": "cursor_expired", "message": "Submission snapshot changed"})
    count = _class_submission_count(db, class_id, from_at, to_at, after_submission_id)
    if after_submission_id is not None:
        query_rows = submission_rows(db, class_id=class_id, from_at=from_at, to_at=to_at,
                                     limit=limit + 1, after_submission_id=id_cursor)
    else:
        after_key = None
        if payload is not None:
            try:
                after_key = (datetime.fromisoformat(payload["last_submitted_at"]),
                             int(payload["last_submission_id"]))
            except (ValueError, TypeError, KeyError):
                raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
        query_rows = submission_rows(db, class_id=class_id, from_at=from_at, to_at=to_at,
                                     limit=limit + 1, class_order=True, after_key=after_key)
    has_more = len(query_rows) > limit
    query_rows = query_rows[:limit]
    selected = [submission_item(row, include_student_name=True) for row in query_rows]
    cursor_extra = {"high_watermark": high_watermark,
                    "after_submission_id": after_submission_id}
    if selected:
        cursor_extra["last_submission_id"] = selected[-1]["submission_id"]
        cursor_extra["last_submitted_at"] = selected[-1]["submitted_at"].isoformat()
    next_cursor = encode_cursor(0, "class_submissions", scope, snapshot,
                                **cursor_extra) if has_more and selected else None
    return {
        "items": selected, "next_cursor": next_cursor, "has_more": has_more,
        "total": count, "high_watermark": high_watermark,
        "max_submission_id": snapshot_marker[1], "as_of": utc_now(),
    }


@app.get(f"{API_PREFIX}/classes/{{class_id}}/submission-changes", response_model=SubmissionChangesPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def class_submission_changes(
    class_id: int,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100),
    from_at: datetime | None = Query(None, alias="from"),
    to_at: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(from_at, to_at)
    if cursor is not None and not str(cursor).strip():
        cursor = None
    visible_class(db, class_id, actor_id)
    scope = _change_scope(actor_id, class_id, from_at, to_at)
    if cursor is not None:
        # Verify cursor authentication and scope before any class-sized query.
        after_seq, previous_through = _decode_change_cursor(cursor, scope)
    with _change_lock:
        if cursor is None:
            all_rows = submission_rows(db, class_id=class_id)
            _sync_class_change_log(class_id, _date_filtered_items(all_rows, None, None, include_student_name=True))
            _change_markers[class_id] = _class_submission_marker(db, class_id)
            _change_last_reconciled[class_id] = time.monotonic()
        else:
            _refresh_class_change_log(db, class_id)
        high_seq = _change_last_id.get(class_id, 0)
        floor = _change_cursor_floor(class_id)
        if cursor is None:
            after_seq, through_seq = 0, high_seq
        else:
            if after_seq < floor - 1 or previous_through < floor - 1 or after_seq > high_seq:
                raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or event history is unavailable"})
            through_seq = high_seq if after_seq >= previous_through else previous_through
        log = _change_logs.get(class_id, [])
        available = [event for event in log if after_seq < event["event_id"] <= through_seq
                     and _change_event_in_range(event, from_at, to_at)]
        selected_events = available[:limit]
        has_more = len(available) > limit
        next_after = selected_events[-1]["event_id"] if has_more and selected_events else through_seq
        next_cursor = _encode_change_cursor(next_after, through_seq, scope)
        events = [SubmissionChange(
            event_id=event["event_id"], kind=event["kind"], submission_id=event["submission_id"],
            version=event["version"], changed_at=event["changed_at"], record=event["record"],
        ) for event in selected_events]
    return SubmissionChangesPage(
        events=events, next_cursor=next_cursor, has_more=has_more,
        high_watermark=through_seq, as_of=utc_now(),
    )


@app.get(f"{API_PREFIX}/submissions/{{submission_id}}", response_model=SubmissionDetail,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def get_submission_detail(
    submission_id: int,
    include: str | None = None,
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    include_set = {part.strip() for part in (include or "").split(",") if part.strip()}
    if include_set - {"source", "testcases"}:
        raise HTTPException(422, {"code": "validation_error", "message": "include supports source,testcases"})
    row = next(iter(submission_rows(db, submission_id=submission_id)), None)
    if row is None:
        raise HTTPException(404, {"code": "not_found", "message": "Submission not found"})
    if not submission_visible(db, row["profile_id"], actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Submission not found"})
    return _submission_detail_payload(db, row, actor_id, include_set)


def _problem_row_visible(row, actor_id: int, db: Session) -> bool:
    return bool(is_super_admin(db, actor_id) or (row["is_public"] and not row["is_organization_private"]))


@app.get(f"{API_PREFIX}/problems/{{problem_id}}/accepted-samples",
         response_model=AcceptedSamplesResponse,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(403, 404)})
def accepted_problem_samples(
    problem_id: int,
    limit: int = Query(3, ge=1, le=3),
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    if not source_scope_allows(actor_id):
        raise HTTPException(403, {"code": "forbidden", "message": "Source-code access is not granted"})
    problem_row = db.execute(select(problem).where(problem.c.id == problem_id)).mappings().first()
    if problem_row is None or not _problem_row_visible(problem_row, actor_id, db):
        raise HTTPException(404, {"code": "not_found", "message": "Problem not found"})

    rows = db.execute(select(
        submission.c.id.label("submission_id"), submission.c.points, submission.c.time,
        submission.c.memory, submission.c.date.label("submitted_at"), language.c.key.label("language_key"),
        submission_source.c.source.label("source_code"),
    ).select_from(submission.join(submission_source, submission_source.c.submission_id == submission.c.id)
        .outerjoin(language, language.c.id == submission.c.language_id))
        .where(
            submission.c.problem_id == problem_id, submission.c.result == "AC",
            submission_source.c.source.is_not(None), submission_source.c.source != "",
        )
        .order_by(submission.c.points.desc(), submission.c.time.asc(),
                  submission.c.date.asc(), submission.c.id.asc())
        .limit(limit)).mappings().all()
    return AcceptedSamplesResponse(items=[AcceptedSample(
        submission_id=row["submission_id"], language_key=row["language_key"],
        source_code=row["source_code"], points=row["points"], time=row["time"],
        memory=row["memory"], submitted_at=as_utc(row["submitted_at"]),
    ) for row in rows], as_of=utc_now())


@app.get(f"{API_PREFIX}/students/{{profile_id}}/submission-samples",
         response_model=StudentSubmissionSamplesResponse,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(403, 404)})
def student_submission_samples(
    profile_id: int,
    from_at: datetime | None = Query(None, alias="from"),
    to_at: datetime | None = Query(None, alias="to"),
    tag_ids: list[int] = Query(..., min_length=1, max_length=100),
    result: str = Query("AC", min_length=1, max_length=16),
    per_group_limit: int = Query(3, ge=1, le=3),
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(from_at, to_at)
    if not source_scope_allows(actor_id):
        raise HTTPException(403, {"code": "forbidden", "message": "Source-code access is not granted"})
    if any(tag_id < 1 for tag_id in tag_ids):
        raise HTTPException(422, {"code": "validation_error", "message": "tag_ids must be positive"})
    tag_ids = sorted(set(tag_ids))
    if profile_row(db, profile_id) is None or not submission_visible(db, profile_id, actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Student not found"})

    visibility = _visible_problem_where(db, actor_id)
    rank = func.row_number().over(
        partition_by=problem_type.c.problemtype_id,
        order_by=(submission.c.date.desc(), submission.c.id.desc()),
    ).label("sample_rank")
    ranked = select(
        submission.c.id.label("submission_id"), submission.c.problem_id,
        submission.c.date.label("submitted_at"), submission.c.time, submission.c.memory,
        problem.c.time_limit.label("problem_time_limit"),
        problem.c.memory_limit.label("problem_memory_limit"),
        language.c.key.label("language_key"), submission_source.c.source.label("source_code"),
        rank,
    ).select_from(
        submission.join(problem, problem.c.id == submission.c.problem_id)
        .join(problem_type, problem_type.c.problem_id == problem.c.id)
        .join(submission_source, submission_source.c.submission_id == submission.c.id)
        .outerjoin(language, language.c.id == submission.c.language_id)
    ).where(
        submission.c.user_id == profile_id,
        submission.c.result == result,
        problem_type.c.problemtype_id.in_(tag_ids),
        submission_source.c.source.is_not(None), submission_source.c.source != "",
        *visibility,
    )
    if from_at is not None:
        ranked = ranked.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        ranked = ranked.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    ranked = ranked.subquery()
    selected = db.execute(select(ranked).where(ranked.c.sample_rank <= per_group_limit)
        .order_by(ranked.c.submitted_at.desc(), ranked.c.submission_id.desc())).mappings().all()
    unique = {}
    for row in selected:
        unique.setdefault(row["submission_id"], row)
    problem_ids = {row["problem_id"] for row in unique.values()}
    tags_by_problem: dict[int, list[int]] = {problem_id: [] for problem_id in problem_ids}
    if problem_ids:
        for problem_id, tag_id in db.execute(select(
            problem_type.c.problem_id, problem_type.c.problemtype_id,
        ).where(problem_type.c.problem_id.in_(problem_ids)).order_by(
            problem_type.c.problem_id, problem_type.c.problemtype_id,
        )).all():
            tags_by_problem[problem_id].append(tag_id)
    return StudentSubmissionSamplesResponse(items=[StudentSubmissionSample(
        submission_id=row["submission_id"], problem_id=row["problem_id"],
        tag_ids=tags_by_problem[row["problem_id"]], submitted_at=as_utc(row["submitted_at"]),
        time=row["time"], memory=row["memory"],
        problem_time_limit=row["problem_time_limit"],
        problem_memory_limit=row["problem_memory_limit"], language_key=row["language_key"],
        source_code=row["source_code"],
    ) for row in unique.values()], as_of=utc_now())


@app.get(f"{API_PREFIX}/problems/{{problem_id}}", response_model=ProblemItem,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def get_problem(problem_id: int, db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id)):
    row = db.execute(select(problem).where(problem.c.id == problem_id)).mappings().first()
    if row is None:
        raise HTTPException(404, {"code": "not_found", "message": "Problem not found"})
    if (not row["is_public"] or row["is_organization_private"]) and not is_super_admin(db, actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Problem not found"})
    type_ids = sorted(set(db.execute(select(problem_type.c.problemtype_id).where(
        problem_type.c.problem_id == problem_id,
    )).scalars().all()))
    version = row["version_update"]
    updated_at = None
    if isinstance(version, datetime):
        updated_at = as_utc(version)
    elif isinstance(version, str):
        try:
            updated_at = as_utc(datetime.fromisoformat(version.replace("Z", "+00:00")))
        except ValueError:
            updated_at = None
    title = row["name"] or row["code"] or f"Problem {row['id']}"
    return {
        "problem_id": row["id"], "code": row["code"], "name": row["name"],
        "title": title, "tag_ids": type_ids, "updated_at": updated_at,
        "version": version,
        "description": row["description"], "points": row["points"],
        "time_limit": row["time_limit"], "memory_limit": row["memory_limit"],
        "group_id": row["group_id"], "is_public": bool(row["is_public"]),
    }


def _visible_problem_where(db: Session, actor_id: int):
    if is_super_admin(db, actor_id):
        return []
    return [problem.c.is_public == 1, problem.c.is_organization_private == 0]


def _catalog_version(db: Session, actor_id: int) -> str:
    visible = _visible_problem_where(db, actor_id)
    problem_rows = [tuple(row) for row in db.execute(select(
        problem.c.id, problem.c.code, problem.c.name,
        problem.c.points, problem.c.time_limit, problem.c.memory_limit,
        problem.c.group_id, problem.c.is_public, problem.c.is_organization_private,
        problem.c.version_update,
    ).where(*visible).order_by(problem.c.id)).all()]
    relation_rows = [tuple(row) for row in db.execute(select(
        problem_type.c.problem_id, problem_type.c.problemtype_id,
    ).select_from(problem_type.join(problem, problem.c.id == problem_type.c.problem_id))
        .where(*visible).order_by(problem_type.c.problem_id, problem_type.c.problemtype_id)).all()]
    tags = [tuple(row) for row in db.execute(select(
        problem_type_catalog.c.id, problem_type_catalog.c.name,
        problem_type_catalog.c.full_name, problem_type_catalog.c.priority,
    ).order_by(problem_type_catalog.c.id)).all()]
    groups = [tuple(row) for row in db.execute(select(
        problem_group.c.id, problem_group.c.name, problem_group.c.full_name,
    ).order_by(problem_group.c.id)).all()]
    encoded = json.dumps({
        "scope": "admin" if is_super_admin(db, actor_id) else "public",
        "problems": problem_rows,
        "relations": relation_rows,
        "tags": tags, "groups": groups,
    }, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def _catalog_etag(version: str) -> str:
    return f'"{version}"'


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    return any(part.strip() == "*" or part.strip().removeprefix("W/") == etag
               for part in header.split(","))


def _tag_item(row) -> dict:
    key = row["name"] or f"tag-{row['id']}"
    return {"tag_id": row["id"], "key": key, "title": row["full_name"] or key, "updated_at": None}


def _problem_group_item(row) -> dict:
    key = row["name"] or f"group-{row['id']}"
    return {"group_id": row["id"], "key": key, "title": row["full_name"] or key}


@app.get(f"{API_PREFIX}/tags", response_model=TagPage,
         responses={**COMMON_ERROR_RESPONSES, 200: {"headers": ETAG_HEADERS},
                    304: {"description": "Catalog version has not changed.", "headers": ETAG_HEADERS},
                    **error_responses(409)})
def list_tags(
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    response: Response = None,
    db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id),
):
    version = _catalog_version(db, actor_id)
    etag = _catalog_etag(version)
    scope = json.dumps({"actor_id": actor_id, "limit": limit}, sort_keys=True, separators=(",", ":"))
    last_id = 0
    if cursor:
        payload = cursor_payload(cursor, "tags", scope, version)
        try:
            last_id = int(payload["last_id"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
    if not cursor and _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    stmt = select(problem_type_catalog).where(problem_type_catalog.c.id > last_id).order_by(
        problem_type_catalog.c.id.asc()).limit(limit + 1)
    rows = list(db.execute(stmt).mappings())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(0, "tags", scope, version, last_id=rows[-1]["id"]) if has_more else None
    return {"items": [_tag_item(row) for row in rows], "catalog_version": version,
            "next_cursor": next_cursor, "has_more": has_more,
            "total": int(db.execute(select(func.count(problem_type_catalog.c.id))).scalar_one()),
            "as_of": utc_now()}


@app.get(f"{API_PREFIX}/problem-groups", response_model=ProblemGroupPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(409)})
def list_problem_groups(
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id),
):
    version = _catalog_version(db, actor_id)
    scope = json.dumps({"actor_id": actor_id, "limit": limit}, sort_keys=True, separators=(",", ":"))
    last_id = 0
    if cursor:
        payload = cursor_payload(cursor, "problem_groups", scope, version)
        try:
            last_id = int(payload["last_id"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
    stmt = select(problem_group).where(problem_group.c.id > last_id).order_by(problem_group.c.id.asc()).limit(limit + 1)
    rows = list(db.execute(stmt).mappings())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(0, "problem_groups", scope, version, last_id=rows[-1]["id"]) if has_more else None
    return {"items": [_problem_group_item(row) for row in rows], "catalog_version": version,
            "next_cursor": next_cursor, "has_more": has_more,
            "total": int(db.execute(select(func.count(problem_group.c.id))).scalar_one()),
            "as_of": utc_now()}


@app.get(f"{API_PREFIX}/problems", response_model=ProblemPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409),
                    200: {"description": "Problem page; `fields=summary` omits each item's description."}})
def list_problems(
    after_id: int | None = Query(None, ge=0),
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100),
    q: str | None = Query(None, max_length=128),
    tag_id: int | None = Query(None, ge=1),
    group_id: int | None = Query(None, ge=1),
    ids: list[int] | None = Query(None, max_length=100),
    fields: str = Query("full", pattern="^(full|summary)$"),
    db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id),
):
    if cursor is not None and not str(cursor).strip():
        cursor = None
    if cursor is not None and after_id is not None:
        raise HTTPException(422, {"code": "validation_error", "message": "Use cursor or after_id, not both"})
    if ids is not None and (len(ids) > 100 or any(problem_id < 1 for problem_id in ids)):
        raise HTTPException(422, {"code": "validation_error", "message": "ids must contain at most 100 positive IDs"})
    actor_scope = "admin" if is_super_admin(db, actor_id) else "public"
    normalized_ids = sorted(set(ids)) if ids is not None else None
    payload = None
    anchor_after_id = after_id
    last_id = after_id or 0
    if cursor:
        payload = cursor_payload(cursor, "problems", None)
        try:
            if "after_id" not in payload or "last_id" not in payload or after_id is not None:
                raise ValueError
            anchor_after_id = int(payload["after_id"]) if payload["after_id"] is not None else None
            last_id = int(payload["last_id"])
            if last_id < (anchor_after_id or 0):
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
    scope = json.dumps({
        "actor_scope": actor_scope, "q": q.strip() if q and q.strip() else None,
        "tag_id": tag_id, "group_id": group_id, "ids": normalized_ids,
        "fields": fields, "after_id": anchor_after_id, "limit": limit,
    }, sort_keys=True, separators=(",", ":"))
    version = _catalog_version(db, actor_id)
    if payload is not None and payload.get("scope") != scope:
        raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
    if payload is not None and payload.get("snapshot") != version:
        raise HTTPException(409, {"code": "cursor_expired", "message": "Problem catalog changed"})

    conditions = _visible_problem_where(db, actor_id)
    search = q.strip() if q and q.strip() else None
    if search:
        term = f"%{escaped_like(search)}%"
        conditions.append(or_(problem.c.code.ilike(term, escape="\\"),
                              problem.c.name.ilike(term, escape="\\")))
    if tag_id is not None:
        conditions.append(select(problem_type.c.id).where(
            problem_type.c.problem_id == problem.c.id,
            problem_type.c.problemtype_id == tag_id,
        ).exists())
    if group_id is not None:
        conditions.append(problem.c.group_id == group_id)
    if normalized_ids is not None:
        conditions.append(problem.c.id.in_(normalized_ids or [-1]))
    if last_id:
        conditions.append(problem.c.id > last_id)
    total_conditions = list(conditions)
    total_conditions = list(conditions)
    if last_id:
        total_conditions = _visible_problem_where(db, actor_id)
        if search:
            total_conditions.append(or_(problem.c.code.ilike(term, escape="\\"),
                                        problem.c.name.ilike(term, escape="\\")))
        if tag_id is not None:
            total_conditions.append(select(problem_type.c.id).where(
                problem_type.c.problem_id == problem.c.id,
                problem_type.c.problemtype_id == tag_id,
            ).exists())
        if group_id is not None:
            total_conditions.append(problem.c.group_id == group_id)
        if normalized_ids is not None:
            total_conditions.append(problem.c.id.in_(normalized_ids or [-1]))
    total = int(db.execute(select(func.count(problem.c.id)).where(*total_conditions)).scalar_one() or 0)
    columns = [problem.c.id, problem.c.code, problem.c.name, problem.c.points,
               problem.c.time_limit, problem.c.memory_limit, problem.c.group_id,
               problem.c.is_public, problem.c.version_update]
    if fields == "full":
        columns.append(problem.c.description)
    rows = list(db.execute(select(*columns).where(*conditions).order_by(problem.c.id.asc()).limit(limit + 1)).mappings())
    has_more = len(rows) > limit
    rows = rows[:limit]
    ids_in_page = [row["id"] for row in rows]
    tag_ids_by_problem: dict[int, list[int]] = {problem_id: [] for problem_id in ids_in_page}
    if ids_in_page:
        for problem_id, type_id in db.execute(select(
            problem_type.c.problem_id, problem_type.c.problemtype_id,
        ).where(problem_type.c.problem_id.in_(ids_in_page)).order_by(
            problem_type.c.problem_id, problem_type.c.problemtype_id)).all():
            tag_ids_by_problem[problem_id].append(type_id)
    items = []
    for row in rows:
        title = row["name"] or row["code"] or f"Problem {row['id']}"
        item = {
            "problem_id": row["id"], "code": row["code"], "title": title,
            "description": row.get("description") if fields == "full" else None,
            "points": row["points"], "time_limit": row["time_limit"],
            "memory_limit": row["memory_limit"], "group_id": row["group_id"],
            "tag_ids": tag_ids_by_problem[row["id"]], "updated_at": None,
            "version": row["version_update"], "is_public": bool(row["is_public"]),
        }
        if fields == "summary":
            item.pop("description")
        items.append(item)
    cursor_extra = {"high_watermark": version, "after_id": anchor_after_id}
    if items:
        cursor_extra["last_id"] = items[-1]["problem_id"]
    next_cursor = encode_cursor(0, "problems", scope, version, **cursor_extra) if has_more and items else None
    data = {"items": items, "catalog_version": version, "next_cursor": next_cursor,
            "has_more": has_more, "total": total, "as_of": utc_now()}
    return JSONResponse(content=jsonable_encoder(data))


@app.get(f"{API_PREFIX}/analytics/catalog", response_model=CatalogSummary,
         responses={**COMMON_ERROR_RESPONSES, 200: {"headers": ETAG_HEADERS},
                    304: {"description": "Catalog version has not changed.", "headers": ETAG_HEADERS}})
def analytics_catalog(
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    db: Session = Depends(get_db), actor_id: int = Depends(actor_profile_id),
):
    version = _catalog_version(db, actor_id)
    etag = _catalog_etag(version)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers={"ETag": etag})
    visible = _visible_problem_where(db, actor_id)
    total = int(db.execute(select(func.count(problem.c.id)).where(*visible)).scalar_one() or 0)
    tagged_total = int(db.execute(select(func.count(func.distinct(problem.c.id)))
        .select_from(problem.join(problem_type, problem_type.c.problem_id == problem.c.id))
        .where(*visible)).scalar_one() or 0)
    tag_counts = dict(db.execute(select(
        problem_type.c.problemtype_id,
        func.count(func.distinct(problem.c.id)),
    ).select_from(problem_type.join(problem, problem.c.id == problem_type.c.problem_id))
        .where(*visible).group_by(problem_type.c.problemtype_id)).all())
    ranked_examples = select(
        problem_type.c.problemtype_id.label("tag_id"), problem.c.name.label("name"),
        problem.c.code.label("code"), problem.c.id.label("problem_id"),
        func.row_number().over(
            partition_by=problem_type.c.problemtype_id,
            order_by=(problem.c.name.asc(), problem.c.id.asc()),
        ).label("rank"),
    ).select_from(problem_type.join(problem, problem.c.id == problem_type.c.problem_id)).where(*visible).subquery()
    example_rows = db.execute(select(ranked_examples.c.tag_id, ranked_examples.c.name,
                                    ranked_examples.c.code, ranked_examples.c.problem_id)
                              .where(ranked_examples.c.rank <= 3)
                              .order_by(ranked_examples.c.tag_id, ranked_examples.c.rank)).all()
    examples: dict[int, list[str]] = {}
    for tag_id, title, code, problem_id in example_rows:
        examples.setdefault(tag_id, []).append(title or code or f"Problem {problem_id}")
    all_tags = db.execute(select(problem_type_catalog.c.id).order_by(problem_type_catalog.c.id)).scalars().all()
    tag_problem_counts = [TagProblemCount(
        tag_id=tag_id, distinct_problem_count=int(tag_counts.get(tag_id, 0)),
        example_titles=examples.get(tag_id, []),
    ) for tag_id in all_tags]
    group_counts = dict(db.execute(select(
        problem.c.group_id, func.count(func.distinct(problem.c.id)),
    ).where(*visible, problem.c.group_id.is_not(None)).group_by(problem.c.group_id)).all())
    groups = db.execute(select(problem_group.c.id).order_by(problem_group.c.id)).scalars().all()
    group_problem_counts = [GroupProblemCount(
        group_id=group_id, distinct_problem_count=int(group_counts.get(group_id, 0)),
    ) for group_id in groups]
    result = CatalogSummary(
        catalog_version=version, total_problem_count=total, tagged_problem_count=tagged_total,
        tag_problem_counts=tag_problem_counts, group_problem_counts=group_problem_counts,
        as_of=utc_now(),
    )
    return JSONResponse(content=jsonable_encoder(result), headers={"ETag": etag})


def _authorized_aggregate_profiles(db: Session, actor_id: int, profile_ids: list[int]) -> list[int]:
    if not 1 <= len(profile_ids) <= 100 or any(value < 1 for value in profile_ids):
        raise HTTPException(422, {"code": "validation_error", "message": "profile_ids must contain 1 to 100 positive IDs"})
    if len(set(profile_ids)) != len(profile_ids):
        raise HTTPException(422, {"code": "validation_error", "message": "profile_ids must not contain duplicates"})
    existing = set(db.execute(select(profile.c.id).where(profile.c.id.in_(profile_ids))).scalars())
    if len(existing) != len(profile_ids):
        raise HTTPException(404, {"code": "not_found", "message": "One or more students are not visible"})

    if is_super_admin(db, actor_id):
        visible = set(db.execute(select(profile_organization.c.profile_id).where(
            profile_organization.c.profile_id.in_(profile_ids),
        ).distinct()).scalars())
    else:
        managed = managed_class_ids(db, actor_id) or set()
        visible = set(db.execute(select(profile_organization.c.profile_id).where(
            profile_organization.c.profile_id.in_(profile_ids),
            profile_organization.c.organization_id.in_(managed or [-1]),
        ).distinct()).scalars())
    visible.add(actor_id)
    if not set(profile_ids).issubset(visible):
        raise HTTPException(404, {"code": "not_found", "message": "One or more students are not visible"})
    return profile_ids


def _result_key(result: str | None) -> str:
    return result or "UNKNOWN"


def _problem_fact_rows(rows: list[dict], tag_ids_by_problem: dict[int, list[int]],
                       group_by_problem: dict[int, int | None]) -> list[dict]:
    by_problem: dict[int, list[dict]] = {}
    for row in rows:
        if row["problem_id"] is None:
            continue
        by_problem.setdefault(row["problem_id"], []).append(row)
    facts = []
    for problem_id in sorted(by_problem):
        attempts = sorted(by_problem[problem_id], key=lambda r: (as_utc(r["submitted_at"]), r["submission_id"]))
        accepted = [row for row in attempts if row["result"] == "AC"]
        first_ac = accepted[0] if accepted else None
        failed_before = sum(
            1 for row in attempts if row["result"] != "AC" and
            (first_ac is None or (as_utc(row["submitted_at"]), row["submission_id"]) <
             (as_utc(first_ac["submitted_at"]), first_ac["submission_id"]))
        )
        verdicts: dict[str, int] = {}
        for row in attempts:
            key = _result_key(row["result"])
            verdicts[key] = verdicts.get(key, 0) + 1
        accepted_times = [float(row["time"]) for row in accepted if row["time"] is not None]
        rapid_failure_pairs = 0
        for previous, current in zip(attempts, attempts[1:]):
            delta = (as_utc(current["submitted_at"]) - as_utc(previous["submitted_at"])).total_seconds()
            if previous["result"] != "AC" and 0 < delta < 30:
                rapid_failure_pairs += 1
        facts.append({
            "problem_id": problem_id, "tag_ids": tag_ids_by_problem.get(problem_id, []),
            "group_id": group_by_problem.get(problem_id), "attempt_count": len(attempts),
            "ac_count": len(accepted),
            "first_ac_submission_id": first_ac["submission_id"] if first_ac else None,
            "first_ac_at": as_utc(first_ac["submitted_at"]) if first_ac else None,
            "failed_before_first_ac_count": failed_before,
            "best_ac_time": min(accepted_times) if accepted_times else None,
            "first_ac_time": float(first_ac["time"]) if first_ac and first_ac["time"] is not None else None,
            "problem_time_limit": attempts[0]["problem_time_limit"],
            "problem_memory_limit": attempts[0]["problem_memory_limit"],
            "rapid_failure_pair_count": rapid_failure_pairs,
            "last_submission_at": max(as_utc(row["submitted_at"]) for row in attempts),
            "verdict_counts": verdicts,
        })
    return facts


def _load_student_fact_data(db: Session, profile_ids: list[int], from_at: datetime | None,
                            to_at: datetime | None, actor_id: int):
    stmt = select(
        submission.c.user_id.label("profile_id"), submission.c.id.label("submission_id"),
        submission.c.problem_id, submission.c.date.label("submitted_at"), submission.c.result,
        submission.c.status, submission.c.points, submission.c.time, submission.c.memory,
        submission.c.version_update, submission.c.judged_date, submission.c.rejudged_date,
        problem.c.group_id, problem.c.time_limit.label("problem_time_limit"),
        problem.c.memory_limit.label("problem_memory_limit"),
    ).select_from(submission.join(problem, problem.c.id == submission.c.problem_id)).where(
        submission.c.user_id.in_(profile_ids), *_visible_problem_where(db, actor_id),
    )
    if from_at is not None:
        stmt = stmt.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        stmt = stmt.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    rows = [dict(row) for row in db.execute(stmt.order_by(
        submission.c.user_id, submission.c.date, submission.c.id,
    )).mappings() if row["submitted_at"] is not None]
    problem_ids = sorted({row["problem_id"] for row in rows if row["problem_id"] is not None})
    tags: dict[int, list[int]] = {problem_id: [] for problem_id in problem_ids}
    if problem_ids:
        for problem_id, tag_id in db.execute(select(problem_type.c.problem_id, problem_type.c.problemtype_id)
            .where(problem_type.c.problem_id.in_(problem_ids))
            .order_by(problem_type.c.problem_id, problem_type.c.problemtype_id)).all():
            tags.setdefault(problem_id, []).append(tag_id)
    groups = {row["id"]: row["group_id"] for row in db.execute(select(
        problem.c.id, problem.c.group_id,
    ).where(problem.c.id.in_(problem_ids or [-1]))).mappings()}
    for row in rows:
        row["group_id"] = groups.get(row["problem_id"], row["group_id"])
    return rows, tags, groups


def _distinct_student_problem_count(db: Session, profile_ids: list[int],
                                    from_at: datetime | None, to_at: datetime | None,
                                    actor_id: int) -> int:
    stmt = select(submission.c.user_id, submission.c.problem_id).select_from(
        submission.join(problem, problem.c.id == submission.c.problem_id),
    ).where(
        submission.c.user_id.in_(profile_ids), *_visible_problem_where(db, actor_id),
    )
    if from_at is not None:
        stmt = stmt.where(submission.c.date >= as_utc(from_at).replace(tzinfo=None))
    if to_at is not None:
        stmt = stmt.where(submission.c.date < as_utc(to_at).replace(tzinfo=None))
    distinct_pairs = stmt.distinct().subquery()
    return int(db.execute(select(func.count()).select_from(distinct_pairs)).scalar_one() or 0)


def _catalog_problem_counts(db: Session, actor_id: int) -> tuple[dict[int, int], list[int], list[int]]:
    visible = _visible_problem_where(db, actor_id)
    tag_counts = dict(db.execute(select(
        problem_type.c.problemtype_id, func.count(func.distinct(problem.c.id)),
    ).select_from(problem_type.join(problem, problem.c.id == problem_type.c.problem_id))
        .where(*visible).group_by(problem_type.c.problemtype_id)).all())
    tags = list(db.execute(select(problem_type_catalog.c.id).order_by(problem_type_catalog.c.id)).scalars())
    groups = list(db.execute(select(problem_group.c.id).order_by(problem_group.c.id)).scalars())
    return {tag_id: int(tag_counts.get(tag_id, 0)) for tag_id in tags}, tags, groups


def _reference_now(db: Session, actor_id: int, profile_ids: list[int]) -> datetime | None:
    query = select(func.max(submission.c.date)).select_from(
        submission.join(problem, problem.c.id == submission.c.problem_id),
    )
    if not is_super_admin(db, actor_id):
        managed = managed_class_ids(db, actor_id) or set()
        authorized_profiles = select(profile_organization.c.profile_id).where(
            profile_organization.c.organization_id.in_(managed or [-1]),
        ).union(select(profile.c.id).where(profile.c.id == actor_id))
        query = query.where(
            submission.c.user_id.in_(authorized_profiles), *_visible_problem_where(db, actor_id),
        )
    return as_utc(db.execute(query).scalar_one_or_none())


@app.post(f"{API_PREFIX}/analytics/students/aggregate", response_model=StudentAggregateResponse,
          responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def aggregate_student_analytics(
    body: StudentAggregateRequest, db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(body.from_at, body.to_at)
    profile_ids = _authorized_aggregate_profiles(db, actor_id, body.profile_ids)
    if body.include_problem_facts and _distinct_student_problem_count(
        db, profile_ids, body.from_at, body.to_at, actor_id,
    ) > 1000:
        raise HTTPException(422, {"code": "validation_error", "message": "include_problem_facts is limited to 1000 facts; use the paged problem-facts endpoint"})
    rows, tags_by_problem, groups_by_problem = _load_student_fact_data(
        db, profile_ids, body.from_at, body.to_at, actor_id,
    )
    by_profile = {profile_id: [] for profile_id in profile_ids}
    for row in rows:
        by_profile[row["profile_id"]].append(row)
    tag_catalog_counts, all_tag_ids, all_group_ids = _catalog_problem_counts(db, actor_id)
    normalized_groups = [(group.key, set(group.tag_ids)) for group in body.tag_groups]
    students = []
    for profile_id in profile_ids:
        student_rows = by_profile[profile_id]
        facts = _problem_fact_rows(student_rows, tags_by_problem, groups_by_problem)
        verdict_counts: dict[str, int] = {}
        for row in student_rows:
            key = _result_key(row["result"])
            verdict_counts[key] = verdict_counts.get(key, 0) + 1
        solved_ids = {fact["problem_id"] for fact in facts if fact["ac_count"] > 0}
        last_submission_at = max((as_utc(row["submitted_at"]) for row in student_rows), default=None)
        tag_stats = []
        rows_by_tag: dict[int, list[dict]] = {tag_id: [] for tag_id in all_tag_ids}
        for row in student_rows:
            for tag_id in tags_by_problem.get(row["problem_id"], []):
                rows_by_tag.setdefault(tag_id, []).append(row)
        for tag_id in all_tag_ids:
            tagged_rows = rows_by_tag[tag_id]
            tagged_problems = {row["problem_id"] for row in tagged_rows}
            solved = {problem_id for problem_id in tagged_problems if problem_id in solved_ids}
            tag_verdicts: dict[str, int] = {}
            for row in tagged_rows:
                key = _result_key(row["result"])
                tag_verdicts[key] = tag_verdicts.get(key, 0) + 1
            tag_stats.append(StudentTagStat(
                tag_id=tag_id, problem_count=tag_catalog_counts.get(tag_id, 0),
                solved_unique_count=len(solved), attempted_unique_count=len(tagged_problems),
                verdict_counts=tag_verdicts,
            ))
        group_stats = []
        for group_id in all_group_ids:
            solved = {fact["problem_id"] for fact in facts
                      if fact["ac_count"] and groups_by_problem.get(fact["problem_id"]) == group_id}
            group_stats.append(StudentGroupStat(group_id=group_id, solved_unique_count=len(solved)))
        requested_stats = []
        for key, requested_tags in normalized_groups:
            matching = [fact for fact in facts if requested_tags.intersection(fact["tag_ids"])]
            requested_stats.append(RequestedGroupStat(
                key=key,
                solved_unique_count=sum(1 for fact in matching if fact["ac_count"] > 0),
                attempted_unique_count=len(matching),
            ))
        students.append(StudentAggregateItem(
            profile_id=profile_id, total_submissions=len(student_rows),
            solved_unique_count=len(solved_ids), last_submission_at=last_submission_at,
            verdict_counts=verdict_counts, tag_stats=tag_stats, group_stats=group_stats,
            requested_group_stats=requested_stats,
            problem_facts=facts if body.include_problem_facts else None,
        ))
    return StudentAggregateResponse(
        students=students, as_of=utc_now(), reference_now=_reference_now(db, actor_id, profile_ids),
        catalog_version=_catalog_version(db, actor_id),
    )


@app.post(f"{API_PREFIX}/analytics/students/alerts", response_model=StudentAlertsResponse,
          responses={**COMMON_ERROR_RESPONSES, **error_responses(404)})
def student_analytics_alerts(
    body: StudentAlertsRequest,
    db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    profile_ids = _authorized_aggregate_profiles(db, actor_id, body.profile_ids)
    at = as_utc(body.at)
    since = at - timedelta(hours=24)
    visible_problems = _visible_problem_where(db, actor_id)
    latest_rows = db.execute(select(
        submission.c.user_id, func.max(submission.c.date),
    ).select_from(submission.join(problem, problem.c.id == submission.c.problem_id)).where(
        submission.c.user_id.in_(profile_ids), *visible_problems,
    ).group_by(submission.c.user_id)).all()
    latest = {profile_id: as_utc(value) for profile_id, value in latest_rows}
    stuck_profiles = set(db.execute(select(submission.c.user_id).select_from(
        submission.join(problem, problem.c.id == submission.c.problem_id),
    ).where(
        submission.c.user_id.in_(profile_ids),
        submission.c.date >= since.replace(tzinfo=None),
        submission.c.date < at.replace(tzinfo=None),
        submission.c.result != "AC",
        *visible_problems,
    ).group_by(submission.c.user_id, submission.c.problem_id)
        .having(func.count(submission.c.id) >= 8)).scalars().all())
    return StudentAlertsResponse(
        items=[StudentAlertItem(
            profile_id=profile_id, last_submission_at=latest.get(profile_id),
            has_stuck_problem=profile_id in stuck_profiles,
        ) for profile_id in profile_ids],
        as_of=utc_now(), reference_now=_reference_now(db, actor_id, profile_ids),
    )


@app.get(f"{API_PREFIX}/students/{{profile_id}}/problem-facts", response_model=ProblemFactsPage,
         responses={**COMMON_ERROR_RESPONSES, **error_responses(404, 409)})
def student_problem_facts(
    profile_id: int, from_at: datetime | None = Query(None, alias="from"),
    to_at: datetime | None = Query(None, alias="to"), cursor: str | None = None,
    limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db),
    actor_id: int = Depends(actor_profile_id),
):
    _validated_dates(from_at, to_at)
    if profile_row(db, profile_id) is None or not submission_visible(db, profile_id, actor_id):
        raise HTTPException(404, {"code": "not_found", "message": "Student not found"})
    rows, tags_by_problem, groups_by_problem = _load_student_fact_data(db, [profile_id], from_at, to_at, actor_id)
    facts = _problem_fact_rows(rows, tags_by_problem, groups_by_problem)
    version = _catalog_version(db, actor_id)
    scope = json.dumps({
        "actor_id": actor_id, "profile_id": profile_id,
        "from": as_utc(from_at).isoformat() if from_at else None,
        "to": as_utc(to_at).isoformat() if to_at else None, "limit": limit,
    }, sort_keys=True, separators=(",", ":"))
    snapshot_rows = [tuple(row.get(key) for key in (
        "submission_id", "problem_id", "submitted_at", "result", "status", "points", "time",
        "memory", "version_update", "judged_date", "rejudged_date",
    )) for row in rows]
    snapshot = fingerprint([{"rows": snapshot_rows, "tags": tags_by_problem,
                             "groups": groups_by_problem, "catalog_version": version}])
    last_problem_id = 0
    if cursor:
        payload = cursor_payload(cursor, "student_problem_facts", scope, snapshot)
        try:
            last_problem_id = int(payload["last_problem_id"])
            if last_problem_id < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, {"code": "cursor_expired", "message": "Cursor expired or does not match this query"})
    page_facts = [fact for fact in facts if fact["problem_id"] > last_problem_id]
    page = page_facts[:limit]
    has_more = len(page_facts) > limit
    next_cursor = encode_cursor(0, "student_problem_facts", scope, snapshot,
                                last_problem_id=page[-1]["problem_id"]) if has_more and page else None
    return ProblemFactsPage(items=page, next_cursor=next_cursor, has_more=has_more,
                             total=len(facts), as_of=utc_now(), catalog_version=version)

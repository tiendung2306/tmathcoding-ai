"""Class sessions ("phiên học") are contests owned by the Source API.

The dashboard no longer creates or stops sessions itself: a session is a contest
mapped to one or more classes, and its live view reads the classes' submissions
inside the contest's time window. The legacy `tmath_virtual_class_session` table is
kept for historical data only.
"""
import asyncio
import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.request_cache import cached_call
from app.core.time import utc_now
from app.schemas.virtual_class import LiveSubmissionEvent, LiveSubmissionItem, LiveSubmissionsResponse, SessionProblem
from app.services.contest_access import get_visible_contest
from app.services.source_gateway import SourceGateway, get_source_gateway

router = APIRouter()
logger = logging.getLogger(__name__)

CONTEST_LIVE_TTL_SECONDS = 3


def _to_utc_aware(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def contest_class_scope(contest, class_id: int | None) -> list[int]:
    """Classes of a contest to read, optionally narrowed to one mapped class."""
    if class_id is None:
        return list(contest.class_ids)
    if class_id not in contest.class_ids:
        raise HTTPException(404, "Lớp không thuộc phiên học này.")
    return [class_id]


async def _class_submissions_in_window(source: SourceGateway, class_id: int, actor_profile_id: int,
                                       starts_at, cutoff) -> list:
    items, cursor, seen_cursors = [], None, set()
    while True:
        page = await source.list_class_submissions(
            class_id, actor_profile_id=actor_profile_id, date_from=starts_at, date_to=cutoff,
            after_submission_id=None, cursor=cursor, limit=100,
        )
        items.extend(page.items)
        if not page.has_more:
            return items
        cursor = page.next_cursor
        if not cursor or cursor in seen_cursors:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả cursor bài nộp không hợp lệ.")
        seen_cursors.add(cursor)


def problem_label(index: int) -> str:
    """A, B, ..., Z, AA, AB, ... like the judge's contest problem labels."""
    label = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


async def _session_problems(source: SourceGateway, contest_id: int, actor_profile_id: int) -> list[SessionProblem]:
    try:
        page = await source.list_contest_problems(contest_id, actor_profile_id=actor_profile_id)
    except HTTPException as exc:
        if exc.status_code == 404:  # provider without contest problems: fall back to all submissions
            return []
        raise
    ordered = sorted(page.items, key=lambda item: (item.order, item.problem_id))
    return [SessionProblem(problem_id=item.problem_id, code=item.code, title=item.title, label=problem_label(index),
                           points=item.points, problem_points=item.problem_points, partial=item.partial)
            for index, item in enumerate(ordered)]


def contest_score(item, problem: SessionProblem | None) -> float | None:
    """Submission points on the contest's scale, the way the judge scores contest submissions."""
    if problem is None or problem.points is None:
        return None
    if item.result == "AC":
        return float(problem.points)
    if not problem.partial or not item.points or not problem.problem_points:
        return 0.0
    return round(min(item.points / problem.problem_points, 1) * problem.points, 3)


async def _contest_live_snapshot(source: SourceGateway, contest_id: int, actor_profile_id: int,
                                 class_id: int | None) -> LiveSubmissionsResponse:
    contest = await get_visible_contest(source, contest_id, actor_profile_id)
    class_ids = contest_class_scope(contest, class_id)
    problems = await _session_problems(source, contest_id, actor_profile_id)
    problem_ids = {problem.problem_id for problem in problems}
    now = _to_utc_aware(utc_now())
    starts_at = _to_utc_aware(contest.starts_at)
    ends_at = _to_utc_aware(contest.ends_at)
    cutoff = min(now, ends_at)
    submissions = {}
    if starts_at < cutoff and class_ids:
        # Classes are independent; load them concurrently (the gateway bounds concurrency).
        pages = await asyncio.gather(*(
            _class_submissions_in_window(source, item, actor_profile_id, starts_at, cutoff)
            for item in class_ids
        ))
        for items in pages:
            for item in items:
                # A session counts only its own problems when the source lists them.
                if not problem_ids or item.problem_id in problem_ids:
                    submissions[item.submission_id] = item

    ordered = sorted(submissions.values(), key=lambda item: (item.submitted_at, item.submission_id), reverse=True)
    by_id = {problem.problem_id: problem for problem in problems}
    return LiveSubmissionsResponse(
        events=[LiveSubmissionEvent(kind="created", submission_id=item.submission_id,
                                    record=_live_item(item, contest_score(item, by_id.get(item.problem_id))))
                for item in ordered],
        problems=problems,
        snapshot=True,
        is_active=contest.status == "active",
    )


@router.get("/contests/{contest_id}/live-submissions", response_model=LiveSubmissionsResponse)
async def get_contest_live_submissions(
    contest_id: int,
    class_id: int | None = Query(None, ge=1, description="Chỉ đọc bài nộp của một lớp thuộc phiên học"),
    source: SourceGateway = Depends(get_source_gateway),
    actor=Depends(get_current_user),
):
    """Submissions by students of the session's classes during its time window."""
    return await cached_call(
        ("contest-live", actor.profile_id, contest_id, class_id), CONTEST_LIVE_TTL_SECONDS,
        lambda: _contest_live_snapshot(source, contest_id, actor.profile_id, class_id),
    )


def _live_item(item, score: float | None = None) -> LiveSubmissionItem:
    return LiveSubmissionItem(
        id=item.submission_id,
        user_id=item.profile_id,
        user_name=item.student_name or f"User {item.profile_id}",
        problem_id=item.problem_id,
        problem_code=item.problem_code,
        problem_name=item.problem_title or item.problem_code or f"Bài #{item.problem_id}",
        date=item.submitted_at,
        result=item.result or item.status or "?",
        points=item.points or 0,
        score=score,
        time=item.time,
        memory=item.memory,
        source=None,
        ai_flags={"has_error": item.result not in (None, "AC")},
    )

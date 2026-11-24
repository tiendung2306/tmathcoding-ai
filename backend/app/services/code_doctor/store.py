"""Persistence for the solution bank and reports, behind a small interface.

``SqlDoctorStore`` writes to ``tmath_dashboard``; ``MemoryDoctorStore`` keeps
the same behaviour in memory for tests and for running without the database.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol

from sqlalchemy import select, update

from app.core.time import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ApproachRecord:
    id: int | None
    problem_id: int
    language: str
    name: str
    control_flow: str
    techniques: list[str]
    complexity_rank: float
    representative_submission_id: int
    summary: str | None = None
    key_ideas: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    time_complexity: str | None = None
    member_count: int = 1
    status: str = "auto"
    is_canonical: bool = False
    card_origin: str = "static"
    reviewed_by: int | None = None
    updated_at: datetime | None = None


@dataclass
class MemberRecord:
    approach_id: int
    submission_id: int
    problem_id: int
    language_key: str | None
    source_hash: str
    cost: int = 0


class DoctorStore(Protocol):
    async def list_approaches(self, problem_id: int) -> list[ApproachRecord]: ...
    async def get_approach(self, approach_id: int) -> ApproachRecord | None: ...
    async def member_ids(self, problem_id: int) -> set[int]: ...
    async def create_approach(self, record: ApproachRecord, member: MemberRecord) -> ApproachRecord: ...
    async def add_member(self, member: MemberRecord) -> None: ...
    async def update_approach(self, approach_id: int, **fields) -> ApproachRecord | None: ...
    async def clear_canonical(self, problem_id: int, except_id: int) -> None: ...
    async def get_report(self, submission_id: int, fingerprint: str) -> dict | None: ...
    async def save_report(self, submission_id: int, fingerprint: str, problem_id: int, approach_id: int | None,
                          verdict: str, origin: str, model: str | None, policy_version: str, report: dict) -> None: ...
    async def add_feedback(self, submission_id: int, fingerprint: str, teacher_profile_id: int,
                           rating: str, note: str | None) -> None: ...


APPROACH_FIELDS = {"name", "summary", "key_ideas", "pitfalls", "time_complexity", "status",
                   "is_canonical", "card_origin", "reviewed_by"}


class MemoryDoctorStore:
    def __init__(self):
        self.approaches: dict[int, ApproachRecord] = {}
        self.members: dict[tuple[int, int], MemberRecord] = {}
        self.reports: dict[int, dict] = {}
        self.feedback: list[dict] = []
        self._ids = itertools.count(1)

    async def list_approaches(self, problem_id):
        return [replace(a) for a in self.approaches.values() if a.problem_id == problem_id]

    async def get_approach(self, approach_id):
        record = self.approaches.get(approach_id)
        return replace(record) if record else None

    async def member_ids(self, problem_id):
        return {m.submission_id for m in self.members.values() if m.problem_id == problem_id}

    async def create_approach(self, record, member):
        stored = replace(record, id=next(self._ids), updated_at=utc_now())
        self.approaches[stored.id] = stored
        self.members[(stored.id, member.submission_id)] = replace(member, approach_id=stored.id)
        return replace(stored)

    async def add_member(self, member):
        key = (member.approach_id, member.submission_id)
        if key in self.members:
            return
        self.members[key] = member
        approach = self.approaches[member.approach_id]
        approach.member_count += 1

    async def update_approach(self, approach_id, **fields):
        record = self.approaches.get(approach_id)
        if record is None:
            return None
        for name, value in fields.items():
            if name in APPROACH_FIELDS:
                setattr(record, name, value)
        record.updated_at = utc_now()
        return replace(record)

    async def clear_canonical(self, problem_id, except_id):
        for record in self.approaches.values():
            if record.problem_id == problem_id and record.id != except_id:
                record.is_canonical = False

    async def get_report(self, submission_id, fingerprint):
        row = self.reports.get(submission_id)
        return row["report"] if row and row["fingerprint"] == fingerprint else None

    async def save_report(self, submission_id, fingerprint, problem_id, approach_id, verdict, origin, model,
                          policy_version, report):
        self.reports[submission_id] = {"fingerprint": fingerprint, "report": report, "origin": origin}

    async def add_feedback(self, submission_id, fingerprint, teacher_profile_id, rating, note):
        self.feedback.append(dict(submission_id=submission_id, fingerprint=fingerprint,
                                  teacher_profile_id=teacher_profile_id, rating=rating, note=note))


def _to_record(row) -> ApproachRecord:
    return ApproachRecord(
        id=row.id, problem_id=row.problem_id, language=row.language, name=row.name,
        control_flow=row.control_flow, techniques=list(row.techniques or []),
        complexity_rank=float(row.complexity_rank or 0), representative_submission_id=row.representative_submission_id,
        summary=row.summary, key_ideas=list(row.key_ideas or []), pitfalls=list(row.pitfalls or []),
        time_complexity=row.time_complexity, member_count=row.member_count, status=row.status,
        is_canonical=bool(row.is_canonical), card_origin=row.card_origin, reviewed_by=row.reviewed_by,
        updated_at=row.updated_at,
    )


class SqlDoctorStore:
    def __init__(self, session_factory=None):
        self._factory = session_factory

    def _sessions(self):
        if self._factory is None:
            from app.core.dashboard_database import DashboardSessionLocal
            self._factory = DashboardSessionLocal
        return self._factory()

    async def list_approaches(self, problem_id):
        from app.models.code_doctor import DoctorSolutionApproach as A
        async with self._sessions() as db:
            rows = (await db.execute(select(A).where(A.problem_id == problem_id).order_by(A.id))).scalars().all()
            return [_to_record(row) for row in rows]

    async def get_approach(self, approach_id):
        from app.models.code_doctor import DoctorSolutionApproach as A
        async with self._sessions() as db:
            row = await db.get(A, approach_id)
            return _to_record(row) if row else None

    async def member_ids(self, problem_id):
        from app.models.code_doctor import DoctorSolutionMember as M
        async with self._sessions() as db:
            rows = await db.execute(select(M.submission_id).where(M.problem_id == problem_id))
            return {row[0] for row in rows}

    async def create_approach(self, record, member):
        from app.models.code_doctor import DoctorSolutionApproach as A, DoctorSolutionMember as M
        async with self._sessions() as db:
            row = A(problem_id=record.problem_id, language=record.language, name=record.name[:255],
                    summary=record.summary, key_ideas=record.key_ideas, pitfalls=record.pitfalls,
                    time_complexity=record.time_complexity, control_flow=record.control_flow[:512],
                    techniques=record.techniques, complexity_rank=record.complexity_rank,
                    representative_submission_id=record.representative_submission_id, member_count=1,
                    status=record.status, is_canonical=record.is_canonical, card_origin=record.card_origin)
            db.add(row)
            await db.flush()
            db.add(M(approach_id=row.id, submission_id=member.submission_id, problem_id=member.problem_id,
                     language_key=member.language_key, source_hash=member.source_hash, cost=member.cost))
            await db.commit()
            return _to_record(row)

    async def add_member(self, member):
        from app.models.code_doctor import DoctorSolutionApproach as A, DoctorSolutionMember as M
        async with self._sessions() as db:
            if await db.get(M, (member.approach_id, member.submission_id)) is not None:
                return
            db.add(M(approach_id=member.approach_id, submission_id=member.submission_id, problem_id=member.problem_id,
                     language_key=member.language_key, source_hash=member.source_hash, cost=member.cost))
            await db.execute(update(A).where(A.id == member.approach_id).values(member_count=A.member_count + 1))
            await db.commit()

    async def update_approach(self, approach_id, **fields):
        from app.models.code_doctor import DoctorSolutionApproach as A
        async with self._sessions() as db:
            row = await db.get(A, approach_id)
            if row is None:
                return None
            for name, value in fields.items():
                if name in APPROACH_FIELDS:
                    setattr(row, name, value)
            row.updated_at = utc_now()
            await db.commit()
            return _to_record(row)

    async def clear_canonical(self, problem_id, except_id):
        from app.models.code_doctor import DoctorSolutionApproach as A
        async with self._sessions() as db:
            await db.execute(update(A).where(A.problem_id == problem_id, A.id != except_id).values(is_canonical=False))
            await db.commit()

    async def get_report(self, submission_id, fingerprint):
        from app.models.code_doctor import DoctorReport as R
        async with self._sessions() as db:
            row = await db.get(R, submission_id)
            return row.report if row is not None and row.input_fingerprint == fingerprint else None

    async def save_report(self, submission_id, fingerprint, problem_id, approach_id, verdict, origin, model,
                          policy_version, report):
        from app.models.code_doctor import DoctorReport as R
        async with self._sessions() as db:
            row = await db.get(R, submission_id)
            values = dict(input_fingerprint=fingerprint, problem_id=problem_id, approach_id=approach_id,
                          verdict=verdict[:16], origin=origin, model=(model or "")[:255] or None,
                          policy_version=policy_version, report=report, created_at=utc_now())
            if row is None:
                db.add(R(submission_id=submission_id, **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            await db.commit()

    async def add_feedback(self, submission_id, fingerprint, teacher_profile_id, rating, note):
        from app.models.code_doctor import DoctorFeedback as F
        async with self._sessions() as db:
            db.add(F(submission_id=submission_id, input_fingerprint=fingerprint,
                     teacher_profile_id=teacher_profile_id, rating=rating, note=note))
            await db.commit()

"""Code Doctor solution bank and reports (dashboard-owned).

Approaches follow Clara's clusters of correct solutions. Source code is never
stored here: members keep the submission ID and a hash, and the source is
read again through Source API with the caller's permissions.
"""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text

from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class DoctorSolutionApproach(DashboardBase):
    __tablename__ = "doctor_solution_approach"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(Integer, nullable=False, index=True)
    language = Column(String(16), nullable=False)
    name = Column(String(255), nullable=False)
    summary = Column(Text)
    key_ideas = Column(JSON)
    pitfalls = Column(JSON)
    time_complexity = Column(String(64))
    control_flow = Column(String(512), nullable=False)
    techniques = Column(JSON, nullable=False)
    complexity_rank = Column(Float, nullable=False, default=0.0)
    representative_submission_id = Column(Integer, nullable=False)
    member_count = Column(Integer, nullable=False, default=1)
    # auto: created by the clustering; approved/rejected: decided by a teacher.
    status = Column(String(16), nullable=False, default="auto")
    is_canonical = Column(Boolean, nullable=False, default=False)
    card_origin = Column(String(16), nullable=False, default="static")
    reviewed_by = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class DoctorSolutionMember(DashboardBase):
    __tablename__ = "doctor_solution_member"
    __table_args__ = (Index("ix_doctor_solution_member_problem", "problem_id", "submission_id"),)

    approach_id = Column(Integer, ForeignKey("doctor_solution_approach.id", ondelete="CASCADE"), primary_key=True)
    submission_id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, nullable=False)
    language_key = Column(String(32))
    source_hash = Column(String(64), nullable=False)
    cost = Column(Integer, nullable=False, default=0)
    added_at = Column(DateTime, nullable=False, default=utc_now)


class DoctorReport(DashboardBase):
    __tablename__ = "doctor_report"

    submission_id = Column(Integer, primary_key=True)
    input_fingerprint = Column(String(64), nullable=False)
    problem_id = Column(Integer, nullable=False, index=True)
    approach_id = Column(Integer)
    verdict = Column(String(16), nullable=False)
    origin = Column(String(16), nullable=False)
    model = Column(String(255))
    policy_version = Column(String(32), nullable=False)
    report = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class DoctorFeedback(DashboardBase):
    __tablename__ = "doctor_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, nullable=False, index=True)
    input_fingerprint = Column(String(64), nullable=False)
    teacher_profile_id = Column(Integer, nullable=False)
    rating = Column(String(16), nullable=False)
    note = Column(Text)
    created_at = Column(DateTime, nullable=False, default=utc_now)

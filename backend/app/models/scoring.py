from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text
from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class ScoringState(DashboardBase):
    __tablename__ = "scoring_state"
    id = Column(Integer, primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    policy = Column(JSON, nullable=False)
    active_run_id = Column(String(32), nullable=True)


class ScoringRun(DashboardBase):
    __tablename__ = "scoring_run"
    id = Column(String(32), primary_key=True)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, index=True)
    actor_id = Column(Integer, nullable=False)
    policy_revision = Column(Integer, nullable=False)
    policy = Column(JSON, nullable=False)
    base_run_id = Column(String(32))
    points_run_id = Column(String(32))
    lease_token = Column(String(32))
    lease_until = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    completed_at = Column(DateTime)
    published_at = Column(DateTime)
    source_as_of = Column(DateTime)
    manifest = Column(JSON)
    diagnostics = Column(JSON)
    progress = Column(String(255), nullable=False, default="Đang chờ worker")
    error = Column(Text)


class ScoringItem(DashboardBase):
    __tablename__ = "scoring_item"
    run_id = Column(String(32), primary_key=True)
    problem_id = Column(Integer, primary_key=True)
    code = Column(String(64), nullable=False)
    title = Column(String(512), nullable=False)
    source_group_id = Column(Integer)
    grade = Column(String(1))
    points = Column(Integer)
    difficulty = Column(Float)
    attempted = Column(Integer, nullable=False, default=0)
    solved = Column(Integer, nullable=False, default=0)
    method = Column(String(24), nullable=False, default="UNCLASSIFIED")


class ScoringProfile(DashboardBase):
    __tablename__ = "scoring_profile"
    run_id = Column(String(32), primary_key=True)
    profile_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    username = Column(String(150), nullable=False)
    total_points = Column(BigInteger, nullable=False, default=0)
    solved_count = Column(Integer, nullable=False, default=0)
    unscored_count = Column(Integer, nullable=False, default=0)
    __table_args__ = (Index("ix_scoring_profile_leaderboard", "run_id", "total_points", "profile_id"),)


class ScoringPair(DashboardBase):
    __tablename__ = "scoring_pair"
    run_id = Column(String(32), primary_key=True)
    profile_id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, primary_key=True)
    has_ac = Column(Boolean, nullable=False)
    first_ac_at = Column(DateTime)
    __table_args__ = (Index("ix_scoring_pair_problem", "run_id", "problem_id", "has_ac"),)

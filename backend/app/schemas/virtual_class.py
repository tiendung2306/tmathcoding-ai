from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class LiveSubmissionItem(BaseModel):
    id: int
    user_id: int
    user_name: str
    problem_id: int
    problem_code: Optional[str] = None
    problem_name: str
    date: datetime
    result: str
    points: float
    # Points on the contest's scale (judge_contestproblem.points), when known.
    score: Optional[float] = None
    time: Optional[float]
    memory: Optional[float]
    source: Optional[str] = None
    ai_flags: dict = {}


class LiveSubmissionEvent(BaseModel):
    kind: str
    submission_id: int
    record: Optional[LiveSubmissionItem] = None


class SessionProblem(BaseModel):
    problem_id: int
    code: str
    title: str
    label: str
    points: Optional[float] = None
    problem_points: Optional[float] = None
    partial: bool = True


class LiveSubmissionsResponse(BaseModel):
    events: List[LiveSubmissionEvent]
    # The session's own problems in contest order; empty when the source has none.
    problems: List[SessionProblem] = []
    cursor: Optional[str] = None
    high_watermark: Optional[int] = None
    snapshot: bool = False
    is_active: bool

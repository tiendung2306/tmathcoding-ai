from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class LiveSubmissionItem(BaseModel):
    id: int
    user_id: int
    user_name: str
    problem_id: int
    problem_name: str
    date: datetime
    result: str
    points: float
    time: Optional[float]
    memory: Optional[float]
    source: Optional[str] = None
    ai_flags: dict = {}
    
class VirtualClassSessionItem(BaseModel):
    id: int
    org_id: int
    name: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None

class VirtualClassSessionListResponse(BaseModel):
    sessions: List[VirtualClassSessionItem]
    active_session: Optional[VirtualClassSessionItem] = None

class VirtualClassStatus(BaseModel):
    org_id: int
    is_active: bool
    session_id: Optional[int] = None
    started_at: Optional[datetime] = None

class LiveSubmissionsResponse(BaseModel):
    submissions: List[LiveSubmissionItem]
    last_id: int

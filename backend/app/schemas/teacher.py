from pydantic import BaseModel
from typing import List, Optional

class ClassSummary(BaseModel):
    id: int
    name: str
    member_count: int = 0

class StudentSearchItem(BaseModel):
    user_id: int
    name: str
    username: str
    points: float
    problem_count: int

class ClassStudentItem(BaseModel):
    user_id: int
    name: str
    username: str
    points: float = 0.0
    problem_count: int = 0
    display_rank: str = "user"
    alerts: List[str] = []
    last_submission_at: Optional[str] = None

class HeatmapStudentRow(BaseModel):
    user_id: int
    student_name: str
    scores: List[float]
    alerts: List[str]  # 'STUCK', 'GAP', 'INACTIVE'

class ClassHeatmapResponse(BaseModel):
    organization_id: int
    organization_name: str
    time_range: str = "all"
    columns: List[str]
    students: List[HeatmapStudentRow]
    class_averages: List[float]

class StudentBloomScore(BaseModel):
    group_id: int
    label: str
    score: float

class StudentDetailSummary(BaseModel):
    total_problems_in_system: int = 0
    total_solved_unique: int = 0
    total_submissions_7d: int = 0
    time_range: str = "all"
    total_submissions_period: int = 0

class StudentDetailResponse(BaseModel):
    """F2.2: Student Search & Detail View."""
    user_id: int
    name: str
    username: str
    time_range: str = "all"
    points: float = 0.0
    performance_points: float = 0.0
    problem_count: int = 0
    display_rank: str = "user"
    organizations: List[str] = []
    bloom_scores: List[StudentBloomScore] = []
    alerts: List[str] = []
    last_submission_at: Optional[str] = None
    summary: StudentDetailSummary

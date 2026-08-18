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

class HeatmapStudentRow(BaseModel):
    user_id: int
    student_name: str
    scores: List[float]
    alerts: List[str]  # 'STUCK', 'GAP', 'INACTIVE'

class ClassHeatmapResponse(BaseModel):
    organization_id: int
    organization_name: str
    columns: List[str]
    students: List[HeatmapStudentRow]
    class_averages: List[float]

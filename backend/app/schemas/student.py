from pydantic import BaseModel
from typing import List, Dict, Optional

class BloomRadar(BaseModel):
    A_Nho: float = 0.0
    B_Hieu: float = 0.0
    C_VanDung: float = 0.0
    D_PhanTich: float = 0.0
    E_DanhGia: float = 0.0
    F_DacBiet: float = 0.0

class SkillTreeNode(BaseModel):
    topic_id: int
    key: str
    name: str
    category: str
    mastery_score: float
    status: str  # 'GREEN', 'YELLOW', 'RED', 'LOCKED'

class SkillTreeResponse(BaseModel):
    user_id: int
    student_name: str
    bloom_radar: BloomRadar
    skill_tree_nodes: List[SkillTreeNode]

class FailedSubmissionItem(BaseModel):
    submission_id: int
    problem_id: int
    problem_code: str
    problem_name: str
    result: str
    status: Optional[str] = None
    date: Optional[str] = None
    points: float = 0.0
    language_id: Optional[int] = None

class TestCaseDetailItem(BaseModel):
    case: int
    status: str
    time: Optional[float] = None
    memory: Optional[float] = None
    points: Optional[float] = None
    total: Optional[float] = None
    feedback: Optional[str] = None
    output: Optional[str] = None

class SubmissionDetailResponse(BaseModel):
    submission_id: int
    user_id: int
    problem_id: int
    problem_code: str
    problem_name: str
    problem_description: str
    time_limit: float
    memory_limit: int
    problem_points: float
    result: str
    status: Optional[str] = None
    date: Optional[str] = None
    time: Optional[float] = None
    memory: Optional[float] = None
    points: float = 0.0
    language_name: str
    source_code: str
    testcases: List[TestCaseDetailItem] = []


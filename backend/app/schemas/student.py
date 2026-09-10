from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class PillarBreakdownItem(BaseModel):
    score: float = 0.0
    base_score: float = 0.0
    precision_mod: float = 0.0
    efficiency_mod: float = 0.0
    code_quality_mod: float = 0.0
    ac_count: int = 0
    total_subs: int = 0
    avg_time_ratio: float = 0.0
    breakdown_items: List[Dict[str, Any]] = []

class AlgorithmRadar(BaseModel):
    time_range: str = "all"
    quy_hoach_dong: float = 0.0
    cau_truc_du_lieu: float = 0.0
    xu_ly_xau: float = 0.0
    ham_co_ban: float = 0.0
    toan_hoc: float = 0.0
    hinh_hoc: float = 0.0
    do_thi: float = 0.0
    tham_lam: float = 0.0
    breakdown: Optional[Dict[str, PillarBreakdownItem]] = None

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
    time_range: str = "all"
    bloom_radar: AlgorithmRadar
    skill_tree_nodes: List[SkillTreeNode]

class StudentRecentSubmission(BaseModel):
    id: int
    date: str
    result: str
    points: float = 0.0
    problem_id: int
    problem_code: str
    problem_name: str

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

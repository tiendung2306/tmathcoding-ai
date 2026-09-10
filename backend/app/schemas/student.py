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

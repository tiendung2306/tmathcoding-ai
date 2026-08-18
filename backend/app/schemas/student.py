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


from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class JudgeProblemAiTag(DashboardBase):
    __tablename__ = "judge_problem_ai_tag"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(Integer, unique=True, nullable=False)
    primary_tag_id = Column(Integer, index=True, nullable=False)
    secondary_tag_ids = Column(JSON, nullable=True)
    bloom_group_id = Column(Integer, index=True, nullable=True)
    reasoning = Column(Text, nullable=True)
    model = Column(String(100), default="Qwen3.8-4B-GGUF")
    created_at = Column(DateTime, default=utc_now, index=True)

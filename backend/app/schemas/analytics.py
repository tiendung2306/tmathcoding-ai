from pydantic import BaseModel, Field
from typing import List, Optional

class TagSubmissionStat(BaseModel):
    total_submissions: int = 0
    ac_count: int = 0
    wa_count: int = 0
    tle_count: int = 0
    other_count: int = 0
    ac_rate: float = 0.0
    wa_rate: float = 0.0
    tle_rate: float = 0.0
    primary_error: Optional[str] = None

class TagMetricItem(BaseModel):
    tag_id: int
    key: str
    name: str
    total_problems: int = 0
    ac_problems: int = 0
    completion_rate: float = 0.0
    tag_weight: str = "medium"  # 'small' (<=3), 'medium' (4-9), 'large' (>=10)
    submissions_stat: TagSubmissionStat
    status: str = "UNATTEMPTED"  # 'MASTERED', 'PRACTICING', 'NEEDS_IMPROVEMENT', 'UNATTEMPTED'

class StudentTagAnalyticsSummary(BaseModel):
    total_problems_in_system: int = 0
    total_solved_unique: int = 0
    total_submissions_7d: int = 0

class StudentTagAnalyticsResponse(BaseModel):
    user_id: int
    student_name: str
    summary: StudentTagAnalyticsSummary
    tags: List[TagMetricItem]

class Recent7DaysSummary(BaseModel):
    submissions_count: int = 0
    active_tags: List[str] = []

class AICommentaryResponse(BaseModel):
    commentary: str
    recent_7days_summary: Recent7DaysSummary
    recommended_tags: List[str] = []
    generated_at: str

class AICommentaryLLMSchema(BaseModel):
    commentary: str = Field(
        description="Lời nhận xét 2 phần cho học sinh (Review 7 ngày qua + Gợi ý vui vẻ hằng ngày)"
    )
    recommended_tags: List[str] = Field(
        default=[],
        description="Danh sách 1-3 tên Tag bài tập gợi ý nên làm tiếp theo"
    )

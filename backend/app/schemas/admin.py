from pydantic import BaseModel, Field
from typing import List, Optional

class AutoTagRecentProblemItem(BaseModel):
    id: int
    problem_id: int
    problem_code: str
    problem_name: str
    primary_tag_id: int
    primary_tag_name: str
    secondary_tag_ids: List[int] = Field(default_factory=list)
    bloom_group_id: Optional[int] = None
    bloom_group_name: Optional[str] = None
    reasoning: str
    model: str
    created_at: str

class AutoTagCurrentBatch(BaseModel):
    total: int
    processed: int
    successful: int
    failed: int
    started_at: str

class AutoTagStatusResponse(BaseModel):
    total_problems: int
    tagged_problems: int
    untagged_problems: int
    progress_percentage: float
    is_running: bool
    current_batch: Optional[AutoTagCurrentBatch] = None
    recent_tags: List[AutoTagRecentProblemItem] = Field(default_factory=list)

class AutoTagBatchRunRequest(BaseModel):
    batch_size: int = Field(default=10, ge=1, le=50, description="Số lượng bài toán cần phân loại trong batch (1-50)")

class AutoTagBatchRunResponse(BaseModel):
    status: str
    message: str
    batch_size: int

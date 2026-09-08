from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(str, Enum):
    CODE_DOCTOR = "CODE_DOCTOR"
    AI_COMMENTARY = "AI_COMMENTARY"
    AUTO_TAG = "AUTO_TAG"
    SELF_STUDY = "SELF_STUDY"


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = "Tác vụ đã được tiếp nhận và xử lý ngầm."
    result: Optional[Any] = None


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    progress: int = Field(default=0, ge=0, le=100)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    deadline_at: Optional[str] = None

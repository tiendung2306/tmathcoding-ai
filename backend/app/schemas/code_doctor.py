"""Code Doctor v2 report: what the teacher sees, and what the model must return."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Direction = Literal["on_track", "partially", "off_track", "unknown"]
Confidence = Literal["high", "medium", "low"]
Severity = Literal["high", "medium", "low"]


# ----------------------------------------------------------------- model output

class LLMFinding(BaseModel):
    point: str = Field(description="Một nhận xét ngắn, cụ thể")
    lines: List[int] = Field(default_factory=list, description="Số dòng L trong bài nộp")


class LLMWeakness(LLMFinding):
    severity: Severity = "medium"


class LLMLogicError(BaseModel):
    lines: List[int] = Field(default_factory=list, description="Số dòng L trong bài nộp có lỗi")
    what: str = Field(description="Đoạn mã sai làm gì")
    why: str = Field(description="Vì sao sai so với đề hoặc lời giải tham chiếu")
    fix: str = Field(description="Sửa tối thiểu cần làm")


class DoctorLLMOutput(BaseModel):
    overview: str = Field(description="2-3 câu kết luận cho giảng viên")
    direction: Literal["on_track", "partially", "off_track"]
    time_complexity: str = ""
    strengths: List[LLMFinding] = Field(default_factory=list)
    weaknesses: List[LLMWeakness] = Field(default_factory=list)
    logic_errors: List[LLMLogicError] = Field(default_factory=list)
    student_hints: List[str] = Field(default_factory=list, description="3 mức: gợi ý chung, chỉ vị trí, cách sửa")
    confidence: Confidence = "medium"


class ApproachCard(BaseModel):
    name: str = Field(description="Tên ngắn của hướng giải, ví dụ 'Mảng cộng dồn'")
    summary: str = Field(description="1-2 câu mô tả ý tưởng")
    key_ideas: List[str] = Field(default_factory=list)
    time_complexity: str = ""
    pitfalls: List[str] = Field(default_factory=list, description="Lỗi hay gặp khi cài đặt hướng này")


# ----------------------------------------------------------------- API report

class DoctorFinding(BaseModel):
    point: str
    lines: List[int] = Field(default_factory=list)
    severity: Optional[Severity] = None


class DoctorLogicError(BaseModel):
    lines: List[int]
    what: str
    why: str
    fix: str
    evidence: Literal["static", "reference_diff", "model"] = "model"


class DoctorStaticFact(BaseModel):
    kind: Literal["info", "risk"]
    text: str
    lines: List[int] = Field(default_factory=list)


class DoctorApproachInfo(BaseModel):
    approach_id: Optional[int] = None
    name: str
    status: str = "auto"
    summary: Optional[str] = None
    time_complexity: Optional[str] = None
    member_count: int = 1
    same_control_flow: Optional[bool] = None
    repair_cost: Optional[int] = None


class DoctorTestSummary(BaseModel):
    passed: Optional[int] = None
    total: Optional[int] = None
    failed_cases: List[int] = Field(default_factory=list)


class DoctorReportData(BaseModel):
    version: str = "doctor-v2"
    verdict: str
    origin: Literal["ai", "fallback", "verdict"]
    fallback_reason: Optional[str] = None
    overview: str
    direction: Direction = "unknown"
    estimated_complexity: Optional[str] = None
    expected_complexity: Optional[str] = None
    nearest_approach: Optional[DoctorApproachInfo] = None
    best_approach: Optional[DoctorApproachInfo] = None
    strengths: List[DoctorFinding] = Field(default_factory=list)
    weaknesses: List[DoctorFinding] = Field(default_factory=list)
    logic_errors: List[DoctorLogicError] = Field(default_factory=list)
    static_facts: List[DoctorStaticFact] = Field(default_factory=list)
    student_hints: List[str] = Field(default_factory=list)
    confidence: Confidence = "low"
    limitations: List[str] = Field(default_factory=list)
    tests: DoctorTestSummary = Field(default_factory=DoctorTestSummary)
    model: Optional[str] = None
    generated_at: Optional[str] = None


class DoctorFeedbackRequest(BaseModel):
    rating: Literal["correct", "partial", "wrong"]
    note: Optional[str] = Field(default=None, max_length=2000)


class DoctorApproachUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[Literal["auto", "approved", "rejected"]] = None
    is_canonical: Optional[bool] = None


class DoctorApproachItem(BaseModel):
    approach_id: int
    problem_id: int
    language: str
    name: str
    summary: Optional[str] = None
    key_ideas: List[str] = Field(default_factory=list)
    pitfalls: List[str] = Field(default_factory=list)
    time_complexity: Optional[str] = None
    control_flow: str
    techniques: List[str] = Field(default_factory=list)
    member_count: int
    representative_submission_id: int
    status: str
    is_canonical: bool
    card_origin: str

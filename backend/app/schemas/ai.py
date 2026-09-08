from pydantic import BaseModel, Field
from typing import List, Optional

class CodeDoctorDiagnosis(BaseModel):
    error_category: str = Field(description="Loại lỗi: TIME_LIMIT_EXCEEDED, WRONG_ANSWER, RUNTIME_ERROR, COMPILE_ERROR")
    advice: str = Field(description="Đoạn văn duy nhất nhận xét và chẩn đoán chính xác nguyên nhân lỗi của bài nộp")
    summary: Optional[str] = Field(default=None, description="Tóm tắt ngắn gọn")
    guiding_question: Optional[str] = Field(default=None, description="Câu hỏi gợi mở (nếu có)")
    actionable_hint: Optional[str] = Field(default=None, description="Gợi ý hướng tiếp cận (nếu có)")

class CodeDoctorRequest(BaseModel):
    submission_id: int
    force_refresh: bool = Field(default=False, description="Đặt True nếu muốn ép LLM phân tích lại, bỏ qua cache")

class CodeDoctorResponse(BaseModel):
    submission_id: int
    user_id: int
    problem_name: str
    diagnosis: CodeDoctorDiagnosis

class AutoTagResult(BaseModel):
    problem_id: int
    primary_tag_id: int = Field(description="ID từ 1 đến 99 trong danh mục judge_problemtype")
    secondary_tag_ids: List[int] = Field(default_factory=list)
    bloom_group_id: int = Field(description="Mức Bloom ID: 4(A), 5(B), 6(C), 7(D), 8(E), 13(F)")
    reasoning: str = Field(description="Lý do ngắn gọn dựa trên phân tích code AC mẫu và giới hạn input N")

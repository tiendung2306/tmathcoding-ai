from pydantic import BaseModel, Field
from typing import List, Optional

class CodeDoctorDiagnosis(BaseModel):
    error_category: str = Field(description="Loại lỗi: TIME_LIMIT_EXCEEDED, WRONG_ANSWER, RUNTIME_ERROR, COMPILE_ERROR")
    summary: str = Field(description="Tóm tắt nguyên nhân lỗi trong bài nộp của học sinh (1-2 câu)")
    guiding_question: str = Field(description="Câu hỏi gợi mở theo phương pháp Socratic để học sinh tự suy nghĩ vị trí dòng code sai")
    actionable_hint: str = Field(description="Gợi ý hướng tiếp cận tiếp theo mà KHÔNG cung cấp code giải")

class CodeDoctorRequest(BaseModel):
    submission_id: int

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

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.dmoj import JudgeSubmission, JudgeSubmissionsource, JudgeProblem, JudgeProfile
from app.schemas.ai import CodeDoctorDiagnosis, CodeDoctorResponse
from app.core.llm_adapter import llm_adapter
from fastapi import HTTPException

class CodeDoctorService:
    @staticmethod
    async def diagnose_submission(submission_id: int, db: AsyncSession) -> CodeDoctorResponse:
        # 1. Fetch submission details
        sub_stmt = select(JudgeSubmission).where(JudgeSubmission.id == submission_id)
        sub_res = await db.execute(sub_stmt)
        submission = sub_res.scalar_one_or_none()
        
        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found.")

        # 2. Fetch source code
        src_stmt = select(JudgeSubmissionsource).where(JudgeSubmissionsource.submission_id == submission_id)
        src_res = await db.execute(src_stmt)
        source_obj = src_res.scalar_one_or_none()
        source_code = source_obj.source if source_obj else "// No source code available"

        # 3. Fetch problem info
        prob_stmt = select(JudgeProblem).where(JudgeProblem.id == submission.problem_id)
        prob_res = await db.execute(prob_stmt)
        problem = prob_res.scalar_one_or_none()
        problem_title = problem.name if problem else "Problem"
        problem_desc = problem.description if problem else ""

        # 4. Construct Socratic Prompt
        system_prompt = (
            "Bạn là AI Code Doctor, chuyên gia huấn luyện lập trình thuật toán trên hệ thống tmath.\n"
            "Nhiệm vụ: Phân tích lỗi trong bài nộp và đưa ra gợi ý theo phương pháp Socratic để học sinh TỰ SUY NGHĨ.\n"
            "BẮT BỘC QUY TẮC: Tuyệt đối KHÔNG viết sẵn đoạn code đáp án hoặc cung cấp lời giải trực tiếp."
        )

        user_prompt = (
            f"Tên bài toán: {problem_title}\n"
            f"Mô tả đề bài: {problem_desc[:1000]}\n"
            f"Kết quả nộp: {submission.result} (Status: {submission.status})\n"
            f"Thông báo lỗi: {submission.error or 'None'}\n"
            f"Mã nguồn học sinh nộp:\n```cpp\n{source_code[:3000]}\n```"
        )

        # 5. Call LLM Adapter via Instructor
        diagnosis = await llm_adapter.generate_structured(
            response_model=CodeDoctorDiagnosis,
            prompt=user_prompt,
            system_prompt=system_prompt
        )

        return CodeDoctorResponse(
            submission_id=submission_id,
            user_id=submission.user_id,
            problem_name=problem_title,
            diagnosis=diagnosis
        )

code_doctor_service = CodeDoctorService()

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.dmoj import JudgeSubmission, JudgeSubmissionsource, JudgeProblem, JudgeProfile
from app.schemas.ai import CodeDoctorDiagnosis, CodeDoctorResponse
from app.core.llm_adapter import llm_adapter
from fastapi import HTTPException

logger = logging.getLogger(__name__)

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
        # name/description có thể NULL -> guard tránh lỗi khi xử lý
        problem_title = (problem.name or "Problem") if problem else "Problem"
        problem_desc = (problem.description or "") if problem else ""

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

        # 5. Call LLM Adapter via Instructor (with timeout & Socratic fallback)
        try:
            diagnosis = await asyncio.wait_for(
                llm_adapter.generate_structured(
                    response_model=CodeDoctorDiagnosis,
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=250
                ),
                timeout=25.0
            )
        except Exception as e:
            logger.warning(f"Code Doctor LLM diagnosis unavailable or timed out: {e}. Falling back to rule-based Socratic hints.")
            verdict = submission.result or "WA"
            if verdict == "TLE":
                cat = "TIME_LIMIT_EXCEEDED"
                summary = f"Chương trình bị quá giới hạn thời gian (TLE) trên bài toán {problem_title}."
                question = "Độ phức tạp thời gian hiện tại là bao nhiêu? Có vòng lặp nào duyệt qua mảng quá nhiều lần không?"
                hint = "Hãy xem xét giảm số phép tính từ O(N²) xuống O(N log N) bằng cách sử dụng sắp xếp, tìm kiếm nhị phân hoặc mảng cộng dồn."
            elif verdict == "WA":
                cat = "WRONG_ANSWER"
                summary = f"Chương trình cho kết quả sai (WA) ở một số trường hợp kiểm thử của bài {problem_title}."
                question = "Bạn đã kiểm tra các trường hợp biên đặc biệt (như N = 0, N = 1, giá trị âm hoặc cực đại) chưa?"
                hint = "Hãy thử chạy tay với test case nhỏ nhất và kiểm tra xem có biến nào bị tràn số kiểu int hay không (cần dùng long long)."
            elif verdict == "RTE":
                cat = "RUNTIME_ERROR"
                summary = f"Chương trình gặp lỗi thực thi (Runtime Error) khi chạy test case."
                question = "Có mảng nào bị truy cập vượt quá kích thước hoặc có phép chia cho 0 không?"
                hint = "Hãy kiểm tra lại kích thước khai báo của mảng theo ràng buộc N của đề bài."
            else:
                cat = verdict
                summary = f"Bài nộp chưa đạt kết quả tối đa ({verdict}) cho bài toán {problem_title}."
                question = "Bạn có thể đọc lại ràng buộc đề bài và kiểm tra lại luồng xử lý chính không?"
                hint = "Hãy kiểm tra kỹ điều kiện dừng của vòng lặp và logic xử lý kết quả."

            diagnosis = CodeDoctorDiagnosis(
                error_category=cat,
                summary=summary,
                guiding_question=question,
                actionable_hint=hint
            )

        return CodeDoctorResponse(
            submission_id=submission_id,
            user_id=submission.user_id,
            problem_name=problem_title,
            diagnosis=diagnosis
        )

code_doctor_service = CodeDoctorService()

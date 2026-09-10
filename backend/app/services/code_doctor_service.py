import asyncio
import json
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.redis import cache_get, cache_set, cache_delete
from app.core.job_manager import job_manager
from app.models.dmoj import (
    JudgeSubmission,
    JudgeSubmissionsource,
    JudgeProblem,
    JudgeProfile,
    JudgeLanguage,
    JudgeSubmissionTestcase,
)
from app.schemas.ai import CodeDoctorDiagnosis, CodeDoctorResponse
from app.schemas.student import FailedSubmissionItem, TestCaseDetailItem, SubmissionDetailResponse
from app.schemas.jobs import JobCreateResponse, JobStatus, JobType
from app.core.llm_adapter import llm_adapter
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CodeDoctorService:
    def __init__(self):
        # In-memory fallback cache (submission_id -> CodeDoctorResponse)
        self._memory_cache: Dict[int, CodeDoctorResponse] = {}

    async def _diagnose_submission_core(
        self, submission_id: int, db: AsyncSession
    ) -> CodeDoctorResponse:
        redis_key = f"tmath:code_doctor:submission:{submission_id}"

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
        problem_title = (problem.name or "Bài toán") if problem else "Bài toán"
        problem_code = (problem.code or f"P{submission.problem_id}") if problem else f"P{submission.problem_id}"
        problem_desc = (problem.description or "") if problem else ""
        time_limit = problem.time_limit if problem and problem.time_limit else 1.0
        memory_limit = problem.memory_limit if problem and problem.memory_limit else 256
        problem_points = problem.points if problem and problem.points else 100.0

        # 4. Fetch programming language
        language_name = "C++"
        code_lang_tag = "cpp"
        if submission.language_id:
            lang_stmt = select(JudgeLanguage).where(JudgeLanguage.id == submission.language_id)
            lang_res = await db.execute(lang_stmt)
            lang_obj = lang_res.scalar_one_or_none()
            if lang_obj:
                language_name = lang_obj.name or lang_obj.common_name or "C++"
                lower_lang = language_name.lower()
                if "python" in lower_lang or "py" in lower_lang:
                    code_lang_tag = "python"
                elif "java" in lower_lang:
                    code_lang_tag = "java"
                elif "pascal" in lower_lang:
                    code_lang_tag = "pascal"

        # 5. Fetch failed test cases details from judge_submissiontestcase
        tc_stmt = (
            select(JudgeSubmissionTestcase)
            .where(JudgeSubmissionTestcase.submission_id == submission_id)
            .order_by(JudgeSubmissionTestcase.case.asc())
            .limit(15)
        )
        tc_res = await db.execute(tc_stmt)
        all_testcases = tc_res.scalars().all()

        tc_summary_parts = []
        if all_testcases:
            passed = sum(1 for tc in all_testcases if tc.status == "AC")
            total_cases = len(all_testcases)
            tc_summary_parts.append(f"- Thống kê test: Đã vượt qua {passed}/{total_cases} test cases.")
            failed_cases = [tc for tc in all_testcases if tc.status != "AC"]
            if failed_cases:
                tc_summary_parts.append("- Các test case bị lỗi:")
                for tc in failed_cases[:3]:
                    details = []
                    if tc.time is not None:
                        details.append(f"thời gian: {tc.time:.2f}s")
                    if tc.memory is not None:
                        details.append(f"bộ nhớ: {tc.memory:.1f}MB")
                    if tc.feedback:
                        details.append(f"phản hồi: {tc.feedback}")
                    if tc.output:
                        clean_out = tc.output.strip().replace("\n", " ")[:60]
                        details.append(f"kết quả in: '{clean_out}'")
                    tc_summary_parts.append(f"  + Test #{tc.case} [{tc.status}]: {', '.join(details) if details else 'Lỗi'}")
        tc_summary = "\n".join(tc_summary_parts) if tc_summary_parts else "- Không có chi tiết từng test case."

        # 6. Construct High-Quality Single-Paragraph Prompt
        system_prompt = (
            "Bạn là Huấn luyện viên Tin học Lập trình Thi đấu trên hệ thống tmath.\n"
            "Nhiệm vụ: Phân tích trực tiếp mã nguồn của học sinh dựa trên đề bài, giới hạn thời gian/bộ nhớ và test case bị lỗi để chỉ ra chính xác nguyên nhân lỗi và cách khắc phục.\n\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. Viết DUY NHẤT 1 ĐOẠN VĂN LIỀN MẠCH (từ 3 đến 5 câu), không xuống dòng.\n"
            "2. TUYỆT ĐỐI KHÔNG chia mục, không gạch đầu dòng, không dùng tiêu đề.\n"
            "3. TUYỆT ĐỐI KHÔNG dùng câu hỏi rập khuôn vô nghĩa như 'Bạn đã kiểm tra các trường hợp biên đặc biệt chưa?'. Lời nhận xét PHẢI ĐI THẲNG vào chi tiết cụ thể:\n"
            "   - Chỉ rõ tên biến, hàm, thuật toán hoặc vị trí logic trong code đang gây ra lỗi.\n"
            "   - Giải thích vì sao code bị lỗi dựa trên ràng buộc đề bài (giới hạn thời gian, bộ nhớ, N) hoặc kết quả test case.\n"
            "   - Gợi ý cách sửa hoặc hướng tối ưu cụ thể mà không chép lại nguyên văn cả bài code.\n"
            "4. Giọng điệu chuyên môn, sư phạm, tự nhiên."
        )

        user_prompt = (
            f"BÀI TOÁN: {problem_title} ({problem_code})\n"
            f"- Giới hạn: {time_limit}s | {memory_limit}MB | Thang điểm: {problem_points}\n"
            f"- Đề bài tóm lược & Ràng buộc:\n{problem_desc[:1200]}\n\n"
            f"BÀI NỘP HỌC SINH:\n"
            f"- Ngôn ngữ: {language_name} | Kết quả: {submission.result} | Thời gian: {submission.time or 0.0}s | Bộ nhớ: {submission.memory or 0.0}MB\n"
            f"{tc_summary}\n\n"
            f"MÃ NGUỒN:\n"
            f"```{code_lang_tag}\n{source_code[:1800]}\n```"
        )

        verdict = submission.result or "WA"
        if verdict == "TLE":
            cat = "TIME_LIMIT_EXCEEDED"
        elif verdict == "WA":
            cat = "WRONG_ANSWER"
        elif verdict == "RTE":
            cat = "RUNTIME_ERROR"
        elif verdict == "CE":
            cat = "COMPILE_ERROR"
        elif verdict == "MLE":
            cat = "MEMORY_LIMIT_EXCEEDED"
        else:
            cat = verdict

        # 7. Call direct text generation (single natural paragraph)
        try:
            raw_advice = await asyncio.wait_for(
                llm_adapter.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=450,
                    temperature=0.2
                ),
                timeout=90.0
            )
            # Normalize into a clean single paragraph
            lines = [line.strip() for line in raw_advice.split("\n") if line.strip()]
            # Remove any artificial labels like 'Nhận xét:' or bullets
            clean_lines = []
            for l in lines:
                cleaned = l.lstrip("#*-0123456789. ")
                if cleaned.lower().startswith("nhận xét:") or cleaned.lower().startswith("chẩn đoán:"):
                    cleaned = cleaned.split(":", 1)[1].strip()
                if cleaned:
                    clean_lines.append(cleaned)
            advice_paragraph = " ".join(clean_lines).strip()
            if not advice_paragraph:
                advice_paragraph = raw_advice.strip()

            # Ensure advice is not empty or too short
            if not advice_paragraph or len(advice_paragraph.strip()) < 15:
                if verdict == "TLE":
                    advice_paragraph = f"Mã nguồn của bạn vượt quá giới hạn thời gian {time_limit}s trên bài toán {problem_title} ({problem_code}). Thuật toán hiện tại có độ phức tạp tính toán lớn so với ràng buộc dữ liệu đầu vào của đề bài; bạn hãy rà soát lại các vòng lặp lồng nhau hoặc các thao tác lặp lại không cần thiết để tối ưu sang cấu trúc dữ liệu hoặc giải thuật có độ phức tạp thấp hơn."
                elif verdict == "RTE":
                    advice_paragraph = f"Chương trình gặp lỗi thực thi (Runtime Error) khi chạy các test case của bài toán {problem_title}. Lỗi này thường xuất phát từ việc truy cập chỉ số mảng vượt quá phạm vi khai báo, phép chia cho 0, hoặc gọi đệ quy quá sâu gây tràn bộ nhớ stack ({memory_limit}MB); bạn hãy kiểm tra lại kích thước mảng và điều kiện biên tại các vòng lặp."
                elif verdict == "WA":
                    advice_paragraph = f"Chương trình chưa cho kết quả chính xác trên các trường hợp kiểm thử của bài toán {problem_title}. Kết quả tính toán thực tế của mã nguồn không khớp với đáp án mẫu trên một số test case; bạn hãy kiểm tra kỹ điều kiện logic xử lý rẽ nhánh và thử chạy tay từng bước với test case nhỏ của đề bài để xác định giá trị biến bị tính sai."
                else:
                    advice_paragraph = f"Bài nộp chưa đạt kết quả tối đa ({verdict}) cho bài toán {problem_title}. Bạn hãy đối chiếu lại toàn bộ luồng xử lý chính với các ràng buộc trong đề bài để hoàn thiện thuật toán."

            diagnosis = CodeDoctorDiagnosis(
                error_category=cat,
                advice=advice_paragraph,
                summary=advice_paragraph
            )
        except Exception as e:
            logger.warning(f"Code Doctor LLM generation unavailable or timed out: {e}. Using fallback.")
            if verdict == "TLE":
                fallback_advice = f"Mã nguồn của bạn vượt quá giới hạn thời gian {time_limit}s trên bài toán {problem_title} ({problem_code}). Thuật toán hiện tại có độ phức tạp tính toán lớn so với ràng buộc dữ liệu đầu vào của đề bài; bạn hãy rà soát lại các vòng lặp lồng nhau hoặc các thao tác lặp lại không cần thiết để tối ưu sang cấu trúc dữ liệu hoặc giải thuật có độ phức tạp thấp hơn."
            elif verdict == "RTE":
                fallback_advice = f"Chương trình gặp lỗi thực thi (Runtime Error) khi chạy các test case của bài toán {problem_title}. Lỗi này thường xuất phát từ việc truy cập chỉ số mảng vượt quá phạm vi khai báo, phép chia cho 0, hoặc gọi đệ quy quá sâu gây tràn bộ nhớ stack ({memory_limit}MB); bạn hãy kiểm tra lại kích thước mảng và điều kiện biên tại các vòng lặp."
            elif verdict == "WA":
                fallback_advice = f"Chương trình chưa cho kết quả chính xác trên các trường hợp kiểm thử của bài toán {problem_title}. Kết quả tính toán thực tế của mã nguồn không khớp với đáp án mẫu trên một số test case; bạn hãy kiểm tra kỹ điều kiện logic xử lý rẽ nhánh và thử chạy tay từng bước với test case nhỏ của đề bài để xác định giá trị biến bị tính sai."
            else:
                fallback_advice = f"Bài nộp chưa đạt kết quả tối đa ({verdict}) cho bài toán {problem_title}. Bạn hãy đối chiếu lại toàn bộ luồng xử lý chính với các ràng buộc trong đề bài để hoàn thiện thuật toán."

            diagnosis = CodeDoctorDiagnosis(
                error_category=cat,
                advice=fallback_advice,
                summary=fallback_advice
            )

        res = CodeDoctorResponse(
            submission_id=submission_id,
            user_id=submission.user_id,
            problem_name=problem_title,
            diagnosis=diagnosis
        )

        # Cache for 7 days (604800s) because submissions are immutable
        await cache_set(redis_key, res.model_dump_json(), expire=7 * 86400)
        self._memory_cache[submission_id] = res

        return res

    async def _execute_diagnose(self, submission_id: int) -> dict:
        """Background executor run by LLMJobManager inside concurrency Semaphore."""
        async with AsyncSessionLocal() as session:
            res = await self._diagnose_submission_core(submission_id, session)
            return res.model_dump()

    async def diagnose_submission_async(
        self, submission_id: int, force_refresh: bool = False
    ) -> JobCreateResponse:
        """Asynchronous non-blocking entry point: returns job_id in ~10ms or cached result in ~1ms."""
        redis_key = f"tmath:code_doctor:submission:{submission_id}"

        if force_refresh:
            await cache_delete(redis_key)
            self._memory_cache.pop(submission_id, None)
        else:
            cached_json = await cache_get(redis_key)
            if cached_json:
                try:
                    logger.info(f"Redis Cache HIT for Code Doctor key '{redis_key}'")
                    return JobCreateResponse(
                        job_id=f"cached_{submission_id}",
                        status=JobStatus.COMPLETED,
                        message="Kết quả chẩn đoán đã sẵn sàng từ bộ nhớ đệm.",
                        result=json.loads(cached_json),
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse cached JSON for '{redis_key}': {e}")

            if submission_id in self._memory_cache:
                logger.info(f"In-memory Cache HIT for Code Doctor key '{submission_id}'")
                return JobCreateResponse(
                    job_id=f"cached_{submission_id}",
                    status=JobStatus.COMPLETED,
                    message="Kết quả chẩn đoán đã sẵn sàng từ bộ nhớ đệm.",
                    result=self._memory_cache[submission_id].model_dump(),
                )

        # Enqueue background job with semaphore & 120s timeout
        job_id, is_new = await job_manager.enqueue_job(
            JobType.CODE_DOCTOR,
            self._execute_diagnose,
            submission_id,
            entity_key=str(submission_id),
            timeout_seconds=120,
            metadata={"submission_id": submission_id},
        )

        return JobCreateResponse(
            job_id=job_id,
            status=JobStatus.PENDING if is_new else JobStatus.PROCESSING,
            message="Tác vụ chẩn đoán bài nộp đang được AI xử lý ngầm.",
        )

    async def diagnose_submission(
        self, submission_id: int, db: AsyncSession, force_refresh: bool = False
    ) -> CodeDoctorResponse:
        """Synchronous helper preserving backward compatibility."""
        redis_key = f"tmath:code_doctor:submission:{submission_id}"
        if not force_refresh:
            cached_json = await cache_get(redis_key)
            if cached_json:
                try:
                    return CodeDoctorResponse.model_validate_json(cached_json)
                except Exception:
                    pass
            if submission_id in self._memory_cache:
                return self._memory_cache[submission_id]
        return await self._diagnose_submission_core(submission_id, db)

    @staticmethod
    async def get_failed_submissions(
        user_id: int, db: AsyncSession, limit: int = 10
    ) -> List[FailedSubmissionItem]:
        """Lấy danh sách các bài nộp bị lỗi gần đây của học sinh (bắt buộc có mã nguồn trong judge_submissionsource)."""
        stmt = (
            select(
                JudgeSubmission.id.label("submission_id"),
                JudgeSubmission.problem_id,
                JudgeProblem.code.label("problem_code"),
                JudgeProblem.name.label("problem_name"),
                JudgeSubmission.result,
                JudgeSubmission.status,
                JudgeSubmission.date,
                JudgeSubmission.points,
                JudgeSubmission.language_id,
            )
            .join(JudgeProblem, JudgeProblem.id == JudgeSubmission.problem_id)
            .join(JudgeSubmissionsource, JudgeSubmissionsource.submission_id == JudgeSubmission.id)
            .where(
                JudgeSubmission.user_id == user_id,
                JudgeSubmission.result != "AC",
                JudgeSubmission.result.isnot(None),
            )
            .order_by(JudgeSubmission.date.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        items = []
        for row in res.all():
            items.append(
                FailedSubmissionItem(
                    submission_id=row.submission_id,
                    problem_id=row.problem_id,
                    problem_code=row.problem_code or f"P{row.problem_id}",
                    problem_name=row.problem_name or f"Bài {row.problem_id}",
                    result=row.result or "FAILED",
                    status=row.status,
                    date=row.date.strftime("%d/%m/%Y %H:%M") if row.date else None,
                    points=row.points or 0.0,
                    language_id=row.language_id,
                )
            )
        return items

    @staticmethod
    async def get_submission_detail(submission_id: int, db: AsyncSession) -> SubmissionDetailResponse:
        """Lấy chi tiết đầy đủ của bài nộp: đề bài, mã nguồn, thông tin test cases."""
        sub_stmt = select(JudgeSubmission).where(JudgeSubmission.id == submission_id)
        sub_res = await db.execute(sub_stmt)
        submission = sub_res.scalar_one_or_none()
        if not submission:
            raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found.")

        src_stmt = select(JudgeSubmissionsource).where(JudgeSubmissionsource.submission_id == submission_id)
        src_res = await db.execute(src_stmt)
        source_obj = src_res.scalar_one_or_none()
        source_code = source_obj.source if source_obj else "// Không có mã nguồn lưu trữ"

        prob_stmt = select(JudgeProblem).where(JudgeProblem.id == submission.problem_id)
        prob_res = await db.execute(prob_stmt)
        problem = prob_res.scalar_one_or_none()
        problem_title = (problem.name or "Bài toán") if problem else "Bài toán"
        problem_code = (problem.code or f"P{submission.problem_id}") if problem else f"P{submission.problem_id}"
        problem_desc = (problem.description or "") if problem else ""
        time_limit = problem.time_limit if problem and problem.time_limit else 1.0
        memory_limit = problem.memory_limit if problem and problem.memory_limit else 256
        problem_points = problem.points if problem and problem.points else 100.0

        language_name = "C++"
        if submission.language_id:
            lang_stmt = select(JudgeLanguage).where(JudgeLanguage.id == submission.language_id)
            lang_res = await db.execute(lang_stmt)
            lang_obj = lang_res.scalar_one_or_none()
            if lang_obj:
                language_name = lang_obj.name or lang_obj.common_name or "C++"

        tc_stmt = (
            select(JudgeSubmissionTestcase)
            .where(JudgeSubmissionTestcase.submission_id == submission_id)
            .order_by(JudgeSubmissionTestcase.case.asc())
        )
        tc_res = await db.execute(tc_stmt)
        testcase_items = [
            TestCaseDetailItem(
                case=tc.case,
                status=tc.status,
                time=tc.time,
                memory=tc.memory,
                points=tc.points,
                total=tc.total,
                feedback=tc.feedback,
                output=tc.output,
            )
            for tc in tc_res.scalars().all()
        ]

        return SubmissionDetailResponse(
            submission_id=submission_id,
            user_id=submission.user_id,
            problem_id=submission.problem_id,
            problem_code=problem_code,
            problem_name=problem_title,
            problem_description=problem_desc,
            time_limit=time_limit,
            memory_limit=memory_limit,
            problem_points=problem_points,
            result=submission.result or "FAILED",
            status=submission.status,
            date=submission.date.strftime("%d/%m/%Y %H:%M:%S") if submission.date else None,
            time=submission.time,
            memory=submission.memory,
            points=submission.points or 0.0,
            language_name=language_name,
            source_code=source_code,
            testcases=testcase_items,
        )


code_doctor_service = CodeDoctorService()

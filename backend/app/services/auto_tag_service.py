import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, NamedTuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.llm_adapter import llm_adapter
from app.models.dmoj import (
    JudgeProblem,
    JudgeSubmission,
    JudgeSubmissionsource,
    JudgeProblemtype,
    JudgeProblemGroup,
    JudgeProblemAiTag
)
from app.schemas.ai import AutoTagResult
from app.services.feature_extractor import feature_extractor

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Mốc thời gian UTC naive (chuẩn lưu chung của DB layer); thay datetime.utcnow() bị deprecated từ Python 3.12."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TagOutcome(NamedTuple):
    """Kết quả gắn nhãn một bài toán: result (kết quả chọn), fallback (phương án heuristic), source."""
    result: AutoTagResult
    source: str
    fallback: AutoTagResult


# Ollama trong Docker Desktop (Mac) chạy CPU-only: prompt processing ~35 t/s,
# generation ~2.6 t/s -> 1 bài mất 100-170s. Timeout phải đủ lớn cho đường CPU này.
LLM_TAG_TIMEOUT_S = 240.0
# JSON tag output ngắn (~200 tokens); cap 512 để generation không kéo dài quá 3 phút
LLM_TAG_MAX_TOKENS = 512


class AutoTagService:
    """
    Service quản lý Pipeline Auto-Tagging F3.1:
    - Quét bài toán chưa gắn nhãn
    - Lấy mã nguồn AC mẫu từ judge_submissionsource
    - Phân tích đặc trưng mã nguồn & ràng buộc N
    - Gọi LLM qua Instructor (với cơ chế Fallback Heuristic an toàn)
    - Lưu kết quả vào judge_problem_ai_tag
    - Quản lý worker chạy batch nền và báo cáo thống kê thực tế
    """

    def __init__(self):
        self.is_running: bool = False
        self.current_batch: Optional[Dict[str, Any]] = None

    async def get_tagging_status(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Lấy thống kê thực tế từ cơ sở dữ liệu MySQL (loại bỏ số liệu cứng).
        """
        # 1. Tổng số bài toán trong hệ thống
        total_stmt = select(func.count(JudgeProblem.id))
        total_res = await db.execute(total_stmt)
        total_problems = total_res.scalar() or 0

        # 2. Số bài toán đã được AI gắn nhãn
        tagged_stmt = select(func.count(JudgeProblemAiTag.id))
        tagged_res = await db.execute(tagged_stmt)
        tagged_problems = tagged_res.scalar() or 0

        untagged_problems = max(0, total_problems - tagged_problems)
        progress_percentage = round((tagged_problems / total_problems * 100), 1) if total_problems > 0 else 0.0

        # 3. Lấy 10 bài toán được AI gắn nhãn gần nhất
        recent_stmt = (
            select(
                JudgeProblemAiTag,
                JudgeProblem.code.label("problem_code"),
                JudgeProblem.name.label("problem_name"),
                JudgeProblemtype.full_name.label("primary_tag_name"),
                JudgeProblemGroup.full_name.label("bloom_group_name")
            )
            .join(JudgeProblem, JudgeProblemAiTag.problem_id == JudgeProblem.id)
            .outerjoin(JudgeProblemtype, JudgeProblemAiTag.primary_tag_id == JudgeProblemtype.id)
            .outerjoin(JudgeProblemGroup, JudgeProblemAiTag.bloom_group_id == JudgeProblemGroup.id)
            .order_by(desc(JudgeProblemAiTag.created_at))
            .limit(10)
        )
        recent_res = await db.execute(recent_stmt)
        recent_rows = recent_res.all()

        recent_tags = []
        for row in recent_rows:
            tag_obj = row.JudgeProblemAiTag
            recent_tags.append({
                "id": tag_obj.id,
                "problem_id": tag_obj.problem_id,
                "problem_code": row.problem_code or f"PROB_{tag_obj.problem_id}",
                "problem_name": row.problem_name or f"Bài toán #{tag_obj.problem_id}",
                "primary_tag_id": tag_obj.primary_tag_id,
                "primary_tag_name": row.primary_tag_name or f"Chủ đề #{tag_obj.primary_tag_id}",
                "secondary_tag_ids": tag_obj.secondary_tag_ids or [],
                "bloom_group_id": tag_obj.bloom_group_id,
                "bloom_group_name": row.bloom_group_name or (f"Mức {tag_obj.bloom_group_id}" if tag_obj.bloom_group_id else "Chưa xác định"),
                "reasoning": tag_obj.reasoning or "",
                "model": tag_obj.model,
                "created_at": tag_obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if tag_obj.created_at else ""
            })

        return {
            "total_problems": total_problems,
            "tagged_problems": tagged_problems,
            "untagged_problems": untagged_problems,
            "progress_percentage": progress_percentage,
            "is_running": self.is_running,
            "current_batch": self.current_batch,
            "recent_tags": recent_tags
        }

    async def tag_problem(self, problem: JudgeProblem, db: AsyncSession) -> TagOutcome:
        """
        Gắn nhãn cho một bài toán:
        1. Tìm mã nguồn bài nộp AC tốt nhất
        2. Trích xuất đặc trưng code AC & ràng buộc N qua FeatureExtractor
        3. Gọi LLM Adapter cấu trúc AutoTagResult (fallback heuristic nếu lỗi)

        Trả về TagOutcome để caller biết tag đến từ LLM hay heuristic (provenance).
        """
        # 1. Tìm mã nguồn AC điểm cao nhất
        sub_stmt = (
            select(JudgeSubmission.id, JudgeSubmissionsource.source)
            .join(JudgeSubmissionsource, JudgeSubmission.id == JudgeSubmissionsource.submission_id)
            .where(
                JudgeSubmission.problem_id == problem.id,
                JudgeSubmission.result == "AC"
            )
            .order_by(desc(JudgeSubmission.points), JudgeSubmission.time.asc())
            .limit(1)
        )
        sub_res = await db.execute(sub_stmt)
        sub_row = sub_res.first()

        ac_source_code = sub_row.source if sub_row and sub_row.source else ""
        problem_desc = problem.description or ""
        problem_name = problem.name or problem.code or f"Bài #{problem.id}"
        time_limit = problem.time_limit or 1.0
        memory_limit = problem.memory_limit or 256000

        # 2. Phân tích đặc trưng
        analysis = feature_extractor.analyze(
            source_code=ac_source_code,
            description=problem_desc,
            time_limit=time_limit,
            memory_limit=memory_limit
        )

        # 3. Chuẩn bị Prompt theo SDD §6
        system_prompt = (
            "Bạn là Chuyên gia Phân tích Thuật toán và Mã nguồn Lập trình.\n"
            "Nhiệm vụ: Phân tích Đề bài, Giới hạn dữ liệu N, và ĐẶC BIỆT LÀ MÃ NGUỒN ĐÃ AC để gán chính xác Tag chủ đề trong 99 judge_problemtype của tmath.\n\n"
            "BẮT BỘC TRẢ VỀ JSON FORMAT CHUẨN:\n"
            "{\n"
            f'  "problem_id": {problem.id},\n'
            '  "primary_tag_id": <int từ 1 đến 99>,\n'
            '  "secondary_tag_ids": [<int>],\n'
            '  "bloom_group_id": <int: 4(A-Nhớ), 5(B-Hiểu), 6(C-Vận dụng), 7(D-Phân tích), 8(E-Đánh giá), 13(F-Đặc biệt)>,\n'
            '  "reasoning": "<Lý do ngắn gọn dựa trên cấu trúc code AC và giới hạn N>"\n'
            "}"
        )

        user_prompt = (
            f"CONTEXT BÀI TOÁN & CODE AC:\n"
            f"- Tiêu đề: {problem_name} (ID: {problem.id}, Code: {problem.code})\n"
            f"- Giới hạn thời gian: {time_limit}s | Bộ nhớ: {memory_limit // 1000}MB\n"
            f"{analysis['features_summary']}\n"
            f"- Trích đoạn nội dung đề bài:\n{problem_desc[:1200]}\n"
            f"- Mã nguồn đã AC mẫu (C++/Python):\n"
            f"```cpp\n{ac_source_code[:2500] if ac_source_code else '// Không có mã nguồn AC, phân tích dựa trên đề bài'}\n```"
        )

        # Phương án heuristic tính sẵn: dùng khi LLM lỗi hoặc trả tag ID ngoài danh mục
        heuristic_result = AutoTagResult(
            problem_id=problem.id,
            primary_tag_id=analysis["heuristic_primary_tag_id"],
            secondary_tag_ids=[],
            bloom_group_id=analysis["heuristic_bloom_group_id"],
            reasoning=analysis["heuristic_reasoning"]
        )

        # 4. Gọi LLM qua Instructor (timeout và max_tokens cho đường CPU-only, xem hằng số ở đầu file)
        try:
            llm_result: AutoTagResult = await asyncio.wait_for(
                llm_adapter.generate_structured(
                    response_model=AutoTagResult,
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,
                    max_tokens=LLM_TAG_MAX_TOKENS
                ),
                timeout=LLM_TAG_TIMEOUT_S
            )
            # Chuẩn hóa problem_id trả về
            llm_result.problem_id = problem.id
            return TagOutcome(result=llm_result, source="llm", fallback=heuristic_result)
        except Exception as e:
            # TimeoutError có str() rỗng -> luôn kèm tên class exception để log không mất thông tin
            logger.warning(
                f"LLM auto-tag failed for problem {problem.id} ({problem.code}): "
                f"{type(e).__name__}: {e}. Sử dụng kết quả suy luận heuristic từ FeatureExtractor."
            )
            # Heuristic fallback
            return TagOutcome(result=heuristic_result, source="heuristic", fallback=heuristic_result)

    async def run_batch_process(self, batch_size: int = 10) -> None:
        """
        Worker chạy trong background:
        - Lấy batch_size bài toán chưa gắn nhãn
        - Lần lượt phân tích, trích xuất đặc trưng, gọi AI và ghi vào DB
        - Có rate limit giữa các bài để đảm bảo an toàn tải hệ thống
        """
        if self.is_running:
            logger.info("Batch auto-tagging process is already running. Skipping duplicate trigger.")
            return

        self.is_running = True
        self.current_batch = {
            "total": batch_size,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "started_at": _utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }

        logger.info(f"Bắt đầu chạy batch auto-tagging cho {batch_size} bài toán...")

        try:
            async with AsyncSessionLocal() as db:
                # Tìm các bài chưa có trong judge_problem_ai_tag
                subquery = select(JudgeProblemAiTag.problem_id)
                stmt = (
                    select(JudgeProblem)
                    .where(~JudgeProblem.id.in_(subquery))
                    .order_by(JudgeProblem.id.asc())
                    .limit(batch_size)
                )
                res = await db.execute(stmt)
                untagged_problems = res.scalars().all()

                if not untagged_problems:
                    logger.info("Tất cả bài toán trong hệ thống đều đã được gắn nhãn.")
                    self.current_batch["total"] = 0
                    return

                self.current_batch["total"] = len(untagged_problems)

                # ID hợp lệ của danh mục: chặn LLM trả tag ID không tồn tại gây FK violation
                tag_ids_res = await db.execute(select(JudgeProblemtype.id))
                valid_tag_ids = {row[0] for row in tag_ids_res.all()}
                bloom_ids_res = await db.execute(select(JudgeProblemGroup.id))
                valid_bloom_ids = {row[0] for row in bloom_ids_res.all()}

                for problem in untagged_problems:
                    try:
                        tag_outcome = await self.tag_problem(problem, db)
                        tag_result = tag_outcome.result

                        # LLM thỉnh thoảng trả ID ngoài danh mục -> rơi về phương án heuristic
                        if tag_result.primary_tag_id not in valid_tag_ids or (
                            tag_result.bloom_group_id is not None
                            and tag_result.bloom_group_id not in valid_bloom_ids
                        ):
                            logger.warning(
                                f"LLM trả tag ID ngoài danh mục cho bài {problem.id} "
                                f"(primary={tag_result.primary_tag_id}, bloom={tag_result.bloom_group_id}). Dùng heuristic."
                            )
                            tag_result = tag_outcome.fallback

                        # Provenance: tag từ heuristic fallback không được ghi nhận là model LLM
                        used_fallback = tag_outcome.source != "llm" or tag_result is tag_outcome.fallback
                        model_name = settings.LLM_MODEL if not used_fallback else "heuristic-fallback"

                        # Lưu vào bảng judge_problem_ai_tag
                        ai_tag_record = JudgeProblemAiTag(
                            problem_id=tag_result.problem_id,
                            primary_tag_id=tag_result.primary_tag_id,
                            secondary_tag_ids=tag_result.secondary_tag_ids,
                            bloom_group_id=tag_result.bloom_group_id,
                            reasoning=tag_result.reasoning,
                            model=model_name,
                            created_at=_utcnow()
                        )
                        db.add(ai_tag_record)
                        await db.commit()

                        self.current_batch["successful"] += 1
                        logger.info(f"Đã gắn nhãn thành công bài {problem.id} ({problem.code}) -> Tag: {tag_result.primary_tag_id}")
                    except Exception as err:
                        await db.rollback()
                        self.current_batch["failed"] += 1
                        logger.error(f"Lỗi khi gắn nhãn bài {problem.id}: {err}")

                    self.current_batch["processed"] += 1

                    # Rate limit: nghỉ 0.5s giữa các bài
                    await asyncio.sleep(0.5)

        except Exception as batch_err:
            logger.error(f"Lỗi nghiêm trọng trong batch auto-tagging worker: {batch_err}")
        finally:
            self.is_running = False
            self.current_batch = None
            logger.info("Hoàn thành tiến trình batch auto-tagging.")

auto_tag_service = AutoTagService()

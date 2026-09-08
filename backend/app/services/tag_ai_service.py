import logging
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_adapter import llm_adapter
from app.core.redis import cache_get, cache_set, cache_delete
from app.schemas.analytics import (
    AICommentaryResponse,
    Recent7DaysSummary,
    AICommentaryLLMSchema,
    StudentTagAnalyticsResponse
)
from app.services.tag_analytics_service import TagAnalyticsService

logger = logging.getLogger(__name__)

class TagAIService:
    def __init__(self):
        # In-memory daily fallback cache in case Redis is temporarily down
        self._daily_cache: Dict[str, AICommentaryResponse] = {}

    def _evict_stale_cache(self, today_str: str) -> None:
        """Removes commentaries cached from previous days to prevent unbounded memory growth."""
        stale_keys = [key for key in self._daily_cache if not key.endswith(f"_{today_str}")]
        for key in stale_keys:
            self._daily_cache.pop(key, None)

    async def get_daily_ai_commentary(
        self,
        user_id: int,
        db: AsyncSession,
        force_refresh: bool = False
    ) -> AICommentaryResponse:
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        redis_key = f"tmath:ai_commentary:{user_id}:{today_str}"
        mem_cache_key = f"{user_id}_{today_str}"

        self._evict_stale_cache(today_str)

        if force_refresh:
            await cache_delete(redis_key)
            self._daily_cache.pop(mem_cache_key, None)
        else:
            # 1. Check Redis Cache first (Fast path: ~1-2ms)
            cached_json = await cache_get(redis_key)
            if cached_json:
                try:
                    logger.info(f"Redis Cache HIT for key '{redis_key}'")
                    return AICommentaryResponse.model_validate_json(cached_json)
                except Exception as e:
                    logger.warning(f"Failed to parse cached JSON for '{redis_key}': {e}")

            # 2. Check local in-memory fallback
            if mem_cache_key in self._daily_cache:
                logger.info(f"In-memory Cache HIT for key '{mem_cache_key}'")
                return self._daily_cache[mem_cache_key]

        # Fetch 7-day & Tag statistics
        analytics: StudentTagAnalyticsResponse = await TagAnalyticsService.get_student_tag_analytics(user_id, db)

        # Collect 7-day active tags & detailed submission stats
        active_tags_7d_details: List[str] = []
        active_tags_names: List[str] = []
        mastered_tags: List[str] = []

        for tag in analytics.tags:
            stat = tag.submissions_stat
            if stat.total_submissions > 0:
                active_tags_names.append(tag.name)
                detail_str = f"• Tag '{tag.name}': nộp {stat.total_submissions} lần (AC: {stat.ac_count}, WA: {stat.wa_count}, TLE: {stat.tle_count})"
                if stat.primary_error:
                    detail_str += f" -> Hay bị lỗi {stat.primary_error}"
                active_tags_7d_details.append(detail_str)

            if tag.status == "MASTERED" and tag.tag_weight == "large":
                mastered_tags.append(tag.name)

        total_sub_7d = analytics.summary.total_submissions_7d

        # Build System Prompt for LLM
        system_prompt = (
            "Bạn là người Thầy / Mentor học tập lập trình thân thiện, vui vẻ trên nền tảng tmath.\n"
            "Nhiệm vụ: Dựa trên dữ liệu 7 ngày qua của học sinh, viết 1 LỜI NHẬN XẾT HẰNG NGÀY ngắn gọn (2-4 câu) gồm 2 phần:\n"
            "1. Nhận xét về hoạt động 7 ngày qua:\n"
            "   - Nếu CÓ nộp bài: Nêu cụ thể các Tag đã làm. ĐẶC BIỆT nếu học sinh có lượt nộp sai (WA - Sai kết quả) hoặc TLE (Vượt quá thời gian), hãy chỉ ra rõ số lượt sai/TLE đó để học sinh lưu ý rút kinh nghiệm (VD: 'ở phần Số học bạn bị nộp sai WA 3 lần và TLE 1 lần').\n"
            "   - Nếu CHƯA nộp bài nào: Động viên vui vẻ, nhẹ nhàng, không áp lực.\n"
            "2. Đưa ra 1 gợi ý vui vẻ, dí dỏm về 1-2 Tag nên thử sức hôm nay để rèn luyện hoặc sửa lỗi.\n"
            "Yêu cầu văn phong: Thân thiện, khuyến khích tinh thần, chèn 1-2 emoji phù hợp 😉. Bắt buộc xuất đúng JSON."
        )

        user_prompt = (
            f"Thông tin học sinh: {analytics.student_name} (ID: {user_id})\n"
            f"- Tổng số lượt nộp bài trong 7 ngày qua: {total_sub_7d}\n"
            f"- Chi tiết nộp bài theo Tag trong 7 ngày qua:\n"
            f"{chr(10).join(active_tags_7d_details) if active_tags_7d_details else '  (Chưa nộp bài nào)'}\n"
            f"- Các Tag thế mạnh tích lũy: {', '.join(mastered_tags[:3]) if mastered_tags else 'Đang trong quá trình tích lũy'}\n\n"
            f"Hãy sinh câu nhận xét hằng ngày và gợi ý 1-2 Tag phù hợp."
        )

        try:
            llm_result: AICommentaryLLMSchema = await llm_adapter.generate_structured(
                response_model=AICommentaryLLMSchema,
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7
            )
            commentary_text = llm_result.commentary
            recommended = llm_result.recommended_tags
        except Exception as e:
            logger.warning(f"LLM commentary generation failed or unavailable: {e}. Falling back to template.")
            # Fallback template
            if total_sub_7d > 0:
                commentary_text = f"Trong 7 ngày vừa qua, bạn đã nộp {total_sub_7d} lượt bài tập! Hôm nay hãy tiếp tục giữ vững phong độ và thử sức thêm các bài toán mới nhé! 😉"
                recommended = active_tags_names[:2] if active_tags_names else ["Mảng 1D", "Sắp xếp"]
            else:
                commentary_text = f"7 ngày qua bạn chưa nộp bài mới nào cả, tranh thủ nghỉ ngơi hay đang bí thuật toán thế? Hôm nay thử khởi động lại bằng 1 bài thuộc mảng cơ bản xem sao nhé! 😉"
                recommended = ["Mảng 1D", "Nhập xuất cơ bản"]

        response_obj = AICommentaryResponse(
            commentary=commentary_text,
            recent_7days_summary=Recent7DaysSummary(
                submissions_count=total_sub_7d,
                active_tags=active_tags_names
            ),
            recommended_tags=recommended,
            generated_at=datetime.utcnow().isoformat() + "Z"
        )

        # Cache response in Redis (24h TTL) and local memory fallback
        await cache_set(redis_key, response_obj.model_dump_json(), expire=86400)
        self._daily_cache[mem_cache_key] = response_obj
        return response_obj

tag_ai_service = TagAIService()

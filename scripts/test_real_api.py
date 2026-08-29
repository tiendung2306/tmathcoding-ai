import asyncio
import sys
import os

# Ensure PYTHONPATH points to app
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import AsyncSessionLocal
from app.services.tag_analytics_service import tag_analytics_service
from app.services.tag_ai_service import tag_ai_service

async def test_real_user(user_id: int):
    print(f"\n==================================================================")
    print(f"🧪 KIỂM THỬ DỮ LIỆU THỰC TẾ TRÊN MYSQL DB - USER ID: {user_id}")
    print(f"==================================================================")

    async with AsyncSessionLocal() as db:
        res = await tag_analytics_service.get_student_tag_analytics(user_id, db)
        print(f"► Tên Học Sinh Thực Tế : {res.student_name}")
        print(f"► Tổng Bài Tập Hệ Thống: {res.summary.total_problems_in_system}")
        print(f"► Số Bài AC Duy Nhất   : {res.summary.total_solved_unique}")
        print(f"► Số Lượt Nộp 7 Ngày Qua: {res.summary.total_submissions_7d}")
        print(f"► Tổng Số Tag Phân Tích: {len(res.tags)}")

        sorted_tags = sorted(res.tags, key=lambda x: x.completion_rate, reverse=True)
        print("\n► Top 5 Tag Có Tỷ Lệ Hoàn Thành Cao Nhất Của Học Sinh:")
        for t in sorted_tags[:5]:
            print(f"   • [{t.key}] {t.name}: {t.completion_rate}% ({t.ac_problems}/{t.total_problems} AC) | Quy mô: {t.tag_weight} | Status: {t.status}")

        active_or_weak = [t for t in res.tags if t.submissions_stat.total_submissions > 0 or t.status == "NEEDS_IMPROVEMENT"]
        if active_or_weak:
            print("\n► Thống kê Lỗi Nộp Bài & Tag Cần Cải Thiện:")
            for t in active_or_weak[:5]:
                print(f"   • [{t.key}] {t.name}: Total Sub: {t.submissions_stat.total_submissions} | WA: {t.submissions_stat.wa_count} | TLE: {t.submissions_stat.tle_count} | Status: {t.status}")
        else:
            print("\n► Trong 7 ngày qua học sinh này chưa nộp bài tập mới nào.")

        print("\n► Gọi AI Advisor Sinh Nhận Xét Hằng Ngày...")
        ai_res = await tag_ai_service.get_daily_ai_commentary(user_id, db, force_refresh=True)
        print(f"💬 NHẬN XẾT AI THỰC TẾ:\n\"{ai_res.commentary}\"")
        print(f"🎯 GỢI Ý CỦA AI: {ai_res.recommended_tags}")
        print(f"⏱️ THỜI GIAN GENERATE: {ai_res.generated_at}")

async def main():
    # Test for real users found in DB
    target_users = [2, 5, 7]
    for uid in target_users:
        await test_real_user(uid)

if __name__ == "__main__":
    asyncio.run(main())

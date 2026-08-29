import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import AsyncSessionLocal
from sqlalchemy import text
from app.services.tag_analytics_service import tag_analytics_service
from app.services.tag_ai_service import tag_ai_service

async def main():
    print("==================================================================")
    print("🧪 KIỂM THỬ THỰC TẾ TRƯỜNG HỢP HỌC SINH CÓ NỘP BÀI TRONG 7 NGÀY QUA")
    print("==================================================================")

    async with AsyncSessionLocal() as db:
        user_id = 5  # HuyP
        
        # 1. Update 5 submissions of user 5 to date = NOW() to simulate 7-day active submissions
        print("► Giả lập 5 lượt nộp bài gần nhất trong 7 ngày qua cho học sinh HuyP (ID: 5)...")
        await db.execute(text("""
            UPDATE judge_submission 
            SET date = NOW() 
            WHERE user_id = 5 
            LIMIT 5;
        """))
        await db.commit()

        # 2. Fetch tag analytics
        res = await tag_analytics_service.get_student_tag_analytics(user_id, db)
        print(f"\n► Học Sinh: {res.student_name}")
        print(f"► Lượt nộp bài trong 7 ngày qua: {res.summary.total_submissions_7d} lượt")
        
        active_tags = [t for t in res.tags if t.submissions_stat.total_submissions > 0]
        print("► Các Tag học sinh đã nộp bài trong 7 ngày qua:")
        for t in active_tags:
            print(f"   • [{t.key}] {t.name}: {t.submissions_stat.total_submissions} lượt nộp | AC: {t.submissions_stat.ac_count} | WA: {t.submissions_stat.wa_count} | TLE: {t.submissions_stat.tle_count}")

        # 3. Call LLM AI Advisor
        print("\n► LLM AI Advisor đang sinh nhận xét thực tế cho trường hợp CÓ NỘP BÀI...")
        ai_res = await tag_ai_service.get_daily_ai_commentary(user_id, db, force_refresh=True)

        print(f"\n💬 NỘI DUNG NHẬN XẾT THỰC TẾ TỪ AI:\n\"{ai_res.commentary}\"")
        print(f"\n🎯 GỢI Ý TAG CỦA AI: {ai_res.recommended_tags}")
        print(f"⏱️ THỜI GIAN GENERATE: {ai_res.generated_at}")

        print("\n==================================================================")

if __name__ == "__main__":
    asyncio.run(main())

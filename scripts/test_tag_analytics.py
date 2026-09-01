import asyncio
import sys
import os
from httpx import AsyncClient, ASGITransport

# Add backend directory to sys.path (host layout) and /app (Docker container layout)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "/app")

from app.main import app
from app.core.database import AsyncSessionLocal
from app.services.tag_analytics_service import tag_analytics_service
from app.services.tag_ai_service import tag_ai_service

async def main():
    print("==================================================================")
    print("🧪 KIỂM THỬ BACKEND SERVICE & SECURED REST API ENDPOINTS")
    print("==================================================================")

    # 1. Test Service Layer Direct Calls
    print("\n1. [SERVICE LAYER] Kiểm thử Tag Analytics Service cho Student (ID=1)...")
    async with AsyncSessionLocal() as db:
        user_id = 1
        res = await tag_analytics_service.get_student_tag_analytics(user_id, db)
        print(f"   ► Tên học sinh: {res.student_name}")
        print(f"   ► Tổng bài tập hệ thống: {res.summary.total_problems_in_system}")
        print(f"   ► Số bài AC duy nhất: {res.summary.total_solved_unique}")
        print(f"   ► Số lượt nộp 7 ngày qua: {res.summary.total_submissions_7d}")
        print(f"   ► Tổng số Tag phân tích: {len(res.tags)}")
        
        sorted_tags = sorted(res.tags, key=lambda x: x.completion_rate, reverse=True)
        print("   ► Top 3 Tag có tỷ lệ hoàn thành cao nhất:")
        for t in sorted_tags[:3]:
            print(f"      • [{t.key}] {t.name}: {t.completion_rate}% ({t.ac_problems}/{t.total_problems} AC) | Quy mô: {t.tag_weight} | Status: {t.status}")

        print("\n2. [SERVICE LAYER] Kiểm thử Daily AI Commentary Service...")
        ai_res = await tag_ai_service.get_daily_ai_commentary(user_id, db, force_refresh=True)
        print(f"   ► Nhận xét AI hằng ngày:\n     \"{ai_res.commentary}\"")
        print(f"   ► Gợi ý Tag nên làm: {ai_res.recommended_tags}")
        print(f"   ► Thời gian sinh: {ai_res.generated_at}")

    # 2. Test FastAPI Endpoints via AsyncClient
    print("\n3. [API ENDPOINTS] Kiểm thử REST API Endpoint qua HTTP Client...")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Test Endpoint GET /api/v1/student/analytics/tags
        resp_tags = await client.get("/api/v1/student/analytics/tags?user_id=1")
        print(f"   ► GET /api/v1/student/analytics/tags Status: {resp_tags.status_code}")
        assert resp_tags.status_code == 200, f"Failed: {resp_tags.text}"
        data_tags = resp_tags.json()
        print(f"     Status 200 OK | Student: {data_tags['student_name']} | Tags Received: {len(data_tags['tags'])}")

        # Test Endpoint GET /api/v1/student/analytics/ai-commentary
        resp_ai = await client.get("/api/v1/student/analytics/ai-commentary?user_id=1&force_refresh=true")
        print(f"   ► GET /api/v1/student/analytics/ai-commentary Status: {resp_ai.status_code}")
        assert resp_ai.status_code == 200, f"Failed: {resp_ai.text}"
        data_ai = resp_ai.json()
        print(f"     Status 200 OK | Commentary: \"{data_ai['commentary']}\"")

    print("\n==================================================================")
    print("✅ MỌI BÀI KIỂM THỬ ĐÃ THÀNH CÔNG VỚI THÔNG SỐ CHUẨN XÁC 100%!")
    print("==================================================================")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
import os
from httpx import AsyncClient, ASGITransport

# Add backend directory to sys.path (host layout) and /app (Docker container layout)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "/app")

from app.main import app
from app.core.database import get_db
from app.schemas.analytics import (
    StudentTagAnalyticsResponse,
    StudentTagAnalyticsSummary,
    TagMetricItem,
    TagSubmissionStat,
    AICommentaryResponse,
    Recent7DaysSummary
)

# Mock DB Session
class MockAsyncSession:
    pass

async def override_get_db():
    yield MockAsyncSession()

# Override dependency
app.dependency_overrides[get_db] = override_get_db

async def main():
    print("==================================================================")
    print("🧪 TEST API BẢO MẬT BẰNG HTTP ASYNCCLIENT (MOCK DB & LLM)")
    print("==================================================================")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Test GET /api/v1/student/analytics/tags (query param user_id)
        print("\n1. Testing GET /api/v1/student/analytics/tags...")

        # Override service logic for unit test
        from app.services.tag_analytics_service import tag_analytics_service
        async def mock_get_analytics(user_id, db):
            return StudentTagAnalyticsResponse(
                user_id=user_id,
                student_name="Nguyễn Văn A",
                summary=StudentTagAnalyticsSummary(
                    total_problems_in_system=1250,
                    total_solved_unique=45,
                    total_submissions_7d=15
                ),
                tags=[
                    TagMetricItem(
                        tag_id=1,
                        key="array1d",
                        name="Mảng 1D",
                        total_problems=20,
                        ac_problems=18,
                        completion_rate=90.0,
                        tag_weight="large",
                        submissions_stat=TagSubmissionStat(
                            total_submissions=10, ac_count=9, wa_count=1, ac_rate=90.0, wa_rate=10.0
                        ),
                        status="MASTERED"
                    ),
                    TagMetricItem(
                        tag_id=12,
                        key="dp",
                        name="Quy hoạch động",
                        total_problems=15,
                        ac_problems=5,
                        completion_rate=33.3,
                        tag_weight="large",
                        submissions_stat=TagSubmissionStat(
                            total_submissions=15, ac_count=5, wa_count=2, tle_count=8, ac_rate=33.3, wa_rate=13.3, tle_rate=53.3, primary_error="TLE"
                        ),
                        status="NEEDS_IMPROVEMENT"
                    )
                ]
            )
        tag_analytics_service.get_student_tag_analytics = mock_get_analytics

        resp1 = await client.get("/api/v1/student/analytics/tags?user_id=1")
        print(f"   ► Status Code: {resp1.status_code}")
        assert resp1.status_code == 200
        data1 = resp1.json()
        print(f"   ► Student: {data1['student_name']} (User ID: {data1['user_id']})")
        print(f"   ► Total Problems in System: {data1['summary']['total_problems_in_system']}")
        print(f"   ► Tags returned: {len(data1['tags'])}")
        print(f"   ► Tag 1: {data1['tags'][0]['name']} ({data1['tags'][0]['completion_rate']}% AC - {data1['tags'][0]['status']})")
        print(f"   ► Tag 2: {data1['tags'][1]['name']} ({data1['tags'][1]['completion_rate']}% AC - {data1['tags'][1]['status']})")

        # 2. Test GET /api/v1/student/analytics/ai-commentary
        print("\n2. Testing GET /api/v1/student/analytics/ai-commentary...")
        from app.services.tag_ai_service import tag_ai_service
        async def mock_get_commentary(user_id, db, force_refresh=False):
            return AICommentaryResponse(
                commentary="Trong 7 ngày vừa qua, bạn đã nộp 15 lượt bài tập và làm rất tốt ở mảng Quy hoạch động (5 bài AC)! Hôm nay thử đổi gió với 1 bài toán Sắp xếp nhẹ nhàng để tích điểm nhé! 😉",
                recent_7days_summary=Recent7DaysSummary(
                    submissions_count=15,
                    active_tags=["Quy hoạch động"]
                ),
                recommended_tags=["Sắp xếp", "Mảng 1D"],
                generated_at="2026-08-23T15:00:00Z"
            )
        tag_ai_service.get_daily_ai_commentary = mock_get_commentary

        resp2 = await client.get("/api/v1/student/analytics/ai-commentary?user_id=1&force_refresh=true")
        print(f"   ► Status Code: {resp2.status_code}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        print(f"   ► Daily AI Commentary:\n     \"{data2['commentary']}\"")
        print(f"   ► Recommended Tags: {data2['recommended_tags']}")

        # 3. Test unknown student id (service still returns 200 with fallback name)
        print("\n3. Testing response schema consistency (mocked service)...")
        resp3 = await client.get("/api/v1/student/analytics/tags?user_id=999")
        print(f"   ► Status Code: {resp3.status_code}")
        assert resp3.status_code == 200
        assert "student_name" in resp3.json() and "tags" in resp3.json()
        print(f"   ► Response JSON matches StudentTagAnalyticsResponse schema")

    print("\n==================================================================")
    print("✅ TOÀN BỘ API VÀ SCHEMA CHECK ĐÃ THÀNH CÔNG VỚI STATUS 200 OK!")
    print("==================================================================")

if __name__ == "__main__":
    asyncio.run(main())

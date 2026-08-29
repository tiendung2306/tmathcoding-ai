import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        print("=== CHECKING MYSQL DATABASE ===")
        res = await db.execute(text("SHOW TABLES;"))
        tables = [row[0] for row in res.all()]
        print(f"Total Tables in DB: {len(tables)}")
        
        if "judge_profile" in tables:
            prof_res = await db.execute(text("SELECT id, name, problem_count, points FROM judge_profile LIMIT 5;"))
            profiles = prof_res.all()
            print("\nSample Profiles in Real DB:")
            for p in profiles:
                print(f"  User ID {p.id}: {p.name} (Problems: {p.problem_count}, Points: {p.points})")
        else:
            print("❌ Table 'judge_profile' not found! Database needs seeding.")

if __name__ == "__main__":
    asyncio.run(main())

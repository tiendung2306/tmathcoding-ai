import asyncio
import sys
import os

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        print("=== DESCRIBE TABLE judge_problemtype ===")
        res = await db.execute(text("DESCRIBE judge_problemtype;"))
        for col in res.all():
            print(f"  Field: {col[0]}, Type: {col[1]}")

        print("\n=== DESCRIBE TABLE judge_problem ===")
        res2 = await db.execute(text("DESCRIBE judge_problem;"))
        for col in res2.all()[:6]:
            print(f"  Field: {col[0]}, Type: {col[1]}")

if __name__ == "__main__":
    asyncio.run(main())

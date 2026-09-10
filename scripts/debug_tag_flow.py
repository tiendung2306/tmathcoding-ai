"""Debug: gọi tag_problem trực tiếp trong container để thấy traceback đầy đủ."""
import asyncio
import traceback
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.dmoj import JudgeProblem
from app.services.auto_tag_service import auto_tag_service


async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(JudgeProblem).order_by(JudgeProblem.id.asc()).limit(1))
        problem = res.scalars().first()
        print(f"PROBLEM: id={problem.id} code={problem.code}", flush=True)
        try:
            outcome = await auto_tag_service.tag_problem(problem, db)
            print(f"SOURCE: {outcome.source}", flush=True)
            print(f"RESULT: {outcome.result}", flush=True)
        except Exception:
            print("=== FULL TRACEBACK ===", flush=True)
            traceback.print_exc()
            sys.stdout.flush()


asyncio.run(main())

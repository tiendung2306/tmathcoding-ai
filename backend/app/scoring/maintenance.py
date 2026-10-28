"""Deployment/operator entry point. Dashboard HTTP routes only expose scoring reads."""
import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.config import settings
from app.core.dashboard_database import DashboardSessionLocal, dashboard_database
from app.models.scoring import ScoringRun
from app.services.source_gateway import close_source_gateway, get_source_gateway_client
from .service import enqueue, publish, reprice_active, run_data, state


async def execute(args):
    try:
        async with DashboardSessionLocal() as db:
            if args.action in ("calibrate", "refresh"):
                result = await enqueue(db, settings.DASHBOARD_ADMIN_PROFILE_ID, args.action)
            elif args.action == "publish":
                result = await publish(db, args.run_id, get_source_gateway_client(), settings.DASHBOARD_ADMIN_PROFILE_ID)
            elif args.action == "reprice":
                result = await reprice_active(db, get_source_gateway_client(), settings.DASHBOARD_ADMIN_PROFILE_ID)
            else:
                current = await state(db)
                rows = (await db.execute(select(ScoringRun).order_by(ScoringRun.created_at.desc()).limit(5))).scalars()
                result = {"active_run_id": current.active_run_id, "runs": [run_data(row) for row in rows]}
            print(json.dumps(result, default=str, ensure_ascii=False))
    finally:
        await close_source_gateway()
        await dashboard_database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "refresh", "publish", "status", "reprice"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "publish" and not args.run_id:
        parser.error("publish requires --run-id")
    asyncio.run(execute(args))

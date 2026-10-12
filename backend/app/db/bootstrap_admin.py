"""Create the one dashboard administrator after migrations have run."""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.dashboard_auth import hash_password
from app.core.dashboard_database import DashboardSessionLocal, dashboard_database
from app.core.database import AsyncSessionLocal, source_database
from app.core.time import utc_now
from app.models.auth import DashboardAccount
from app.models.dmoj import JudgeProfile


async def bootstrap(password: str) -> None:
    async with AsyncSessionLocal() as source:
        profile = (await source.execute(select(JudgeProfile).where(
            JudgeProfile.id == settings.DASHBOARD_ADMIN_PROFILE_ID
        ))).scalar_one_or_none()
        if profile is None or not profile.super_admin:
            raise RuntimeError("DASHBOARD_ADMIN_PROFILE_ID must refer to a source super admin")
    async with DashboardSessionLocal() as dashboard:
        existing = (await dashboard.execute(select(DashboardAccount))).scalar_one_or_none()
        if existing is not None:
            raise RuntimeError("Dashboard administrator already exists; no account was changed")
        now = utc_now()
        dashboard.add(DashboardAccount(
            username="admin", password_hash=await hash_password(password), role="admin",
            admin_slot=1, source_profile_id=profile.id,
            created_at=now, updated_at=now,
        ))
        await dashboard.commit()


async def main() -> None:
    try:
        password = getpass.getpass("Initial admin password: ")
        if not password:
            raise RuntimeError("Password is required")
        await bootstrap(password)
        print("Created dashboard administrator: admin")
    finally:
        await dashboard_database.close()
        await source_database.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

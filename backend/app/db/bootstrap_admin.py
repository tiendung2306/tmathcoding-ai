"""Create the one dashboard administrator after migrations have run."""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.dashboard_auth import hash_password
from app.core.dashboard_database import DashboardSessionLocal, dashboard_database
from app.core.time import utc_now
from app.models.auth import DashboardAccount
from app.services.source_gateway import get_source_gateway_client


async def bootstrap(password: str) -> None:
    profile_id = settings.DASHBOARD_ADMIN_PROFILE_ID
    profile = await get_source_gateway_client().get_access(
        profile_id, actor_profile_id=profile_id,
    )
    if not profile.exists or not profile.is_active or not profile.is_super_admin:
        raise RuntimeError("DASHBOARD_ADMIN_PROFILE_ID must refer to an active source super admin")
    async with DashboardSessionLocal() as dashboard:
        existing = (await dashboard.execute(select(DashboardAccount))).scalar_one_or_none()
        if existing is not None:
            raise RuntimeError("Dashboard administrator already exists; no account was changed")
        now = utc_now()
        dashboard.add(DashboardAccount(
            username="admin", password_hash=await hash_password(password), role="admin",
            admin_slot=1, source_profile_id=profile.profile_id,
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
        from app.services.source_gateway import close_source_gateway
        await close_source_gateway()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

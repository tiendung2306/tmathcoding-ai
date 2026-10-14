import unittest
from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.db import bootstrap_admin
from app.db.offline_source_config import OfflineSourceSettings


class FakeSession:
    def __init__(self):
        self.added = None
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, _query):
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def add(self, record):
        self.added = record

    async def commit(self):
        self.committed = True


class BootstrapAdminTests(unittest.IsolatedAsyncioTestCase):
    def test_offline_source_settings_builds_only_source_database_url(self):
        with patch.dict("os.environ", {
            "SOURCE_DB_HOST": "source-db",
            "SOURCE_DB_PORT": "3307",
            "SOURCE_DB_USER": "reader",
            "SOURCE_DB_PASSWORD": "secret",
            "SOURCE_DB_NAME": "source",
        }, clear=True):
            config = OfflineSourceSettings()
        self.assertEqual(config.database_url.host, "source-db")
        self.assertEqual(config.database_url.port, 3307)
        self.assertEqual(config.database_url.database, "source")
        self.assertEqual(config.database_url.username, "reader")

    async def test_bootstrap_validates_admin_through_source_gateway(self):
        session = FakeSession()
        gateway = SimpleNamespace(get_access=AsyncMock(return_value=SimpleNamespace(
            exists=True, is_active=True, is_super_admin=True, profile_id=42,
        )))
        with patch.object(bootstrap_admin.settings, "DASHBOARD_ADMIN_PROFILE_ID", 42), \
                patch.object(bootstrap_admin, "get_source_gateway_client", return_value=gateway), \
                patch.object(bootstrap_admin, "DashboardSessionLocal", return_value=session), \
                patch.object(bootstrap_admin, "hash_password", new=AsyncMock(return_value="hashed")):
            await bootstrap_admin.bootstrap("secret")
        gateway.get_access.assert_awaited_once_with(42, actor_profile_id=42)
        self.assertTrue(session.committed)
        self.assertEqual(session.added.source_profile_id, 42)

    async def test_bootstrap_rejects_source_profile_without_super_admin_access(self):
        gateway = SimpleNamespace(get_access=AsyncMock(return_value=SimpleNamespace(
            exists=True, is_active=True, is_super_admin=False, profile_id=42,
        )))
        with patch.object(bootstrap_admin.settings, "DASHBOARD_ADMIN_PROFILE_ID", 42), \
                patch.object(bootstrap_admin, "get_source_gateway_client", return_value=gateway), \
                patch.object(bootstrap_admin, "DashboardSessionLocal") as dashboard_session:
            with self.assertRaisesRegex(RuntimeError, "active source super admin"):
                await bootstrap_admin.bootstrap("secret")
        dashboard_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import class_student_service as roster


class RosterGateway:
    def __init__(self):
        self.calls = 0

    async def list_class_students(self, class_id, *, actor_profile_id, cursor=None, limit=100):
        self.calls += 1
        return SimpleNamespace(items=[f"roster-v{self.calls}"], next_cursor=None, has_more=False)


class RosterCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        roster.reset_roster_cache()

    async def test_reads_do_not_extend_roster_lifetime(self):
        gateway, clock = RosterGateway(), [0.0]
        with patch.object(roster.time, "monotonic", side_effect=lambda: clock[0]):
            for second in range(0, 600, 30):  # a class polled every 30 seconds for 10 minutes
                clock[0] = float(second)
                students = await roster.get_class_students(gateway, 1, 7)
        self.assertGreaterEqual(gateway.calls, 600 // roster._CACHE_TTL_SECONDS)
        self.assertNotEqual(students, ["roster-v1"])

    async def test_roster_is_reused_within_ttl(self):
        gateway, clock = RosterGateway(), [100.0]
        with patch.object(roster.time, "monotonic", side_effect=lambda: clock[0]):
            await roster.get_class_students(gateway, 1, 7)
            clock[0] += roster._CACHE_TTL_SECONDS - 1
            await roster.get_class_students(gateway, 1, 7)
        self.assertEqual(gateway.calls, 1)


if __name__ == "__main__":
    unittest.main()

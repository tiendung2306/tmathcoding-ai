import asyncio
import gc
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.job_manager import LLMJobManager
from app.schemas.jobs import JobStatus


class JobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Exercise the in-memory fallback (no Redis in unit tests).
        self.redis = patch("app.core.job_manager.get_redis_client", return_value=None)
        self.redis.start()

    async def asyncTearDown(self):
        self.redis.stop()

    async def test_running_job_survives_garbage_collection(self):
        manager = LLMJobManager(max_concurrency=1)
        release = asyncio.Event()

        async def work():
            await release.wait()
            return {"ok": True}

        job_id, created = await manager.enqueue_job("CODE_DOCTOR", work, entity_key="1")
        self.assertTrue(created)
        self.assertEqual(len(manager._running_tasks), 1)
        await asyncio.sleep(0)
        gc.collect()
        release.set()
        for _ in range(20):
            await asyncio.sleep(0)
        self.assertEqual((await manager.get_job(job_id)).status, JobStatus.COMPLETED)
        self.assertEqual(manager._running_tasks, set())

    async def test_queued_job_is_reused_but_not_forever(self):
        manager = LLMJobManager(max_concurrency=1)
        first, created = await manager.create_job("CODE_DOCTOR", entity_key="9", timeout_seconds=30)
        self.assertTrue(created)
        self.assertEqual(await manager.create_job("CODE_DOCTOR", entity_key="9", timeout_seconds=30), (first, False))
        record = manager._mem_jobs[first]
        record["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        second, created = await manager.create_job("CODE_DOCTOR", entity_key="9", timeout_seconds=30)
        self.assertTrue(created)
        self.assertNotEqual(second, first)
        self.assertEqual((await manager.get_job(first)).status, JobStatus.FAILED)


if __name__ == "__main__":
    unittest.main()

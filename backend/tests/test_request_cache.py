import asyncio
import unittest
from unittest.mock import patch

from app.core import request_cache


class RequestCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        request_cache.reset_request_cache()

    async def test_concurrent_identical_calls_share_one_computation(self):
        calls = 0

        async def compute():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"items": [1, 2]}

        results = await asyncio.gather(*(request_cache.cached_call("k", 5, compute) for _ in range(10)))
        self.assertEqual(calls, 1)
        self.assertTrue(all(result == {"items": [1, 2]} for result in results))
        results[0]["items"].append(3)  # callers get private copies
        self.assertEqual(await request_cache.cached_call("k", 5, compute), {"items": [1, 2]})
        self.assertEqual(calls, 1)

    async def test_failures_are_not_cached_and_entries_expire(self):
        attempts = 0

        async def flaky():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("source down")
            return attempts

        with self.assertRaises(RuntimeError):
            await request_cache.cached_call("f", 5, flaky)
        self.assertEqual(await request_cache.cached_call("f", 5, flaky), 2)
        clock = [request_cache.time.monotonic() + 10]
        with patch.object(request_cache.time, "monotonic", side_effect=lambda: clock[0]):
            self.assertEqual(await request_cache.cached_call("f", 5, flaky), 3)

    async def test_one_caller_cancelling_does_not_cancel_the_shared_work(self):
        gate = asyncio.Event()

        async def slow():
            await gate.wait()
            return "done"

        first = asyncio.create_task(request_cache.cached_call("s", 5, slow))
        second = asyncio.create_task(request_cache.cached_call("s", 5, slow))
        await asyncio.sleep(0)
        first.cancel()
        gate.set()
        self.assertEqual(await second, "done")


if __name__ == "__main__":
    unittest.main()

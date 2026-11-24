"""Short-lived, in-process response cache with request coalescing.

Heavy read endpoints (class heatmap, student detail, contest live submissions) are
often requested by several tabs or pollers at once. Concurrent identical calls share
one computation, and the result is reused for a few seconds. Callers always get a
private deep copy, so post-processing such as score overlays cannot corrupt the cache.
Failures are never cached. The shared computation runs as its own task, so one caller
disconnecting does not cancel it for the others.
"""
from __future__ import annotations

import asyncio
import copy
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Hashable

_MAX_ENTRIES = 256
_values: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
_inflight: dict[Hashable, asyncio.Task] = {}


def reset_request_cache() -> None:
    _values.clear()
    _inflight.clear()


def _store(key: Hashable, ttl_seconds: float, task: asyncio.Task) -> None:
    if _inflight.get(key) is task:
        _inflight.pop(key, None)
    if task.cancelled() or task.exception() is not None or ttl_seconds <= 0:
        return
    _values[key] = (time.monotonic(), task.result())
    _values.move_to_end(key)
    while len(_values) > _MAX_ENTRIES:
        _values.popitem(last=False)


async def cached_call(key: Hashable, ttl_seconds: float, factory: Callable[[], Awaitable[Any]]) -> Any:
    hit = _values.get(key)
    if hit is not None and time.monotonic() - hit[0] < ttl_seconds:
        _values.move_to_end(key)
        return copy.deepcopy(hit[1])

    task = _inflight.get(key)
    if task is None:
        task = asyncio.create_task(factory())
        _inflight[key] = task
        task.add_done_callback(lambda done: _store(key, ttl_seconds, done))
    return copy.deepcopy(await asyncio.shield(task))

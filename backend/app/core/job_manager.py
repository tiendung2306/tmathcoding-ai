import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional, Set, Tuple

from app.core.redis import cache_delete, cache_get, cache_set, get_redis_client
from app.schemas.jobs import JobStatus, JobStatusResponse, JobType

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None


class LLMJobManager:
    """Production-grade LLM Job Manager with Redis backing, concurrency limiting,

    deduplication, and 3-tier dead-worker (zombie task) recovery.
    """

    def __init__(self, max_concurrency: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._sweeper_task: Optional[asyncio.Task] = None

        # In-memory fallbacks if Redis is down
        self._mem_jobs: Dict[str, dict] = {}
        self._mem_refs: Dict[str, str] = {}
        self._mem_processing: Set[str] = set()

    # --------------------------------------------------------------------------
    # Redis Key Helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"tmath:job:{job_id}"

    @staticmethod
    def _ref_key(job_type: str, entity_key: str) -> str:
        return f"tmath:job:ref:{job_type}:{entity_key}"

    @staticmethod
    def _processing_set_key() -> str:
        return "tmath:jobs:processing"

    # --------------------------------------------------------------------------
    # Storage Access (Redis with in-memory fallback)
    # --------------------------------------------------------------------------
    async def _save_job_record(self, record: dict, expire: int = 86400) -> None:
        job_id = record["job_id"]
        json_str = json.dumps(record, ensure_ascii=False)
        saved = await cache_set(self._job_key(job_id), json_str, expire=expire)
        if not saved:
            self._mem_jobs[job_id] = record

    async def _get_job_record(self, job_id: str) -> Optional[dict]:
        json_str = await cache_get(self._job_key(job_id))
        if json_str:
            try:
                return json.loads(json_str)
            except Exception as e:
                logger.warning(f"Failed to decode job record for '{job_id}': {e}")
        return self._mem_jobs.get(job_id)

    async def _add_to_processing(self, job_id: str) -> None:
        client = get_redis_client()
        if client:
            try:
                await client.sadd(self._processing_set_key(), job_id)
                return
            except Exception as e:
                logger.warning(f"Redis sadd failed for processing set: {e}")
        self._mem_processing.add(job_id)

    async def _remove_from_processing(self, job_id: str) -> None:
        client = get_redis_client()
        if client:
            try:
                await client.srem(self._processing_set_key(), job_id)
                return
            except Exception as e:
                logger.warning(f"Redis srem failed for processing set: {e}")
        self._mem_processing.discard(job_id)

    async def _get_all_processing_job_ids(self) -> Set[str]:
        client = get_redis_client()
        if client:
            try:
                members = await client.smembers(self._processing_set_key())
                return {m if isinstance(m, str) else m.decode() for m in members}
            except Exception as e:
                logger.warning(f"Redis smembers failed for processing set: {e}")
        return set(self._mem_processing)

    # --------------------------------------------------------------------------
    # Core Job Lifecycle
    # --------------------------------------------------------------------------
    async def create_job(
        self,
        job_type: str,
        entity_key: Optional[str] = None,
        timeout_seconds: int = 120,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        """Creates a job or returns an active existing job_id for the same entity."""
        now_iso = _utc_now_iso()

        # Check deduplication reference lock
        if entity_key:
            ref_k = self._ref_key(job_type, entity_key)
            existing_job_id = await cache_get(ref_k) or self._mem_refs.get(ref_k)
            if existing_job_id:
                existing_record = await self._get_job_record(existing_job_id)
                if existing_record:
                    status = existing_record.get("status")
                    if status in [JobStatus.PENDING, JobStatus.PROCESSING]:
                        # Check if it didn't exceed deadline
                        deadline_str = existing_record.get("deadline_at")
                        deadline_dt = _parse_iso(deadline_str)
                        if not deadline_dt or datetime.now(timezone.utc) <= deadline_dt:
                            logger.info(f"Reusing active job '{existing_job_id}' for {job_type}:{entity_key}")
                            return existing_job_id, False
                        else:
                            # Stale job, mark failed and create fresh one
                            await self.fail_job(
                                existing_job_id,
                                "Tác vụ trước đó bị gián đoạn do hết thời gian tối đa (Worker Timeout)."
                            )

        # Generate new job ID
        clean_type = job_type.lower().replace("_", "")
        job_id = f"job_{clean_type}_{uuid.uuid4().hex[:12]}"

        record = {
            "job_id": job_id,
            "job_type": job_type,
            "entity_key": entity_key,
            "status": JobStatus.PENDING,
            "progress": 0,
            "result": None,
            "error": None,
            "metadata": metadata or {},
            "timeout_seconds": timeout_seconds,
            "created_at": now_iso,
            "updated_at": now_iso,
            "started_at": None,
            "deadline_at": None,
        }

        await self._save_job_record(record, expire=86400)

        if entity_key:
            ref_k = self._ref_key(job_type, entity_key)
            await cache_set(ref_k, job_id, expire=timeout_seconds + 60)
            self._mem_refs[ref_k] = job_id

        return job_id, True

    async def get_job(self, job_id: str) -> Optional[JobStatusResponse]:
        """Retrieves a job. TIER 1: Performs Lazy Dead Job Check on read."""
        record = await self._get_job_record(job_id)
        if not record:
            return None

        # Tier 1 Lazy Evaluation: If PROCESSING and deadline expired, mark FAILED
        if record.get("status") == JobStatus.PROCESSING:
            deadline_str = record.get("deadline_at")
            deadline_dt = _parse_iso(deadline_str)
            if deadline_dt and datetime.now(timezone.utc) > deadline_dt:
                logger.warning(f"Lazy Dead-Job Reaper triggered for job '{job_id}' (exceeded deadline)")
                await self.fail_job(
                    job_id,
                    "Tác vụ bị gián đoạn hoặc vượt quá thời gian tối đa cho phép (Worker Crash / Timeout)."
                )
                record = await self._get_job_record(job_id)

        return JobStatusResponse(
            job_id=record["job_id"],
            job_type=record.get("job_type", "UNKNOWN"),
            status=record["status"],
            progress=record.get("progress", 0),
            result=record.get("result"),
            error=record.get("error"),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            started_at=record.get("started_at"),
            deadline_at=record.get("deadline_at"),
        )

    async def start_job(self, job_id: str) -> None:
        record = await self._get_job_record(job_id)
        if not record:
            return
        now = datetime.now(timezone.utc)
        timeout = record.get("timeout_seconds", 120)
        deadline = now.timestamp() + timeout
        deadline_dt = datetime.fromtimestamp(deadline, tz=timezone.utc)

        record["status"] = JobStatus.PROCESSING
        record["progress"] = 15
        record["started_at"] = now.isoformat()
        record["deadline_at"] = deadline_dt.isoformat()
        record["updated_at"] = now.isoformat()

        await self._save_job_record(record, expire=86400)
        await self._add_to_processing(job_id)
        logger.info(f"Job '{job_id}' started. Deadline: {record['deadline_at']}")

    async def complete_job(self, job_id: str, result: Any) -> None:
        record = await self._get_job_record(job_id)
        if not record:
            return
        now_iso = _utc_now_iso()
        record["status"] = JobStatus.COMPLETED
        record["progress"] = 100
        record["result"] = result
        record["updated_at"] = now_iso

        await self._save_job_record(record, expire=86400)
        await self._remove_from_processing(job_id)

        # Release deduplication ref lock
        entity_key = record.get("entity_key")
        job_type = record.get("job_type")
        if entity_key and job_type:
            ref_k = self._ref_key(job_type, entity_key)
            await cache_delete(ref_k)
            self._mem_refs.pop(ref_k, None)

        logger.info(f"Job '{job_id}' completed successfully.")

    async def fail_job(self, job_id: str, error_message: str) -> None:
        record = await self._get_job_record(job_id)
        if not record:
            return
        now_iso = _utc_now_iso()
        record["status"] = JobStatus.FAILED
        record["error"] = error_message
        record["updated_at"] = now_iso

        await self._save_job_record(record, expire=86400)
        await self._remove_from_processing(job_id)

        # Release deduplication ref lock
        entity_key = record.get("entity_key")
        job_type = record.get("job_type")
        if entity_key and job_type:
            ref_k = self._ref_key(job_type, entity_key)
            await cache_delete(ref_k)
            self._mem_refs.pop(ref_k, None)

        logger.warning(f"Job '{job_id}' marked FAILED: {error_message}")

    # --------------------------------------------------------------------------
    # Job Enqueuing and Execution with Concurrency Limiting
    # --------------------------------------------------------------------------
    async def enqueue_job(
        self,
        job_type: str,
        task_func: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        entity_key: Optional[str] = None,
        timeout_seconds: int = 120,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Tuple[str, bool]:
        """Enqueues a task for async execution controlled by Semaphore.

        Returns (job_id, is_new_job).
        """
        job_id, is_new = await self.create_job(
            job_type=job_type,
            entity_key=entity_key,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )

        if is_new:
            asyncio.create_task(
                self._run_job_wrapper(job_id, task_func, timeout_seconds, *args, **kwargs)
            )

        return job_id, is_new

    async def _run_job_wrapper(
        self,
        job_id: str,
        task_func: Callable[..., Coroutine[Any, Any, Any]],
        timeout_seconds: int,
        *args,
        **kwargs,
    ) -> None:
        """Executes the task within semaphore limit, updating state and deadline."""
        async with self._semaphore:
            try:
                await self.start_job(job_id)
                # Run with strict timeout
                result = await asyncio.wait_for(
                    task_func(*args, **kwargs),
                    timeout=float(timeout_seconds),
                )
                await self.complete_job(job_id, result)
            except asyncio.TimeoutError:
                logger.error(f"Job '{job_id}' timed out after {timeout_seconds}s.")
                await self.fail_job(
                    job_id,
                    f"Tác vụ vượt quá giới hạn thời gian {timeout_seconds}s của hệ thống."
                )
            except Exception as e:
                logger.exception(f"Job '{job_id}' encountered an unhandled error: {e}")
                await self.fail_job(
                    job_id,
                    f"Lỗi khi thực thi tác vụ: {str(e) or 'Ngoại lệ không xác định'}"
                )

    # --------------------------------------------------------------------------
    # TIER 2: Periodic Background Dead-Job Sweeper
    # --------------------------------------------------------------------------
    async def _sweeper_loop(self, interval_seconds: int = 30) -> None:
        logger.info(f"LLM Job Sweeper started (interval: {interval_seconds}s)")
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                active_ids = await self._get_all_processing_job_ids()
                if not active_ids:
                    continue

                now = datetime.now(timezone.utc)
                for job_id in list(active_ids):
                    record = await self._get_job_record(job_id)
                    if not record:
                        await self._remove_from_processing(job_id)
                        continue
                    if record.get("status") == JobStatus.PROCESSING:
                        deadline_str = record.get("deadline_at")
                        deadline_dt = _parse_iso(deadline_str)
                        if deadline_dt and now > deadline_dt:
                            logger.warning(
                                f"Sweeper found dead zombie task '{job_id}'. Marking FAILED."
                            )
                            await self.fail_job(
                                job_id,
                                "Tác vụ bị gián đoạn hoặc worker dừng đột ngột (Worker Crash / Timeout)."
                            )
            except asyncio.CancelledError:
                logger.info("LLM Job Sweeper cancelled.")
                break
            except Exception as e:
                logger.warning(f"Error in LLM Job Sweeper loop: {e}")

    def start_sweeper(self, interval_seconds: int = 30) -> None:
        if self._sweeper_task is None or self._sweeper_task.done():
            self._sweeper_task = asyncio.create_task(self._sweeper_loop(interval_seconds))

    def stop_sweeper(self) -> None:
        if self._sweeper_task and not self._sweeper_task.done():
            self._sweeper_task.cancel()
            self._sweeper_task = None

    # --------------------------------------------------------------------------
    # TIER 3: Startup Recovery (Clean up orphaned jobs across server restarts)
    # --------------------------------------------------------------------------
    async def startup_recovery(self) -> None:
        """Called on FastAPI lifespan startup to recover any zombie tasks from previous run."""
        try:
            active_ids = await self._get_all_processing_job_ids()
            if not active_ids:
                return
            logger.info(f"Startup Recovery: found {len(active_ids)} orphaned jobs. Cleaning up...")
            for job_id in active_ids:
                record = await self._get_job_record(job_id)
                if record and record.get("status") in [JobStatus.PENDING, JobStatus.PROCESSING]:
                    await self.fail_job(
                        job_id,
                        "Tác vụ bị gián đoạn do máy chủ khởi động lại (Server Restart Recovery)."
                    )
            logger.info("Startup Recovery completed.")
        except Exception as e:
            logger.warning(f"Startup Recovery encountered error: {e}")


# Global Singleton Instance
job_manager = LLMJobManager(max_concurrency=2)

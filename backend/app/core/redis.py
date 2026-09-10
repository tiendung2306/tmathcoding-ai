import logging
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_pool: Optional[aioredis.ConnectionPool] = None
_redis_client: Optional[aioredis.Redis] = None

async def init_redis_pool() -> None:
    """Initializes the global Redis connection pool and verifies connectivity with PING."""
    global _redis_pool, _redis_client
    try:
        port = settings.REDIS_PORT
        # When running in Docker network with service name 'redis', internal port is always 6379
        if settings.REDIS_HOST == "redis":
            port = 6379

        _redis_pool = aioredis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=port,
            decode_responses=True,
            max_connections=20,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
        await _redis_client.ping()
        logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{port}")
    except Exception as e:
        logger.warning(f"Unable to connect to Redis at {settings.REDIS_HOST}:{port}: {e}. Fallback in-memory cache will be used.")
        _redis_client = None

async def close_redis_pool() -> None:
    """Gracefully closes Redis connections on application shutdown."""
    global _redis_client, _redis_pool
    if _redis_client:
        try:
            await _redis_client.aclose()
            logger.info("Redis client connections closed.")
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        _redis_client = None
    if _redis_pool:
        try:
            await _redis_pool.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting Redis pool: {e}")
        _redis_pool = None

def get_redis_client() -> Optional[aioredis.Redis]:
    """Returns the global active Redis client or None if Redis is unavailable."""
    return _redis_client

async def cache_get(key: str) -> Optional[str]:
    """Safely retrieves a string value from Redis (Fail-open: returns None on failure)."""
    client = get_redis_client()
    if not client:
        return None
    try:
        return await client.get(key)
    except Exception as e:
        logger.warning(f"Redis GET failed for key '{key}': {e}")
        return None

async def cache_set(key: str, value: str, expire: int = 86400) -> bool:
    """Safely writes a string value to Redis with TTL (Fail-open: returns False on failure)."""
    client = get_redis_client()
    if not client:
        return False
    try:
        await client.set(key, value, ex=expire)
        return True
    except Exception as e:
        logger.warning(f"Redis SET failed for key '{key}': {e}")
        return False

async def cache_delete(key: str) -> bool:
    """Safely deletes a key from Redis (Fail-open: returns False on failure)."""
    client = get_redis_client()
    if not client:
        return False
    try:
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis DELETE failed for key '{key}': {e}")
        return False

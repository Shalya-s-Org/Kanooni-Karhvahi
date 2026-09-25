from typing import AsyncGenerator, Dict, Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import logger

redis_pool: Optional[aioredis.ConnectionPool] = None


def get_redis_pool() -> Optional[aioredis.ConnectionPool]:
    global redis_pool
    if redis_pool is None:
        try:
            redis_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0
            )
        except Exception as e:
            logger.warning("Could not initialize Redis pool: %s", e)
            redis_pool = None
    return redis_pool


async def get_redis_client() -> AsyncGenerator[Optional[aioredis.Redis], None]:
    """
    Dependency for obtaining an asynchronous Redis client.
    """
    pool = get_redis_pool()
    if pool is None:
        yield None
        return

    client = aioredis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_connection() -> Dict[str, Any]:
    """
    Verifies live connectivity to Redis.
    """
    try:
        pool = get_redis_pool()
        if pool is None:
            return {"connected": False, "message": "Redis pool could not be initialized"}
        client = aioredis.Redis(connection_pool=pool)
        pong = await client.ping()
        await client.aclose()
        if pong:
            return {"connected": True, "message": "Redis ping succeeded."}
        return {"connected": False, "message": "Redis did not respond with PONG"}
    except Exception as e:
        return {"connected": False, "message": f"Redis connection failed: {str(e)}"}

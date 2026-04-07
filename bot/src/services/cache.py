"""
Shared Redis cache utility.
Provides a singleton async Redis client with typed get/set helpers.
"""
import json
from typing import Any

import structlog
from redis.asyncio import Redis, from_url

from src.config import settings

log = structlog.get_logger()

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def cache_get(key: str) -> Any | None:
    """Get JSON-decoded value from Redis. Returns None on miss or error."""
    try:
        r = await get_redis()
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        log.debug("cache.get_failed", key=key, error=str(e))
    return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Set JSON-encoded value in Redis with TTL in seconds. Silently ignores errors."""
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    except Exception as e:
        log.debug("cache.set_failed", key=key, error=str(e))


async def cache_incr(key: str, ttl_if_new: int) -> int:
    """Increment counter in Redis. Sets TTL only on first increment."""
    try:
        r = await get_redis()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, ttl_if_new)
        return count
    except Exception as e:
        log.debug("cache.incr_failed", key=key, error=str(e))
        return 0

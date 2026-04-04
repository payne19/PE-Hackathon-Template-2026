"""
Redis cache layer for URL lookups.

Windows options for running Redis:
  1. WSL2:  wsl --install  then  sudo apt install redis  then  redis-server
  2. Memurai (Redis-compatible Windows native): https://www.memurai.com/
  3. Docker Desktop:  docker run -p 6379:6379 redis:7-alpine

If Redis is unreachable the cache silently falls back to Postgres only.
Nothing breaks — it just won't be cached.
"""
import os
import logging

import redis

logger = logging.getLogger(__name__)

# TTL for cached entries: 24 hours
CACHE_TTL = int(os.environ.get("REDIS_TTL", 86400))

# Key prefixes
_PREFIX_CODE = "url:code:"        # url:code:{short_code}  →  original_url
_PREFIX_ORIG = "url:orig:"        # url:orig:{original_url} →  short_code  (dedup)


def _client() -> redis.Redis | None:
    """Return a Redis client, or None if unavailable."""
    try:
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            db=int(os.environ.get("REDIS_DB", 0)),
            decode_responses=True,
            socket_connect_timeout=1,
        )
        r.ping()
        return r
    except Exception:
        logger.warning("Redis unavailable — running without cache")
        return None


# Module-level client (initialised once per process)
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _redis
    if _redis is None:
        _redis = _client()
    return _redis


# ── Public API ────────────────────────────────────────────────────────────────

def get_original_url(short_code: str) -> str | None:
    """
    Cache lookup: short_code → original_url.
    Returns None on miss or Redis error.
    """
    r = get_redis()
    if r is None:
        return None
    try:
        return r.get(f"{_PREFIX_CODE}{short_code}")
    except Exception as exc:
        logger.warning("Redis get failed: %s", exc)
        return None


def get_existing_code(original_url: str) -> str | None:
    """
    Cache lookup: original_url → short_code (dedup check).
    Returns None on miss or Redis error.
    """
    r = get_redis()
    if r is None:
        return None
    try:
        return r.get(f"{_PREFIX_ORIG}{original_url}")
    except Exception as exc:
        logger.warning("Redis get failed: %s", exc)
        return None


def set_url(short_code: str, original_url: str) -> None:
    """Store both directions in Redis."""
    r = get_redis()
    if r is None:
        return
    try:
        pipe = r.pipeline()
        pipe.setex(f"{_PREFIX_CODE}{short_code}", CACHE_TTL, original_url)
        pipe.setex(f"{_PREFIX_ORIG}{original_url}", CACHE_TTL, short_code)
        pipe.execute()
    except Exception as exc:
        logger.warning("Redis set failed: %s", exc)


def invalidate_code(short_code: str, original_url: str) -> None:
    """Remove a URL from cache (e.g. when it's deactivated)."""
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(f"{_PREFIX_CODE}{short_code}", f"{_PREFIX_ORIG}{original_url}")
    except Exception as exc:
        logger.warning("Redis delete failed: %s", exc)

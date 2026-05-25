"""Redis cache wrapper with serialization support."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache wrapper with key prefixing and TTL support."""

    def __init__(self, redis_client: Any, prefix: str = "quant_os", default_ttl: int = 3600) -> None:
        self._redis = redis_client
        self._prefix = prefix
        self._default_ttl = default_ttl

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        full_key = self._make_key(key)
        try:
            data = await self._redis.get(full_key)
            if data is None:
                return None
            return json.loads(data)
        except Exception as exc:
            logger.warning("Cache GET failed for %s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        full_key = self._make_key(key)
        try:
            data = json.dumps(value, default=str)
            await self._redis.setex(full_key, ttl or self._default_ttl, data)
            return True
        except Exception as exc:
            logger.warning("Cache SET failed for %s: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        try:
            await self._redis.delete(full_key)
            return True
        except Exception as exc:
            logger.warning("Cache DELETE failed for %s: %s", key, exc)
            return False

    async def exists(self, key: str) -> bool:
        full_key = self._make_key(key)
        try:
            return bool(await self._redis.exists(full_key))
        except Exception:
            return False

    async def clear_prefix(self, pattern: str) -> int:
        full_pattern = self._make_key(pattern)
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=full_pattern, count=100)
                if keys:
                    deleted += await self._redis.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.warning("Cache clear_prefix failed for %s: %s", pattern, exc)
            return 0

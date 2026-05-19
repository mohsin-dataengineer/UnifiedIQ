"""In-process TTL cache wrapper (Part 2.4)."""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache


class CacheService:
    def __init__(self, *, maxsize: int, ttl: int) -> None:
        self._default_ttl = ttl
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        # TTLCache uses a single TTL; a per-key override would need a second
        # cache instance. Keep one cache until a real need appears (Principle 8).
        if ttl is not None and ttl != self._default_ttl:
            raise ValueError("per-key TTL override is not supported")
        self._cache[key] = value

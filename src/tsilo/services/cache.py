"""Simple in-memory TTL cache for reducing repeated database queries."""

import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL expiration.

    Suitable for caching permission checks and module metadata in a
    single-process deployment. For multi-process, use an external cache.
    """

    def __init__(self, default_ttl: float, max_size: int = 1024) -> None:
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Module metadata cache: 5-minute TTL
module_cache = TTLCache(default_ttl=300.0, max_size=512)

# Permission cache: 1-minute TTL
permission_cache = TTLCache(default_ttl=60.0, max_size=2048)

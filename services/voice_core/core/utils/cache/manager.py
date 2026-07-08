"""
Small global cache manager copied for the extracted Xiaozhi core.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

from .config import CacheConfig, CacheType
from .strategies import CacheEntry, CacheStrategy


class GlobalCacheManager:
    def __init__(self):
        self._logger = None
        self._caches: Dict[str, Dict[str, CacheEntry]] = {}
        self._configs: Dict[str, CacheConfig] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._last_cleanup = time.time()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "cleanups": 0}

    @property
    def logger(self):
        if self._logger is None:
            from config.logger import setup_logging

            self._logger = setup_logging()
        return self._logger

    def _get_cache_name(self, cache_type: CacheType, namespace: str = "") -> str:
        return f"{cache_type.value}:{namespace}" if namespace else cache_type.value

    def _get_or_create_cache(
        self, cache_name: str, config: CacheConfig
    ) -> Dict[str, CacheEntry]:
        with self._global_lock:
            if cache_name not in self._caches:
                self._caches[cache_name] = (
                    OrderedDict()
                    if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]
                    else {}
                )
                self._configs[cache_name] = config
                self._locks[cache_name] = threading.RLock()
            return self._caches[cache_name]

    def set(
        self,
        cache_type: CacheType,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        namespace: str = "",
    ) -> None:
        cache_name = self._get_cache_name(cache_type, namespace)
        config = self._configs.get(cache_name) or CacheConfig.for_type(cache_type)
        cache = self._get_or_create_cache(cache_name, config)
        effective_ttl = ttl if ttl is not None else config.ttl

        with self._locks[cache_name]:
            entry = CacheEntry(value=value, timestamp=time.time(), ttl=effective_ttl)
            if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]:
                if key in cache:
                    del cache[key]
                cache[key] = entry
                if config.max_size and len(cache) > config.max_size:
                    del cache[next(iter(cache))]
                    self._stats["evictions"] += 1
            else:
                cache[key] = entry
                if config.max_size and len(cache) > config.max_size:
                    del cache[next(iter(cache))]
                    self._stats["evictions"] += 1

        self._maybe_cleanup(cache_name)

    def get(
        self, cache_type: CacheType, key: str, namespace: str = ""
    ) -> Optional[Any]:
        cache_name = self._get_cache_name(cache_type, namespace)
        if cache_name not in self._caches:
            self._stats["misses"] += 1
            return None

        cache = self._caches[cache_name]
        config = self._configs[cache_name]
        with self._locks[cache_name]:
            if key not in cache:
                self._stats["misses"] += 1
                return None

            entry = cache[key]
            if entry.is_expired():
                del cache[key]
                self._stats["misses"] += 1
                return None

            entry.touch()
            if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]:
                del cache[key]
                cache[key] = entry

            self._stats["hits"] += 1
            return entry.value

    def delete(self, cache_type: CacheType, key: str, namespace: str = "") -> bool:
        cache_name = self._get_cache_name(cache_type, namespace)
        if cache_name not in self._caches:
            return False

        with self._locks[cache_name]:
            if key in self._caches[cache_name]:
                del self._caches[cache_name][key]
                return True
        return False

    def clear(self, cache_type: CacheType, namespace: str = "") -> None:
        cache_name = self._get_cache_name(cache_type, namespace)
        if cache_name in self._caches:
            with self._locks[cache_name]:
                self._caches[cache_name].clear()

    def invalidate_pattern(
        self, cache_type: CacheType, pattern: str, namespace: str = ""
    ) -> int:
        cache_name = self._get_cache_name(cache_type, namespace)
        if cache_name not in self._caches:
            return 0

        deleted_count = 0
        with self._locks[cache_name]:
            keys_to_delete = [key for key in self._caches[cache_name] if pattern in key]
            for key in keys_to_delete:
                del self._caches[cache_name][key]
                deleted_count += 1
        return deleted_count

    def _cleanup_expired(self, cache_name: str) -> int:
        if cache_name not in self._caches:
            return 0

        deleted_count = 0
        with self._locks[cache_name]:
            expired_keys = [
                key for key, entry in self._caches[cache_name].items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self._caches[cache_name][key]
                deleted_count += 1
        return deleted_count

    def _maybe_cleanup(self, cache_name: str):
        config = self._configs.get(cache_name)
        if not config:
            return

        now = time.time()
        if now - self._last_cleanup > config.cleanup_interval:
            self._last_cleanup = now
            deleted = self._cleanup_expired(cache_name)
            if deleted > 0:
                self._stats["cleanups"] += 1
                self.logger.debug(f"Cleaned cache {cache_name}: {deleted} expired entries")


cache_manager = GlobalCacheManager()

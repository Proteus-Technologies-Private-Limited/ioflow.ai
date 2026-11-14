"""
Cache Manager for Flow Designer V2

Implements multi-tier caching for application metadata, service schemas,
and parameter templates to minimize API calls and token usage.
"""

import json
import hashlib
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import redis
from functools import lru_cache
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cache entry"""
    key: str
    value: Any
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0
    size_bytes: int = 0
    tier: str = "memory"  # memory, redis, disk

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.utcnow()

    def touch(self):
        """Mark entry as accessed."""
        self.hit_count += 1


class CacheTier:
    """Base class for cache tiers"""

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def clear(self) -> int:
        raise NotImplementedError


class MemoryCacheTier(CacheTier):
    """In-memory cache tier using LRU"""

    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        entry = self.cache.get(key)
        if entry and not entry.is_expired():
            entry.touch()
            return entry.value
        elif entry:
            del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self._evict_lru()

        expires_at = None
        if ttl:
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()

        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            size_bytes=len(json.dumps(value) if isinstance(value, (dict, list)) else str(value)),
            tier="memory"
        )
        self.cache[key] = entry
        return True

    def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self.cache and not self.cache[key].is_expired()

    def clear(self) -> int:
        count = len(self.cache)
        self.cache.clear()
        return count

    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self.cache:
            return

        lru_key = min(
            self.cache.keys(),
            key=lambda k: (self.cache[k].hit_count, self.cache[k].created_at)
        )
        del self.cache[lru_key]


class RedisCacheTier(CacheTier):
    """Redis cache tier"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 2):
        try:
            self.client = redis.Redis(host=host, port=port, db=db, decode_responses=False)
            self.client.ping()
            self.enabled = True
            logger.info("Redis cache tier connected")
        except Exception as e:
            logger.warning(f"Redis cache tier disabled: {e}")
            self.client = None
            self.enabled = False

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None

        try:
            data = self.client.get(f"fd_cache:{key}")
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.enabled:
            return False

        try:
            data = pickle.dumps(value)
            redis_key = f"fd_cache:{key}"
            if ttl:
                self.client.setex(redis_key, ttl, data)
            else:
                self.client.set(redis_key, data)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.enabled:
            return False

        try:
            return self.client.delete(f"fd_cache:{key}") > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        if not self.enabled:
            return False

        try:
            return self.client.exists(f"fd_cache:{key}") > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    def clear(self) -> int:
        if not self.enabled:
            return 0

        try:
            keys = list(self.client.scan_iter(match="fd_cache:*"))
            if keys:
                return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
        return 0


class DiskCacheTier(CacheTier):
    """SQLite-based disk cache tier"""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".ioflow" / "cache"

        cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "flow_designer_cache.db"

        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at TEXT,
                    expires_at TEXT,
                    hit_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")

    def get(self, key: str) -> Optional[Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()

                if row:
                    value_blob, expires_at = row

                    # Check expiration
                    if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
                        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                        return None

                    # Update hit count
                    conn.execute(
                        "UPDATE cache SET hit_count = hit_count + 1 WHERE key = ?",
                        (key,)
                    )

                    return pickle.loads(value_blob)
        except Exception as e:
            logger.error(f"Disk cache get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            expires_at = None
            if ttl:
                expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()

            value_blob = pickle.dumps(value)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache (key, value, created_at, expires_at, hit_count)
                    VALUES (?, ?, ?, ?, 0)
                """, (key, value_blob, datetime.utcnow().isoformat(), expires_at))
            return True
        except Exception as e:
            logger.error(f"Disk cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Disk cache delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM cache WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                    (key, datetime.utcnow().isoformat())
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Disk cache exists error: {e}")
            return False

    def clear(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache")
                count = cursor.fetchone()[0]
                conn.execute("DELETE FROM cache")
                return count
        except Exception as e:
            logger.error(f"Disk cache clear error: {e}")
            return 0

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (datetime.utcnow().isoformat(),)
                )
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Disk cache cleanup error: {e}")
            return 0


class FlowDesignCache:
    """
    Multi-tier cache manager for Flow Designer V2.
    Implements L1 (memory), L2 (Redis), and L3 (disk) caching.
    """

    # Cache key prefixes for different data types
    PREFIX_APP = "app:"
    PREFIX_SERVICE = "svc:"
    PREFIX_PARAM = "param:"
    PREFIX_TEMPLATE = "tpl:"
    PREFIX_SCHEMA = "schema:"

    # Default TTLs (in seconds)
    TTL_APP = 3600  # 1 hour
    TTL_SERVICE = 7200  # 2 hours
    TTL_PARAM = 86400  # 24 hours
    TTL_TEMPLATE = 604800  # 7 days
    TTL_SCHEMA = 86400  # 24 hours

    def __init__(self, use_redis: bool = True, use_disk: bool = True):
        """
        Initialize cache manager.

        Args:
            use_redis: Enable Redis tier
            use_disk: Enable disk tier
        """
        # Initialize cache tiers
        self.memory_tier = MemoryCacheTier(max_size=500)
        self.redis_tier = RedisCacheTier() if use_redis else None
        self.disk_tier = DiskCacheTier() if use_disk else None

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "evictions": 0
        }

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Get cached application data."""
        key = f"{self.PREFIX_APP}{app_id}"
        return self._get_tiered(key)

    def set_application(self, app_id: str, data: Dict[str, Any]) -> bool:
        """Cache application data."""
        key = f"{self.PREFIX_APP}{app_id}"
        return self._set_tiered(key, data, self.TTL_APP)

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get cached service data."""
        key = f"{self.PREFIX_SERVICE}{service_id}"
        return self._get_tiered(key)

    def set_service(self, service_id: str, data: Dict[str, Any]) -> bool:
        """Cache service data."""
        key = f"{self.PREFIX_SERVICE}{service_id}"
        return self._set_tiered(key, data, self.TTL_SERVICE)

    def get_parameter_schema(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get cached parameter schema."""
        key = f"{self.PREFIX_SCHEMA}{service_id}"
        return self._get_tiered(key)

    def set_parameter_schema(self, service_id: str, schema: Dict[str, Any]) -> bool:
        """Cache parameter schema."""
        key = f"{self.PREFIX_SCHEMA}{service_id}"
        return self._set_tiered(key, schema, self.TTL_SCHEMA)

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get cached template."""
        key = f"{self.PREFIX_TEMPLATE}{template_id}"
        return self._get_tiered(key)

    def set_template(self, template_id: str, template: Dict[str, Any]) -> bool:
        """Cache template."""
        key = f"{self.PREFIX_TEMPLATE}{template_id}"
        return self._set_tiered(key, template, self.TTL_TEMPLATE)

    def get_applications_list(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached applications list."""
        return self._get_tiered("applications_list")

    def set_applications_list(self, apps: List[Dict[str, Any]]) -> bool:
        """Cache applications list."""
        # Create lightweight version
        lightweight_apps = [
            {
                "id": app.get("id"),
                "name": app.get("name"),
                "type": app.get("type"),
                "services_count": len(app.get("services", []))
            }
            for app in apps
        ]
        return self._set_tiered("applications_list", lightweight_apps, self.TTL_APP)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching pattern.

        Args:
            pattern: Key pattern (e.g., "app:*")

        Returns:
            Number of entries invalidated
        """
        count = 0

        # Clear from memory tier
        keys_to_delete = [k for k in self.memory_tier.cache.keys() if self._match_pattern(k, pattern)]
        for key in keys_to_delete:
            if self.memory_tier.delete(key):
                count += 1

        # Clear from Redis tier
        if self.redis_tier and self.redis_tier.enabled:
            try:
                redis_pattern = f"fd_cache:{pattern}"
                keys = list(self.redis_tier.client.scan_iter(match=redis_pattern))
                if keys:
                    count += self.redis_tier.client.delete(*keys)
            except Exception as e:
                logger.error(f"Redis pattern delete error: {e}")

        logger.info(f"Invalidated {count} cache entries matching pattern '{pattern}'")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = 0
        if self.stats["hits"] + self.stats["misses"] > 0:
            hit_rate = self.stats["hits"] / (self.stats["hits"] + self.stats["misses"]) * 100

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "writes": self.stats["writes"],
            "evictions": self.stats["evictions"],
            "hit_rate": f"{hit_rate:.1f}%",
            "memory_entries": len(self.memory_tier.cache),
            "memory_size_bytes": sum(e.size_bytes for e in self.memory_tier.cache.values())
        }

    def cleanup(self) -> int:
        """Clean up expired entries across all tiers."""
        count = 0

        # Memory tier cleanup
        expired = [k for k, v in self.memory_tier.cache.items() if v.is_expired()]
        for key in expired:
            self.memory_tier.delete(key)
            count += 1

        # Disk tier cleanup
        if self.disk_tier:
            count += self.disk_tier.cleanup_expired()

        logger.info(f"Cleaned up {count} expired cache entries")
        return count

    def _get_tiered(self, key: str) -> Optional[Any]:
        """Get value from cache tiers (L1 -> L2 -> L3)."""
        # Try L1 (memory)
        value = self.memory_tier.get(key)
        if value is not None:
            self.stats["hits"] += 1
            logger.debug(f"Cache hit (L1): {key}")
            return value

        # Try L2 (Redis)
        if self.redis_tier:
            value = self.redis_tier.get(key)
            if value is not None:
                # Promote to L1
                self.memory_tier.set(key, value)
                self.stats["hits"] += 1
                logger.debug(f"Cache hit (L2): {key}")
                return value

        # Try L3 (disk)
        if self.disk_tier:
            value = self.disk_tier.get(key)
            if value is not None:
                # Promote to L1 and L2
                self.memory_tier.set(key, value)
                if self.redis_tier:
                    self.redis_tier.set(key, value)
                self.stats["hits"] += 1
                logger.debug(f"Cache hit (L3): {key}")
                return value

        self.stats["misses"] += 1
        logger.debug(f"Cache miss: {key}")
        return None

    def _set_tiered(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache tiers."""
        success = False

        # Write to L1 (memory)
        if self.memory_tier.set(key, value, ttl):
            success = True

        # Write to L2 (Redis)
        if self.redis_tier:
            self.redis_tier.set(key, value, ttl)

        # Write to L3 (disk) for important data
        if self.disk_tier and (key.startswith(self.PREFIX_TEMPLATE) or
                               key.startswith(self.PREFIX_SCHEMA)):
            self.disk_tier.set(key, value, ttl)

        if success:
            self.stats["writes"] += 1
            logger.debug(f"Cached: {key}")

        return success

    @staticmethod
    def _match_pattern(key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple wildcard support)."""
        if "*" not in pattern:
            return key == pattern

        # Simple wildcard matching
        pattern_parts = pattern.split("*")
        if len(pattern_parts) == 2:
            # Pattern like "prefix*" or "*suffix"
            if pattern.startswith("*"):
                return key.endswith(pattern_parts[1])
            elif pattern.endswith("*"):
                return key.startswith(pattern_parts[0])

        return False


# Singleton instance
_cache_manager: Optional[FlowDesignCache] = None

def get_cache_manager() -> FlowDesignCache:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = FlowDesignCache()
    return _cache_manager
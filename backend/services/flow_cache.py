"""
Cache for flow definition reads.

The execution hot path (MQTT/webhook/schedule triggers) loads the full flow
row from Postgres on every execution. This cache serves those reads from
Redis (shared across worker processes) or an in-process memory store, keyed
by (tenant schema, flow_id).

Backend selection (settings.flow_cache_backend):
  auto    — Redis via settings.redis_url when reachable at first use, else
            the in-process memory backend. With Redis the cache — and its
            invalidation — is shared by every worker process.
  redis   — force Redis (a failed connection logs an error and degrades to
            the memory backend so the server stays functional).
  memory  — force the in-process backend (per-process; relies on the TTL to
            converge if multiple workers run).

Invalidation is automatic: SQLAlchemy session hooks collect every Flow row
touched during a flush and drop the matching cache entries after the commit
lands — so ANY code path that saves a flow (designer save, import, status
change, auto-deactivation, agents) clears the cache without needing explicit
calls. The TTL is only a backstop for out-of-band edits (direct SQL).

Reads and invalidations run synchronously (the engine calls them inside
asyncio.to_thread; commit hooks run wherever the commit runs), so the Redis
client is the sync redis.Redis — never the asyncio one.

Memory-backend entries are deep-copied on both set and get: the execution
engine mutates node data during debug runs, and executions must never see
each other's (or the cache's) mutations. Redis entries are JSON snapshots,
which gives the same isolation for free.
"""
import copy
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from core.config import settings

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "ioflow:flowcache:"


class _MemoryBackend:
    """In-process TTL + LRU store."""

    name = 'memory'

    def __init__(self):
        # "schema:flow_id" -> (cached_at_monotonic, entry)
        self._entries: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._entries.get(key)
            if item is None:
                return None
            cached_at, entry = item
            if ttl > 0 and time.monotonic() - cached_at > ttl:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            # Copy inside the lock so a concurrent invalidation can't hand out
            # a half-updated entry
            return copy.deepcopy(entry)

    def set(self, key: str, entry: Dict[str, Any], ttl: float):
        max_entries = int(getattr(settings, 'flow_cache_max_entries', 1000) or 1000)
        with self._lock:
            self._entries[key] = (time.monotonic(), copy.deepcopy(entry))
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def delete_by_flow_id(self, flow_id: str) -> int:
        suffix = f":{flow_id}"
        with self._lock:
            stale = [k for k in self._entries if k.endswith(suffix)]
            for k in stale:
                del self._entries[k]
            return len(stale)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._entries)


class _RedisBackend:
    """Redis-backed store shared by all worker processes.

    Entries are JSON with a native Redis TTL. Any Redis error degrades to a
    cache miss / no-op (the caller falls back to the database), so a Redis
    outage can never break flow execution.
    """

    name = 'redis'

    def __init__(self, client):
        self._client = client
        self._last_error_log = 0.0

    def _log_error(self, operation: str, error: Exception):
        # Rate-limit error logs to one every 30 seconds
        now = time.monotonic()
        if now - self._last_error_log >= 30.0:
            self._last_error_log = now
            logger.warning(f"Flow cache Redis {operation} failed "
                           f"(degrading to DB reads): {error}")

    def get(self, key: str, ttl: float) -> Optional[Dict[str, Any]]:
        try:
            raw = self._client.get(_REDIS_KEY_PREFIX + key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            self._log_error('get', e)
            return None

    def set(self, key: str, entry: Dict[str, Any], ttl: float):
        try:
            raw = json.dumps(entry, default=str)
            if ttl > 0:
                self._client.setex(_REDIS_KEY_PREFIX + key, max(1, int(ttl)), raw)
            else:
                self._client.set(_REDIS_KEY_PREFIX + key, raw)
        except Exception as e:
            self._log_error('set', e)

    def delete(self, key: str) -> bool:
        try:
            return bool(self._client.delete(_REDIS_KEY_PREFIX + key))
        except Exception as e:
            self._log_error('delete', e)
            return False

    def delete_by_flow_id(self, flow_id: str) -> int:
        return self._delete_pattern(f"{_REDIS_KEY_PREFIX}*:{flow_id}")

    def clear(self):
        self._delete_pattern(f"{_REDIS_KEY_PREFIX}*")

    def _delete_pattern(self, pattern: str) -> int:
        try:
            deleted = 0
            for key in self._client.scan_iter(match=pattern, count=200):
                deleted += self._client.delete(key)
            return deleted
        except Exception as e:
            self._log_error('scan-delete', e)
            return 0

    def size(self) -> int:
        try:
            return sum(1 for _ in self._client.scan_iter(
                match=f"{_REDIS_KEY_PREFIX}*", count=200))
        except Exception as e:
            self._log_error('size', e)
            return -1


def _create_backend():
    """Resolve the backend from settings (see module docstring)."""
    mode = str(getattr(settings, 'flow_cache_backend', 'auto') or 'auto').lower()
    if mode == 'memory':
        logger.info("Flow cache using in-process memory backend (configured)")
        return _MemoryBackend()

    redis_url = getattr(settings, 'redis_url', None)
    if redis_url:
        try:
            import redis as redis_sync
            client = redis_sync.Redis.from_url(
                redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            client.ping()
            logger.info(f"Flow cache using Redis backend ({mode}) — "
                        f"shared across worker processes")
            return _RedisBackend(client)
        except Exception as e:
            if mode == 'redis':
                logger.error(f"flow_cache_backend='redis' but Redis is unreachable "
                             f"({e}) — falling back to in-process memory cache")
            else:
                logger.info(f"Flow cache: Redis not reachable ({e}) — "
                            f"using in-process memory backend")
    elif mode == 'redis':
        logger.error("flow_cache_backend='redis' but redis_url is not configured — "
                     "falling back to in-process memory cache")
    return _MemoryBackend()


class FlowDefinitionCache:
    def __init__(self, backend=None):
        self._backend = backend
        self._backend_lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, 'flow_cache_enabled', True))

    def _get_backend(self):
        # Lazy init so importing this module never blocks on a Redis ping
        if self._backend is None:
            with self._backend_lock:
                if self._backend is None:
                    self._backend = _create_backend()
        return self._backend

    @staticmethod
    def _key(schema_name: str, flow_id) -> str:
        return f"{schema_name}:{flow_id}"

    def get(self, schema_name: str, flow_id) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        ttl = float(getattr(settings, 'flow_cache_ttl_seconds', 300) or 0)
        entry = self._get_backend().get(self._key(schema_name, flow_id), ttl)
        if entry is None:
            self.misses += 1
        else:
            self.hits += 1
        return entry

    def set(self, schema_name: str, flow_id, entry: Dict[str, Any]):
        if not self.enabled:
            return
        ttl = float(getattr(settings, 'flow_cache_ttl_seconds', 300) or 0)
        self._get_backend().set(self._key(schema_name, flow_id), entry, ttl)

    def invalidate(self, schema_name: str, flow_id):
        if self._get_backend().delete(self._key(schema_name, flow_id)):
            self.invalidations += 1
            logger.debug(f"Flow cache invalidated for {schema_name}:{flow_id}")

    def invalidate_flow_id(self, flow_id):
        """Schema unknown — drop every entry for this flow_id (safe fallback)."""
        self.invalidations += self._get_backend().delete_by_flow_id(str(flow_id))

    def clear(self):
        self._get_backend().clear()

    def stats(self) -> Dict[str, Any]:
        backend = self._get_backend()
        return {
            'enabled': self.enabled,
            'backend': backend.name,
            'entries': backend.size(),
            'hits': self.hits,
            'misses': self.misses,
            'invalidations': self.invalidations,
        }


flow_cache = FlowDefinitionCache()


# ---------------------------------------------------------------------------
# Automatic invalidation on ANY ORM write to a Flow row.
#
# after_flush records which flows the session touched; after_commit (i.e. only
# once the change is actually visible to other readers) drops their cache
# entries. Invalidating at commit time instead of flush time closes the race
# where a concurrent reader re-caches the old row between flush and commit.
# after_rollback discards the pending set — nothing changed.
# ---------------------------------------------------------------------------

def _collect_dirty_flows(session, flush_context):
    """after_flush: remember which Flow rows this session touched."""
    try:
        from db.models import Flow
        touched = None
        for obj in list(session.new) + list(session.dirty) + list(session.deleted):
            if isinstance(obj, Flow):
                if touched is None:
                    touched = session.info.setdefault('_flow_cache_dirty', set())
                touched.add(str(obj.flow_id))
    except Exception as e:
        logger.warning(f"Flow cache dirty-tracking failed: {e}")
        session.info['_flow_cache_dirty'] = {'*'}


def _invalidate_committed_flows(session):
    """after_commit: drop cache entries for the flows this session changed."""
    dirty = session.info.pop('_flow_cache_dirty', None)
    if not dirty:
        return
    if '*' in dirty:
        flow_cache.clear()
        return
    schema_name = session.info.get('schema_name')
    for flow_id in dirty:
        if schema_name:
            flow_cache.invalidate(schema_name, flow_id)
        else:
            flow_cache.invalidate_flow_id(flow_id)


def _discard_dirty_flows(session):
    """after_rollback: the changes never landed — nothing to invalidate."""
    session.info.pop('_flow_cache_dirty', None)


def _register_invalidation_listeners():
    try:
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        event.listen(Session, 'after_flush', _collect_dirty_flows)
        event.listen(Session, 'after_commit', _invalidate_committed_flows)
        event.listen(Session, 'after_rollback', _discard_dirty_flows)
        logger.info("Flow cache invalidation listeners registered")
    except Exception as e:
        logger.error(f"Failed to register flow cache invalidation listeners: {e}")


_register_invalidation_listeners()

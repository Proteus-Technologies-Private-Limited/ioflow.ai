"""
Distributed Lock Manager for IOFlow
Provides distributed locking with Redis (cluster mode) or SQLite (standalone mode) fallback
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from sqlalchemy import text, and_
from sqlalchemy.exc import IntegrityError

from db.database import get_db_context
from core.config import settings

logger = logging.getLogger(__name__)


class DistributedLockManager:
    """
    Manages distributed locks across multiple workers/servers.
    Uses Redis if available, falls back to SQLite for standalone mode.
    """

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or str(uuid.uuid4())
        self.redis_client: Optional[redis.Redis] = None
        self.use_redis = False
        self.local_locks: Dict[str, Dict[str, Any]] = {}
        self._lock_refresh_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize the lock manager and determine which backend to use."""
        if self._initialized:
            return

        # Try to connect to Redis if URL is configured
        redis_url = getattr(settings, 'redis_url', None) or getattr(settings, 'REDIS_URL', None)

        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                await self.redis_client.ping()
                self.use_redis = True
                logger.info(f"Distributed lock manager using Redis at {redis_url}")
            except (RedisError, RedisConnectionError, Exception) as e:
                logger.warning(f"Redis not available ({str(e)}), falling back to SQLite locks")
                self.redis_client = None
                self.use_redis = False
        else:
            logger.info("No Redis URL configured, using SQLite locks")

        # Ensure distributed_locks table exists for SQLite mode
        if not self.use_redis:
            await self._ensure_locks_table()

        self._initialized = True

    async def _ensure_locks_table(self):
        """Ensure the distributed_locks table exists in the database."""
        # PostgreSQL-only - locks table will be created via migrations if needed
        return  # No-op for PostgreSQL

        with get_db_context() as db:
            try:
                # Create table if it doesn't exist
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS distributed_locks (
                        lock_key TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        acquired_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        metadata TEXT
                    )
                """))

                # Create index for expiration queries
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_distributed_locks_expires
                    ON distributed_locks(expires_at)
                """))

                db.commit()
                logger.debug("Distributed locks table ready")
            except Exception as e:
                logger.error(f"Error creating distributed_locks table: {e}")
                db.rollback()

    async def acquire_lock(self, key: str, ttl: int = 60, retry_count: int = 0) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: The lock key
            ttl: Time to live in seconds
            retry_count: Number of retries if lock is held

        Returns:
            True if lock acquired, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        if self.use_redis:
            return await self._acquire_redis_lock(key, ttl, retry_count)
        else:
            return await self._acquire_sqlite_lock(key, ttl, retry_count)

    async def _acquire_redis_lock(self, key: str, ttl: int, retry_count: int) -> bool:
        """Acquire lock using Redis."""
        lock_key = f"ioflow:lock:{key}"
        lock_value = f"{self.worker_id}:{uuid.uuid4()}"

        for attempt in range(retry_count + 1):
            try:
                # SET NX EX - atomic operation
                acquired = await self.redis_client.set(
                    lock_key,
                    lock_value,
                    nx=True,  # Only set if not exists
                    ex=ttl    # Expire after ttl seconds
                )

                if acquired:
                    # Store lock info for later reference
                    self.local_locks[key] = {
                        'value': lock_value,
                        'ttl': ttl,
                        'acquired_at': time.time()
                    }

                    # Start refresh task for long-running locks
                    if ttl > 10:
                        self._start_refresh_task(key, ttl)

                    logger.debug(f"Acquired Redis lock: {key} (owner: {self.worker_id})")
                    return True

            except Exception as e:
                logger.error(f"Error acquiring Redis lock {key}: {e}")

            if attempt < retry_count:
                await asyncio.sleep(1)

        return False

    async def _acquire_sqlite_lock(self, key: str, ttl: int, retry_count: int) -> bool:
        """Acquire lock using SQLite."""
        lock_key = f"ioflow:lock:{key}"
        owner_id = f"{self.worker_id}:{uuid.uuid4()}"

        for attempt in range(retry_count + 1):
            with get_db_context() as db:
                try:
                    # Clean up expired locks
                    db.execute(text("""
                        DELETE FROM distributed_locks
                        WHERE expires_at < :now
                    """), {'now': datetime.utcnow()})

                    # Try to acquire lock
                    expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                    db.execute(text("""
                        INSERT INTO distributed_locks (lock_key, owner_id, acquired_at, expires_at)
                        VALUES (:key, :owner, :now, :expires)
                    """), {
                        'key': lock_key,
                        'owner': owner_id,
                        'now': datetime.utcnow(),
                        'expires': expires_at
                    })
                    db.commit()

                    # Store lock info
                    self.local_locks[key] = {
                        'value': owner_id,
                        'ttl': ttl,
                        'acquired_at': time.time()
                    }

                    # Start refresh task
                    if ttl > 10:
                        self._start_refresh_task(key, ttl)

                    logger.debug(f"Acquired SQLite lock: {key} (owner: {self.worker_id})")
                    return True

                except IntegrityError:
                    # Lock already exists
                    db.rollback()

                    # Check if lock is expired
                    result = db.execute(text("""
                        SELECT expires_at FROM distributed_locks
                        WHERE lock_key = :key
                    """), {'key': lock_key}).first()

                    if result:
                        # Parse the expiration time
                        expires_at = result[0]
                        if isinstance(expires_at, str):
                            expires_at = datetime.fromisoformat(expires_at)

                        if expires_at < datetime.utcnow():
                            # Lock is expired, try to clean and retry
                            db.execute(text("""
                                DELETE FROM distributed_locks
                                WHERE lock_key = :key AND expires_at < :now
                            """), {'key': lock_key, 'now': datetime.utcnow()})
                            db.commit()
                            continue

                except Exception as e:
                    logger.error(f"Error acquiring SQLite lock {key}: {e}")
                    db.rollback()

            if attempt < retry_count:
                await asyncio.sleep(1)

        return False

    async def extend_lock(self, key: str, ttl: int = 60) -> bool:
        """
        Extend the TTL of an existing lock.

        Args:
            key: The lock key
            ttl: New TTL in seconds

        Returns:
            True if extended, False otherwise
        """
        if key not in self.local_locks:
            return False

        if self.use_redis:
            return await self._extend_redis_lock(key, ttl)
        else:
            return await self._extend_sqlite_lock(key, ttl)

    async def _extend_redis_lock(self, key: str, ttl: int) -> bool:
        """Extend Redis lock."""
        lock_key = f"ioflow:lock:{key}"
        lock_info = self.local_locks.get(key)

        if not lock_info:
            return False

        try:
            # Check if we still own the lock
            current_value = await self.redis_client.get(lock_key)
            if current_value == lock_info['value']:
                # Extend the TTL
                await self.redis_client.expire(lock_key, ttl)
                logger.debug(f"Extended Redis lock: {key} for {ttl}s")
                return True
        except Exception as e:
            logger.error(f"Error extending Redis lock {key}: {e}")

        return False

    async def _extend_sqlite_lock(self, key: str, ttl: int) -> bool:
        """Extend SQLite lock."""
        lock_key = f"ioflow:lock:{key}"
        lock_info = self.local_locks.get(key)

        if not lock_info:
            return False

        with get_db_context() as db:
            try:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                result = db.execute(text("""
                    UPDATE distributed_locks
                    SET expires_at = :expires
                    WHERE lock_key = :key AND owner_id = :owner
                """), {
                    'key': lock_key,
                    'owner': lock_info['value'],
                    'expires': expires_at
                })
                db.commit()

                if result.rowcount > 0:
                    logger.debug(f"Extended SQLite lock: {key} for {ttl}s")
                    return True

            except Exception as e:
                logger.error(f"Error extending SQLite lock {key}: {e}")
                db.rollback()

        return False

    async def release_lock(self, key: str) -> bool:
        """
        Release a distributed lock.

        Args:
            key: The lock key

        Returns:
            True if released, False otherwise
        """
        # Cancel refresh task if exists
        if key in self._lock_refresh_tasks:
            self._lock_refresh_tasks[key].cancel()
            del self._lock_refresh_tasks[key]

        if key not in self.local_locks:
            return False

        if self.use_redis:
            result = await self._release_redis_lock(key)
        else:
            result = await self._release_sqlite_lock(key)

        if result:
            del self.local_locks[key]

        return result

    async def _release_redis_lock(self, key: str) -> bool:
        """Release Redis lock."""
        lock_key = f"ioflow:lock:{key}"
        lock_info = self.local_locks.get(key)

        if not lock_info:
            return False

        try:
            # Use Lua script for atomic check-and-delete
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
            """

            result = await self.redis_client.eval(
                lua_script,
                1,
                lock_key,
                lock_info['value']
            )

            if result:
                logger.debug(f"Released Redis lock: {key}")
                return True

        except Exception as e:
            logger.error(f"Error releasing Redis lock {key}: {e}")

        return False

    async def _release_sqlite_lock(self, key: str) -> bool:
        """Release SQLite lock."""
        lock_key = f"ioflow:lock:{key}"
        lock_info = self.local_locks.get(key)

        if not lock_info:
            return False

        with get_db_context() as db:
            try:
                result = db.execute(text("""
                    DELETE FROM distributed_locks
                    WHERE lock_key = :key AND owner_id = :owner
                """), {
                    'key': lock_key,
                    'owner': lock_info['value']
                })
                db.commit()

                if result.rowcount > 0:
                    logger.debug(f"Released SQLite lock: {key}")
                    return True

            except Exception as e:
                logger.error(f"Error releasing SQLite lock {key}: {e}")
                db.rollback()

        return False

    def _start_refresh_task(self, key: str, ttl: int):
        """Start a background task to refresh lock before expiration."""
        if key in self._lock_refresh_tasks:
            self._lock_refresh_tasks[key].cancel()

        async def refresh_loop():
            refresh_interval = max(ttl // 2, 5)  # Refresh at half TTL or minimum 5s
            try:
                while key in self.local_locks:
                    await asyncio.sleep(refresh_interval)
                    if not await self.extend_lock(key, ttl):
                        logger.warning(f"Failed to refresh lock: {key}")
                        break
            except asyncio.CancelledError:
                pass

        self._lock_refresh_tasks[key] = asyncio.create_task(refresh_loop())

    @asynccontextmanager
    async def lock(self, key: str, ttl: int = 60, retry_count: int = 0):
        """
        Context manager for acquiring and releasing locks.

        Usage:
            async with lock_manager.lock('my_key', ttl=30):
                # Do work while holding lock
                pass
        """
        acquired = await self.acquire_lock(key, ttl, retry_count)
        if not acquired:
            raise RuntimeError(f"Failed to acquire lock: {key}")

        try:
            yield
        finally:
            await self.release_lock(key)

    async def cleanup(self):
        """Clean up resources."""
        # Cancel all refresh tasks
        for task in self._lock_refresh_tasks.values():
            task.cancel()
        self._lock_refresh_tasks.clear()

        # Release all held locks
        keys = list(self.local_locks.keys())
        for key in keys:
            await self.release_lock(key)

        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()

    @staticmethod
    def get_execution_lock_key(flow_id: str, trigger_data: Dict[str, Any]) -> str:
        """
        Generate a unique lock key for flow execution based on content.
        This prevents duplicate processing of the same trigger data.
        """
        # Create a deterministic hash of the trigger data
        data_str = json.dumps(trigger_data, sort_keys=True)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()[:8]

        return f"exec:{flow_id}:{data_hash}"
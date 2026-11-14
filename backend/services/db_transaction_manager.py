"""
Per-execution database transaction manager.

Supports *flow-scoped* database transactions. When a database application is
configured with ``autocommit = false``, every DML statement run by a single
flow execution shares ONE pinned connection and is committed only when an
explicit ``commit`` step runs. If the flow ends (or pauses) with an open
transaction, it is rolled back automatically.

The registry is keyed by ``(execution_id, pool_key)`` so that several database
applications used within the same flow each get their own independent
transaction, and so that concurrent flow executions never share a connection.

Only *synchronous* connection pools (``DatabaseConnectionPool`` from
``services.database_executor``) are pinned here. The truly-async executor
delegates to the sync executor when autocommit is disabled, so transactional
work always flows through the sync path.

Concurrency note: a pinned connection is a single database session and is NOT
safe for concurrent use. Transaction mode therefore assumes the DML nodes in a
flow run sequentially. Parallel branches that both write inside the same
transaction are unsupported.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class _PinnedTxn:
    """A connection borrowed from a pool and held open for a flow execution."""

    __slots__ = ('pool', 'conn')

    def __init__(self, pool, conn):
        self.pool = pool
        self.conn = conn


# execution_id -> { pool_key: _PinnedTxn }
_registry: dict = {}
# Guards the structure of _registry (not the DB IO itself).
_lock = asyncio.Lock()


async def get_sync_connection(execution_id, pool_key, pool):
    """Return the connection pinned to ``execution_id`` for ``pool_key``.

    On first use a connection is borrowed from ``pool`` and pinned with
    autocommit disabled so DML accumulates in a transaction. Subsequent calls
    for the same execution/pool return the same connection.
    """
    if execution_id is None:
        # No execution context to scope the transaction to — fall back to a
        # plain borrowed connection (still transactional for this single call).
        conn = await pool.get_connection()
        _disable_autocommit(conn)
        return conn

    async with _lock:
        pinned = _registry.get(execution_id, {}).get(pool_key)
        if pinned is not None:
            return pinned.conn

    # Acquire outside the lock — get_connection() may perform IO (liveness probe).
    conn = await pool.get_connection()
    _disable_autocommit(conn)

    async with _lock:
        txns = _registry.setdefault(execution_id, {})
        existing = txns.get(pool_key)
        if existing is not None:
            # Another coroutine pinned one concurrently; keep theirs, hand ours
            # back so we don't leak a pool slot.
            await pool.return_connection(conn)
            return existing.conn
        txns[pool_key] = _PinnedTxn(pool, conn)
        logger.info(
            f"Pinned transactional DB connection for execution {execution_id} "
            f"(pool_key={pool_key})"
        )
        return conn


def has_pinned(execution_id, pool_key) -> bool:
    """Whether a transaction is currently pinned for this execution/pool."""
    return pool_key in _registry.get(execution_id, {})


async def commit(execution_id, pool_key) -> bool:
    """Commit the pinned transaction and return its connection to the pool.

    Returns True if a transaction was committed, False if none was open.
    """
    return await _finish(execution_id, pool_key, commit=True)


async def rollback(execution_id, pool_key) -> bool:
    """Roll back the pinned transaction and return its connection to the pool.

    Returns True if a transaction was rolled back, False if none was open.
    """
    return await _finish(execution_id, pool_key, commit=False)


async def release_all(execution_id) -> None:
    """Roll back and return every connection pinned to this execution.

    Called when a flow finishes or pauses. Any transaction left open (i.e. not
    explicitly committed) is discarded so no work is silently half-applied and
    no pool slot is leaked.
    """
    async with _lock:
        txns = _registry.pop(execution_id, None)
    if not txns:
        return
    for pool_key, pinned in txns.items():
        await _rollback_and_return(pinned, execution_id, pool_key)


async def _finish(execution_id, pool_key, commit: bool) -> bool:
    async with _lock:
        txns = _registry.get(execution_id)
        pinned = txns.pop(pool_key, None) if txns else None
        if txns is not None and not txns:
            _registry.pop(execution_id, None)
    if pinned is None:
        logger.info(
            f"No open transaction to {'commit' if commit else 'roll back'} for "
            f"execution {execution_id} (pool_key={pool_key})"
        )
        return False

    loop = asyncio.get_event_loop()
    try:
        if commit:
            await loop.run_in_executor(None, pinned.conn.commit)
            logger.info(
                f"Committed transaction for execution {execution_id} "
                f"(pool_key={pool_key})"
            )
        else:
            await loop.run_in_executor(None, pinned.conn.rollback)
            logger.info(
                f"Rolled back transaction for execution {execution_id} "
                f"(pool_key={pool_key})"
            )
    except Exception as e:
        logger.error(
            f"Failed to {'commit' if commit else 'roll back'} transaction for "
            f"execution {execution_id}: {e}"
        )
        # Connection state is uncertain — discard it rather than returning a
        # poisoned session to the pool.
        try:
            pinned.pool.discard_connection(pinned.conn)
        except Exception:
            pass
        return True
    await _return_clean(pinned)
    return True


async def _rollback_and_return(pinned, execution_id, pool_key) -> None:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, pinned.conn.rollback)
        logger.info(
            f"Auto-rolled-back uncommitted transaction for execution "
            f"{execution_id} (pool_key={pool_key})"
        )
    except Exception as e:
        logger.warning(
            f"Error rolling back pinned transaction for execution "
            f"{execution_id}: {e}"
        )
        try:
            pinned.pool.discard_connection(pinned.conn)
        except Exception:
            pass
        return
    await _return_clean(pinned)


async def _return_clean(pinned) -> None:
    """Restore autocommit and return the connection to its pool."""
    try:
        if hasattr(pinned.conn, 'autocommit'):
            pinned.conn.autocommit = True
    except Exception:
        # Couldn't restore autocommit — discard so the next borrower gets a
        # clean session instead of one stuck in a transaction.
        try:
            pinned.pool.discard_connection(pinned.conn)
        except Exception:
            pass
        return
    try:
        await pinned.pool.return_connection(pinned.conn)
    except Exception as e:
        logger.warning(f"Error returning pinned connection to pool: {e}")


def _disable_autocommit(conn) -> None:
    """Put a freshly borrowed connection into manual-transaction mode."""
    if not hasattr(conn, 'autocommit'):
        return
    try:
        if conn.autocommit:
            conn.autocommit = False
    except Exception:
        # A stray open transaction blocks toggling autocommit — clear it first.
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.autocommit = False
        except Exception:
            pass

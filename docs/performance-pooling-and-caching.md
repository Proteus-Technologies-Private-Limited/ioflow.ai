# Performance: Application Connection Pooling & Flow Definition Caching

Implemented 2026-07-05. Two independent mechanisms:

## 1. Tenant/instance/credential-aware database connection pools

Database services (`database_query` executor family — sync `database_executor.py`
and async `async_database_executor.py`) reuse connections instead of connecting
per execution. Pools are keyed:

```
{subscription_id}_{database_type}_{fingerprint}          (sync)
{subscription_id}_{database_type}_async_{fingerprint}    (async)
```

- **Tenant-specific and instance-specific** — `subscription_id` is one row per
  (tenant, application connection). A tenant with three connections of the same
  database application gets three isolated pools; two tenants never share a
  pool even with identical credentials.
- **Credential/URL-aware (dynamic)** — the `fingerprint` is a SHA-1 of the
  connection URL + auth credentials + pool config (`connection_fingerprint()`
  in `backend/services/database_executor.py`). When a user updates the
  connection's credentials or base URL, the next execution computes a new
  fingerprint, creates a fresh pool, and **closes the stale pool first**
  (`evict_stale_pools()`) so server-side connection slots are not leaked and
  old credentials are never reused. No restart or manual invalidation needed.
- Pool size / timeouts come from the application's `auth_config`
  (`connection_pool_size`, default 10; `connection_timeout`).
- Dead connections are detected and replaced by the existing
  connection-lost handling (`_is_connection_lost_error`).

Notes:
- Pools for deleted subscriptions linger idle until process restart (bounded:
  at most one pool per subscription per database type); the database server's
  idle timeout reclaims the connections.
- FTP/SFTP file-protocol services intentionally connect per call (stateful
  session protocols; low reuse value).
- HTTP/REST services already share a process-wide `httpx.AsyncClient` pool.

## 2. Flow definition cache (`backend/services/flow_cache.py`)

Every trigger (MQTT, webhook, schedule, manual, API) previously loaded the full
flow row from Postgres per execution. `ExecutionEngine._load_flow_info()` now
serves flow reads from a cache keyed `(tenant schema, flow_id)` holding
`flow_definition`, `flow_name`, `trigger_config`, `is_synchronous`,
`sync_timeout`.

### Backends

`FLOW_CACHE_BACKEND` selects where entries live:

| Mode | Behavior |
|---|---|
| `auto` (default) | **Redis** (`REDIS_URL`) when reachable at first use — the cache and its invalidation are shared by every worker process. Falls back to the in-process memory backend otherwise. |
| `redis` | Force Redis; if unreachable an error is logged and the memory backend is used so the server stays functional. |
| `memory` | Force the in-process store (per-process; multiple workers converge within the TTL). |

Redis entries are JSON snapshots under `ioflow:flowcache:{schema}:{flow_id}`
with a native Redis TTL. Any Redis error at runtime degrades to a cache miss
(the execution falls back to the database read) — a Redis outage can never
break flow execution. The client is the sync `redis.Redis`: cache reads run
inside `asyncio.to_thread` and invalidations run wherever the DB commit runs,
so nothing blocks the event loop.

### Automatic invalidation on flow changes

Invalidation needs **no explicit calls in API endpoints**. SQLAlchemy session
hooks do it globally:

1. `after_flush` records every `Flow` row a session inserts/updates/deletes;
2. `after_commit` drops the matching cache entries — only once the change is
   actually visible to other readers (avoids re-caching a not-yet-committed
   old row);
3. `after_rollback` discards the pending set (nothing changed).

The tenant schema is stamped on each session (`db.info['schema_name']` in
`get_tenant_db`), so invalidation is schema-precise; if a session has no
schema stamp, the flow_id is invalidated across all schemas (safe fallback).

This covers every save path: flow designer saves, imports, status changes,
auto-deactivation sweeps, collaboration and agent edits — anything that writes
a `Flow` row through the ORM. Direct SQL edits bypass the hooks; the TTL
backstop (below) covers those.

### Configuration (env, `backend/.env`)

| Setting | Default | Meaning |
|---|---|---|
| `FLOW_CACHE_ENABLED` | `true` | Turn the cache off entirely if needed |
| `FLOW_CACHE_BACKEND` | `auto` | `auto` \| `redis` \| `memory` (see above) |
| `FLOW_CACHE_TTL_SECONDS` | `300` | Backstop expiry for out-of-band edits |
| `FLOW_CACHE_MAX_ENTRIES` | `1000` | LRU cap (memory backend only; Redis uses the TTL) |

### Safety properties

- Executions can mutate their copy of a definition (debug mode does) without
  poisoning the cache: memory entries are deep-copied on set and get, Redis
  entries are JSON snapshots deserialized fresh per read.
- With the Redis backend, invalidation is cluster-wide — a flow saved through
  any worker is dropped from the cache every other worker reads. The memory
  backend keeps the single-worker assumption (run.py caps workers at 1) and
  converges within the TTL if multiple processes run.
- `flow_cache.stats()` returns backend, hits/misses/invalidations/entry count.

## Verification

```
venv/bin/python test-script/test_pooling_and_cache.py
```

27 checks: fingerprint stability/rotation, stale-pool eviction isolation,
cache hit/miss/TTL/LRU/deep-copy, commit-hook invalidation (flush → commit →
drop; rollback keeps), `ExecutionEngine` serving the second read without a DB
query, and — when Redis is reachable — live Redis tests: auto-mode selection,
cross-worker visibility and invalidation, SCAN-based flow_id-wide
invalidation, native TTLs, outage degradation, and memory fallback. A live
check against the local Postgres + Redis (real ORM commit on a flow row →
Redis cache entry dropped) was run as part of the implementation.

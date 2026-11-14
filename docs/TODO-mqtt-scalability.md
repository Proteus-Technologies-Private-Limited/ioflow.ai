# TODO: MQTT Trigger Scalability

**Status:** Tiers 1–3 + observability implemented 2026-07-05 (see checkboxes). Tier 4 remains the long-term roadmap item.
**Implementation notes (2026-07-05):**
- Dispatcher (bounded queue + worker pool + batching/rate-limit/dedup) lives in `backend/services/mqtt_listener_service.py` (`MqttDispatcher`, `MqttFlowRoute`, `resolve_mqtt_perf_config`).
- Flow-level logging implemented centrally in `ExecutionEngine._log_execution` via per-execution policies (`_init_log_policy` / `_apply_log_policy`); UI in Flow Settings → Execution Logging. `errors_only` buffers logs in memory and flushes on the first error-level entry; the `FlowExecution` row itself is still created up front (deferring it would break execution-status updates, WebSocket notifications and result storage — accepted deviation).
- DB offloading (Tier 3) covers the hot path: flow load + execution insert + start log, per-node current_step/start/completion logs, and completion bookkeeping now run in `asyncio.to_thread`. The balance check and less-hot paths still run inline — follow-up candidates.
- MQTT seed app bumped 1.0.0 → 1.1.0 with Performance & Delivery defaults in `event_configuration`.
**Context:** The MQTT trigger (commit `9f444df`) executes a full flow per incoming message with no queue, no concurrency cap, and blocking DB work on the async event loop. With thousands of devices publishing events, flow executions will pile up and the blocking DB calls will slow the entire backend (API + WebSockets share the same event loop). Plan agreed: implement Tier 1 + 2 now; Tier 3 alongside; Tier 4 is the long-term roadmap item. All tunables follow the configurability model below so users can fine-tune execution per flow.

## Identified bottlenecks

1. **Unbounded dispatch** — `backend/services/mqtt_listener_service.py` `on_message` schedules `_execute_triggered_flow` directly onto the main event loop via `run_coroutine_threadsafe`. No queue, no cap: N messages/sec = N concurrent executions.
2. **Blocking DB on the event loop** — `ExecutionEngine.execute_flow` (`backend/services/execution_engine.py:57-82`) uses synchronous SQLAlchemy (`db.query`, `db.commit`) inside async coroutines. Every DB round trip freezes the event loop that serves all API traffic. Biggest single problem.
3. **High per-message overhead** — each message constructs a new `ExecutionEngine` (fresh `httpx.AsyncClient` pool each time), inserts a `FlowExecution` row, writes per-step logs, sends WebSocket notifications, and does 2 Redis round trips for the lock (~5-10 Postgres writes per event).
4. **Dedup lock is a no-op for MQTT** — `get_execution_lock_key` (`backend/services/distributed_lock.py:455`) hashes `trigger_data`, but `_build_variables` stamps `datetime.now().isoformat()` (microseconds) into it, so every message gets a unique key. Pure Redis cost, no dedup. Multi-worker deployments would also each stamp their own timestamp, so cross-worker dedup fails too.
5. **Single process** — listener + execution live in the API server process; adding backend instances would duplicate MQTT connections and executions rather than share load.

---

## Configurability model

Users must be able to fine-tune execution without code changes. Every knob introduced by the tiers below slots into one of two scopes:

- **Operator scope (env)** — protects the *server*. Defined in `backend/core/config.py` (pydantic `Settings`, reads `backend/.env`). User-level settings can never exceed these ceilings.
- **User scope (flow / connection / app)** — shapes *behavior*. Resolved through the precedence chain the listener already uses for `topic_filter`/`qos`/`payload_format` (`mqtt_listener_service.py:553-567`):

```
flow trigger_config  >  subscription_config (per connection)  >  event_configuration (seed app default)  >  env setting  >  hardcoded default
```

### Trigger node UI — where fine-tuning appears (clarified)

The flow-designer **trigger node** must expose the MQTT fine-tuning section (batching, rate limit, dedup — "Performance & Delivery") for **both** attachment models:

1. **Trigger type `mqtt`** — flat broker config on the flow (`MqttTriggerConfig.js`). Section renders below the connection fields, collapsed by default.
2. **Trigger type `event`** — when the selected application event has `event_type == 'mqtt'`, the *same* fine-tuning section renders in the event trigger config. The frontend must look up the selected event's `event_type` to decide; the fields are written to the same `trigger_config` keys (`mqtt_batch_size`, …) that `watch_event_flow` already resolves through the precedence chain. Non-MQTT application events (webhook/polling) never show the section.

Both paths write identical keys, so the backend resolution logic is shared — no per-attachment-model branching in the listener.

### Flow-level execution logging (clarified — applies to ALL flows, not just MQTT)

Execution log level is a **flow-level setting with a default, configurable in every flow design** — MQTT and non-MQTT triggers alike. It is not an MQTT trigger option; it lives with the flow (proposed: `flow_definition.settings.execution_log_level`, so no schema migration is needed; the flow designer already owns `flow_definition`).

| Level | What is stored per node/step |
|---|---|
| `full` (default) | Current behavior — detailed per-step logs (inputs, outputs, timing) |
| `node_summary` | **One line per node** — node name, status, duration, and a single-line result/error summary. No detailed payloads. |
| `errors_only` | Nothing while the flow succeeds; on failure, write the `FlowExecution` row + logs for the failing path (lazy write — buffer in memory until an error occurs) |

- `flow_log_sample_rate` (0.0–1.0, default `1.0`) — flow-level companion setting (renamed from the earlier `mqtt_log_sample_rate`; it is not MQTT-specific). For high-frequency flows: the sampled fraction of executions logs at the configured level; unsampled executions fall back to `errors_only`. Applies to all trigger types.
- Env-scope floor: `flow_log_min_level` (operator can force at least `errors_only` everywhere; default unset).
- ExecutionEngine reads the level once at execution start; the log writer honors it on every step — implement in the engine's logging helper, **not** per-trigger code (no application-specific hardcoding in execution classes, per project convention).
- Frontend: a "Logging" selector in flow settings (all flows), showing the default when unset.

---

## Tier 1 — Bounded queue + worker pool (do first)

Operator scope (new `Settings` fields, `backend/.env` overridable):

- [x] `mqtt_dispatch_queue_size: int = 1000` — `asyncio.Queue(maxsize=N)` between `on_message` and flow execution in `mqtt_listener_service.py`
- [x] `mqtt_worker_pool_size: int = 20` — fixed worker pool draining the queue (global cap on concurrent MQTT-triggered executions)
- [x] `mqtt_overflow_policy: str = "drop_oldest"` — `drop_oldest` (stay realtime, lose stale readings) | `drop_newest` | `block` (stall paho's network thread so the broker's QoS 1 in-flight window absorbs the burst — no data loss, backpressure to broker)

User scope:

- [x] `mqtt_max_concurrent` on trigger_config (default `0` = bounded only by the global pool) — per-flow concurrency cap so one chatty telemetry flow can't starve a critical alarm flow. Effective value = `min(mqtt_max_concurrent, mqtt_worker_pool_size)`; clamped at attach time so user settings never exceed the operator ceiling.

Observability:

- [x] Expose per-listener queue depth, dropped-message count, and executions/sec in `get_active_listeners()`

## Tier 2 — Batching & rate limiting on the trigger config (biggest conceptual win)

User scope — add to `TriggerConfig` (`backend/api/flows.py`), to `subscription_config`, and to `event_configuration` in the MQTT seed app; resolved via the standard precedence chain. Surfaced in the trigger node for **both** `mqtt` triggers and MQTT application-event triggers (see Configurability model):

- [x] `mqtt_batch_size` (default `1` = no batching, fully backward compatible) — accumulate messages per flow; fire one execution with `variables.messages = [...]` + `variables.message_count` when size or window is hit (1,000 msg/s → 1 execution/s). Keep `topic`/`payload` pointing at the first message so existing `{{trigger.payload}}` references don't break; document that batched flows iterate `messages`.
- [x] `mqtt_batch_window_seconds` (default `0` = size-only) — flush a partial batch after this window
- [x] `mqtt_max_rate` (default `0` = unlimited) — max executions/sec for this flow
- [x] `mqtt_rate_overflow` (default `fold`) — `fold` excess into the next batch | `drop`
- [x] Validation in the `TriggerConfig` validator: `1 ≤ batch_size ≤ 10000`, `0 ≤ window ≤ 3600`, `rate ≥ 0`
- [x] Frontend: collapsible "Performance & Delivery" section in `MqttTriggerConfig.js` AND in the event-trigger config when the selected application event is MQTT
- [x] Update `docs/mqtt-trigger.md` + bump the MQTT seed app version (`backend/seed-applications/mqtt.json`, 1.0.0 → 1.1.0) per project convention

## Tier 3 — Stop blocking the event loop / cut per-message overhead

- [x] Move sync SQLAlchemy calls in the execution path to a thread pool (`asyncio.to_thread` / `run_in_executor`) — or migrate hot paths to async DB. Internal, no knob.
- [x] Reuse a shared `httpx.AsyncClient` instead of one per `ExecutionEngine` instance. Internal, no knob.
- [x] Flow-level execution logging (`execution_log_level`: `full` | `node_summary` | `errors_only` + `flow_log_sample_rate`) — see Configurability model above. Applies to ALL flows; defaults per flow; configurable in every flow design.
- [x] Fix the dedup lock via user-scope config (the current lock is a silent no-op — timestamp in the hash):
  - `mqtt_dedup`: `off` (default for MQTT — matches today's effective behavior and saves 2 Redis round trips/message) | `payload` (hash topic + raw payload, timestamp excluded) | `key` (user template, e.g. `{{payload.device_id}}:{{payload.seq}}` — only the user knows what makes their messages unique)
  - `mqtt_dedup_window_seconds` (default `300`) — becomes the Redis lock TTL

## Tier 4 — Decouple execution from the API process (roadmap / real horizontal scale)

Operator scope only — deployment topology is never a per-flow decision:

- [ ] `mqtt_execution_mode`: `inline` (today) | `queued` — listener only enqueues trigger events into Redis Streams (or Celery/arq); separate worker processes consume and execute flows; scale by adding workers
- [ ] `shared_subscription: true` per application connection (`subscription_config` — per-broker capability, the user knows if their broker speaks MQTT 5): rewrite subscriptions to `$share/ioflow/<topic>` so the broker load-balances across listener instances
- [ ] Revisit `clean_session=True`: QoS 1 offline queuing is currently discarded on reconnect
- [ ] Telemetry history: with TimescaleDB now installed locally, high-volume MQTT payloads can be persisted to a hypertable instead of per-execution rows (future design)

## Observability (makes it *fine-tunable*, not just configurable)

- [x] `get_active_listeners()` reports per listener: queue depth, dropped count, executions/sec, current batch fill, and the **effective resolved config** (so users can see which level of the precedence chain won)
- [x] Config changes on flow update already re-attach the listener (`watch_flow`/`watch_event_flow`), so user-scope settings take effect live; env-scope settings need a backend restart. State this in `docs/mqtt-trigger.md`.

## Local infrastructure (done 2026-07-04)

- Docker Compose (`docker-compose.yml`, project root): TimescaleDB 2.28.2 on PostgreSQL 17.10 (`localhost:5433` — the machine's native EDB Postgres owns 5432) + Redis 7 (`localhost:6379`)
- Verify anytime with `venv/bin/python test-script/verify_infra.py`
- `backend/.env`: `DATABASE_URL` → local Postgres, `REDIS_URL` added; SQLite URL kept commented for switch-back. SQLite code paths untouched.

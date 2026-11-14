# MQTT Trigger

Fires a flow every time a message is published to an MQTT topic the flow subscribes
to. MQTT is a **push protocol over a persistent connection** — IOFlow keeps one
long-lived TCP connection to the broker and the broker pushes each matching message
the instant it is published. There is no polling and no continuous reading; an idle
connection costs only a keepalive ping every 60s.

There are **two ways** to use it:

1. **MQTT application + "New Message" event (recommended)** — install the `mqtt`
   seed application, create a connection (broker URL + username/password, with a
   working *Test Connection* button), then in the flow designer pick
   *Application Event → MQTT → New Message* and set the topic filter. All flows
   using the same MQTT application share **one** broker connection; messages are
   routed to each flow by topic filter. Each installed MQTT application (or its
   connection) can point at a **different broker**.
2. **Standalone `mqtt` trigger type** — broker details stored flat on the flow's
   trigger config; one dedicated connection per flow. Useful for one-off flows
   without installing the application.

## Architecture

```
                       ┌── application model (shared) ─────────────────────────┐
MQTT broker A ──> paho client (one per application connection, per tenant)
                  └─ on_message ──> match topic vs each flow's filter
                        └─ per matching flow: asyncio.run_coroutine_threadsafe
                              └─ ExecutionEngine.execute_flow(trigger_type='mqtt')

                       ┌── flow-level model (dedicated) ───────────────────────┐
MQTT broker B ──> paho client (one per active flow with trigger type 'mqtt')
                  └─ on_message ──> asyncio.run_coroutine_threadsafe
                        └─ ExecutionEngine.execute_flow(trigger_type='mqtt')
```

**Duplicate-delivery protection**: brokers deliver one copy of a message per
matching subscription on the same connection. Because routing to flows happens
client-side, the shared connection subscribes only to a *minimal covering set*
of the flows' topic filters (e.g. `home/#` subsumes `home/energy/#`, so only
`home/#` is subscribed). Filters that partially overlap without nesting (e.g.
`a/+/c` and `a/b/+`) can still double-deliver — avoid that combination on one
application connection.

## MQTT seed application (`backend/seed-applications/mqtt.json`)

- **App**: `app_type: mqtt`, `auth_type: basic`. Broker URL format
  `mqtt://host:1883` or `mqtts://host:8883` — set per connection via
  `subscription_config.base_url` (falls back to the application `base_url`).
- **Event**: `new_message` (`event_type: mqtt`) exposing
  `topic / payload / payload_raw / qos / retain / timestamp` via its
  `output_schema`. Defaults (`topic_filter`, `qos`, `payload_format`) live in
  `event_configuration`; per-connection overrides in `subscription_config`;
  per-flow overrides in the flow trigger config (`mqtt_topic_filter`,
  `mqtt_qos`, `mqtt_payload_format` — set in the designer's MQTT Subscription
  panel when the event is selected).
- **Test Connection**: `POST /api/v1/applications/test-connection` with an
  `mqtt://` / `mqtts://` `base_url` performs a real CONNECT and reports
  authentication failures ("Not authorized") and unreachable brokers distinctly
  (`api/applications.py`, MQTT branch).
- **Lifecycle**: activating a flow bound to an MQTT event attaches it to the
  application's shared connection (creating it on first attach); deactivating
  detaches it and tears the connection down when the last flow detaches.
  Activation fails with a clear error if the application has no active
  connection ("Connect to the MQTT application first").

- **Service**: `backend/services/mqtt_listener_service.py`
  (`MqttListenerService` singleton, keyed `"{tenant_id}:{flow_id}"`).
- **Lifecycle**: registered as `mqtt_listener` in `BackgroundServiceManager`
  (leader election ensures one worker runs it). Listeners attach/detach
  immediately from the flow update / activate / deactivate / draft API paths in
  `backend/api/flows.py`. Flow delete requires deactivation first, which already
  disconnects the client.
- **Reconnection**: paho native reconnect (`reconnect_delay_set(min_delay=1,
  max_delay=30)` + `connect_async` + `loop_start`). Recovery from a broker
  restart or network drop happens in seconds (verified <1s in testing); the
  service's `reload_all_listeners()` on startup is only a drift safety net.
  Subscriptions are re-established inside `on_connect`, so they survive
  reconnects.
- **Deduplication**: `DistributedLockManager` execution lock, same as
  file-watcher — defense-in-depth on top of leader election.
- **Payload safety**: malformed JSON on a `json`-format subscription falls back
  to the raw string, logs a warning, and still fires the flow. A bad payload
  never crashes the listener or drops the message.

## `trigger_config` schema (flat keys, matching the `file_change` style)

```json
{
  "type": "mqtt",
  "mqtt_host": "mqtt.example.com",
  "mqtt_port": 1883,
  "mqtt_tls": false,
  "mqtt_username": "hass",
  "mqtt_password": "<password>",
  "mqtt_client_id": "",
  "mqtt_topic_filter": "home/#",
  "mqtt_qos": 1,
  "mqtt_payload_format": "json"
}
```

- `mqtt_host`, `mqtt_topic_filter` — required (validated at consumption time;
  invalid config logs an error and skips the listener without crashing).
- `mqtt_client_id` — auto-generates `ioflow-<flow_id>` when empty.
- `mqtt_qos` — 0/1/2, default 1.
- `mqtt_payload_format` — `json` (parse, fall back to raw on failure) or `plain`.
- `mqtt_tls` — calls `tls_set()` with system CAs; client-cert auth is not built
  yet (POC posture: plaintext + username/password).

**Important — ACL**: the broker user must have **read/subscribe** permission on
the topic filter. Publish-only device users (e.g. the IoT project's `iot` user)
can NOT be used for the trigger; use a user with read access (e.g. `hass`).

## Performance & Delivery (scalability fine-tuning)

Every incoming message no longer schedules an unbounded flow execution.
Messages go through a **bounded dispatch queue** drained by a **fixed worker
pool**, with optional per-flow batching, rate limiting and deduplication.

### Operator scope (env — `backend/.env`, protects the server)

| Setting | Default | Meaning |
|---|---|---|
| `MQTT_DISPATCH_QUEUE_SIZE` | `1000` | Bounded queue between paho's network threads and flow execution |
| `MQTT_WORKER_POOL_SIZE` | `20` | Global cap on concurrent MQTT-triggered executions |
| `MQTT_OVERFLOW_POLICY` | `drop_oldest` | `drop_oldest` (stay realtime, lose stale readings) \| `drop_newest` \| `block` (stall paho's network thread so the broker's QoS 1 in-flight window absorbs the burst — no data loss, backpressure to broker) |
| `FLOW_LOG_MIN_LEVEL` | unset | Cap execution log verbosity for every flow (`node_summary` or `errors_only`) |

User-level settings can never exceed these ceilings. Env changes need a
backend restart.

### User scope (per flow / connection / app event)

Available in the flow designer's trigger node under **Performance & Delivery**
— for **both** the flat `mqtt` trigger and `event` triggers bound to an MQTT
application event. All keys can also be set per connection
(`subscription_config`) or per app event (`event_configuration`); resolution:

```
flow trigger_config > subscription_config > event_configuration > default
```

| Key | Default | Meaning |
|---|---|---|
| `mqtt_batch_size` | `1` | Messages accumulated per execution. `1` = no batching (fully backward compatible). With batching, 1,000 msg/s at batch 1000 → 1 execution/s |
| `mqtt_batch_window_seconds` | `0` | Flush a partial batch after this window (`0` = size-only) |
| `mqtt_max_rate` | `0` | Max executions/sec for this flow (`0` = unlimited) |
| `mqtt_rate_overflow` | `fold` | `fold` excess into the next batch \| `drop` |
| `mqtt_max_concurrent` | `0` | Per-flow concurrency cap (`0` = bounded only by the global pool; clamped to `MQTT_WORKER_POOL_SIZE`) |
| `mqtt_dedup` | `off` | `off` \| `payload` (hash topic + raw payload) \| `key` (user template) |
| `mqtt_dedup_key` | `""` | Template for `key` mode, e.g. `{{payload.device_id}}:{{payload.seq}}` |
| `mqtt_dedup_window_seconds` | `300` | Dedup window = Redis lock TTL |

Config changes on flow update re-attach the listener automatically
(`watch_flow` / `watch_event_flow`), so user-scope settings take effect live
without a restart.

### Batched executions

When `mqtt_batch_size > 1`, the flow receives:

| Variable | Meaning |
|---|---|
| `input.messages` | Array of all messages in the batch (each with `topic`/`payload`/`payload_raw`/`qos`/`retain`/`timestamp`) |
| `input.message_count` | Number of messages in the batch |
| `input.topic`, `input.payload`, ... | Keep pointing at the FIRST message so existing `{{trigger.payload}}` references don't break |

Batched flows should iterate `input.messages` (e.g. with a Loop node).

### Observability

`get_active_listeners()` (background-services API) reports per listener:
dispatch queue depth, dropped-message count, executions started,
executions/sec (60s window), dedup skips, current batch fill, and the
**effective resolved config** with the precedence level that won for each key
(`flow` / `connection` / `event` / `default`).

## Flow-level execution logging (applies to ALL flows, not just MQTT)

Flow Settings → **Execution Logging** (stored in
`flow_definition.settings.execution_log_level`; no schema migration):

| Level | What is stored per node/step |
|---|---|
| `full` (default) | Detailed per-step logs (inputs, outputs, timing) |
| `node_summary` | One line per node — start/completion, status, short summary; heavy payloads stripped |
| `errors_only` | Nothing while the flow succeeds; on failure the buffered logs of the failing run are flushed |

`flow_log_sample_rate` (0.0–1.0, default 1.0): the sampled fraction of
executions logs at the configured level; unsampled executions fall back to
`errors_only`. The operator can cap verbosity everywhere with
`FLOW_LOG_MIN_LEVEL`.

## Variables exposed to the flow

| Variable | Meaning |
|---|---|
| `input.topic` | Topic the message was published to |
| `input.payload` | Decoded payload (parsed object when JSON) |
| `input.payload_raw` | Raw payload string |
| `input.qos` | QoS of the received message |
| `input.retain` | Whether it was a retained message |
| `input.timestamp` | ISO timestamp when the message was received |
| `input.messages` | Only when batching: all messages in the batch |
| `input.message_count` | Only when batching: batch size |

## Writing readings to TimescaleDB (no new code)

Downstream writes reuse the existing Postgres-compatible `database_query`
executor. One-time table setup on the Timescale host:

```sql
CREATE TABLE IF NOT EXISTS mqtt_readings (
  time        TIMESTAMPTZ NOT NULL DEFAULT now(),
  topic       TEXT NOT NULL,
  device_id   TEXT,
  metric      TEXT,
  value       DOUBLE PRECISION,
  payload     JSONB
);
SELECT create_hypertable('mqtt_readings', 'time', if_not_exists => TRUE);
```

Flow pattern: `MQTT trigger` → `database_query (execute_command)` node with an
`INSERT INTO mqtt_readings (topic, payload) VALUES (...)` statement binding
`input.topic` / `input.payload_raw`.

## Files touched

- **New**: `backend/services/mqtt_listener_service.py`,
  `backend/seed-applications/mqtt.json`,
  `frontend/src/components/flow/MqttTriggerConfig.js`
- **Modified**: `backend/requirements.txt` (paho-mqtt>=2.0),
  `backend/services/background_manager.py`, `backend/api/flows.py`
  (TriggerConfig fields, `valid_types` whitelist, trigger wiring for both the
  `mqtt` type and MQTT-backed `event` triggers),
  `backend/api/applications.py` (test-connection MQTT branch; `mqtt` in the
  `AppTypeEnum`/`EventTypeEnum` response enums),
  `backend/schemas/application_schemas.py` (`mqtt` in `AppTypeEnum`/`EventTypeEnum`),
  `backend/api/seed_applications.py`, `backend/mcp_server/tools/management_tools.py`,
  `backend/mcp_server/tools/documentation_tools.py` (event-type/app-type value lists),
  `backend/db/application_models.py` (TriggerType enum),
  `backend/mcp_server/validators/schema_validator.py` (`mqtt` event_type +
  app_type enums),
  `frontend/src/components/flow/TriggerSelector.js`,
  `frontend/src/pages/FlowDesigner.js` (import, load-on-open, variables panel,
  build-on-save, view-source, config-panel render, MQTT event subscription
  panel + eventTriggerKind),
  `frontend/src/components/flow/TriggerNode.js`,
  `frontend/src/plugins/IconRegistry.js` (SignalIcon for `mqtt`).

## Verification

Automated integration tests (real broker, mocked ExecutionEngine), run with
`cd backend && ../venv/bin/python ../test-script/<name>.py`:

- `test-script/test_mqtt_trigger_e2e.py` — flow-level model: connect/subscribe,
  JSON parse, malformed-JSON fallback, plain format, unwatch, service stop,
  config validation, reconnect-after-socket-drop (<1s). 19/19 passed 2026-07-03.
- `test-script/test_mqtt_app_event_e2e.py` — application model: one shared
  client for multiple flows, topic routing (only matching flows fire),
  overlapping filters fire all matching flows exactly once (covering-set
  subscription), detach keeps the connection until the last flow leaves,
  non-MQTT events no-op, missing connection raises, real credential
  encrypt/decrypt round-trip. 14/14 passed 2026-07-04.
- Test-connection endpoint exercised over HTTP (TestClient): success with valid
  credentials, "Not authorized" with wrong password, timeout for unreachable
  broker — all verified 2026-07-04 against the live IoT broker.

Manual UI verification (needs backend + frontend running):
1. Create a flow, pick the **MQTT** trigger, configure broker/topic, save.
2. Activate the flow; backend log shows
   `Started MQTT listener for flow ... (topic: ...)` then
   `MQTT connected for flow ..., subscribed to ...`.
3. `mosquitto_pub -h <broker> -u iot -P '<pw>' -t home/verify -m '{"test":true}'`
   → a flow execution appears within ~1s.
4. Deactivate → log shows `Stopped MQTT listener for flow ...`.

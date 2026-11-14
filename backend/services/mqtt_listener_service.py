import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse
from collections import deque
import asyncio
import hashlib
import json
import logging
import re
import time
from core.config import settings
from db.database import get_tenant_db

# Import models - PostgreSQL Only
from db.models import Flow, FlowStatus

logger = logging.getLogger(__name__)


def _deserialize_json_field(value):
    """JSONB columns come back as JSON strings in SQLite mode."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
    return value or {}


def parse_broker_url(base_url: str):
    """Parse mqtt://host:port or mqtts://host:port into (host, port, use_tls).

    Also tolerates a bare "host" or "host:port" with no scheme.
    Returns None if no host can be extracted.
    """
    if not base_url:
        return None
    url = base_url.strip()
    if '://' not in url:
        url = f'mqtt://{url}'
    parsed = urlparse(url)
    if parsed.scheme not in ('mqtt', 'mqtts', 'tcp', 'ssl'):
        return None
    if not parsed.hostname:
        return None
    use_tls = parsed.scheme in ('mqtts', 'ssl')
    port = parsed.port or (8883 if use_tls else 1883)
    return parsed.hostname, port, use_tls


def _filter_covers(covering: str, covered: str) -> bool:
    """True if every topic matching `covered` also matches `covering`.

    Used to subscribe a minimal covering set of topic filters on a shared
    connection — the broker delivers one copy per matching subscription, so
    subscribing both 'home/#' and 'home/a/#' would double-deliver messages.
    """
    if covering == covered:
        return True
    a = covering.split('/')
    b = covered.split('/')
    i = 0
    while True:
        a_tok = a[i] if i < len(a) else None
        b_tok = b[i] if i < len(b) else None
        if a_tok == '#':
            return True
        if a_tok is None and b_tok is None:
            return True
        if a_tok is None or b_tok is None:
            return False
        if b_tok == '#':
            return False
        if a_tok == '+':
            i += 1
            continue
        if b_tok == '+':
            return False
        if a_tok != b_tok:
            return False
        i += 1


def _decode_payload(msg, payload_format: str):
    """Decode an MQTT message payload defensively — never raises."""
    try:
        payload_raw = msg.payload.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        payload_raw = msg.payload.decode('utf-8', errors='replace') if msg.payload else ''
        logger.warning(f"MQTT payload on {msg.topic} is not valid UTF-8, replaced invalid characters")

    payload = payload_raw
    if payload_format == 'json':
        try:
            payload = json.loads(payload_raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"MQTT payload on {msg.topic} is not valid JSON, falling back to raw string")
            payload = payload_raw
    return payload, payload_raw


def _build_variables(msg, payload, payload_raw) -> dict:
    return {
        'topic': msg.topic,
        'payload': payload,
        'payload_raw': payload_raw,
        'qos': msg.qos,
        'retain': bool(msg.retain),
        'timestamp': datetime.now().isoformat()
    }


# ---------------------------------------------------------------------------
# Performance & Delivery configuration (batching, rate limiting, dedup,
# per-flow concurrency). Resolved through the standard precedence chain:
#   flow trigger_config > subscription_config > event_configuration > default
# The same mqtt_* keys are accepted at every level, so backend resolution is
# shared between both attachment models (no per-attachment branching).
# ---------------------------------------------------------------------------

MQTT_PERF_DEFAULTS = {
    'mqtt_batch_size': 1,                 # 1 = no batching (backward compatible)
    'mqtt_batch_window_seconds': 0.0,     # 0 = size-only flush
    'mqtt_max_rate': 0.0,                 # executions/sec, 0 = unlimited
    'mqtt_rate_overflow': 'fold',         # fold excess into next batch | drop
    'mqtt_max_concurrent': 0,             # 0 = bounded only by the global pool
    'mqtt_dedup': 'off',                  # off | payload | key
    'mqtt_dedup_key': '',                 # template, e.g. {{payload.device_id}}:{{payload.seq}}
    'mqtt_dedup_window_seconds': 300,     # Redis dedup lock TTL
}


def resolve_mqtt_perf_config(trigger_config: Optional[dict] = None,
                             subscription_config: Optional[dict] = None,
                             event_configuration: Optional[dict] = None):
    """Resolve Performance & Delivery settings for one flow attachment.

    Returns (resolved, sources) where sources records which precedence level
    won for each key ('flow' | 'connection' | 'event' | 'default') so
    get_active_listeners() can show users where each effective value came from.
    Invalid values fall back to defaults instead of breaking the listener.
    """
    scopes = (('flow', trigger_config),
              ('connection', subscription_config),
              ('event', event_configuration))
    resolved, sources = {}, {}
    for key, default in MQTT_PERF_DEFAULTS.items():
        value, source = default, 'default'
        for scope_name, cfg in scopes:
            if isinstance(cfg, dict) and cfg.get(key) not in (None, ''):
                value, source = cfg[key], scope_name
                break
        resolved[key], sources[key] = value, source

    def _sanitize_number(key, cast, lo, hi):
        try:
            resolved[key] = min(max(cast(resolved[key]), lo), hi)
        except (TypeError, ValueError):
            resolved[key] = MQTT_PERF_DEFAULTS[key]
            sources[key] = 'default'

    _sanitize_number('mqtt_batch_size', int, 1, 10000)
    _sanitize_number('mqtt_batch_window_seconds', float, 0.0, 3600.0)
    _sanitize_number('mqtt_max_rate', float, 0.0, 1000000.0)
    _sanitize_number('mqtt_max_concurrent', int, 0, 1000000)
    _sanitize_number('mqtt_dedup_window_seconds', int, 1, 86400)

    if resolved['mqtt_rate_overflow'] not in ('fold', 'drop'):
        resolved['mqtt_rate_overflow'] = MQTT_PERF_DEFAULTS['mqtt_rate_overflow']
        sources['mqtt_rate_overflow'] = 'default'
    if resolved['mqtt_dedup'] not in ('off', 'payload', 'key'):
        resolved['mqtt_dedup'] = 'off'
        sources['mqtt_dedup'] = 'default'
    if resolved['mqtt_dedup'] == 'key' and not str(resolved['mqtt_dedup_key'] or '').strip():
        logger.warning("mqtt_dedup='key' without mqtt_dedup_key template — dedup disabled")
        resolved['mqtt_dedup'] = 'off'
        sources['mqtt_dedup'] = 'default'

    # User settings never exceed the operator ceiling
    pool_size = max(1, int(getattr(settings, 'mqtt_worker_pool_size', 20)))
    if resolved['mqtt_max_concurrent'] > 0:
        resolved['mqtt_max_concurrent'] = min(resolved['mqtt_max_concurrent'], pool_size)

    return resolved, sources


_DEDUP_TEMPLATE_RE = re.compile(r'\{\{\s*([\w.]+)\s*\}\}')


def _render_dedup_key(template: str, variables: dict) -> str:
    """Render a user dedup-key template ({{payload.device_id}}:{{payload.seq}})
    against the trigger variables. Missing paths render as empty strings."""
    def _lookup(match):
        value = variables
        for part in match.group(1).split('.'):
            if not isinstance(value, dict):
                return ''
            value = value.get(part)
            if value is None:
                return ''
        return str(value)
    try:
        return _DEDUP_TEMPLATE_RE.sub(_lookup, template)
    except Exception as e:
        logger.warning(f"Failed to render mqtt_dedup_key template '{template}': {e}")
        return template


def _batch_variables(batch: List[dict]) -> dict:
    """Build trigger variables for a batch of messages.

    A single message stays exactly as before (fully backward compatible).
    For batches, topic/payload/... keep pointing at the FIRST message so
    existing {{trigger.payload}} references don't break; batched flows
    iterate variables.messages instead.
    """
    if len(batch) == 1:
        return batch[0]
    combined = dict(batch[0])
    combined['messages'] = batch
    combined['message_count'] = len(batch)
    return combined


async def _execute_triggered_flow(schema_name: str, tenant_id: str, flow_id: str,
                                  user_id, lock_manager, variables: dict,
                                  perf: Optional[dict] = None, route=None):
    """Shared trigger path: optional content-based dedup + ExecutionEngine invocation.

    Dedup hashes stable message content (never the receive timestamp — the old
    lock hashed trigger_data including a microsecond timestamp, making it a
    silent no-op). Default is 'off', which also saves 2 Redis round trips per
    message. The lock is intentionally NOT released after execution: its TTL
    IS the dedup window.
    """
    try:
        logger.debug(f"Triggering flow {flow_id} for MQTT message on {variables.get('topic')}")

        trigger_data = {
            'trigger_source': 'mqtt',
            'variables': variables
        }

        perf = perf or {}
        dedup_mode = perf.get('mqtt_dedup', 'off')
        if lock_manager and dedup_mode in ('payload', 'key'):
            if dedup_mode == 'payload':
                basis = f"{variables.get('topic', '')}|{variables.get('payload_raw', '')}"
            else:
                basis = _render_dedup_key(str(perf.get('mqtt_dedup_key', '')), variables)
            digest = hashlib.md5(basis.encode('utf-8', errors='replace')).hexdigest()[:16]
            lock_key = f"mqtt-dedup:{flow_id}:{digest}"

            acquired = await lock_manager.acquire_lock(
                lock_key,
                ttl=int(perf.get('mqtt_dedup_window_seconds', 300)),
                retry_count=0
            )
            if not acquired:
                if route is not None:
                    route.dedup_skipped += 1
                logger.debug(f"Deduplicated MQTT message for flow {flow_id} ({lock_key})")
                return

        # Import here to avoid circular dependency
        from services.execution_engine import ExecutionEngine

        execution_engine = ExecutionEngine(
            schema_name,
            tenant_id=tenant_id,
            user_id=user_id
        )
        await execution_engine.execute_flow(
            flow_id=flow_id,
            trigger_data=trigger_data,
            trigger_type='mqtt'
        )

    except Exception as e:
        logger.error(f"Failed to trigger flow {flow_id} for MQTT message: {str(e)}")


class MqttFlowRoute:
    """Runtime state for one flow attachment: subscription details, the
    resolved Performance & Delivery config, batching/rate-limit state and
    the counters surfaced by get_active_listeners().

    Batching/rate state is only ever touched on the main event loop, so no
    locking is needed.
    """

    def __init__(self, tenant_id: str, schema_name: str, flow_id: str, user_id,
                 topic_filter: str, qos: int, payload_format: str,
                 perf: dict, perf_sources: dict):
        self.tenant_id = tenant_id
        self.schema_name = schema_name
        self.flow_id = flow_id
        self.user_id = user_id
        self.topic_filter = topic_filter
        self.qos = qos
        self.payload_format = payload_format
        self.perf = perf
        self.perf_sources = perf_sources

        # Per-flow concurrency cap (already clamped to the worker pool size)
        max_concurrent = int(perf.get('mqtt_max_concurrent', 0) or 0)
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent > 0 else None

        # Batching / rate-limit state
        self.pending: List[dict] = []
        self.flush_handle = None            # asyncio.TimerHandle for window/fold flush
        self.rate_window_start = 0.0
        self.rate_count = 0

        # Observability counters
        self.messages_received = 0
        self.messages_dropped = 0
        self.executions_started = 0
        self.dedup_skipped = 0
        self.exec_timestamps = deque(maxlen=1000)

    def executions_per_second(self, window: float = 60.0) -> float:
        now = time.monotonic()
        recent = sum(1 for t in self.exec_timestamps if now - t <= window)
        return round(recent / window, 3)

    def cancel_flush(self):
        if self.flush_handle is not None:
            self.flush_handle.cancel()
            self.flush_handle = None

    def stats(self) -> dict:
        return {
            'messages_received': self.messages_received,
            'messages_dropped': self.messages_dropped,
            'executions_started': self.executions_started,
            'executions_per_second': self.executions_per_second(),
            'dedup_skipped': self.dedup_skipped,
            'batch_fill': len(self.pending),
        }


class MqttDispatcher:
    """Bounded queue + fixed worker pool between paho's network threads and
    flow execution (Tier 1), plus per-flow batching and rate limiting (Tier 2).

    Before: every incoming message scheduled a full flow execution directly
    onto the event loop — N messages/sec meant N concurrent executions.
    Now paho threads only hand messages over; a fixed pool of workers drains
    a bounded queue, so execution concurrency is capped no matter the
    message rate.
    """

    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.service = None                 # MqttListenerService (for lock_manager)
        self.queue: Optional[asyncio.Queue] = None
        self.workers: List[asyncio.Task] = []
        self.dropped_total = 0
        self.executions_total = 0
        self._last_drop_log = 0.0

    def start(self, loop: asyncio.AbstractEventLoop, service):
        self.loop = loop
        self.service = service
        queue_size = max(1, int(getattr(settings, 'mqtt_dispatch_queue_size', 1000)))
        pool_size = max(1, int(getattr(settings, 'mqtt_worker_pool_size', 20)))
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.workers = [loop.create_task(self._worker(i)) for i in range(pool_size)]
        logger.info(f"MQTT dispatcher started (queue: {queue_size}, workers: {pool_size}, "
                    f"overflow: {getattr(settings, 'mqtt_overflow_policy', 'drop_oldest')})")

    async def stop(self):
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
        self.queue = None
        logger.info("MQTT dispatcher stopped")

    @property
    def running(self) -> bool:
        return self.queue is not None and self.loop is not None

    # ------------------------------------------------------------------
    # Ingest — called from paho network threads
    # ------------------------------------------------------------------

    def ingest_from_thread(self, route: MqttFlowRoute, variables: dict):
        """Hand a decoded message from a paho thread to the event loop."""
        if not self.running:
            logger.error(f"MQTT dispatcher not running, dropping message for flow {route.flow_id}")
            return
        if getattr(settings, 'mqtt_overflow_policy', 'drop_oldest') == 'block':
            # Backpressure: keep paho's network thread blocked until the
            # message is accepted, so the broker's QoS 1 in-flight window
            # absorbs the burst instead of our memory. No data loss.
            try:
                asyncio.run_coroutine_threadsafe(
                    self._ingest_blocking(route, variables), self.loop
                ).result()
            except Exception as e:
                logger.error(f"MQTT dispatch (block) failed for flow {route.flow_id}: {e}")
        else:
            self.loop.call_soon_threadsafe(self._ingest, route, variables)

    # ------------------------------------------------------------------
    # Batching + rate limiting — event loop only
    # ------------------------------------------------------------------

    def _ingest(self, route: MqttFlowRoute, variables: dict):
        try:
            job_vars = self._accept(route, variables)
            if job_vars is not None:
                self._enqueue_nowait(route, job_vars)
        except Exception as e:
            logger.error(f"MQTT dispatch failed for flow {route.flow_id}: {e}", exc_info=True)

    async def _ingest_blocking(self, route: MqttFlowRoute, variables: dict):
        job_vars = self._accept(route, variables)
        if job_vars is not None:
            # True backpressure: suspends until a queue slot frees, which in
            # turn blocks the paho thread waiting on the future's result.
            await self.queue.put((route, job_vars))

    def _accept(self, route: MqttFlowRoute, variables: dict) -> Optional[dict]:
        """Accumulate one message. Returns execution variables when a batch is
        ready to dispatch now, else None (buffered for size/window/rate)."""
        route.messages_received += 1
        route.pending.append(variables)

        batch_size = int(route.perf.get('mqtt_batch_size', 1))
        window = float(route.perf.get('mqtt_batch_window_seconds', 0) or 0)

        # Cap the fold/batch buffer so a permanently rate-limited flow can't
        # grow memory without bound (drops oldest, counted — never silent)
        cap = max(batch_size * 10, 1000)
        if len(route.pending) > cap:
            overflow = len(route.pending) - cap
            del route.pending[:overflow]
            self._count_drop(route, overflow, reason="batch buffer cap")

        if len(route.pending) >= batch_size:
            return self._try_flush(route)
        if window > 0 and route.flush_handle is None:
            route.flush_handle = self.loop.call_later(window, self._flush_timer, route)
        return None

    def _try_flush(self, route: MqttFlowRoute) -> Optional[dict]:
        """Apply the per-flow rate limit; return batch variables if this flow
        is allowed to execute now, else defer (fold) or drop."""
        route.cancel_flush()
        if not route.pending:
            return None

        max_rate = float(route.perf.get('mqtt_max_rate', 0) or 0)
        if max_rate > 0:
            now = time.monotonic()
            if now - route.rate_window_start >= 1.0:
                route.rate_window_start = now
                route.rate_count = 0
            if route.rate_count >= max_rate:
                if route.perf.get('mqtt_rate_overflow', 'fold') == 'drop':
                    self._count_drop(route, len(route.pending), reason="rate limit")
                    route.pending = []
                    return None
                # fold: hold messages and retry when the 1s rate window rolls over
                delay = max(0.05, 1.0 - (now - route.rate_window_start))
                route.flush_handle = self.loop.call_later(delay, self._flush_timer, route)
                return None
            route.rate_count += 1

        batch = route.pending
        route.pending = []
        return _batch_variables(batch)

    def _flush_timer(self, route: MqttFlowRoute):
        """Window/fold timer fired — flush whatever is pending."""
        route.flush_handle = None
        try:
            job_vars = self._try_flush(route)
            if job_vars is not None:
                # Timer flushes run on the event loop and must never block it,
                # so under the 'block' policy they fall back to drop_oldest.
                self._enqueue_nowait(route, job_vars)
        except Exception as e:
            logger.error(f"MQTT batch flush failed for flow {route.flow_id}: {e}", exc_info=True)

    def flush_route(self, route: MqttFlowRoute):
        """Flush and drop any pending state when a route detaches."""
        route.cancel_flush()
        route.pending = []

    # ------------------------------------------------------------------
    # Queue + workers
    # ------------------------------------------------------------------

    def _enqueue_nowait(self, route: MqttFlowRoute, job_vars: dict):
        try:
            self.queue.put_nowait((route, job_vars))
            return
        except asyncio.QueueFull:
            pass

        policy = getattr(settings, 'mqtt_overflow_policy', 'drop_oldest')
        if policy == 'drop_newest':
            self._count_drop(route, job_vars.get('message_count', 1), reason="queue full (drop_newest)")
            return

        # drop_oldest (also the fallback for timer flushes under 'block'):
        # discard the stalest queued execution to stay realtime
        try:
            old_route, old_vars = self.queue.get_nowait()
            self.queue.task_done()
            self._count_drop(old_route, old_vars.get('message_count', 1), reason="queue full (drop_oldest)")
        except asyncio.QueueEmpty:
            pass
        try:
            self.queue.put_nowait((route, job_vars))
        except asyncio.QueueFull:
            self._count_drop(route, job_vars.get('message_count', 1), reason="queue full")

    def _count_drop(self, route: MqttFlowRoute, message_count: int, reason: str):
        route.messages_dropped += int(message_count or 1)
        self.dropped_total += int(message_count or 1)
        # Rate-limit drop warnings to one every 5 seconds
        now = time.monotonic()
        if now - self._last_drop_log >= 5.0:
            self._last_drop_log = now
            logger.warning(f"MQTT dispatcher dropping messages ({reason}) — "
                           f"flow {route.flow_id}, {self.dropped_total} dropped total")

    async def _worker(self, index: int):
        while True:
            try:
                route, job_vars = await self.queue.get()
            except asyncio.CancelledError:
                raise
            try:
                if route.semaphore is not None:
                    # Per-flow cap: one chatty telemetry flow can't starve a
                    # critical alarm flow of the whole pool
                    async with route.semaphore:
                        await self._run(route, job_vars)
                else:
                    await self._run(route, job_vars)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"MQTT worker {index} failed executing flow {route.flow_id}: {e}",
                             exc_info=True)
            finally:
                self.queue.task_done()

    async def _run(self, route: MqttFlowRoute, job_vars: dict):
        route.executions_started += 1
        route.exec_timestamps.append(time.monotonic())
        self.executions_total += 1
        lock_manager = self.service.lock_manager if self.service else None
        await _execute_triggered_flow(route.schema_name, route.tenant_id, route.flow_id,
                                      route.user_id, lock_manager, job_vars,
                                      perf=route.perf, route=route)

    def get_stats(self) -> dict:
        return {
            'queue_depth': self.queue.qsize() if self.queue else 0,
            'queue_max_size': self.queue.maxsize if self.queue else 0,
            'worker_pool_size': len(self.workers),
            'overflow_policy': getattr(settings, 'mqtt_overflow_policy', 'drop_oldest'),
            'dropped_total': self.dropped_total,
            'executions_total': self.executions_total,
        }


class MqttListenerHandler:
    """Handles MQTT messages for a single flow's own broker connection
    (trigger_config type == 'mqtt', broker details flat on the flow)."""

    def __init__(self, route: MqttFlowRoute, dispatcher: MqttDispatcher,
                 lock_manager = None):
        self.route = route
        self.dispatcher = dispatcher
        self.lock_manager = lock_manager
        # Convenience aliases (also kept for backward compatibility)
        self.tenant_id = route.tenant_id
        self.schema_name = route.schema_name
        self.flow_id = route.flow_id
        self.topic_filter = route.topic_filter
        self.qos = route.qos
        self.payload_format = route.payload_format
        self.user_id = route.user_id

    # paho-mqtt CallbackAPIVersion.VERSION2 callback signatures
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            # (Re)subscribe on every connect so subscriptions survive reconnects
            result, mid = client.subscribe(self.topic_filter, qos=self.qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"MQTT connected for flow {self.flow_id}, subscribed to "
                            f"'{self.topic_filter}' (qos: {self.qos})")
            else:
                logger.error(f"MQTT subscribe failed for flow {self.flow_id} "
                             f"topic '{self.topic_filter}': {mqtt.error_string(result)}")
        else:
            logger.error(f"MQTT connect failed for flow {self.flow_id}: {reason_code}")

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            logger.warning(f"MQTT unexpected disconnect for flow {self.flow_id} "
                           f"({reason_code}). Auto-reconnecting...")
        else:
            logger.info(f"MQTT disconnected for flow {self.flow_id}")

    def on_message(self, client, userdata, msg):
        try:
            logger.debug(f"MQTT message received for flow {self.flow_id} on topic {msg.topic}")
            payload, payload_raw = _decode_payload(msg, self.payload_format)
            variables = _build_variables(msg, payload, payload_raw)

            # Hand off to the bounded dispatcher (batching + rate limiting +
            # worker pool) instead of scheduling an unbounded execution
            self.dispatcher.ingest_from_thread(self.route, variables)
        except Exception as e:
            logger.error(f"Error scheduling flow trigger for MQTT message: {e}", exc_info=True)

    async def trigger_flow(self, variables: dict):
        """Kept for backward compatibility — delegates to the shared trigger path."""
        await _execute_triggered_flow(self.schema_name, self.tenant_id, self.flow_id,
                                      self.user_id, self.lock_manager, variables,
                                      perf=self.route.perf, route=self.route)


class MqttAppHandler:
    """Handles MQTT messages for one application connection (subscription).

    One broker connection per (tenant, application); multiple flows attach
    routes to it. Each incoming message is matched against every flow's topic
    filter and fires each matching flow.
    """

    def __init__(self, tenant_id: str, schema_name: str, app_id: str,
                 loop: asyncio.AbstractEventLoop, dispatcher: MqttDispatcher,
                 lock_manager = None):
        self.tenant_id = tenant_id
        self.schema_name = schema_name
        self.app_id = app_id
        self.loop = loop
        self.dispatcher = dispatcher
        self.lock_manager = lock_manager
        # flow_id -> MqttFlowRoute
        self.flow_routes: Dict[str, MqttFlowRoute] = {}
        # Filters currently subscribed on the broker (covering set) -> qos
        self.active_subs: Dict[str, int] = {}

    def desired_subscriptions(self) -> Dict[str, int]:
        """Minimal covering set of the flows' topic filters, each at the max
        qos of the filters it covers.

        Routing to flows happens client-side in on_message, so only ONE broker
        subscription per covered region is needed — overlapping subscriptions
        would make the broker deliver duplicate copies of each message.
        """
        qos_by_filter: Dict[str, int] = {}
        for route in self.flow_routes.values():
            tf = route.topic_filter
            qos_by_filter[tf] = max(qos_by_filter.get(tf, 0), route.qos)

        kept: Dict[str, int] = {}
        for tf, qos in sorted(qos_by_filter.items()):
            covered_by = next((g for g in kept if _filter_covers(g, tf)), None)
            if covered_by is not None:
                kept[covered_by] = max(kept[covered_by], qos)
                continue
            # Absorb any kept filters this one covers
            absorbed_qos = qos
            for g in [g for g in list(kept) if _filter_covers(tf, g)]:
                absorbed_qos = max(absorbed_qos, kept.pop(g))
            kept[tf] = absorbed_qos
        return kept

    def sync_subscriptions(self, client):
        """Diff active broker subscriptions against the desired covering set."""
        desired = self.desired_subscriptions()
        for tf in [tf for tf in self.active_subs if tf not in desired]:
            try:
                client.unsubscribe(tf)
                del self.active_subs[tf]
                logger.info(f"MQTT app {self.app_id}: unsubscribed '{tf}'")
            except Exception as e:
                logger.warning(f"MQTT app {self.app_id}: unsubscribe '{tf}' failed: {str(e)}")
        for tf, qos in desired.items():
            if self.active_subs.get(tf) == qos:
                continue
            result, mid = client.subscribe(tf, qos=qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.active_subs[tf] = qos
                logger.info(f"MQTT app {self.app_id}: subscribed '{tf}' (qos: {qos})")
            else:
                logger.error(f"MQTT app {self.app_id}: subscribe failed for "
                             f"'{tf}': {mqtt.error_string(result)}")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(f"MQTT app {self.app_id} connected")
            # Fresh session (clean_session=True): resubscribe everything
            self.active_subs = {}
            self.sync_subscriptions(client)
        else:
            logger.error(f"MQTT connect failed for app {self.app_id}: {reason_code}")

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            logger.warning(f"MQTT unexpected disconnect for app {self.app_id} "
                           f"({reason_code}). Auto-reconnecting...")
        else:
            logger.info(f"MQTT disconnected for app {self.app_id}")

    def on_message(self, client, userdata, msg):
        try:
            # Route the message to every flow whose topic filter matches
            matched = [
                (flow_id, route) for flow_id, route in list(self.flow_routes.items())
                if mqtt.topic_matches_sub(route.topic_filter, msg.topic)
            ]
            if not matched:
                logger.debug(f"MQTT app {self.app_id}: no flow route matches topic {msg.topic}")
                return

            logger.debug(f"MQTT app {self.app_id}: message on {msg.topic} matches "
                         f"{len(matched)} flow(s)")
            for flow_id, route in matched:
                payload, payload_raw = _decode_payload(msg, route.payload_format)
                variables = _build_variables(msg, payload, payload_raw)
                # Hand off to the bounded dispatcher (batching + rate limiting
                # + worker pool) instead of scheduling an unbounded execution
                self.dispatcher.ingest_from_thread(route, variables)
        except Exception as e:
            logger.error(f"Error routing MQTT message for app {self.app_id}: {e}", exc_info=True)


class MqttListenerService:
    """Manages MQTT broker subscriptions for flows.

    Two attachment models:
    - Flow-level (`trigger_config.type == 'mqtt'`): broker details stored flat on
      the flow, one dedicated client per flow.
    - Application-level (`trigger_config.type == 'event'` bound to an application
      event with `event_type == 'mqtt'`): broker + credentials come from the
      ApplicationSubscription (each application connection may target a different
      broker), ONE shared client per (tenant, application), and messages are
      routed to all attached flows by topic filter.
    """

    def __init__(self):
        # Flow-level clients — key: f"{tenant_id}:{flow_id}"
        self.clients: Dict[str, mqtt.Client] = {}
        self.handlers: Dict[str, MqttListenerHandler] = {}
        # Application-level clients — key: f"{tenant_id}:app:{app_id}"
        self.app_clients: Dict[str, mqtt.Client] = {}
        self.app_handlers: Dict[str, MqttAppHandler] = {}
        # Reverse index for event-driven flows — f"{tenant_id}:{flow_id}" -> app key
        self.flow_app_index: Dict[str, str] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.lock_manager = None  # Will be injected by BackgroundServiceManager
        # Bounded queue + worker pool between paho threads and flow execution
        self.dispatcher = MqttDispatcher()

    async def start(self):
        """Start the MQTT listener service and load all active MQTT listeners."""
        # Store the main event loop
        self.loop = asyncio.get_running_loop()
        self.dispatcher.start(self.loop, self)
        logger.info("MQTT listener service started")

        # Load existing MQTT listeners
        await self.reload_all_listeners()

    async def stop(self):
        """Stop all MQTT listeners (flow-level and application-level)."""
        for listener_key, client in list(self.clients.items()) + list(self.app_clients.items()):
            try:
                client.loop_stop()
                client.disconnect()
                logger.info(f"Stopped MQTT listener for {listener_key}")
            except Exception as e:
                logger.error(f"Error stopping MQTT listener for {listener_key}: {str(e)}")

        self.clients.clear()
        self.handlers.clear()
        self.app_clients.clear()
        self.app_handlers.clear()
        self.flow_app_index.clear()
        await self.dispatcher.stop()
        logger.info("MQTT listener service stopped")

    async def reload_all_listeners(self):
        """Reload all MQTT listeners from database."""
        try:
            # PostgreSQL multi-tenant mode
            from db.database import get_db
            from db.models import Tenant

            main_db = next(get_db())
            try:
                tenants = main_db.query(Tenant).filter(Tenant.status == 'active').all()
                for tenant in tenants:
                    tenant_id = str(tenant.tenant_id)
                    schema_name = f"tenant_{tenant_id.replace('-', '_')}"
                    await self.reload_tenant_listeners(tenant_id, schema_name)
            finally:
                main_db.close()

        except Exception as e:
            logger.error(f"Failed to reload MQTT listeners: {str(e)}")

    async def reload_tenant_listeners(self, tenant_id: str, schema_name: str):
        """Reload MQTT listeners for a specific tenant (both attachment models)."""
        try:
            with get_tenant_db(schema_name) as db:
                # Flows live in the shared ioflow.flows table (models are
                # schema-qualified, so the tenant search_path does not isolate
                # them) — filter by tenant_id or every tenant's pass would
                # attach listeners for all tenants' flows.
                flows = db.query(Flow).filter(
                    Flow.tenant_id == tenant_id,
                    Flow.status == FlowStatus.ACTIVE
                ).all()
                for flow in flows:
                    trigger_config = flow.trigger_config or {}
                    trigger_type = trigger_config.get('type')
                    if trigger_type == 'mqtt':
                        # Flow-level broker config
                        await self.watch_flow(tenant_id, schema_name, flow)
                    elif trigger_type == 'event':
                        # Application-event flows: watch_event_flow no-ops unless
                        # the referenced event is an MQTT event
                        try:
                            await self.watch_event_flow(tenant_id, schema_name, flow)
                        except Exception as e:
                            logger.error(f"Failed to attach MQTT event listener for "
                                         f"flow {flow.flow_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to reload MQTT listeners for tenant {tenant_id}: {str(e)}")

    # ------------------------------------------------------------------
    # Application-level (seed application / subscription) attachment
    # ------------------------------------------------------------------

    def _resolve_mqtt_event(self, trigger_config: dict, tenant_id: str):
        """Return (event, application, subscription) data if this event-trigger
        references an MQTT application event, else (None, None, None).
        Queries the main DB."""
        app_id = trigger_config.get('app_id')
        event_name = trigger_config.get('event_name')
        event_id = trigger_config.get('event_id')
        if not app_id or not (event_name or event_id):
            return None, None, None

        from db.database import get_db
        from db.application_models import Application, ApplicationEvent, ApplicationSubscription

        main_db = next(get_db())
        try:
            query = main_db.query(ApplicationEvent).filter(
                ApplicationEvent.app_id == app_id,
                ApplicationEvent.event_type == 'mqtt',
                ApplicationEvent.is_active == True
            )
            if event_id:
                event = query.filter(ApplicationEvent.event_id == event_id).first()
            else:
                event = query.filter(ApplicationEvent.event_name == event_name).first()
            if not event:
                return None, None, None

            application = main_db.query(Application).filter(
                Application.app_id == app_id
            ).first()

            subscription = main_db.query(ApplicationSubscription).filter(
                ApplicationSubscription.tenant_id == tenant_id,
                ApplicationSubscription.app_id == app_id,
                ApplicationSubscription.status == 'active'
            ).first()

            # Detach plain data before the session closes
            event_data = {
                'event_id': event.event_id,
                'event_configuration': _deserialize_json_field(event.event_configuration),
            }
            app_data = {
                'base_url': application.base_url if application else None,
            }
            sub_data = None
            if subscription:
                sub_data = {
                    'auth_credentials': subscription.auth_credentials,
                    'subscription_config': _deserialize_json_field(subscription.subscription_config),
                }
            return event_data, app_data, sub_data
        finally:
            main_db.close()

    async def watch_event_flow(self, tenant_id: str, schema_name: str, flow: Flow) -> bool:
        """Attach a flow with an application-event trigger to its application's
        shared broker connection.

        Returns False (no-op) when the referenced event is not an MQTT event.
        Raises ValueError when it IS an MQTT event but cannot be attached
        (missing subscription, unusable broker URL, ...) so API callers can
        surface the problem.
        """
        trigger_config = flow.trigger_config or {}
        if trigger_config.get('type') != 'event':
            return False

        flow_id = str(flow.flow_id)
        app_id = trigger_config.get('app_id')

        try:
            event_data, app_data, sub_data = self._resolve_mqtt_event(trigger_config, tenant_id)
        except Exception as e:
            # Unexpected lookup failure must not break activation of
            # webhook/polling event flows — log and treat as not-an-MQTT-event
            logger.error(f"Failed to resolve application event for flow {flow_id}: {str(e)}")
            return False
        if not event_data:
            return False  # Not an MQTT event — webhook/polling systems own it

        if not sub_data:
            raise ValueError(
                f"No active MQTT connection (subscription) for application {app_id}. "
                f"Connect to the MQTT application first."
            )

        # Broker: connection-level base_url overrides the application default
        sub_config = sub_data['subscription_config'] or {}
        broker_url = sub_config.get('base_url') or app_data.get('base_url')
        parsed = parse_broker_url(broker_url)
        if not parsed:
            raise ValueError(f"Invalid MQTT broker URL '{broker_url}' for application {app_id}")
        host, port, use_tls = parsed

        # Credentials from the encrypted subscription
        username = password = None
        if sub_data['auth_credentials']:
            try:
                from utils.crypto_utils import decrypt_credentials
                creds = decrypt_credentials(sub_data['auth_credentials']) or {}
                username = creds.get('username')
                password = creds.get('password')
            except Exception as e:
                logger.error(f"Failed to decrypt MQTT credentials for app {app_id}: {str(e)}")

        # Route config: flow override > connection default > event default
        event_config = event_data['event_configuration'] or {}
        topic_filter = (trigger_config.get('mqtt_topic_filter')
                        or sub_config.get('topic_filter')
                        or event_config.get('topic_filter', '#'))
        try:
            qos = int(trigger_config.get('mqtt_qos')
                      or sub_config.get('qos')
                      or event_config.get('qos', 1))
        except (TypeError, ValueError):
            qos = 1
        if qos not in (0, 1, 2):
            qos = 1
        payload_format = (trigger_config.get('mqtt_payload_format')
                          or sub_config.get('payload_format')
                          or event_config.get('payload_format', 'json'))

        if not self.loop:
            raise ValueError("No event loop available for the MQTT listener service")

        app_key = f"{tenant_id}:app:{app_id}"
        flow_key = f"{tenant_id}:{flow_id}"

        # Performance & Delivery: flow > connection > event defaults > hardcoded
        perf, perf_sources = resolve_mqtt_perf_config(
            trigger_config=trigger_config,
            subscription_config=sub_config,
            event_configuration=event_config,
        )
        route = MqttFlowRoute(
            tenant_id=tenant_id,
            schema_name=schema_name,
            flow_id=flow_id,
            user_id=flow.created_by,
            topic_filter=topic_filter,
            qos=qos,
            payload_format=payload_format,
            perf=perf,
            perf_sources=perf_sources,
        )

        existing_handler = self.app_handlers.get(app_key)
        if existing_handler:
            # Reuse the application's shared connection — just add/update the route
            old_route = existing_handler.flow_routes.get(flow_id)
            if old_route is not None:
                self.dispatcher.flush_route(old_route)
            existing_handler.flow_routes[flow_id] = route
            self.flow_app_index[flow_key] = app_key
            client = self.app_clients.get(app_key)
            if client and client.is_connected():
                existing_handler.sync_subscriptions(client)
            logger.info(f"Attached flow {flow_id} to existing MQTT connection for app {app_id} "
                        f"(topic: {topic_filter}, qos: {qos}) — "
                        f"{len(existing_handler.flow_routes)} flow(s) on this connection")
            return True

        # First flow for this application connection — create the shared client
        handler = MqttAppHandler(
            tenant_id=tenant_id,
            schema_name=schema_name,
            app_id=app_id,
            loop=self.loop,
            dispatcher=self.dispatcher,
            lock_manager=self.lock_manager,
        )
        handler.flow_routes[flow_id] = route

        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"ioflow-app-{str(app_id)[:12]}-{tenant_id[:8]}",
            clean_session=True,
        )
        if username:
            client.username_pw_set(username, password)
        if use_tls:
            client.tls_set()

        client.on_connect = handler.on_connect
        client.on_disconnect = handler.on_disconnect
        client.on_message = handler.on_message

        # Native reconnect backoff — recovery must happen in seconds,
        # not wait for a periodic listener reload sweep
        client.reconnect_delay_set(min_delay=1, max_delay=30)

        client.connect_async(host, port, keepalive=60)
        client.loop_start()

        self.app_clients[app_key] = client
        self.app_handlers[app_key] = handler
        self.flow_app_index[flow_key] = app_key

        logger.info(f"Started shared MQTT connection for app {app_id} on {host}:{port} "
                    f"(tls: {use_tls}) with flow {flow_id} (topic: {topic_filter}, qos: {qos})")
        return True

    async def unwatch_event_flow(self, tenant_id: str, flow_id: str):
        """Detach an event-driven flow from its application's shared connection.
        Disconnects the shared client when the last flow detaches. No-op if the
        flow was never attached."""
        flow_key = f"{tenant_id}:{flow_id}"
        app_key = self.flow_app_index.pop(flow_key, None)
        if not app_key:
            return

        handler = self.app_handlers.get(app_key)
        client = self.app_clients.get(app_key)
        if not handler:
            return

        removed_route = handler.flow_routes.pop(flow_id, None)
        if removed_route is not None:
            self.dispatcher.flush_route(removed_route)

        if not handler.flow_routes:
            # Last flow on this connection — tear it down
            try:
                if client:
                    client.loop_stop()
                    client.disconnect()
                logger.info(f"Stopped shared MQTT connection {app_key} "
                            f"(last flow {flow_id} detached)")
            except Exception as e:
                logger.error(f"Failed to stop shared MQTT connection {app_key}: {str(e)}")
            self.app_clients.pop(app_key, None)
            self.app_handlers.pop(app_key, None)
        else:
            # Other flows still attached — drop broker subscriptions no longer needed
            if client and client.is_connected():
                handler.sync_subscriptions(client)
            logger.info(f"Detached flow {flow_id} from shared MQTT connection {app_key} — "
                        f"{len(handler.flow_routes)} flow(s) remain")

    # ------------------------------------------------------------------
    # Flow-level (flat trigger_config) attachment
    # ------------------------------------------------------------------

    async def watch_flow(self, tenant_id: str, schema_name: str, flow: Flow):
        """Start a dedicated MQTT subscription for a flow with broker details
        stored flat on its trigger_config (trigger type 'mqtt').

        Args:
            tenant_id: The tenant ID
            schema_name: The database schema name
            flow: The flow to listen for
        """
        flow_id = str(flow.flow_id)
        listener_key = f"{tenant_id}:{flow_id}"

        # Stop existing listener if any
        if listener_key in self.clients:
            try:
                self.clients[listener_key].loop_stop()
                self.clients[listener_key].disconnect()
            except Exception as e:
                logger.warning(f"Error stopping previous MQTT client for flow {flow_id}: {str(e)}")
            del self.clients[listener_key]
            previous_handler = self.handlers.pop(listener_key, None)
            if previous_handler is not None:
                self.dispatcher.flush_route(previous_handler.route)

        trigger_config = flow.trigger_config or {}

        # Extract configuration
        host = trigger_config.get('mqtt_host')
        if not host:
            logger.error(f"No mqtt_host specified for flow {flow_id}")
            return

        topic_filter = trigger_config.get('mqtt_topic_filter')
        if not topic_filter:
            logger.error(f"No mqtt_topic_filter specified for flow {flow_id}")
            return

        try:
            port = int(trigger_config.get('mqtt_port', 1883))
        except (TypeError, ValueError):
            logger.error(f"Invalid mqtt_port for flow {flow_id}: {trigger_config.get('mqtt_port')}")
            return

        try:
            qos = int(trigger_config.get('mqtt_qos', 1))
        except (TypeError, ValueError):
            qos = 1
        if qos not in (0, 1, 2):
            logger.warning(f"Invalid mqtt_qos {qos} for flow {flow_id}, defaulting to 1")
            qos = 1

        username = trigger_config.get('mqtt_username')
        password = trigger_config.get('mqtt_password')
        client_id = trigger_config.get('mqtt_client_id') or f"ioflow-{flow_id}"
        use_tls = bool(trigger_config.get('mqtt_tls', False))
        payload_format = trigger_config.get('mqtt_payload_format', 'json')

        # Ensure we have an event loop
        if not self.loop:
            logger.error(f"No event loop available for flow {flow_id}")
            return

        try:
            # Performance & Delivery: flow trigger_config > hardcoded defaults
            perf, perf_sources = resolve_mqtt_perf_config(trigger_config=trigger_config)
            route = MqttFlowRoute(
                tenant_id=tenant_id,
                schema_name=schema_name,
                flow_id=flow_id,
                user_id=flow.created_by,
                topic_filter=topic_filter,
                qos=qos,
                payload_format=payload_format,
                perf=perf,
                perf_sources=perf_sources,
            )
            handler = MqttListenerHandler(
                route=route,
                dispatcher=self.dispatcher,
                lock_manager=self.lock_manager,
            )

            # Create and start the MQTT client
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=client_id,
                clean_session=True,
            )
            if username:
                client.username_pw_set(username, password)
            if use_tls:
                client.tls_set()

            client.on_connect = handler.on_connect
            client.on_disconnect = handler.on_disconnect
            client.on_message = handler.on_message

            # Native reconnect backoff — recovery must happen in seconds,
            # not wait for a periodic listener reload sweep
            client.reconnect_delay_set(min_delay=1, max_delay=30)

            # connect_async + loop_start: non-blocking connect handled by
            # paho's background network thread (keeps retrying if broker is down)
            client.connect_async(host, port, keepalive=60)
            client.loop_start()

            # Store references
            self.clients[listener_key] = client
            self.handlers[listener_key] = handler

            logger.info(f"Started MQTT listener for flow {flow_id} on {host}:{port} "
                        f"(topic: {topic_filter}, qos: {qos}, client_id: {client_id}, tls: {use_tls})")

        except Exception as e:
            logger.error(f"Failed to start MQTT listener for flow {flow_id}: {str(e)}")

    async def unwatch_flow(self, tenant_id: str, flow_id: str):
        """Stop the MQTT subscription for a specific flow (both attachment models)."""
        listener_key = f"{tenant_id}:{flow_id}"

        if listener_key in self.clients:
            try:
                client = self.clients[listener_key]
                client.loop_stop()
                client.disconnect()
                del self.clients[listener_key]
                removed_handler = self.handlers.pop(listener_key, None)
                if removed_handler is not None:
                    self.dispatcher.flush_route(removed_handler.route)
                logger.info(f"Stopped MQTT listener for flow {flow_id}")
            except Exception as e:
                logger.error(f"Failed to stop MQTT listener for flow {flow_id}: {str(e)}")

        # Event-driven flows attach to a shared app connection instead
        if listener_key in self.flow_app_index:
            await self.unwatch_event_flow(tenant_id, flow_id)

    @staticmethod
    def _describe_route(route: MqttFlowRoute) -> Dict[str, Any]:
        """Per-flow observability: counters + the effective resolved config
        (and which precedence level each value came from) so users can see
        which level of the chain won."""
        return {
            'topic_filter': route.topic_filter,
            'qos': route.qos,
            'payload_format': route.payload_format,
            'stats': route.stats(),
            'effective_config': dict(route.perf),
            'config_sources': dict(route.perf_sources),
        }

    def get_active_listeners(self) -> List[Dict]:
        """Get information about active MQTT listeners, including per-flow
        queue/drop/rate stats and the effective resolved configuration."""
        listeners = []
        dispatcher_stats = self.dispatcher.get_stats()
        for listener_key, handler in self.handlers.items():
            tenant_id, flow_id = listener_key.split(':', 1)
            listeners.append({
                'tenant_id': tenant_id,
                'flow_id': flow_id,
                'attachment': 'flow',
                **self._describe_route(handler.route),
                'dispatcher': dispatcher_stats,
            })
        for app_key, handler in self.app_handlers.items():
            for flow_id, route in handler.flow_routes.items():
                listeners.append({
                    'tenant_id': handler.tenant_id,
                    'flow_id': flow_id,
                    'attachment': 'application',
                    'app_id': handler.app_id,
                    **self._describe_route(route),
                    'dispatcher': dispatcher_stats,
                })
        return listeners


# Global MQTT listener instance
mqtt_listener_service = MqttListenerService()

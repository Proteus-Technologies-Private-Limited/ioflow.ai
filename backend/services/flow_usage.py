"""Usage and cost of the external APIs a flow calls — metered per run, per step.

A connector service declares what its responses cost in
``response_config.usage`` (data in the seed application, never code):

    "usage": {
      "currency": "USD",
      "price_note": "X API pay-per-use list price, Oct 2026",
      "meters": [
        {"meter": "post_read", "label": "Posts read", "unit": "post",
         "count": "data", "price": {"amount": 0.005, "per": 1}},
        {"meter": "input_tokens", "label": "Input tokens", "unit": "token",
         "value": "usage.input_tokens", "dimension_path": "model",
         "price": {"per": 1000000, "by": {"claude-sonnet-5-5": 2.0}}}
      ]
    }

- ``count`` — a dotted path in the response body; the quantity is the
  length of the list there (posts returned, users expanded), or 1 for a
  single object (one user looked up).
- ``value`` — a dotted path to a number (tokens used).
- ``dimension_path`` — what the price depends on (the model that answered);
  ``price.by`` maps it to an amount, ``price.amount`` is the flat / fallback one.

A tenant whose contract differs puts its own prices on the CONNECTION:
``subscription_config.usage_prices = {"<meter>": {"amount"|"by"|"per": …}}``
(merged over the connector's). Every row stores the price it was costed at, so
a later price change never rewrites history.

Recording happens where every HTTP response is already logged
(``ApiCallExecutor._log_http_response``) and only for 2xx answers of a REAL
execution — a direct "test this service" call has no execution row and
records nothing. Metering must never break a run: every failure here is
logged and swallowed.

Rows live in ``flow_usage`` BESIDE ``flow_executions`` — the schema the
FlowExecution model names (``ioflow`` on PostgreSQL, where every tenant's
flows and runs are stored and told apart by tenant id), else the tenant
schema. Created on first use (existence is checked first: the runtime role
may not own the schema). Days are UTC days.
A connector's ``price_note`` (what the price is, where it comes from, what the
estimate cannot see) is shown beside the figures.

A flow may carry ``flow_definition.settings.budget = {"daily": 5.0}``: once a
UTC day's recorded cost reaches it, new runs — and further metered calls of a
run already going — stop with a plain reason until the next UTC day.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from db.database import get_tenant_db
from db.db_compat import is_sqlite

logger = logging.getLogger(__name__)

TABLE = "flow_usage"
_SCHEMA_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,63}$")
_ready: set = set()
_ready_lock = threading.Lock()


class BudgetReached(RuntimeError):
    """A flow's daily budget is used up."""


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

def _store_schema(schema: str) -> str:
    """The schema that holds flow_executions — where usage rows must live, so the
    INSERT … SELECT finds the run (the engine's tenant schema may hold none)."""
    try:
        from db.models import FlowExecution
        return getattr(FlowExecution.__table__, "schema", None) or schema
    except Exception:  # noqa: BLE001 - fall back to the caller's schema
        return schema


def _qualified(schema: str) -> str:
    if is_sqlite:
        return TABLE
    if not schema or not _SCHEMA_RE.match(schema):
        raise ValueError(f"Not a tenant schema name: {schema!r}")
    return f'"{schema}".{TABLE}'


def ensure_table(schema: str) -> str:
    """Create ``flow_usage`` beside flow_executions if it is missing; return its name."""
    schema = _store_schema(schema)
    name = _qualified(schema)
    if schema in _ready:
        return name
    with _ready_lock:
        if schema in _ready:
            return name
        with get_tenant_db(schema) as db:
            if is_sqlite:
                exists = db.execute(text(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :t"), {"t": TABLE}).first()
            else:
                exists = db.execute(text(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = :t"),
                    {"s": schema, "t": TABLE}).first()
            if not exists:
                db.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {name} (
                        usage_id VARCHAR(36) PRIMARY KEY,
                        execution_id VARCHAR(36) NOT NULL,
                        flow_id VARCHAR(36),
                        node_id VARCHAR(100),
                        app_id VARCHAR(36),
                        app_name VARCHAR(255),
                        service_name VARCHAR(255),
                        meter VARCHAR(64) NOT NULL,
                        label VARCHAR(255),
                        unit VARCHAR(64),
                        dimension VARCHAR(128),
                        quantity NUMERIC(20, 4) NOT NULL,
                        unit_amount NUMERIC(20, 10),
                        price_per NUMERIC(20, 4),
                        cost NUMERIC(20, 8),
                        currency VARCHAR(8),
                        price_source VARCHAR(16),
                        recorded_at TIMESTAMP NOT NULL
                    )"""))
                idx = "" if is_sqlite else f'"{schema}".'
                db.execute(text(f"CREATE INDEX IF NOT EXISTS idx_flow_usage_flow_time ON {name} (flow_id, recorded_at)"))
                db.execute(text(f"CREATE INDEX IF NOT EXISTS idx_flow_usage_execution ON {name} (execution_id)"))
                db.commit()
                logger.info("Created %s%s", idx, TABLE)
        _ready.add(schema)
    return name


# ---------------------------------------------------------------------------
# Reading a response
# ---------------------------------------------------------------------------

def _get(body: Any, path: str) -> Any:
    cur = body
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _num(v: Any) -> float:
    if isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return 0.0


def _merge_price(base: Optional[dict], override: Optional[dict]) -> Optional[dict]:
    if not isinstance(override, dict):
        return base if isinstance(base, dict) else None
    merged = dict(base or {})
    for k, v in override.items():
        if k == "by" and isinstance(v, dict):
            merged["by"] = dict(merged.get("by") or {}, **v)
        else:
            merged[k] = v
    return merged


def price_of(price: Optional[dict], dimension: str) -> tuple[Optional[float], float]:
    """(amount per ``per`` units, per) for a dimension; amount None = unpriced."""
    if not isinstance(price, dict):
        return None, 1.0
    per = _num(price.get("per")) or 1.0
    by = price.get("by") or {}
    if dimension and isinstance(by, dict) and dimension in by:
        return _num(by[dimension]), per
    if price.get("amount") is not None:
        return _num(price.get("amount")), per
    return None, per


def measure(usage_cfg: dict, body: Any, overrides: Optional[dict] = None) -> List[dict]:
    """The metered quantities of one response, priced. Pure — used by tests."""
    if not isinstance(usage_cfg, dict) or not isinstance(body, dict):
        return []
    currency = str(usage_cfg.get("currency") or "USD")
    overrides = overrides if isinstance(overrides, dict) else {}
    out = []
    for m in usage_cfg.get("meters") or []:
        if not isinstance(m, dict) or not m.get("meter"):
            continue
        if m.get("count"):
            got = _get(body, m["count"])
            # A list counts its items; a single object (a one-user lookup) is one.
            qty = float(len(got)) if isinstance(got, list) else (1.0 if isinstance(got, dict) else 0.0)
        else:
            qty = _num(_get(body, m.get("value")))
        if qty <= 0:
            continue
        dimension = str(_get(body, m["dimension_path"]) or "") if m.get("dimension_path") else ""
        override = overrides.get(m["meter"])
        price = _merge_price(m.get("price"), override)
        amount, per = price_of(price, dimension)
        out.append({
            "meter": str(m["meter"])[:64], "label": str(m.get("label") or m["meter"])[:255],
            "unit": str(m.get("unit") or "")[:64], "dimension": dimension[:128], "quantity": qty,
            "unit_amount": amount, "price_per": per,
            "cost": (qty / per * amount) if amount is not None else None,
            "currency": currency[:8],
            "price_source": "none" if amount is None else ("connection" if isinstance(override, dict) else "connector"),
        })
    return out


def record_response(context: Optional[dict], service_config: Optional[dict], body: Any, status_code: Any) -> None:
    """Meter one HTTP answer of a flow step. Never raises."""
    try:
        if not context or not context.get("execution_id") or not isinstance(service_config, dict):
            return
        if not (isinstance(status_code, int) and 200 <= status_code < 300):
            return
        usage_cfg = (service_config.get("response_config") or {}).get("usage")
        rows = measure(usage_cfg, body, service_config.get("usage_price_overrides"))
        schema = context.get("schema_name") or context.get("tenant_schema")
        if not rows or not schema or schema == "public":
            return
        insert_rows(schema, str(context["execution_id"]), context.get("current_node_id"), service_config, rows,
                    datetime.now(timezone.utc).replace(tzinfo=None))
    except Exception as exc:  # noqa: BLE001 - metering must never fail a run
        logger.warning("Could not record usage for execution %s: %s",
                       (context or {}).get("execution_id"), exc)


def insert_rows(schema: str, execution_id: str, node_id: Optional[str], service_config: dict,
                rows: List[dict], recorded_at: datetime) -> int:
    """Write measured rows for one call; returns how many were written."""
    name = ensure_table(schema)
    schema = _store_schema(schema)
    executions = "flow_executions" if is_sqlite else f'"{schema}".flow_executions'
    written = 0
    with get_tenant_db(schema) as db:
        for r in rows:
            # INSERT … SELECT: only a real execution is metered, and the flow id
            # comes from the execution row, never from the caller.
            written += db.execute(text(f"""
                INSERT INTO {name} (usage_id, execution_id, flow_id, node_id, app_id, app_name, service_name,
                    meter, label, unit, dimension, quantity, unit_amount, price_per, cost, currency,
                    price_source, recorded_at)
                SELECT :usage_id, fe.execution_id, fe.flow_id, :node_id, :app_id, :app_name, :service_name,
                    :meter, :label, :unit, :dimension, :quantity, :unit_amount, :price_per, :cost, :currency,
                    :price_source, :recorded_at
                FROM {executions} fe WHERE fe.execution_id = :execution_id"""), dict(
                r, usage_id=str(uuid.uuid4()), execution_id=execution_id,
                node_id=str(node_id or "")[:100],
                app_id=str(service_config.get("app_id") or "")[:36] or None,
                app_name=str(service_config.get("app_name") or "")[:255] or None,
                service_name=str(service_config.get("service_name") or "")[:255] or None,
                recorded_at=recorded_at)).rowcount or 0
        db.commit()
    return written


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def budget_of(flow_definition: Optional[dict]) -> Optional[dict]:
    b = ((flow_definition or {}).get("settings") or {}).get("budget")
    if isinstance(b, dict) and _num(b.get("daily")) > 0:
        return {"daily": _num(b["daily"]), "currency": str(b.get("currency") or "USD")}
    return None


def _day_start(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def spent_today(schema: str, flow_id: str) -> float:
    name = ensure_table(schema)
    with get_tenant_db(schema) as db:
        v = db.execute(text(f"SELECT COALESCE(SUM(cost), 0) FROM {name} WHERE flow_id = :f AND recorded_at >= :d"),
                       {"f": flow_id, "d": _day_start()}).scalar()
    return float(v or 0)


def check_budget(schema: str, flow_id: Optional[str], budget: Optional[dict]) -> None:
    """Raise BudgetReached when today's recorded cost has reached the budget."""
    if not budget or not flow_id or not schema:
        return
    try:
        spent = spent_today(schema, flow_id)
    except Exception as exc:  # noqa: BLE001 - an unreadable meter must not stop a flow
        logger.warning("Budget check skipped for flow %s: %s", flow_id, exc)
        return
    if spent >= budget["daily"]:
        raise BudgetReached(
            f"Daily budget reached: {budget['currency']} {spent:.2f} of {budget['daily']:.2f} spent today (UTC). "
            "Runs resume after midnight UTC, or raise the budget.")


# ---------------------------------------------------------------------------
# Summary for the flow owner
# ---------------------------------------------------------------------------

def _day_expr() -> str:
    return "date(recorded_at)" if is_sqlite else "CAST(date_trunc('day', recorded_at) AS DATE)"


def summary(schema: str, flow_id: str, flow_definition: Optional[dict] = None,
            days: int = 30, runs: int = 20) -> Dict[str, Any]:
    """What a flow's external calls used and cost: totals, per day, per step
    and meter, and per run (latest first)."""
    days = max(1, min(int(days or 30), 366))
    runs = max(0, min(int(runs or 20), 200))
    name = ensure_table(schema)
    since = _day_start() - timedelta(days=days - 1)
    labels = {n.get("id"): (n.get("data") or {}).get("label") or n.get("id")
              for n in (flow_definition or {}).get("nodes") or [] if isinstance(n, dict)}
    params = {"f": flow_id, "since": since}
    with get_tenant_db(schema) as db:
        by_day = [{"day": str(d), "cost": float(c or 0), "unpriced": int(u or 0)} for d, c, u in db.execute(text(f"""
            SELECT {_day_expr()} AS day, SUM(cost), SUM(CASE WHEN cost IS NULL THEN 1 ELSE 0 END)
            FROM {name} WHERE flow_id = :f AND recorded_at >= :since GROUP BY 1 ORDER BY 1"""), params)]
        by_step = [{
            "node_id": n, "label": labels.get(n, n), "app_name": a, "service_name": s, "meter": m,
            "meter_label": ml, "unit": un, "dimension": dim or "", "quantity": float(q or 0),
            "cost": float(c) if c is not None else None, "calls_metered": int(k or 0),
        } for n, a, s, m, ml, un, dim, q, c, k in db.execute(text(f"""
            SELECT node_id, MAX(app_name), MAX(service_name), meter, MAX(label), MAX(unit), dimension,
                   SUM(quantity), SUM(cost), COUNT(*)
            FROM {name} WHERE flow_id = :f AND recorded_at >= :since
            GROUP BY node_id, meter, dimension ORDER BY SUM(cost) DESC"""), params)]
        run_rows = db.execute(text(f"""
            SELECT execution_id, MIN(recorded_at), SUM(cost), SUM(CASE WHEN cost IS NULL THEN 1 ELSE 0 END)
            FROM {name} WHERE flow_id = :f AND recorded_at >= :since
            GROUP BY execution_id ORDER BY MIN(recorded_at) DESC LIMIT :n"""), dict(params, n=runs)).fetchall()
        run_meters: dict = {}
        if run_rows:
            ids = [r[0] for r in run_rows]
            marks = ", ".join(f":x{i}" for i in range(len(ids)))
            for x, m, ml, un, q, c in db.execute(text(f"""
                SELECT execution_id, meter, MAX(label), MAX(unit), SUM(quantity), SUM(cost)
                FROM {name} WHERE execution_id IN ({marks}) GROUP BY execution_id, meter"""),
                    {f"x{i}": v for i, v in enumerate(ids)}):
                run_meters.setdefault(x, []).append({"meter": m, "label": ml, "unit": un, "quantity": float(q or 0),
                                                      "cost": float(c) if c is not None else None})
        currency = db.execute(text(f"SELECT MAX(currency) FROM {name} WHERE flow_id = :f"), {"f": flow_id}).scalar()
        notes = _price_notes(db, name, flow_id) if by_step else []
    today = str(_day_start().date())
    total = sum(d["cost"] for d in by_day)
    budget = budget_of(flow_definition)
    today_cost = next((d["cost"] for d in by_day if d["day"] == today), 0.0)
    week = [d["cost"] for d in by_day if d["day"] >= str((_day_start() - timedelta(days=6)).date())]
    return {
        "flow_id": flow_id, "currency": currency or (budget or {}).get("currency") or "USD",
        "days": days, "since": str(since.date()), "today": today,
        "total_cost": total, "today_cost": today_cost, "last_7_days_cost": sum(week),
        "has_unpriced": any(d["unpriced"] for d in by_day),
        "budget": dict(budget, spent_today=today_cost, reached=today_cost >= budget["daily"]) if budget else None,
        "by_day": by_day, "by_step": by_step,
        "runs": [{"execution_id": x, "started_at": t.isoformat() if hasattr(t, "isoformat") else str(t),
                  "cost": float(c or 0), "unpriced": int(u or 0), "meters": run_meters.get(x, [])}
                 for x, t, c, u in run_rows],
        "basis": "Estimated from each call's response and the connector's list prices (or the connection's own "
                 "prices). Days are UTC.",
        "price_notes": notes,
    }


def _price_notes(db, name: str, flow_id: str) -> List[dict]:
    """Each metered connector service's own ``price_note``."""
    services = "application_services" if is_sqlite else "ioflow.application_services"
    out, seen = [], set()
    for app_id, service_name, app_name in db.execute(text(
            f"SELECT DISTINCT app_id, service_name, app_name FROM {name} WHERE flow_id = :f"), {"f": flow_id}):
        if not app_id or (app_id, service_name) in seen:
            continue
        seen.add((app_id, service_name))
        cfg = db.execute(text(f"SELECT response_config FROM {services} WHERE app_id = :a AND service_name = :s"),
                         {"a": app_id, "s": service_name}).scalar()
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except ValueError:
                cfg = None
        note = ((cfg or {}).get("usage") or {}).get("price_note") if isinstance(cfg, dict) else None
        if note and all(n["note"] != note for n in out):
            out.append({"app_name": app_name, "note": note})
    return out

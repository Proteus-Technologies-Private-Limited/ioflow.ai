"""Meter flow runs that happened before usage metering existed.

Every external call's answer is already in ``execution_logs`` (message
``API Response: …``, data ``{status_code, body}``). For each run with no
``flow_usage`` rows yet, this measures those answers with the connector's
CURRENT ``response_config.usage`` (and the connection's own ``usage_prices``)
and records them at the time the answer was logged. A run already metered is
skipped, so the script can be re-run.

Update the installed connectors first (Seed applications → Update, or
``POST /api/v1/seed-applications/<key>/update``): a service whose stored
response_config has no ``usage`` block meters nothing.

    cd backend && ../venv/bin/python scripts/backfill_flow_usage.py [--flow FLOW_ID] [--days 30] [--dry-run]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from db.database import engine  # noqa: E402
from db.db_compat import is_sqlite  # noqa: E402
from services import flow_usage  # noqa: E402


def _json(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return {}
    return v or {}


def tenant_schemas(conn) -> list:
    if is_sqlite:
        return ["default"]
    return [r[0] for r in conn.execute(text(
        "SELECT table_schema FROM information_schema.tables WHERE table_name = 'flow_executions' ORDER BY 1"))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--flow", help="only this flow id")
    ap.add_argument("--schema", help="only this tenant schema")
    ap.add_argument("--days", type=int, default=30, help="runs started in the last N days (default 30)")
    ap.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    args = ap.parse_args()
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.days)
    services = "application_services" if is_sqlite else "ioflow.application_services"
    apps = "applications" if is_sqlite else "ioflow.applications"
    subs = "application_subscriptions" if is_sqlite else "ioflow.application_subscriptions"

    with engine.connect() as conn:
        schemas = [args.schema] if args.schema else tenant_schemas(conn)
        svc_cache: dict = {}

        def service(service_id: str = None, app_id: str = None, service_name: str = None):
            key = service_id or (app_id, service_name)
            if key not in svc_cache:
                where, params = (("s.service_id = :i", {"i": service_id}) if service_id else
                                 ("s.app_id = :a AND s.service_name = :n", {"a": app_id, "n": service_name}))
                svc_cache[key] = conn.execute(text(
                    f"SELECT s.service_name, s.response_config, s.app_id, a.app_name FROM {services} s "
                    f"JOIN {apps} a ON a.app_id = s.app_id WHERE {where}"), params).first()
            return svc_cache[key]

        totals = {"runs": 0, "calls": 0, "rows": 0, "cost": 0.0}
        for schema in schemas:
            q = lambda t: t if is_sqlite else f'"{schema}".{t}'  # noqa: E731
            flow_filter = "AND fe.flow_id = :flow" if args.flow else ""
            runs = conn.execute(text(f"""
                SELECT fe.execution_id, fe.flow_id, f.flow_definition, f.tenant_id
                FROM {q('flow_executions')} fe JOIN {q('flows')} f ON f.flow_id = fe.flow_id
                WHERE fe.started_at >= :since {flow_filter}"""),
                {"since": since, "flow": args.flow}).fetchall()
            if not runs:
                continue
            table = flow_usage.ensure_table(schema) if not args.dry_run else None
            for execution_id, flow_id, definition, tenant_id in runs:
                if table and conn.execute(text(f"SELECT 1 FROM {table} WHERE execution_id = :x LIMIT 1"),
                                          {"x": execution_id}).first():
                    continue
                nodes = {n.get("id"): (n.get("data") or {}) for n in (_json(definition).get("nodes") or [])}
                logs = conn.execute(text(f"""
                    SELECT step_id, timestamp, data FROM {q('execution_logs')}
                    WHERE execution_id = :x AND message LIKE 'API Response%' ORDER BY timestamp"""),
                    {"x": execution_id}).fetchall()
                # A step that is no longer in the flow is still named in the run's
                # own "Executing action node" log (app_id + service).
                called = {}
                for step_id, data in conn.execute(text(f"""
                        SELECT step_id, data FROM {q('execution_logs')}
                        WHERE execution_id = :x AND message LIKE 'Executing action node%'"""), {"x": execution_id}):
                    d = _json(data)
                    if d.get("app_id") and d.get("service"):
                        called.setdefault(step_id, (d["app_id"], d["service"]))
                metered = False
                for step_id, ts, data in logs:
                    node = nodes.get(step_id) or {}
                    if node.get("serviceId"):
                        svc = service(service_id=node["serviceId"])
                    elif step_id in called:
                        svc = service(app_id=called[step_id][0], service_name=called[step_id][1])
                    else:
                        svc = None
                    if not svc:
                        continue
                    service_name, response_config, app_id, app_name = svc
                    usage_cfg = _json(response_config).get("usage")
                    if not usage_cfg:
                        continue
                    data = _json(data)
                    status = data.get("status_code")
                    if not (isinstance(status, int) and 200 <= status < 300):
                        continue
                    sub_cfg = conn.execute(text(
                        f"SELECT subscription_config FROM {subs} WHERE app_id = :a AND tenant_id = :t"),
                        {"a": app_id, "t": tenant_id}).scalar()
                    rows = flow_usage.measure(usage_cfg, data.get("body"), _json(sub_cfg).get("usage_prices"))
                    if not rows:
                        continue
                    totals["calls"] += 1
                    totals["cost"] += sum(r["cost"] or 0 for r in rows)
                    metered = True
                    if args.dry_run:
                        totals["rows"] += len(rows)
                    else:
                        totals["rows"] += flow_usage.insert_rows(
                            schema, execution_id, step_id,
                            {"app_id": app_id, "app_name": app_name, "service_name": service_name}, rows, ts)
                totals["runs"] += 1 if metered else 0
                if metered:
                    print(f"{schema} flow {flow_id} run {execution_id}: metered")
    verb = "would write" if args.dry_run else "wrote"
    print(f"{totals['runs']} runs, {totals['calls']} metered calls, {verb} {totals['rows']} rows, "
          f"estimated cost {totals['cost']:.4f}")


if __name__ == "__main__":
    main()

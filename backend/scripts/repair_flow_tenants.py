#!/usr/bin/env python3
"""Move flows stored under tenant "default" to the tenant of the user who saved them.

The MCP bridge's ``create_or_update_flow`` used to read a flat ``tenant_id``
from ``/api/v1/auth/me``, which nests it (``tenant.tenant_id``), and fell back
to ``"default"``. Every flow an agent saved with a token therefore belonged to
no tenant: its owner could neither open nor delete it. The tool no longer has
a fallback; this script repairs the rows it already wrote.

A flow is moved to ``users.tenant_id`` of its ``created_by``. A flow whose
creator is unknown (``mcp_service`` or a deleted user) is listed and left
alone — guessing its owner would hand it to the wrong tenant.

Usage (from backend/):
    python scripts/repair_flow_tenants.py           # dry run: what would move
    python scripts/repair_flow_tenants.py --apply   # move them
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from sqlalchemy import text  # noqa: E402

from db.database import engine  # noqa: E402
from db.db_compat import table_ref  # noqa: E402

UNPLACED = ("default", "")


def main(apply: bool) -> int:
    flows, users = table_ref("flows"), table_ref("users")
    try:
        with engine.begin() as conn:
            rows = conn.execute(text(
                f"SELECT f.flow_id, f.flow_name, f.created_by, u.tenant_id, u.email "
                f"FROM {flows} f LEFT JOIN {users} u ON u.user_id = f.created_by "
                f"WHERE f.tenant_id IS NULL OR f.tenant_id = :d OR f.tenant_id = :e"
            ), {"d": UNPLACED[0], "e": UNPLACED[1]}).fetchall()
            movable = [r for r in rows if r.tenant_id]
            orphans = [r for r in rows if not r.tenant_id]
            for r in movable:
                print(f"{'MOVE' if apply else 'would move'}  {r.flow_id}  {r.flow_name!r}  "
                      f"-> tenant {r.tenant_id} ({r.email})")
            for r in orphans:
                print(f"LEFT        {r.flow_id}  {r.flow_name!r}  creator {r.created_by!r} is not a user")
            if apply:
                for r in movable:
                    conn.execute(text(f"UPDATE {flows} SET tenant_id = :t WHERE flow_id = :f"),
                                 {"t": r.tenant_id, "f": r.flow_id})
    except Exception as exc:  # noqa: BLE001
        print(f"repair failed, nothing changed: {exc}", file=sys.stderr)
        return 1
    print(f"\n{len(movable)} flow(s) {'moved' if apply else 'to move'}, "
          f"{len(orphans)} left (unknown creator)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv[1:]))

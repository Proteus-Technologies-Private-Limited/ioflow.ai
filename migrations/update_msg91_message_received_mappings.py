#!/usr/bin/env python3
"""Update installed MSG91 WhatsApp `message_received` event parameter mappings.

The seed app's `message_received` output_schema was originally written for a
Meta/WhatsApp-Cloud-style flat payload ($.from, $.to, $.text.body, ...). MSG91's
real "Inbound Request" webhook uses different field names (customerNumber,
integratedNumber, text, customerName, contentType, ts, ...). Installed apps store
their own copy of `output_schema` in the `application_events` table and the
execution engine extracts trigger parameters from THAT copy at runtime — so
fixing the seed JSON alone does not update already-installed apps.

This migration copies the corrected `output_schema` from the seed file
(backend/seed-applications/msg91_whatsapp.json) into every installed
`message_received` event belonging to a MSG91 WhatsApp app (seed_key =
'msg91_whatsapp'). The previous output_schema values are backed up to
backup-files/db/ before changes are applied.

Usage:
  python3 migrations/update_msg91_message_received_mappings.py            # dry-run
  python3 migrations/update_msg91_message_received_mappings.py --apply    # write
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = "/opt/ioflow/backend/ioflow.db"
PROJECT_ROOT = Path("/opt/ioflow")
SEED_FILE = PROJECT_ROOT / "backend" / "seed-applications" / "msg91_whatsapp.json"
BACKUP_DIR = PROJECT_ROOT / "backup-files" / "db"
SEED_KEY = "msg91_whatsapp"
EVENT_NAME = "message_received"


def load_new_output_schema() -> dict:
    seed = json.loads(SEED_FILE.read_text())
    for ev in seed.get("events", []):
        if ev.get("event_name") == EVENT_NAME:
            return ev["output_schema"]
    raise SystemExit(f"Could not find '{EVENT_NAME}' event in {SEED_FILE}")


def main() -> None:
    apply = "--apply" in sys.argv
    new_schema = load_new_output_schema()
    new_schema_json = json.dumps(new_schema)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT e.event_id, e.app_id, e.output_schema, a.app_name
        FROM application_events e
        JOIN applications a ON a.app_id = e.app_id
        WHERE a.seed_key = ? AND e.event_name = ?
        """,
        (SEED_KEY, EVENT_NAME),
    ).fetchall()

    if not rows:
        print(f"No installed '{EVENT_NAME}' events found for seed_key='{SEED_KEY}'. Nothing to do.")
        return

    print(f"Found {len(rows)} installed '{EVENT_NAME}' event(s) for MSG91 WhatsApp apps.")
    print(f"Mode: {'APPLY (writing changes)' if apply else 'DRY-RUN (no changes written)'}\n")

    backup = {}
    changed = 0
    for r in rows:
        cur = r["output_schema"]
        cur_norm = json.dumps(json.loads(cur)) if isinstance(cur, str) and cur else json.dumps(cur)
        if cur_norm == new_schema_json:
            print(f"  [skip] app {r['app_id']} event {r['event_id']} already up to date")
            continue
        changed += 1
        backup[r["event_id"]] = {"app_id": r["app_id"], "old_output_schema": cur}
        old_maps = {}
        try:
            old_maps = (json.loads(cur) if isinstance(cur, str) else (cur or {})).get(
                "parameter_extraction", {}
            ).get("mappings", {})
        except Exception:
            pass
        print(f"  [update] app {r['app_id']} ({r['app_name']}) event {r['event_id']}")
        print(f"           old mappings: {old_maps or '{}'}")
        if apply:
            conn.execute(
                "UPDATE application_events SET output_schema = ? WHERE event_id = ?",
                (new_schema_json, r["event_id"]),
            )

    if apply and changed:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bpath = BACKUP_DIR / f"msg91_message_received_output_schema_{ts}.json"
        bpath.write_text(json.dumps(backup, indent=2))
        conn.commit()
        print(f"\nApplied {changed} update(s). Previous values backed up to:\n  {bpath}")
    elif not apply and changed:
        print(f"\n{changed} event(s) would be updated. Re-run with --apply to write changes.")
    else:
        print("\nAll events already up to date.")

    conn.close()


if __name__ == "__main__":
    main()

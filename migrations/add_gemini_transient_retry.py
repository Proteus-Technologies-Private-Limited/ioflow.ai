#!/usr/bin/env python3
"""Apply generic transient-failure retry config to the Google Gemini services.

Root cause addressed:
    The Gemini ``generate_content`` (and ``upload_file``) calls intermittently
    return HTTP 503 "This model is currently experiencing high demand ...".
    The api_call executor previously had no transient-retry on returned status
    codes (only on network exceptions), so a single overload response aborted
    the entire flow execution.

This migration merges a ``retry_config`` block into the ``response_config`` of
the existing Gemini ``generate_content`` and ``upload_file`` service rows so the
executor (services/service_executors.py::_request_with_transient_retry) retries
transient upstream failures with an escalating backoff bounded by a 2-minute
wall-clock window. The retry_config values are read from the seed JSON
(backend/seed-applications/google_gemini.json) so the seed remains the single
source of truth.

It also bumps the Google Gemini application version to match the seed (2.7.0).

Idempotent: re-running only refreshes the retry_config / version to the seed
values. A timestamped backup of the prior response_config rows is written to
backup-files/db/ before any change.

Run:  python3 migrations/add_gemini_transient_retry.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = "/opt/ioflow/backend/ioflow.db"
PROJECT_ROOT = Path("/opt/ioflow")
SEED_PATH = PROJECT_ROOT / "backend" / "seed-applications" / "google_gemini.json"
BACKUP_DIR = PROJECT_ROOT / "backup-files" / "db"

GEMINI_APP_NAME = "Google Gemini"
TARGET_SERVICES = ("generate_content", "upload_file")


def _loads_maybe_double(raw):
    """Parse a JSON column that may be single- or double-serialized."""
    if raw is None:
        return {}
    value = raw
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        value = json.loads(value)
    # Handle accidental double-encoding (a JSON string of a JSON object)
    if isinstance(value, str):
        value = json.loads(value)
    return value or {}


def main() -> int:
    if not Path(DB_PATH).exists():
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 1
    if not SEED_PATH.exists():
        print(f"ERROR: seed file not found at {SEED_PATH}", file=sys.stderr)
        return 1

    seed = json.loads(SEED_PATH.read_text())
    seed_version = seed["application"]["version"]
    # Map service_name -> retry_config from the seed
    seed_retry = {}
    for svc in seed.get("services", []):
        rc = (svc.get("response_config") or {}).get("retry_config")
        if svc.get("service_name") in TARGET_SERVICES and rc:
            seed_retry[svc["service_name"]] = rc

    missing = [s for s in TARGET_SERVICES if s not in seed_retry]
    if missing:
        print(f"ERROR: seed missing retry_config for: {missing}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        app_row = conn.execute(
            "SELECT app_id, version FROM applications WHERE app_name = ?",
            (GEMINI_APP_NAME,),
        ).fetchone()
        if not app_row:
            print(f"ERROR: application '{GEMINI_APP_NAME}' not found", file=sys.stderr)
            return 1
        app_id = app_row["app_id"]

        rows = conn.execute(
            "SELECT service_id, service_name, response_config FROM application_services "
            "WHERE app_id = ? AND service_name IN (?, ?)",
            (app_id, *TARGET_SERVICES),
        ).fetchall()
        found = {r["service_name"]: r for r in rows}

        not_in_db = [s for s in TARGET_SERVICES if s not in found]
        if not_in_db:
            print(f"WARNING: services not present in DB (skipped): {not_in_db}")

        # Backup prior response_config for the affected rows
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"google_gemini_services_response_config_{ts}.json"
        backup_payload = {
            "db_path": DB_PATH,
            "app_id": app_id,
            "prior_app_version": app_row["version"],
            "services": {
                r["service_name"]: {
                    "service_id": r["service_id"],
                    "response_config": r["response_config"],
                }
                for r in rows
            },
        }
        backup_path.write_text(json.dumps(backup_payload, indent=2))
        print(f"Backed up prior config to {backup_path}")

        updated = []
        for name, row in found.items():
            rc = _loads_maybe_double(row["response_config"])
            if not isinstance(rc, dict):
                rc = {}
            before = json.dumps(rc.get("retry_config"), sort_keys=True)
            rc["retry_config"] = seed_retry[name]
            after = json.dumps(rc.get("retry_config"), sort_keys=True)
            conn.execute(
                "UPDATE application_services SET response_config = ? WHERE service_id = ?",
                (json.dumps(rc), row["service_id"]),
            )
            status = "unchanged" if before == after else "updated"
            updated.append((name, status))
            print(f"  {name}: retry_config {status}")

        # Bump application version to match the seed
        conn.execute(
            "UPDATE applications SET version = ? WHERE app_id = ?",
            (seed_version, app_id),
        )
        print(f"Application version: {app_row['version']} -> {seed_version}")

        conn.commit()
        print(f"\nDone. {len(updated)} service row(s) processed.")
        print("NOTE: restart the backend for executor code changes to take effect "
              "(no hot reload).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

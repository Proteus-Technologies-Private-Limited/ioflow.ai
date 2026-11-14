#!/usr/bin/env python3
"""
Migration: Clear `seed_key` on non-canonical application instances

Problem
-------
`seed_key` is meant to uniquely identify the ONE canonical (global) seed
application for a connector — e.g. `google_drive` -> the "Google Drive" seed
app. Flow import resolves a node's `_seed_key` to a local app_id by building a
`{seed_key: app_id}` map across ALL applications.

When a user creates a tenant/global *instance* of a seed app (the
"create custom app" flow), the instance inherited the parent's `seed_key`.
That produced multiple application rows sharing one seed_key. Because the
import resolver overwrites on collision ("last row wins"), `_seed_key` could
resolve to an instance the importing tenant is NOT subscribed to (often an
orphan instance with zero subscriptions), so the import screen wrongly showed
the app as "Not Subscribed" and asked the user to set it up again.

Concrete case that triggered this: three rows carried seed_key `google_drive`
(the canonical "Google Drive" plus two instances named "Mohammed"); the
resolver picked an unsubscribed instance and flagged Google Drive as missing.

Fix
---
A `seed_key` belongs ONLY to the canonical seed app (`is_seed_app = 1`,
`parent_seed_app_id IS NULL`). Instances are identified by
`parent_seed_app_id` and `is_seed_app = 0`. This migration clears `seed_key`
on every application row that is an instance (has a non-null
`parent_seed_app_id` and is not itself a seed app) so each seed_key maps to
exactly one canonical app_id again.

Safety
------
* Only nulls a row's seed_key when a canonical `is_seed_app = 1` row with the
  SAME seed_key exists — never orphans a seed_key.
* Backs up every affected (app_id, app_name, seed_key) to a timestamped JSON
  under backup-files/ before writing, so the change is fully revertible.
* Idempotent: re-running finds nothing to do.
* Instances are referenced at execution/import time by app_id /
  parent_seed_app_id / instance_number, NOT by seed_key, so clearing seed_key
  on instances does not affect their own flows.

The DB path is resolved from settings / backend/.env (never hardcoded).
"""

import sqlite3
import os
import sys
import json
import datetime


def _resolve_db_path():
    db_url = None
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
        from core.config import settings
        db_url = settings.database_url
    except Exception:
        pass

    if not db_url:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
                        break

    if not db_url or not db_url.startswith('sqlite'):
        return None
    return db_url.split('sqlite:///', 1)[1]


def migrate():
    db_path = _resolve_db_path()
    if not db_path:
        print("Could not resolve a SQLite DATABASE_URL from settings/.env")
        return False
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Canonical seed apps own the seed_key.
        canonical_keys = {
            r['seed_key']
            for r in cursor.execute(
                "SELECT DISTINCT seed_key FROM applications "
                "WHERE seed_key IS NOT NULL AND is_seed_app = 1"
            ).fetchall()
        }

        # Polluting rows: instances (have a parent, not a seed app) that still
        # carry a seed_key which a canonical app owns.
        rows = cursor.execute(
            "SELECT app_id, app_name, seed_key, parent_seed_app_id, is_seed_app "
            "FROM applications "
            "WHERE seed_key IS NOT NULL "
            "AND parent_seed_app_id IS NOT NULL "
            "AND (is_seed_app IS NULL OR is_seed_app = 0)"
        ).fetchall()

        targets = [r for r in rows if r['seed_key'] in canonical_keys]

        # Defensive: instance carries a seed_key with NO canonical owner -> do
        # not touch it (nulling would lose the only mapping). Report instead.
        orphan_key_rows = [r for r in rows if r['seed_key'] not in canonical_keys]
        if orphan_key_rows:
            print("\n  WARNING: instance rows carry a seed_key with no canonical "
                  "is_seed_app=1 owner; leaving them untouched:")
            for r in orphan_key_rows:
                print(f"    - {r['app_name']!r} (app_id={r['app_id']}) seed_key={r['seed_key']}")

        if not targets:
            print("\nNo non-canonical instance rows carry a seed_key. Nothing to do.")
            conn.commit()
            return True

        # Backup before mutating.
        backup_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'backup-files', 'migrations'
        )
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'clear_seed_key_on_app_instances_{stamp}.json')
        with open(backup_path, 'w') as f:
            json.dump(
                [{'app_id': r['app_id'], 'app_name': r['app_name'], 'seed_key': r['seed_key']}
                 for r in targets],
                f, indent=2
            )
        print(f"\nBacked up {len(targets)} affected row(s) to:\n  {backup_path}")

        print("\nClearing seed_key on the following instance rows:")
        for r in targets:
            print(f"  - {r['app_name']!r:24} app_id={r['app_id']} "
                  f"seed_key={r['seed_key']} (parent={r['parent_seed_app_id']})")

        cursor.executemany(
            "UPDATE applications SET seed_key = NULL WHERE app_id = ?",
            [(r['app_id'],) for r in targets]
        )
        conn.commit()
        print(f"\nUpdated {cursor.rowcount if cursor.rowcount != -1 else len(targets)} row(s).")

        # Verify: every remaining seed_key now maps to exactly one row.
        dups = cursor.execute(
            "SELECT seed_key, COUNT(*) n FROM applications "
            "WHERE seed_key IS NOT NULL GROUP BY seed_key HAVING n > 1"
        ).fetchall()
        if dups:
            print("\n  WARNING: seed_key collisions still remain (unexpected):")
            for r in dups:
                print(f"    - {r['seed_key']}: {r['n']} rows")
        else:
            print("\nVerified: no seed_key is shared by more than one application.")

        return True
    except Exception as e:
        conn.rollback()
        print(f"Migration failed, rolled back: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    ok = migrate()
    sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""
Migration: Add `currency` column to frontend_flow_applications

Multi-currency billing for Micro SaaS apps needs a currency stored with each
app's billing configuration. This adds a `currency` (ISO 4217) column and
backfills every existing app to a sensible default of 'USD'.

The billing ledger tables (micro_saas_billing_transactions, micro_saas_usage_logs,
micro_saas_billing_config, micro_saas_subscribers) already exist in the schema —
this migration only adds the missing app-level currency column.

The DB path is resolved from settings / backend/.env (never hardcoded), so it
targets the live database rather than the empty repo placeholder.
"""

import sqlite3
import os
import sys


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
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(frontend_flow_applications)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'currency' not in columns:
            print("Adding 'currency' column (default 'USD')...")
            cursor.execute(
                "ALTER TABLE frontend_flow_applications ADD COLUMN currency VARCHAR(3) DEFAULT 'USD'"
            )
            # Backfill any rows that came through with NULL (older SQLite versions)
            cursor.execute(
                "UPDATE frontend_flow_applications SET currency = 'USD' WHERE currency IS NULL"
            )
            print("'currency' column added and backfilled to 'USD'")
        else:
            print("'currency' column already exists")

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM frontend_flow_applications WHERE currency IS NULL")
        nulls = cursor.fetchone()[0]
        print(f"Migration completed. Rows with NULL currency remaining: {nulls}")
        return True
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

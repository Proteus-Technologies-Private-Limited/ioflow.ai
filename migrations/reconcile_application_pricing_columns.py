#!/usr/bin/env python3
"""
Reconcile the live SQLite schema with the SQLAlchemy models.

Background
----------
On some deployments, columns added to the models over time (e.g. the
enhanced-billing fields: billing_mode, is_free, currency, ...) were never
applied to the SQLite database. Any query that touches such a table then fails
with e.g.:

    sqlite3.OperationalError: no such column: application_pricing.billing_mode
    sqlite3.OperationalError: no such column: execution_cost_logs.billing_mode

This surfaces in non-obvious places -- for example deleting an application,
where SQLAlchemy cascade-loads several related tables (application_pricing,
execution_cost_logs, ...) and the generated SELECT references every mapped
column.

Rather than patch one table at a time, this migration introspects ALL mapped
models and, for every table that exists in the database, adds any column the
model declares but the table is missing. New columns are added as NULLABLE
(with the model's default when it is a simple constant) -- this is the safe
path for backfilling an existing table in SQLite, which cannot add a NOT NULL
column without a constant default. NOT NULL is still enforced by the ORM going
forward.

Idempotent and safe to re-run. Resolves the DB path from DATABASE_URL, or takes
it as the first CLI argument.
"""
import os
import sqlite3
import sys

# Make `backend` importable regardless of CWD.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))


def resolve_db_path():
    """Resolve the SQLite file path from DATABASE_URL, else backend/ioflow.db."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        try:
            from backend.core.config import settings  # type: ignore
            db_url = getattr(settings, "database_url", None)
        except Exception:
            db_url = None

    if db_url and db_url.startswith("sqlite"):
        path = db_url.split("sqlite:///", 1)[-1]  # handles 3 or 4 slashes
        if path:
            return path
    return os.path.join(ROOT, "backend", "ioflow.db")


def load_metadata():
    """Import all model modules so every table registers on Base.metadata."""
    # Importing the db package triggers `from .models import *`; also import the
    # secondary model modules so their tables register on the shared metadata.
    from backend.db.models import Base  # type: ignore  # noqa: F401
    for mod in (
        "models",
        "pricing_models",
        "application_models",
        "marketplace_models",
        "collaboration_models",
        "subscription_preferences",
        "ai_conversation_models",
        "flow_example_models",
        "google_oauth_models",
        "polling_models",
    ):
        try:
            __import__(f"backend.db.{mod}")
        except Exception as e:  # noqa: BLE001
            print(f"  (skipped backend.db.{mod}: {e})")
    return Base.metadata


def sqlite_type(column):
    """Compile a SQLAlchemy column type to its SQLite DDL string."""
    from sqlalchemy.dialects import sqlite as sqlite_dialect
    try:
        return column.type.compile(dialect=sqlite_dialect.dialect())
    except Exception:
        return "TEXT"


def literal_default(column):
    """Return a SQLite DDL default clause for a column, or '' if none/complex."""
    default = column.default
    if default is not None and not getattr(default, "is_callable", False) \
            and getattr(default, "is_scalar", False):
        val = default.arg
        if isinstance(val, bool):
            return f" DEFAULT {1 if val else 0}"
        if isinstance(val, (int, float)):
            return f" DEFAULT {val}"
        if isinstance(val, str):
            return " DEFAULT '" + val.replace("'", "''") + "'"
    server_default = column.server_default
    if server_default is not None:
        text = getattr(getattr(server_default, "arg", None), "text", None)
        if text:
            return f" DEFAULT {text}"
    return ""


def reconcile(db_path):
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False

    print(f"Using database: {db_path}")
    metadata = load_metadata()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    total_added = 0
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        live_tables = {row[0] for row in cursor.fetchall()}

        for table_name, table in metadata.tables.items():
            if table_name not in live_tables:
                continue  # don't create tables here; only reconcile existing ones

            cursor.execute(f"PRAGMA table_info('{table_name}')")
            existing = {row[1] for row in cursor.fetchall()}

            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = sqlite_type(column)
                default = literal_default(column)
                ddl = f'ALTER TABLE "{table_name}" ADD COLUMN ' \
                      f'"{column.name}" {col_type}{default}'
                try:
                    cursor.execute(ddl)
                    total_added += 1
                    print(f"  ✓ {table_name}.{column.name} ({col_type}{default})")
                except Exception as e:  # noqa: BLE001
                    print(f"  ✗ {table_name}.{column.name}: {e}")

        conn.commit()
        if total_added:
            print(f"\n✅ Added {total_added} missing column(s).")
        else:
            print("\n✅ Schema already up to date; no columns added.")
        return True
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else resolve_db_path()
    ok = reconcile(db_path)
    sys.exit(0 if ok else 1)

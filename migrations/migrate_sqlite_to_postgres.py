#!/usr/bin/env python3
"""
Migrate all IOFlow data from the SQLite database (backend/ioflow.db) to the
PostgreSQL database configured in backend/.env (DATABASE_URL).

Approach:
  - Import every model module so Base.metadata knows all PostgreSQL tables
    (they live in the 'ioflow' schema).
  - create_all() missing tables, then copy each SQLite table whose name
    matches a model table, in FK dependency order.
  - Coerce values per target column type: JSON strings -> dict/list for
    JSONB, 0/1 -> bool, ISO strings -> datetime, enum names -> enum values.
  - Chunked inserts; on a failed chunk, fall back to row-by-row and report
    skipped rows instead of aborting the whole migration.
  - Provision tenant schemas (create_schema + create_tenant_tables) for
    every migrated tenant, mirroring the app's registration path.
  - Print a source-vs-target row count report at the end.

Idempotency: tables that already contain rows in PostgreSQL are skipped.

Usage:
    venv/bin/python migrations/migrate_sqlite_to_postgres.py [--sqlite-path backend/ioflow.db]
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

CHUNK = 2000

MODEL_MODULES = [
    'db.models',
    'db.application_models',
    'db.ai_conversation_models',
    'db.collaboration_models',
    'db.documentation_models',
    'db.flow_example_models',
    'db.google_oauth_models',
    'db.marketplace_models',
    'db.polling_models',
    'db.pricing_models',
    'db.subscription_preferences',
    'db.user_settings_models',
]


def import_all_models():
    imported, failed = [], []
    for mod in MODEL_MODULES:
        try:
            __import__(mod)
            imported.append(mod)
        except Exception as e:
            failed.append((mod, str(e)))
    return imported, failed


def parse_dt(value):
    if value is None or isinstance(value, (datetime, date)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def coerce(value, col):
    """Coerce a SQLite value to what the PostgreSQL column expects."""
    if value is None:
        return None
    t = col.type
    if isinstance(t, (sa.JSON, postgresql.JSONB, postgresql.JSON)):
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                result = json.loads(s)
            except (ValueError, TypeError):
                return value  # store as a JSON string scalar
            # Unwrap double/triple-encoded JSON, but only when the inner
            # value is a dict/list — a decoded plain string stays a string.
            for _ in range(4):
                if not isinstance(result, str):
                    break
                try:
                    inner = json.loads(result)
                except (ValueError, TypeError):
                    break
                if isinstance(inner, (dict, list)):
                    result = inner
                else:
                    break
            return result
        return value
    if isinstance(t, sa.Boolean):
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 't', 'yes', 'y')
        return bool(value)
    if isinstance(t, (sa.DateTime, sa.TIMESTAMP)):
        return parse_dt(value)
    if isinstance(t, sa.Integer) and isinstance(value, str):
        s = value.strip()
        try:
            return int(s)
        except ValueError:
            return None  # corrupt source data (e.g. unresolved '{{...}}' templates)
    if isinstance(t, sa.Date):
        dt = parse_dt(value)
        return dt.date() if isinstance(dt, datetime) else dt
    if isinstance(t, sa.Enum):
        # Coerce toward the labels the PostgreSQL enum TYPE was created with
        # (t.enums) — those are names OR values depending on values_callable.
        s = str(value)
        labels = list(t.enums or [])
        if s in labels:
            return s
        enum_cls = getattr(t, 'enum_class', None)
        if enum_cls:
            for member in enum_cls:
                if s in (member.value, member.name):
                    if member.name in labels:
                        return member.name
                    if member.value in labels:
                        return member.value
        for label in labels:
            if label.lower() == s.lower():
                return label
        return s  # let the DB report it if truly invalid
    return value


def fixup_tenant(item, src):
    """Tenants with NULL email_domain (NOT NULL in PostgreSQL): derive it
    from the tenant owner's email, else a placeholder."""
    if not item.get('email_domain'):
        row = src.execute(
            "SELECT email FROM users WHERE tenant_id = ? LIMIT 1",
            (item.get('tenant_id'),)).fetchone()
        if row and row[0] and '@' in row[0]:
            item['email_domain'] = row[0].split('@')[1]
        else:
            item['email_domain'] = 'unknown.local'
    return item


def fixup_doc_page(item, src):
    """Documentation pages with NULL title/slug (NOT NULL in PostgreSQL)."""
    if not item.get('title'):
        item['title'] = item.get('page_name') or item.get('slug') or 'Untitled'
    if not item.get('slug'):
        base = str(item.get('title') or item.get('page_id') or 'untitled')
        item['slug'] = ''.join(ch if ch.isalnum() else '-' for ch in base.lower()).strip('-') or 'untitled'
    return item


FIXUPS = {
    'tenants': fixup_tenant,
    'app_documentation_pages': fixup_doc_page,
}


def migrate_subscription_preferences(src, engine):
    """tenant_subscription_preferences lives on its OWN declarative Base in
    PostgreSQL mode (public schema, UUID columns) — handle it separately."""
    try:
        from db.subscription_preferences import TenantSubscriptionPreferences
        model_table = TenantSubscriptionPreferences.__table__
        # The model's FK targets ioflow.tenants in a DIFFERENT MetaData, which
        # create_all cannot resolve — create an FK-free structural clone
        # (matches how the table exists when created by the app's migrations).
        md = sa.MetaData()
        table = sa.Table(
            model_table.name, md,
            *[sa.Column(c.name, c.type, primary_key=c.primary_key,
                        nullable=c.nullable, unique=c.unique)
              for c in model_table.columns]
        )
        table.create(bind=engine, checkfirst=True)
    except Exception as e:
        print(f"WARNING: could not create tenant_subscription_preferences: {e}")
        return ('tenant_subscription_preferences', 0, 0, 0)

    src_count = src.execute(
        'SELECT count(*) FROM tenant_subscription_preferences').fetchone()[0]
    if src_count == 0:
        return ('tenant_subscription_preferences', 0, 0, 0)

    src_cols = [r[1] for r in src.execute('PRAGMA table_info("tenant_subscription_preferences")')]
    common = [c for c in src_cols if c in table.columns]
    pks = [c.name for c in table.primary_key.columns]
    with engine.connect() as conn:
        existing = {tuple(str(v) for v in row) for row in conn.execute(
            sa.text(f'SELECT {", ".join(pks)} FROM "{table.name}"'))}

    copied = skipped = present = 0
    for row in src.execute('SELECT * FROM tenant_subscription_preferences'):
        key = tuple(str(row[p]) for p in pks)
        if key in existing:
            present += 1
            continue
        item = {c: coerce(row[c], table.columns[c]) for c in common}
        try:
            with engine.begin() as conn:
                conn.execute(table.insert(), item)
            copied += 1
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                print(f"  ROW SKIPPED in tenant_subscription_preferences: "
                      f"{str(e).splitlines()[0][:160]}")
    print(f"COPIED tenant_subscription_preferences: {copied}/{src_count - present} new"
          + (f" ({skipped} skipped)" if skipped else ""))
    return ('tenant_subscription_preferences', src_count, copied, skipped)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sqlite-path',
                        default=os.path.join(PROJECT_ROOT, 'backend', 'ioflow.db'))
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_path):
        print(f"ERROR: SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    from db.database import engine, is_sqlite, Base, create_schema, create_tenant_tables
    if is_sqlite:
        print("ERROR: DATABASE_URL points at SQLite — set it to PostgreSQL in backend/.env first.")
        sys.exit(1)

    print(f"Target : {engine.url.render_as_string(hide_password=True)}")
    print(f"Source : {args.sqlite_path}")

    imported, failed = import_all_models()
    print(f"Model modules imported: {len(imported)}; failed: {len(failed)}")
    for mod, err in failed:
        print(f"  WARNING: could not import {mod}: {err}")

    # Make sure every known table exists in PostgreSQL
    with engine.connect() as conn:
        conn.execute(sa.text('CREATE SCHEMA IF NOT EXISTS ioflow'))
        conn.commit()
    Base.metadata.create_all(bind=engine)

    src = sqlite3.connect(args.sqlite_path)
    src.row_factory = sqlite3.Row
    sqlite_tables = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    target_tables = {t.name: t for t in Base.metadata.sorted_tables}
    unmapped = sorted(sqlite_tables - set(target_tables))

    report = []          # (table, src_count, copied, skipped)
    column_notes = []

    for table in Base.metadata.sorted_tables:
        if table.name not in sqlite_tables:
            continue
        src_count = src.execute(f'SELECT count(*) FROM "{table.name}"').fetchone()[0]
        if src_count == 0:
            report.append((table.name, 0, 0, 0, 0))
            continue

        # Per-row merge: only copy rows whose primary key is not yet present
        pks = [c.name for c in table.primary_key.columns]
        existing_keys = set()
        if pks:
            with engine.connect() as conn:
                existing_keys = {tuple(str(v) for v in row) for row in conn.execute(
                    sa.text(f'SELECT {", ".join(pks)} FROM '
                            f'{table.schema or "ioflow"}."{table.name}"'))}

        src_cols = [r[1] for r in src.execute(f'PRAGMA table_info("{table.name}")')]
        common = [c for c in src_cols if c in table.columns]
        missing_in_pg = [c for c in src_cols if c not in table.columns]
        if missing_in_pg:
            column_notes.append(f"{table.name}: sqlite-only columns dropped: {missing_in_pg}")

        col_objs = {c: table.columns[c] for c in common}
        sel_cols = ', '.join(f'"{c}"' for c in common)
        cursor = src.execute(f'SELECT {sel_cols} FROM "{table.name}"')

        fixup = FIXUPS.get(table.name)
        copied = skipped = already = 0
        while True:
            rows = cursor.fetchmany(CHUNK)
            if not rows:
                break
            payload = []
            for row in rows:
                if pks and tuple(str(row[p]) for p in pks) in existing_keys:
                    already += 1
                    continue
                item = {c: coerce(row[c], col_objs[c]) for c in common}
                if fixup:
                    item = fixup(item, src)
                payload.append(item)
            if not payload:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(table.insert(), payload)
                copied += len(payload)
            except Exception:
                # Fall back row-by-row so one bad row doesn't lose the chunk
                for item in payload:
                    try:
                        with engine.begin() as conn:
                            conn.execute(table.insert(), item)
                        copied += 1
                    except Exception as row_err:
                        skipped += 1
                        if skipped <= 3:
                            msg = str(row_err).splitlines()[0][:160]
                            print(f"  ROW SKIPPED in {table.name}: {msg}")
        report.append((table.name, src_count, copied, already, skipped))
        if copied or skipped:
            print(f"COPIED {table.name}: {copied} new / {src_count} src"
                  + (f" ({already} already present)" if already else "")
                  + (f" ({skipped} skipped)" if skipped else ""))

    # Reset sequences for integer autoincrement PKs
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            for col in table.primary_key.columns:
                if isinstance(col.type, sa.Integer):
                    schema = table.schema or "ioflow"
                    seq = conn.execute(
                        sa.text("SELECT pg_get_serial_sequence(:t, :c)"),
                        {"t": f'{schema}.{table.name}', "c": col.name}).scalar()
                    if seq:
                        conn.execute(sa.text(
                            f'SELECT setval(:s, COALESCE((SELECT MAX("{col.name}") '
                            f'FROM {schema}."{table.name}"), 1))'
                        ), {"s": seq})
        conn.commit()

    # Provision tenant schemas like the registration path does
    print("\nProvisioning tenant schemas...")
    with engine.connect() as conn:
        tenants = conn.execute(sa.text(
            'SELECT tenant_id, schema_name FROM ioflow.tenants')).fetchall()
    for tenant_id, schema_name in tenants:
        if not schema_name:
            continue
        try:
            create_schema(schema_name)
            create_tenant_tables(schema_name)
        except Exception as e:
            print(f"  WARNING: tenant schema {schema_name}: {e}")
    print(f"Tenant schemas provisioned: {len(tenants)}")

    # tenant_subscription_preferences lives on its own Base — handle last
    # (needs ioflow.tenants populated for its FK)
    name, s, c, k = migrate_subscription_preferences(src, engine)
    report.append((name, s, c, 0, k))

    print("\n===== Migration report =====")
    total_src = total_new = total_present = total_skipped = 0
    for name, src_count, copied, already, skipped in report:
        total_src += src_count
        total_new += copied
        total_present += already
        total_skipped += skipped
        ok = (copied + already + skipped == src_count) and skipped == 0
        flag = "" if (ok or src_count == 0) else "  <-- CHECK"
        print(f"{name:42s} src={src_count:<8d} new={copied:<7d} "
              f"present={already:<7d} skipped={skipped}{flag}")
    print(f"{'TOTAL':42s} src={total_src:<8d} new={total_new:<7d} "
          f"present={total_present:<7d} skipped={total_skipped}")

    if unmapped:
        print("\nSQLite tables with NO matching PostgreSQL model (not copied):")
        for name in unmapped:
            n = src.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            print(f"  {name} ({n} rows)")
    for note in column_notes:
        print(f"NOTE: {note}")

    src.close()


if __name__ == '__main__':
    main()

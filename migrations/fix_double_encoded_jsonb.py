#!/usr/bin/env python3
"""
Repair JSONB columns that hold double-encoded JSON after the SQLite ->
PostgreSQL migration.

SQLite stored JSON columns as TEXT; some rows were JSON-encoded twice, so
they migrated as JSONB *string scalars* like:
    '"{\"header_name\": \"Authorization\"}"'
instead of objects. FastAPI response models then fail with
"Input should be a valid dictionary".

For every JSONB column in the ioflow schema, this script finds rows where
jsonb_typeof(col) = 'string', parses the inner text, and replaces the value
ONLY when it decodes to a dict or list (repeatedly, to handle triple
encoding). Legitimate string values (e.g. plain-text execution results) are
left untouched.

Idempotent — safe to re-run.

Usage:
    venv/bin/python migrations/fix_double_encoded_jsonb.py [--dry-run]
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

import sqlalchemy as sa


def deep_decode(text):
    """Decode nested JSON-in-string until we reach a dict/list, else None."""
    value = text
    for _ in range(5):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, (dict, list)) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    from db.database import engine, is_sqlite
    if is_sqlite:
        print("DATABASE_URL points at SQLite — nothing to do (this fixes JSONB columns).")
        return

    with engine.connect() as conn:
        jsonb_cols = conn.execute(sa.text("""
            SELECT c.table_name, c.column_name,
                   (SELECT string_agg(quote_ident(kcu.column_name), ',')
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = c.table_schema
                      AND tc.table_name = c.table_name
                      AND tc.constraint_type = 'PRIMARY KEY') AS pk_cols
            FROM information_schema.columns c
            WHERE c.table_schema = 'ioflow' AND c.data_type = 'jsonb'
            ORDER BY c.table_name, c.column_name
        """)).fetchall()

    total_fixed = total_left = 0
    for tbl, col, pk_cols in jsonb_cols:
        if not pk_cols:
            continue
        pk_list = pk_cols.split(',')
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                f'SELECT {pk_cols}, "{col}" #>> \'{{}}\' AS inner_text '
                f'FROM ioflow."{tbl}" WHERE jsonb_typeof("{col}") = \'string\''
            )).fetchall()
        if not rows:
            continue

        fixed = left = 0
        for row in rows:
            inner = row[-1]
            decoded = deep_decode(inner)
            if decoded is None:
                left += 1
                continue
            if args.dry_run:
                fixed += 1
                continue
            where = ' AND '.join(f'{pk} = :pk{i}' for i, pk in enumerate(pk_list))
            params = {f'pk{i}': row[i] for i in range(len(pk_list))}
            params['val'] = json.dumps(decoded)
            try:
                with engine.begin() as conn:
                    conn.execute(sa.text(
                        f'UPDATE ioflow."{tbl}" SET "{col}" = CAST(:val AS JSONB) WHERE {where}'
                    ), params)
                fixed += 1
            except Exception as e:
                left += 1
                print(f"  ERROR updating {tbl}.{col}: {str(e).splitlines()[0][:120]}")

        total_fixed += fixed
        total_left += left
        note = " (dry run)" if args.dry_run else ""
        print(f"{tbl}.{col}: fixed {fixed}{note}, left as genuine strings: {left}")

    print(f"\nTOTAL: fixed {total_fixed}, left untouched {total_left}"
          + (" (dry run — no changes written)" if args.dry_run else ""))


if __name__ == '__main__':
    main()

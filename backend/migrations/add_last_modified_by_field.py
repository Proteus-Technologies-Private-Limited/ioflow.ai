#!/usr/bin/env python3
"""
Migration to add last_modified_by field to flows table
"""

import sqlite3
import sys
from pathlib import Path

def migrate_sqlite():
    """Add last_modified_by field to flows table in SQLite database"""
    db_path = Path(__file__).parent.parent / "ioflow.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(flows)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'last_modified_by' in columns:
            print("Column 'last_modified_by' already exists in flows table")
            return True

        # Add the column
        print("Adding 'last_modified_by' column to flows table...")
        cursor.execute("""
            ALTER TABLE flows
            ADD COLUMN last_modified_by VARCHAR(36)
        """)

        # Initially set last_modified_by to created_by for existing flows
        print("Setting initial values for last_modified_by...")
        cursor.execute("""
            UPDATE flows
            SET last_modified_by = created_by
            WHERE last_modified_by IS NULL
        """)

        conn.commit()
        print("✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def migrate_postgresql():
    """Add last_modified_by field to flows table in PostgreSQL database"""
    import psycopg2
    from core.config import settings

    # Parse database URL
    import re
    pattern = r"postgresql://([^:]+):([^@]+)@([^/]+)/(.+)"
    match = re.match(pattern, settings.database_url)

    if not match:
        print("Invalid PostgreSQL database URL")
        return False

    user, password, host, database = match.groups()

    conn = psycopg2.connect(
        dbname=database,
        user=user,
        password=password,
        host=host.split(':')[0],
        port=host.split(':')[1] if ':' in host else 5432
    )
    cursor = conn.cursor()

    try:
        # Get all tenant schemas
        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name LIKE 'tenant_%'
        """)
        tenant_schemas = [row[0] for row in cursor.fetchall()]

        for schema in tenant_schemas:
            print(f"Processing schema: {schema}")

            # Check if column exists
            cursor.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = '{schema}'
                AND table_name = 'flows'
                AND column_name = 'last_modified_by'
            """)

            if cursor.fetchone():
                print(f"  Column 'last_modified_by' already exists in {schema}.flows")
                continue

            # Add the column
            print(f"  Adding 'last_modified_by' column to {schema}.flows...")
            cursor.execute(f"""
                ALTER TABLE {schema}.flows
                ADD COLUMN last_modified_by VARCHAR(36)
            """)

            # Set initial values
            cursor.execute(f"""
                UPDATE {schema}.flows
                SET last_modified_by = created_by
                WHERE last_modified_by IS NULL
            """)

        conn.commit()
        print("✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Run the appropriate migration based on database type"""
    from core.config import settings

    if settings.database_url.startswith("sqlite"):
        print("Running SQLite migration...")
        return migrate_sqlite()
    elif settings.database_url.startswith("postgresql"):
        print("Running PostgreSQL migration...")
        return migrate_postgresql()
    else:
        print(f"Unsupported database type: {settings.database_url}")
        return False

if __name__ == "__main__":
    # Add backend to path
    backend_path = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_path))

    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Migration to add distributed_locks table for SQLite-based distributed locking
This table is only used when Redis is not available.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
from db.database import is_sqlite

def create_distributed_locks_table():
    """Create the distributed_locks table for SQLite."""

    if not is_sqlite:
        print("This migration is only for SQLite. Skipping for other databases.")
        return

    # Extract the database file path from the connection string
    db_path = settings.database_url.replace("sqlite:///", "")

    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    print(f"Adding distributed_locks table to {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create the distributed_locks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distributed_locks (
                lock_key TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                acquired_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                metadata TEXT
            )
        """)

        # Create index for expiration queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_distributed_locks_expires
            ON distributed_locks(expires_at)
        """)

        conn.commit()
        print("✅ Successfully created distributed_locks table")

        # Verify the table was created
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='distributed_locks'
        """)

        if cursor.fetchone():
            print("✅ Table verified successfully")
        else:
            print("⚠️ Table creation could not be verified")

    except Exception as e:
        print(f"❌ Error creating distributed_locks table: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """Run the migration."""
    print("=" * 60)
    print("DISTRIBUTED LOCKS TABLE MIGRATION")
    print("=" * 60)

    create_distributed_locks_table()

    print("\n" + "=" * 60)
    print("Migration completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
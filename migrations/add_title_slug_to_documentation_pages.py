#!/usr/bin/env python3
"""
Migration: Add title and slug columns to app_documentation_pages table

The model expects both title/slug and page_title/page_slug columns.
This migration adds the missing title and slug columns and populates them
from the existing page_title and page_slug columns.
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_db_path():
    """Resolve the active SQLite database path from settings / .env.

    The previous version hardcoded backend/ioflow.db relative to this repo,
    which is an empty placeholder file. The live database location is defined
    by DATABASE_URL in backend/.env, so we must honor it.
    """
    db_url = None

    # Prefer the application settings (single source of truth)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
        from core.config import settings
        db_url = settings.database_url
    except Exception:
        pass

    # Fallback: read DATABASE_URL directly from backend/.env
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

    # sqlite:////abs/path -> /abs/path  ;  sqlite:///rel/path -> rel/path
    path = db_url.split('sqlite:///', 1)[1]
    if not path.startswith('/'):
        path = '/' + path if db_url.startswith('sqlite:////') else path
    return path


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
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(app_documentation_pages)")
        columns = [col[1] for col in cursor.fetchall()]

        print(f"Current columns: {columns}")

        # Add title column if missing
        if 'title' not in columns:
            print("Adding 'title' column...")
            cursor.execute("ALTER TABLE app_documentation_pages ADD COLUMN title VARCHAR(255)")
            # Copy data from page_title
            cursor.execute("UPDATE app_documentation_pages SET title = page_title WHERE title IS NULL")
            print("'title' column added and populated from page_title")
        else:
            print("'title' column already exists")

        # Add slug column if missing
        if 'slug' not in columns:
            print("Adding 'slug' column...")
            cursor.execute("ALTER TABLE app_documentation_pages ADD COLUMN slug VARCHAR(255)")
            # Copy data from page_slug
            cursor.execute("UPDATE app_documentation_pages SET slug = page_slug WHERE slug IS NULL")
            print("'slug' column added and populated from page_slug")
        else:
            print("'slug' column already exists")

        conn.commit()
        print("Migration completed successfully!")

        # Verify
        cursor.execute("PRAGMA table_info(app_documentation_pages)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Final columns: {columns}")

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

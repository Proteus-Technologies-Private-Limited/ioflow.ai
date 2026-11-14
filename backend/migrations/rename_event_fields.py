#!/usr/bin/env python3
"""
Migration to rename trigger_type to event_type and trigger_config to event_configuration
"""

import sqlite3
import json
import sys
import os
from pathlib import Path

def run_migration():
    """Run the migration to rename event fields"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / "ioflow.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if columns already renamed
        cursor.execute("PRAGMA table_info(application_events)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'event_type' in column_names and 'event_configuration' in column_names:
            print("✅ Columns already renamed, skipping migration")
            return True
        
        if 'trigger_type' not in column_names or 'trigger_config' not in column_names:
            print("❌ Original columns not found, database may be in inconsistent state")
            return False
        
        print("Starting migration...")
        
        # SQLite doesn't support ALTER COLUMN directly, so we need to:
        # 1. Create new table with new column names
        # 2. Copy data
        # 3. Drop old table
        # 4. Rename new table
        
        cursor.execute("""
            CREATE TABLE application_events_new (
                event_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                event_type TEXT NOT NULL,
                event_configuration TEXT,
                output_schema TEXT,
                sample_payload TEXT,
                api_endpoint TEXT UNIQUE,
                sync_mode TEXT DEFAULT 'asynchronous',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES applications(app_id) ON DELETE CASCADE
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO application_events_new (
                event_id, app_id, event_name, display_name, description,
                event_type, event_configuration, output_schema, sample_payload,
                api_endpoint, sync_mode, is_active, created_at
            )
            SELECT 
                event_id, app_id, event_name, display_name, description,
                trigger_type, trigger_config, output_schema, sample_payload,
                api_endpoint, sync_mode, is_active, created_at
            FROM application_events
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE application_events")
        
        # Rename new table
        cursor.execute("ALTER TABLE application_events_new RENAME TO application_events")
        
        # Recreate indexes if they exist
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_events_app_id 
            ON application_events(app_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_events_event_name 
            ON application_events(event_name)
        """)
        
        # Commit changes
        conn.commit()
        
        print("✅ Migration completed successfully")
        
        # Verify migration
        cursor.execute("PRAGMA table_info(application_events)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print("\nNew column names:")
        for col in column_names:
            if col in ['event_type', 'event_configuration']:
                print(f"  ✅ {col}")
            else:
                print(f"  - {col}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
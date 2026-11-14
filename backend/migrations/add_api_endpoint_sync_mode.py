#!/usr/bin/env python3
"""
Migration to add api_endpoint and sync_mode columns to application_events table
and invocation_api_key columns to application_subscriptions table
"""

import sqlite3
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

def migrate():
    # Get database path from settings
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "")
    else:
        print("This migration is for SQLite only")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist before adding them
        cursor.execute("PRAGMA table_info(application_events)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add api_endpoint column if it doesn't exist
        if 'api_endpoint' not in columns:
            print("Adding api_endpoint column to application_events...")
            cursor.execute("""
                ALTER TABLE application_events 
                ADD COLUMN api_endpoint VARCHAR(500)
            """)
            print("✓ Added api_endpoint column")
        else:
            print("✓ api_endpoint column already exists")
        
        # Add sync_mode column if it doesn't exist
        if 'sync_mode' not in columns:
            print("Adding sync_mode column to application_events...")
            cursor.execute("""
                ALTER TABLE application_events 
                ADD COLUMN sync_mode VARCHAR(50) DEFAULT 'asynchronous'
            """)
            print("✓ Added sync_mode column")
        else:
            print("✓ sync_mode column already exists")
        
        # Check application_subscriptions table
        cursor.execute("PRAGMA table_info(application_subscriptions)")
        sub_columns = [col[1] for col in cursor.fetchall()]
        
        # Add invocation_api_key column if it doesn't exist
        if 'invocation_api_key' not in sub_columns:
            print("Adding invocation_api_key column to application_subscriptions...")
            cursor.execute("""
                ALTER TABLE application_subscriptions 
                ADD COLUMN invocation_api_key VARCHAR(255)
            """)
            print("✓ Added invocation_api_key column")
        else:
            print("✓ invocation_api_key column already exists")
        
        # Add api_key_created_at column if it doesn't exist
        if 'api_key_created_at' not in sub_columns:
            print("Adding api_key_created_at column to application_subscriptions...")
            cursor.execute("""
                ALTER TABLE application_subscriptions 
                ADD COLUMN api_key_created_at DATETIME
            """)
            print("✓ Added api_key_created_at column")
        else:
            print("✓ api_key_created_at column already exists")
        
        # Add api_key_last_used_at column if it doesn't exist
        if 'api_key_last_used_at' not in sub_columns:
            print("Adding api_key_last_used_at column to application_subscriptions...")
            cursor.execute("""
                ALTER TABLE application_subscriptions 
                ADD COLUMN api_key_last_used_at DATETIME
            """)
            print("✓ Added api_key_last_used_at column")
        else:
            print("✓ api_key_last_used_at column already exists")
        
        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Generate API keys for existing subscriptions that don't have them
        cursor.execute("""
            SELECT subscription_id, invocation_api_key 
            FROM application_subscriptions 
            WHERE invocation_api_key IS NULL OR invocation_api_key = ''
        """)
        subscriptions_without_keys = cursor.fetchall()
        
        if subscriptions_without_keys:
            print(f"\nFound {len(subscriptions_without_keys)} subscriptions without API keys")
            import secrets
            from datetime import datetime
            
            for sub_id, _ in subscriptions_without_keys:
                api_key = f"ioflow_{secrets.token_urlsafe(32)}"
                cursor.execute("""
                    UPDATE application_subscriptions 
                    SET invocation_api_key = ?, api_key_created_at = ?
                    WHERE subscription_id = ?
                """, (api_key, datetime.utcnow(), sub_id))
                print(f"✓ Generated API key for subscription {sub_id}")
            
            conn.commit()
            print("✅ Generated API keys for all existing subscriptions")
        
    except sqlite3.Error as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
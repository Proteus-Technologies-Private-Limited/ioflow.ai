#!/usr/bin/env python
"""Add missing columns to SQLite database"""

import sqlite3
import sys
from datetime import datetime

def migrate_database(db_path):
    """Add missing columns to SQLite database"""
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check existing columns in users table
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = {col[1] for col in cursor.fetchall()}
        print(f"Existing columns in users table: {existing_columns}")
        
        # Add missing columns to users table (SQLite doesn't support non-constant defaults in ALTER TABLE)
        missing_columns = [
            ("auth_provider", "VARCHAR"),
            ("status", "VARCHAR(1)"),
            ("acct_lock", "VARCHAR(1)"),
            ("role", "VARCHAR"),
            ("last_login_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP"),
        ]
        
        for col_name, col_type in missing_columns:
            if col_name not in existing_columns:
                print(f"Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column already exists: {col_name}")
        
        # Rename columns if needed
        if "username" in existing_columns and "user_name" not in existing_columns:
            print("Renaming username to user_name")
            cursor.execute("ALTER TABLE users RENAME COLUMN username TO user_name")
            
        if "password_hash" in existing_columns and "pass_wd_sha" not in existing_columns:
            print("Renaming password_hash to pass_wd_sha")
            cursor.execute("ALTER TABLE users RENAME COLUMN password_hash TO pass_wd_sha")
        
        # Check existing columns in tenants table
        cursor.execute("PRAGMA table_info(tenants)")
        existing_tenant_columns = {col[1] for col in cursor.fetchall()}
        print(f"\nExisting columns in tenants table: {existing_tenant_columns}")
        
        # Add missing columns to tenants table
        missing_tenant_columns = [
            ("email_domain", "VARCHAR(255)"),
            ("web_site", "VARCHAR(255)"),
            ("gst_no", "VARCHAR(50)"),
            ("user_id_own", "VARCHAR(36)"),
            ("created_at", "TIMESTAMP"),
            ("status", "VARCHAR(20)"),
        ]
        
        for col_name, col_type in missing_tenant_columns:
            if col_name not in existing_tenant_columns:
                print(f"Adding column to tenants: {col_name}")
                cursor.execute(f"ALTER TABLE tenants ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column already exists in tenants: {col_name}")
        
        # Update existing records to have default values
        print("\nUpdating existing records with default values...")
        cursor.execute("UPDATE users SET status = 'A' WHERE is_active = 1 AND status IS NULL")
        cursor.execute("UPDATE users SET status = 'N' WHERE (is_active = 0 OR is_active IS NULL) AND status IS NULL")
        cursor.execute("UPDATE users SET auth_provider = 'email' WHERE auth_provider IS NULL")
        cursor.execute("UPDATE users SET acct_lock = 'N' WHERE acct_lock IS NULL")
        cursor.execute("UPDATE users SET role = 'FLOW_DESIGNER' WHERE role IS NULL")
        cursor.execute("UPDATE users SET created_at = datetime('now') WHERE created_at IS NULL")
        cursor.execute("UPDATE tenants SET status = 'active' WHERE status IS NULL")
        cursor.execute("UPDATE tenants SET created_at = datetime('now') WHERE created_at IS NULL")
        
        # Commit changes
        conn.commit()
        print("\nMigration completed successfully!")
        
        # Show final schema
        print("\nFinal users table schema:")
        cursor.execute("PRAGMA table_info(users)")
        for col in cursor.fetchall():
            print(f"  {col[1]} {col[2]}")
            
        print("\nFinal tenants table schema:")
        cursor.execute("PRAGMA table_info(tenants)")
        for col in cursor.fetchall():
            print(f"  {col[1]} {col[2]}")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ioflow.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    # Backup the database first
    import shutil
    backup_path = db_path + ".backup"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    migrate_database(db_path)
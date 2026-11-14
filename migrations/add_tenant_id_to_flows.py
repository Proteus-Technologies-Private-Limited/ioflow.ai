#!/usr/bin/env python3
"""
Script to add tenant_id column to flows table and populate it
"""

import sqlite3
import sys

def migrate_flows_table():
    try:
        # Connect to the database
        conn = sqlite3.connect('ioflow.db')
        cursor = conn.cursor()
        
        # Check if tenant_id column already exists
        cursor.execute("PRAGMA table_info(flows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'tenant_id' in columns:
            print("tenant_id column already exists in flows table")
            return
        
        # Add tenant_id column
        print("Adding tenant_id column to flows table...")
        cursor.execute("ALTER TABLE flows ADD COLUMN tenant_id VARCHAR(36)")
        
        # Get the tenant_id from users table for each flow
        print("Updating existing flows with tenant_id...")
        cursor.execute("""
            UPDATE flows 
            SET tenant_id = (
                SELECT u.tenant_id 
                FROM users u 
                WHERE u.user_id = flows.created_by
            )
            WHERE created_by IS NOT NULL
        """)
        
        # For flows without created_by, set a default tenant_id
        # First, get any active tenant
        cursor.execute("SELECT tenant_id FROM tenants WHERE status = 'active' LIMIT 1")
        default_tenant = cursor.fetchone()
        
        if default_tenant:
            cursor.execute("""
                UPDATE flows 
                SET tenant_id = ? 
                WHERE tenant_id IS NULL
            """, (default_tenant[0],))
        
        # Commit the changes
        conn.commit()
        
        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM flows WHERE tenant_id IS NULL")
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"WARNING: {null_count} flows still have NULL tenant_id")
        else:
            print("Successfully added tenant_id to all flows")
        
        # Show sample data
        cursor.execute("SELECT flow_id, flow_name, tenant_id FROM flows LIMIT 5")
        print("\nSample flows with tenant_id:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} -> tenant_id: {row[2]}")
        
        conn.close()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_flows_table()
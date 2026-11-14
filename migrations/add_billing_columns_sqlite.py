#!/usr/bin/env python3
"""
Add missing enhanced billing columns to SQLite database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

import sqlite3

def add_billing_columns():
    """Add enhanced billing columns to the database"""

    db_path = 'backend/ioflow.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(application_pricing)")
        columns = cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        print(f"Existing columns: {existing_columns}")

        # Add billing_mode if not exists
        if 'billing_mode' not in existing_columns:
            print("Adding billing_mode column...")
            cursor.execute("""
                ALTER TABLE application_pricing
                ADD COLUMN billing_mode VARCHAR(20) DEFAULT 'prepaid'
            """)
            print("✓ Added billing_mode column")
        else:
            print("⚠ billing_mode column already exists")

        # Add is_free if not exists
        if 'is_free' not in existing_columns:
            print("Adding is_free column...")
            cursor.execute("""
                ALTER TABLE application_pricing
                ADD COLUMN is_free BOOLEAN DEFAULT 0
            """)
            print("✓ Added is_free column")
        else:
            print("⚠ is_free column already exists")

        # Add service_pricing_enabled if not exists
        if 'service_pricing_enabled' not in existing_columns:
            print("Adding service_pricing_enabled column...")
            cursor.execute("""
                ALTER TABLE application_pricing
                ADD COLUMN service_pricing_enabled BOOLEAN DEFAULT 0
            """)
            print("✓ Added service_pricing_enabled column")
        else:
            print("⚠ service_pricing_enabled column already exists")

        # Create service_pricing table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_pricing (
                service_pricing_id VARCHAR(36) PRIMARY KEY,
                service_id VARCHAR(36) NOT NULL,
                cost_per_request NUMERIC(10, 4) DEFAULT 0,
                cost_per_kb NUMERIC(10, 6),
                cost_per_token NUMERIC(10, 8),
                is_free BOOLEAN DEFAULT 0,
                override_app_pricing BOOLEAN DEFAULT 1,
                currency VARCHAR(3) DEFAULT 'USD',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (service_id) REFERENCES application_services(service_id)
            )
        """)
        print("✓ Service pricing table ready")

        # Commit changes
        conn.commit()

        # Verify columns were added
        cursor.execute("PRAGMA table_info(application_pricing)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print("\n✅ Final columns in application_pricing:")
        for col in column_names:
            if col in ['billing_mode', 'is_free', 'service_pricing_enabled']:
                print(f"  ✓ {col}")

        print("\n✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    add_billing_columns()
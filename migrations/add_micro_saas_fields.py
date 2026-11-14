#!/usr/bin/env python3
"""
Add Micro SaaS fields to frontend_flow_applications table
and create micro_saas_billing_config table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

import sqlite3
import json

def add_micro_saas_fields():
    """Add Micro SaaS fields to the database"""

    db_path = 'backend/ioflow.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("Starting Micro SaaS Fields Migration")
        print("=" * 60)

        # Check existing columns in frontend_flow_applications
        cursor.execute("PRAGMA table_info(frontend_flow_applications)")
        columns = cursor.fetchall()
        existing_columns = [col[1] for col in columns]
        print(f"\nExisting columns in frontend_flow_applications: {len(existing_columns)}")

        # Add visibility column
        if 'visibility' not in existing_columns:
            print("\n1. Adding visibility column...")
            cursor.execute("""
                ALTER TABLE frontend_flow_applications
                ADD COLUMN visibility VARCHAR(20) DEFAULT 'private'
            """)
            print("   ✓ Added visibility column (default: 'private')")
        else:
            print("\n1. ⚠ visibility column already exists")

        # Add billing_preference column
        if 'billing_preference' not in existing_columns:
            print("\n2. Adding billing_preference column...")
            cursor.execute("""
                ALTER TABLE frontend_flow_applications
                ADD COLUMN billing_preference VARCHAR(50) DEFAULT 'free'
            """)
            print("   ✓ Added billing_preference column (default: 'free')")
        else:
            print("\n2. ⚠ billing_preference column already exists")

        # Add pricing_config column (JSON)
        if 'pricing_config' not in existing_columns:
            print("\n3. Adding pricing_config column...")
            cursor.execute("""
                ALTER TABLE frontend_flow_applications
                ADD COLUMN pricing_config TEXT DEFAULT NULL
            """)
            print("   ✓ Added pricing_config column (JSON)")
        else:
            print("\n3. ⚠ pricing_config column already exists")

        # Add usage_limits column (JSON)
        if 'usage_limits' not in existing_columns:
            print("\n4. Adding usage_limits column...")
            cursor.execute("""
                ALTER TABLE frontend_flow_applications
                ADD COLUMN usage_limits TEXT DEFAULT NULL
            """)
            print("   ✓ Added usage_limits column (JSON)")
        else:
            print("\n4. ⚠ usage_limits column already exists")

        # Add marketplace_enabled column
        if 'marketplace_enabled' not in existing_columns:
            print("\n5. Adding marketplace_enabled column...")
            cursor.execute("""
                ALTER TABLE frontend_flow_applications
                ADD COLUMN marketplace_enabled BOOLEAN DEFAULT 0
            """)
            print("   ✓ Added marketplace_enabled column (default: false)")
        else:
            print("\n5. ⚠ marketplace_enabled column already exists")

        # Create micro_saas_billing_config table if not exists
        print("\n6. Creating micro_saas_billing_config table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS micro_saas_billing_config (
                billing_config_id VARCHAR(36) PRIMARY KEY,
                frontend_app_id VARCHAR(36) NOT NULL UNIQUE,
                billing_preference VARCHAR(50) NOT NULL DEFAULT 'free',
                pricing_config TEXT,
                usage_limits TEXT,
                prepaid_balance NUMERIC(10, 2) DEFAULT 0,
                total_revenue NUMERIC(10, 2) DEFAULT 0,
                active_subscribers_count INTEGER DEFAULT 0,
                total_executions INTEGER DEFAULT 0,
                currency VARCHAR(3) DEFAULT 'USD',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id)
            )
        """)
        print("   ✓ micro_saas_billing_config table ready")

        # Create micro_saas_subscribers table if not exists
        print("\n7. Creating micro_saas_subscribers table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS micro_saas_subscribers (
                subscriber_id VARCHAR(36) PRIMARY KEY,
                frontend_app_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36),
                tenant_id VARCHAR(36),
                subscription_status VARCHAR(20) DEFAULT 'active',
                billing_cycle_start TIMESTAMP,
                billing_cycle_end TIMESTAMP,
                last_payment_date TIMESTAMP,
                last_payment_amount NUMERIC(10, 2),
                total_paid NUMERIC(10, 2) DEFAULT 0,
                execution_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
            )
        """)
        print("   ✓ micro_saas_subscribers table ready")

        # Create micro_saas_usage_logs table if not exists
        print("\n8. Creating micro_saas_usage_logs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS micro_saas_usage_logs (
                log_id VARCHAR(36) PRIMARY KEY,
                frontend_app_id VARCHAR(36) NOT NULL,
                subscriber_id VARCHAR(36),
                execution_id VARCHAR(36),
                execution_time_ms INTEGER,
                cost_incurred NUMERIC(10, 4) DEFAULT 0,
                billing_basis VARCHAR(50),
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (subscriber_id) REFERENCES micro_saas_subscribers(subscriber_id)
            )
        """)
        print("   ✓ micro_saas_usage_logs table ready")

        # Create micro_saas_billing_transactions table if not exists
        print("\n9. Creating micro_saas_billing_transactions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS micro_saas_billing_transactions (
                transaction_id VARCHAR(36) PRIMARY KEY,
                frontend_app_id VARCHAR(36) NOT NULL,
                subscriber_id VARCHAR(36),
                transaction_type VARCHAR(50) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(3) DEFAULT 'USD',
                description TEXT,
                payment_gateway VARCHAR(50),
                payment_gateway_transaction_id VARCHAR(255),
                status VARCHAR(20) DEFAULT 'pending',
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id),
                FOREIGN KEY (subscriber_id) REFERENCES micro_saas_subscribers(subscriber_id)
            )
        """)
        print("   ✓ micro_saas_billing_transactions table ready")

        # Commit all changes
        conn.commit()

        # Verify columns were added
        cursor.execute("PRAGMA table_info(frontend_flow_applications)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)

        print("\nNew columns in frontend_flow_applications:")
        new_columns = ['visibility', 'billing_preference', 'pricing_config', 'usage_limits', 'marketplace_enabled']
        for col in new_columns:
            if col in column_names:
                print(f"  ✓ {col}")
            else:
                print(f"  ✗ {col} - FAILED TO ADD")

        # Count existing frontend apps
        cursor.execute("SELECT COUNT(*) FROM frontend_flow_applications")
        count = cursor.fetchone()[0]
        print(f"\nTotal frontend applications: {count}")
        if count > 0:
            print("  ✓ All existing apps set to visibility='private', billing_preference='free'")

        print("\nNew tables created:")
        tables = ['micro_saas_billing_config', 'micro_saas_subscribers',
                  'micro_saas_usage_logs', 'micro_saas_billing_transactions']
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                print(f"  ✓ {table}")
            else:
                print(f"  ✗ {table} - FAILED TO CREATE")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    success = add_micro_saas_fields()
    sys.exit(0 if success else 1)

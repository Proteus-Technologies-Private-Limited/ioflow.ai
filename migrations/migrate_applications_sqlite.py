#!/usr/bin/env python
"""Add application management tables to SQLite database"""

import sqlite3
import sys
import os
from pathlib import Path

def migrate_database(db_path):
    """Add application management tables to SQLite database"""
    print(f"Adding application tables to: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create applications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                app_id VARCHAR(36) PRIMARY KEY,
                app_name VARCHAR(255) NOT NULL,
                app_type VARCHAR(50) NOT NULL,
                tenant_id_owner VARCHAR(36) REFERENCES tenants(tenant_id),
                description TEXT,
                icon_url VARCHAR(500),
                category VARCHAR(100),
                auth_type VARCHAR(50) NOT NULL,
                auth_config TEXT,
                webhook_config TEXT,
                status VARCHAR(20) DEFAULT 'active',
                version VARCHAR(20) DEFAULT '1.0.0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(36) REFERENCES users(user_id),
                UNIQUE(app_name, app_type, tenant_id_owner)
            )
        """)
        print("✅ Created applications table")
        
        # Create application_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_events (
                event_id VARCHAR(36) PRIMARY KEY,
                app_id VARCHAR(36) NOT NULL REFERENCES applications(app_id) ON DELETE CASCADE,
                event_name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                description TEXT,
                trigger_type VARCHAR(50) NOT NULL,
                trigger_config TEXT,
                output_schema TEXT,
                sample_payload TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(app_id, event_name)
            )
        """)
        print("✅ Created application_events table")
        
        # Create application_services table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_services (
                service_id VARCHAR(36) PRIMARY KEY,
                app_id VARCHAR(36) NOT NULL REFERENCES applications(app_id) ON DELETE CASCADE,
                service_name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                description TEXT,
                service_type VARCHAR(50) NOT NULL,
                http_method VARCHAR(10),
                endpoint_template VARCHAR(500),
                headers_template TEXT,
                body_template TEXT,
                is_async BOOLEAN DEFAULT 0,
                async_config TEXT,
                input_schema TEXT,
                output_schema TEXT,
                error_schema TEXT,
                retry_config TEXT,
                timeout_seconds INTEGER DEFAULT 30,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(app_id, service_name)
            )
        """)
        print("✅ Created application_services table")
        
        # Create application_subscriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_subscriptions (
                subscription_id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(tenant_id),
                app_id VARCHAR(36) NOT NULL REFERENCES applications(app_id),
                auth_credentials TEXT,
                subscription_config TEXT,
                webhook_url VARCHAR(500),
                status VARCHAR(20) DEFAULT 'active',
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(tenant_id, app_id)
            )
        """)
        print("✅ Created application_subscriptions table")
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_type ON applications(app_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_tenant ON applications(tenant_id_owner)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_events_app_id ON application_events(app_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_events_trigger_type ON application_events(trigger_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_services_app_id ON application_services(app_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_services_type ON application_services(service_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_subscriptions_tenant ON application_subscriptions(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_subscriptions_app ON application_subscriptions(app_id)")
        print("✅ Created indexes")
        
        # Commit changes
        conn.commit()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ioflow.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    # Backup the database first
    import shutil
    backup_path = db_path + ".backup_apps"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    migrate_database(db_path)
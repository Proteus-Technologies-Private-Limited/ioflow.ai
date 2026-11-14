"""
Script to create application tables in SQLite database
"""
import sqlite3
import sys
from pathlib import Path

def create_application_tables():
    """Create application-related tables in SQLite database"""
    # Path to SQLite database
    db_path = Path(__file__).parent / "ioflow.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create applications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                app_id VARCHAR(36) PRIMARY KEY,
                tenant_id_owner VARCHAR(36),
                created_by VARCHAR(36),
                app_name VARCHAR(255) NOT NULL,
                app_type VARCHAR(50) NOT NULL,
                description TEXT,
                icon_url VARCHAR(500),
                category VARCHAR(100),
                base_url VARCHAR(500),
                auth_type VARCHAR(50) NOT NULL,
                auth_config TEXT,
                webhook_config TEXT,
                status VARCHAR(20) DEFAULT 'active',
                version VARCHAR(20) DEFAULT '1.0.0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id_owner) REFERENCES tenants(tenant_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)
        
        # Create application_events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_events (
                event_id VARCHAR(36) PRIMARY KEY,
                app_id VARCHAR(36) NOT NULL,
                event_name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                description TEXT,
                trigger_type VARCHAR(50) NOT NULL,
                trigger_config TEXT,
                output_schema TEXT,
                sample_payload TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES applications(app_id)
            )
        """)
        
        # Create application_services table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_services (
                service_id VARCHAR(36) PRIMARY KEY,
                app_id VARCHAR(36) NOT NULL,
                service_name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                description TEXT,
                service_type VARCHAR(50) NOT NULL,
                service_config TEXT,
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
                FOREIGN KEY (app_id) REFERENCES applications(app_id)
            )
        """)
        
        # Create application_subscriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_subscriptions (
                subscription_id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) NOT NULL,
                app_id VARCHAR(36) NOT NULL,
                auth_credentials TEXT,
                subscription_config TEXT,
                webhook_url VARCHAR(500),
                status VARCHAR(20) DEFAULT 'active',
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                FOREIGN KEY (app_id) REFERENCES applications(app_id)
            )
        """)
        
        conn.commit()
        print("Successfully created application tables")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'application%'")
        tables = cursor.fetchall()
        print(f"Created tables: {[t[0] for t in tables]}")
        
        return True
            
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = create_application_tables()
    sys.exit(0 if success else 1)
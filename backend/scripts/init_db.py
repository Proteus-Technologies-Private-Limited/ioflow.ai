#!/usr/bin/env python
"""Initialize the database with required schemas and tables"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import init_db, engine
from sqlalchemy import text

def main():
    print("Initializing IOFlow database...")
    
    try:
        # Check database connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL: {version}")
        
        # Initialize database
        init_db()
        print("✅ Database initialized successfully")
        
        # Create sample global application
        print("\nCreating sample application...")
        with engine.connect() as conn:
            # Check if sample app exists
            result = conn.execute(
                text("SELECT COUNT(*) FROM ioflow.applications WHERE app_name = 'Sample Webhook App'")
            )
            if result.fetchone()[0] == 0:
                conn.execute(text("""
                    INSERT INTO ioflow.applications 
                    (app_id, app_name, app_type, description, auth_config, events, services) 
                    VALUES 
                    (
                        gen_random_uuid()::text,
                        'Sample Webhook App',
                        'global',
                        'A sample application for testing webhooks',
                        '{"type": "none"}'::jsonb,
                        '[{"name": "test_event", "display_name": "Test Event", "trigger_type": "webhook", "webhook_path": "/sample/test", "parameters": []}]'::jsonb,
                        '[{"name": "log_message", "display_name": "Log Message", "method": "POST", "endpoint": "/log", "async": false, "parameters": [{"name": "message", "type": "string", "required": true}]}]'::jsonb
                    )
                """))
                conn.commit()
                print("✅ Sample application created")
            else:
                print("ℹ️  Sample application already exists")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure PostgreSQL is running and the connection details in .env are correct.")
        sys.exit(1)

if __name__ == "__main__":
    main()
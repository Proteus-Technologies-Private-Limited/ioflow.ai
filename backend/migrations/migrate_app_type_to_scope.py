#!/usr/bin/env python3
"""
Migration script to:
1. Rename app_type column to app_scope
2. Add new app_type column for application type (database/email/api/etc)
3. Migrate existing data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings
import json

def migrate_database():
    """Migrate the database schema and data"""
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = settings.database_url.startswith("sqlite")
        
        if is_sqlite:
            print("Migrating SQLite database...")
            
            # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
            # First, let's add the new columns
            try:
                # Add app_scope column if it doesn't exist
                conn.execute(text("ALTER TABLE applications ADD COLUMN app_scope VARCHAR(50) DEFAULT 'global'"))
                print("Added app_scope column")
            except Exception as e:
                print(f"app_scope column might already exist: {e}")
            
            try:
                # Add new app_type column (for application type)
                conn.execute(text("ALTER TABLE applications ADD COLUMN app_type_new VARCHAR(50)"))
                print("Added app_type_new column")
            except Exception as e:
                print(f"app_type_new column might already exist: {e}")
            
            # Copy data from old app_type to app_scope
            conn.execute(text("""
                UPDATE applications 
                SET app_scope = app_type 
                WHERE app_scope IS NULL OR app_scope = 'global'
            """))
            
            # Set new app_type based on services and category
            # For email applications
            conn.execute(text("""
                UPDATE applications 
                SET app_type_new = 'email'
                WHERE app_id IN (
                    SELECT DISTINCT app_id 
                    FROM application_services 
                    WHERE service_type IN ('smtp_send', 'pop3_receive', 'imap_receive', 'email_send')
                )
            """))
            
            # For database applications
            conn.execute(text("""
                UPDATE applications 
                SET app_type_new = 'database'
                WHERE app_id IN (
                    SELECT DISTINCT app_id 
                    FROM application_services 
                    WHERE service_type = 'database_query'
                ) OR category = 'Database'
            """))
            
            # For flow applications (published flows)
            conn.execute(text("""
                UPDATE applications 
                SET app_type_new = 'flow'
                WHERE app_id IN (
                    SELECT app_id FROM published_applications
                )
            """))
            
            # Default remaining to API
            conn.execute(text("""
                UPDATE applications 
                SET app_type_new = 'api'
                WHERE app_type_new IS NULL
            """))
            
            print("Data migration completed")
            
        else:
            print("Migrating PostgreSQL database...")
            
            # PostgreSQL supports proper ALTER COLUMN
            try:
                # Add app_scope column
                conn.execute(text("ALTER TABLE ioflow.applications ADD COLUMN IF NOT EXISTS app_scope VARCHAR(50) DEFAULT 'global'"))
                print("Added app_scope column")
            except Exception as e:
                print(f"Error adding app_scope: {e}")
            
            try:
                # Copy data from app_type to app_scope
                conn.execute(text("UPDATE ioflow.applications SET app_scope = app_type WHERE app_scope = 'global'"))
                
                # Add new app_type column
                conn.execute(text("ALTER TABLE ioflow.applications ADD COLUMN IF NOT EXISTS app_type_new VARCHAR(50)"))
                print("Added app_type_new column")
            except Exception as e:
                print(f"Error: {e}")
            
            # Set new app_type based on services
            conn.execute(text("""
                UPDATE ioflow.applications 
                SET app_type_new = 'email'
                WHERE app_id IN (
                    SELECT DISTINCT app_id 
                    FROM ioflow.application_services 
                    WHERE service_type IN ('smtp_send', 'pop3_receive', 'imap_receive', 'email_send')
                )
            """))
            
            conn.execute(text("""
                UPDATE ioflow.applications 
                SET app_type_new = 'database'
                WHERE app_id IN (
                    SELECT DISTINCT app_id 
                    FROM ioflow.application_services 
                    WHERE service_type = 'database_query'
                ) OR category = 'Database'
            """))
            
            conn.execute(text("""
                UPDATE ioflow.applications 
                SET app_type_new = 'flow'
                WHERE app_id IN (
                    SELECT app_id FROM ioflow.published_applications
                )
            """))
            
            conn.execute(text("""
                UPDATE ioflow.applications 
                SET app_type_new = 'api'
                WHERE app_type_new IS NULL
            """))
            
            # Drop old app_type column and rename new one
            try:
                conn.execute(text("ALTER TABLE ioflow.applications DROP COLUMN app_type"))
                conn.execute(text("ALTER TABLE ioflow.applications RENAME COLUMN app_type_new TO app_type"))
            except Exception as e:
                print(f"Error renaming columns: {e}")
            
            print("Data migration completed")

def update_seed_applications():
    """Update seed application JSON files"""
    import glob
    
    seed_dir = os.path.join(os.path.dirname(__file__), '..', 'seed-applications')
    
    for json_file in glob.glob(os.path.join(seed_dir, '*.json')):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if 'application' in data:
                app = data['application']
                
                # Move app_type to app_scope
                if 'app_type' in app:
                    app['app_scope'] = app.get('app_type', 'global')
                
                # Determine new app_type based on services
                services = data.get('services', [])
                service_types = [s.get('service_type') for s in services]
                
                if any(st in ['smtp_send', 'pop3_receive', 'imap_receive'] for st in service_types):
                    app['app_type'] = 'email'
                elif any(st == 'database_query' for st in service_types):
                    app['app_type'] = 'database'
                elif app.get('category') == 'Database':
                    app['app_type'] = 'database'
                else:
                    app['app_type'] = 'api'
                
                # Save updated file
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"Updated {os.path.basename(json_file)}")
        
        except Exception as e:
            print(f"Error updating {json_file}: {e}")

if __name__ == "__main__":
    print("Starting migration...")
    
    # Update database
    migrate_database()
    
    # Update seed files
    update_seed_applications()
    
    print("\nMigration completed!")
    print("\nNOTE: You may need to restart the application for changes to take effect.")
    print("Also update any code that references 'app_type' for scope to use 'app_scope' instead.")
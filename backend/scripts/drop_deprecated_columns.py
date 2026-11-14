#!/usr/bin/env python3
"""
Script to drop deprecated columns from application_services table
WARNING: This is a destructive operation. Ensure data has been migrated before running.
"""

import sqlite3
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def drop_deprecated_columns():
    """Drop deprecated columns from the database"""
    
    # Connect to SQLite database
    conn = sqlite3.connect('../ioflow.db')
    cursor = conn.cursor()
    
    try:
        # SQLite doesn't support DROP COLUMN directly, so we need to:
        # 1. Create a new table without the deprecated columns
        # 2. Copy data from the old table
        # 3. Drop the old table
        # 4. Rename the new table
        
        logger.info("Creating new table structure without deprecated columns...")
        
        # Create new table without deprecated columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_services_new (
                service_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                service_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                service_type TEXT NOT NULL,
                service_config TEXT,
                is_async BOOLEAN DEFAULT 0,
                async_config TEXT,
                input_schema TEXT,
                output_schema TEXT,
                error_schema TEXT,
                retry_config TEXT,
                response_config TEXT,
                timeout_seconds INTEGER DEFAULT 30,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (app_id) REFERENCES applications(app_id)
            )
        """)
        
        logger.info("Copying data to new table...")
        
        # Copy data from old table to new table (excluding deprecated columns)
        cursor.execute("""
            INSERT INTO application_services_new (
                service_id, app_id, service_name, display_name, description,
                service_type, service_config, is_async, async_config,
                input_schema, output_schema, error_schema, retry_config,
                response_config, timeout_seconds, is_active, created_at
            )
            SELECT 
                service_id, app_id, service_name, display_name, description,
                service_type, service_config, is_async, async_config,
                input_schema, output_schema, error_schema, retry_config,
                response_config, timeout_seconds, is_active, created_at
            FROM application_services
        """)
        
        rows_copied = cursor.rowcount
        logger.info(f"Copied {rows_copied} rows to new table")
        
        # Drop the old table
        logger.info("Dropping old table...")
        cursor.execute("DROP TABLE application_services")
        
        # Rename new table to original name
        logger.info("Renaming new table...")
        cursor.execute("ALTER TABLE application_services_new RENAME TO application_services")
        
        # Commit changes
        conn.commit()
        logger.info("✅ Successfully dropped deprecated columns!")
        
        # Verify the new structure
        cursor.execute("PRAGMA table_info(application_services)")
        columns = cursor.fetchall()
        logger.info("\nNew table structure:")
        for col in columns:
            logger.info(f"  - {col[1]} ({col[2]})")
        
        # Check for deprecated columns
        deprecated_cols = ['http_method', 'endpoint_template', 'headers_template', 'body_template']
        existing_cols = [col[1] for col in columns]
        
        removed_cols = [col for col in deprecated_cols if col not in existing_cols]
        if removed_cols:
            logger.info(f"\n✅ Successfully removed columns: {', '.join(removed_cols)}")
        else:
            logger.warning("\n⚠️  No deprecated columns were found to remove")
            
    except Exception as e:
        logger.error(f"Failed to drop columns: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    """Main function with confirmation prompt"""
    
    print("\n⚠️  WARNING: This will permanently remove the following columns:")
    print("  - http_method")
    print("  - endpoint_template")
    print("  - headers_template")
    print("  - body_template")
    print("\nMake sure all data has been migrated to service_config!")
    
    response = input("\nDo you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    drop_deprecated_columns()

if __name__ == "__main__":
    main()
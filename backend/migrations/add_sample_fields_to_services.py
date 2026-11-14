"""
Add sample_input and sample_output columns to application_services table
"""

import sqlite3
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add sample_input and sample_output columns to application_services table"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / "ioflow.db"
    
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(application_services)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add sample_input column if it doesn't exist
        if 'sample_input' not in column_names:
            logger.info("Adding sample_input column to application_services table")
            cursor.execute("""
                ALTER TABLE application_services 
                ADD COLUMN sample_input TEXT
            """)
            logger.info("sample_input column added successfully")
        else:
            logger.info("sample_input column already exists")
        
        # Add sample_output column if it doesn't exist
        if 'sample_output' not in column_names:
            logger.info("Adding sample_output column to application_services table")
            cursor.execute("""
                ALTER TABLE application_services 
                ADD COLUMN sample_output TEXT
            """)
            logger.info("sample_output column added successfully")
        else:
            logger.info("sample_output column already exists")
        
        # Commit changes
        conn.commit()
        
        # Verify columns were added
        cursor.execute("PRAGMA table_info(application_services)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'sample_input' in column_names and 'sample_output' in column_names:
            logger.info("Migration completed successfully - both columns are present")
            
            # Count existing services
            cursor.execute("SELECT COUNT(*) FROM application_services")
            service_count = cursor.fetchone()[0]
            logger.info(f"Total services in database: {service_count}")
            
            # Check if any services have sample data from seed files
            cursor.execute("""
                SELECT service_name, sample_input, sample_output 
                FROM application_services 
                WHERE sample_input IS NOT NULL OR sample_output IS NOT NULL
                LIMIT 5
            """)
            services_with_samples = cursor.fetchall()
            if services_with_samples:
                logger.info(f"Found {len(services_with_samples)} services with sample data")
                for service in services_with_samples:
                    logger.info(f"  - {service[0]}: has_input={service[1] is not None}, has_output={service[2] is not None}")
            else:
                logger.info("No services have sample data yet (this is expected for existing installations)")
                logger.info("Sample data will be populated when applications are reinstalled or updated")
        else:
            logger.error("Migration failed - columns were not added properly")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = migrate()
    if success:
        print("\n✅ Migration completed successfully!")
        print("Note: Sample data will be populated when applications are reinstalled or updated.")
    else:
        print("\n❌ Migration failed. Check the logs above for details.")
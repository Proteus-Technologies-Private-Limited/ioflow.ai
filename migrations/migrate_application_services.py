#!/usr/bin/env python3
"""
Migration script to add missing columns to application_services table
"""
import logging
from sqlalchemy import create_engine, text, inspect
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_application_services():
    """Add missing columns to application_services table"""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Get current columns
        inspector = inspect(engine)
        existing_columns = [col['name'] for col in inspector.get_columns('application_services')]
        
        logger.info(f"Existing columns: {existing_columns}")
        
        # Define columns to add
        columns_to_add = []
        
        if 'service_config' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN service_config TEXT")
            
        if 'http_method' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN http_method VARCHAR(10)")
            
        if 'endpoint_template' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN endpoint_template VARCHAR(500)")
            
        if 'headers_template' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN headers_template TEXT")
            
        if 'body_template' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN body_template TEXT")
            
        if 'is_async' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN is_async BOOLEAN DEFAULT 0")
            
        if 'async_config' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN async_config TEXT")
            
        if 'input_schema' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN input_schema TEXT")
            
        if 'output_schema' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN output_schema TEXT")
            
        if 'error_schema' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN error_schema TEXT")
            
        if 'retry_config' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN retry_config TEXT")
            
        if 'timeout_seconds' not in existing_columns:
            columns_to_add.append("ALTER TABLE application_services ADD COLUMN timeout_seconds INTEGER DEFAULT 30")
            
        # Execute migrations
        if columns_to_add:
            logger.info(f"Adding {len(columns_to_add)} columns...")
            for sql in columns_to_add:
                try:
                    conn.execute(text(sql))
                    logger.info(f"Executed: {sql}")
                except Exception as e:
                    logger.error(f"Error executing {sql}: {e}")
            conn.commit()
            logger.info("Migration completed successfully!")
        else:
            logger.info("No columns to add - schema is up to date")
            
        # Verify the migration
        inspector = inspect(engine)
        final_columns = [col['name'] for col in inspector.get_columns('application_services')]
        logger.info(f"Final columns: {final_columns}")

if __name__ == "__main__":
    migrate_application_services()
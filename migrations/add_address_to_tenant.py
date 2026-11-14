"""
Migration script to add address field to tenants table
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_address_field():
    """Add address field to tenants table"""
    # Use absolute path for database to ensure we're modifying the correct one
    backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
    db_path = os.path.join(backend_dir, 'ioflow.db')
    db_url = f"sqlite:///{db_path}"

    logger.info(f"Using database: {db_url}")
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            # Check if column already exists
            if db_url.startswith("sqlite"):
                result = conn.execute(text("PRAGMA table_info(tenants)"))
                columns = [row[1] for row in result]

                if 'address' not in columns:
                    logger.info("Adding 'address' column to tenants table...")
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN address TEXT"))
                    conn.commit()
                    logger.info("Successfully added 'address' column to tenants table")
                else:
                    logger.info("Column 'address' already exists in tenants table")
            else:
                # PostgreSQL
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'ioflow'
                    AND table_name = 'tenants'
                    AND column_name = 'address'
                """))

                if not result.fetchone():
                    logger.info("Adding 'address' column to tenants table...")
                    conn.execute(text("ALTER TABLE ioflow.tenants ADD COLUMN address TEXT"))
                    conn.commit()
                    logger.info("Successfully added 'address' column to tenants table")
                else:
                    logger.info("Column 'address' already exists in tenants table")

    except Exception as e:
        logger.error(f"Error adding address field: {str(e)}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    logger.info("Starting migration: add_address_to_tenant")
    add_address_field()
    logger.info("Migration completed successfully")

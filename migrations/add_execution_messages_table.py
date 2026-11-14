"""
Migration script to add execution_messages table for multi-worker WebSocket support
"""
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Create execution_messages table"""
    engine = create_engine(settings.database_url)

    # SQL to create the table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS execution_messages (
        message_id VARCHAR(36) PRIMARY KEY,
        execution_id VARCHAR(36) NOT NULL,
        tenant_id VARCHAR(36) NOT NULL,
        message_type VARCHAR(50) NOT NULL,
        message_data TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        consumed INTEGER NOT NULL DEFAULT 0
    );
    """

    # SQL to create indexes
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_execution_messages_execution_id ON execution_messages(execution_id);",
        "CREATE INDEX IF NOT EXISTS idx_execution_messages_tenant_id ON execution_messages(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_execution_messages_execution_tenant ON execution_messages(execution_id, tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_execution_messages_tenant_consumed_created ON execution_messages(tenant_id, consumed, created_at);"
    ]

    try:
        with engine.connect() as conn:
            # Create table
            logger.info("Creating execution_messages table...")
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("✓ Table created successfully")

            # Create indexes
            for idx_sql in create_indexes_sql:
                logger.info(f"Creating index...")
                conn.execute(text(idx_sql))
                conn.commit()
            logger.info("✓ All indexes created successfully")

        logger.info("Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()

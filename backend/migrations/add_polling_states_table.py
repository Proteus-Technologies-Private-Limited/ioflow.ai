"""
Add polling_states table for generic polling mechanism
"""
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from core.config import settings
import logging

logger = logging.getLogger(__name__)

def create_polling_states_table():
    """Create the polling_states table"""
    engine = create_engine(settings.database_url)
    
    # SQL for creating the table
    if settings.database_url.startswith("sqlite"):
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS polling_states (
            polling_state_id VARCHAR(36) PRIMARY KEY,
            flow_id VARCHAR(36) NOT NULL,
            app_id VARCHAR(36) NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            event_name VARCHAR(255) NOT NULL,
            last_poll_state JSON,
            last_poll_timestamp TIMESTAMP,
            last_successful_poll TIMESTAMP,
            items_processed JSON,
            items_processed_count INTEGER DEFAULT 0,
            consecutive_errors INTEGER DEFAULT 0,
            last_error TEXT,
            last_error_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(flow_id, app_id, event_name)
        );
        """
        
        create_indices_sql = [
            "CREATE INDEX IF NOT EXISTS idx_polling_states_flow_id ON polling_states(flow_id);",
            "CREATE INDEX IF NOT EXISTS idx_polling_states_tenant_id ON polling_states(tenant_id);"
        ]
    else:
        # PostgreSQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS polling_states (
            polling_state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            flow_id UUID NOT NULL,
            app_id UUID NOT NULL,
            tenant_id UUID NOT NULL,
            event_name VARCHAR(255) NOT NULL,
            last_poll_state JSONB,
            last_poll_timestamp TIMESTAMP,
            last_successful_poll TIMESTAMP,
            items_processed JSONB DEFAULT '[]'::jsonb,
            items_processed_count INTEGER DEFAULT 0,
            consecutive_errors INTEGER DEFAULT 0,
            last_error TEXT,
            last_error_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(flow_id, app_id, event_name)
        );
        """
        
        create_indices_sql = [
            "CREATE INDEX IF NOT EXISTS idx_polling_states_flow_id ON polling_states(flow_id);",
            "CREATE INDEX IF NOT EXISTS idx_polling_states_tenant_id ON polling_states(tenant_id);"
        ]
    
    try:
        with engine.connect() as conn:
            # Create table
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("Created polling_states table")
            
            # Create indices
            for index_sql in create_indices_sql:
                conn.execute(text(index_sql))
                conn.commit()
            logger.info("Created indices for polling_states table")
            
            return True
            
    except OperationalError as e:
        if "already exists" in str(e):
            logger.info("polling_states table already exists")
            return True
        else:
            logger.error(f"Error creating polling_states table: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error creating polling_states table: {e}")
        raise
    finally:
        engine.dispose()

def drop_polling_states_table():
    """Drop the polling_states table (for rollback)"""
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS polling_states CASCADE;"))
            conn.commit()
            logger.info("Dropped polling_states table")
            return True
    except Exception as e:
        logger.error(f"Error dropping polling_states table: {e}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run migration
    print("Creating polling_states table...")
    if create_polling_states_table():
        print("✅ Successfully created polling_states table")
    else:
        print("❌ Failed to create polling_states table")
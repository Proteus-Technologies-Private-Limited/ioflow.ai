"""
Migration script to add chat_sessions and node_session_states tables
for chat input trigger and agent session continuity support.
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
    """Create chat_sessions and node_session_states tables"""
    engine = create_engine(settings.database_url)

    # SQL to create chat_sessions table
    create_chat_sessions_sql = """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        flow_id VARCHAR(36) NOT NULL,
        user_id VARCHAR(36) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_message_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        message_count INTEGER NOT NULL DEFAULT 0,
        expires_at TIMESTAMP
    );
    """

    # SQL to create node_session_states table
    create_node_session_states_sql = """
    CREATE TABLE IF NOT EXISTS node_session_states (
        id VARCHAR(36) PRIMARY KEY,
        node_id VARCHAR(100) NOT NULL,
        chat_session_id VARCHAR(36) NOT NULL,
        tenant_id VARCHAR(36) NOT NULL,
        node_type VARCHAR(50) NOT NULL,
        agent_session_id VARCHAR(100),
        session_data TEXT,
        user_id VARCHAR(36),
        flow_id VARCHAR(36),
        first_invocation_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_invocation_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        invocation_count INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (chat_session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
        CONSTRAINT unique_node_chat_session UNIQUE (node_id, chat_session_id, tenant_id)
    );
    """

    # SQL to create indexes for chat_sessions
    chat_sessions_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant_id ON chat_sessions(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_flow_id ON chat_sessions(flow_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_status ON chat_sessions(status);",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires_at ON chat_sessions(expires_at);"
    ]

    # SQL to create indexes for node_session_states
    node_session_states_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_node_session_states_node_id ON node_session_states(node_id);",
        "CREATE INDEX IF NOT EXISTS idx_node_session_states_chat_session_id ON node_session_states(chat_session_id);",
        "CREATE INDEX IF NOT EXISTS idx_node_session_states_tenant_id ON node_session_states(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_node_session_states_is_active ON node_session_states(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_node_session_states_lookup ON node_session_states(node_id, chat_session_id, tenant_id, is_active);"
    ]

    try:
        with engine.connect() as conn:
            # Create chat_sessions table
            logger.info("Creating chat_sessions table...")
            conn.execute(text(create_chat_sessions_sql))
            conn.commit()
            logger.info("  Table chat_sessions created successfully")

            # Create chat_sessions indexes
            logger.info("Creating indexes for chat_sessions...")
            for idx_sql in chat_sessions_indexes_sql:
                conn.execute(text(idx_sql))
                conn.commit()
            logger.info("  Indexes created successfully")

            # Create node_session_states table
            logger.info("Creating node_session_states table...")
            conn.execute(text(create_node_session_states_sql))
            conn.commit()
            logger.info("  Table node_session_states created successfully")

            # Create node_session_states indexes
            logger.info("Creating indexes for node_session_states...")
            for idx_sql in node_session_states_indexes_sql:
                conn.execute(text(idx_sql))
                conn.commit()
            logger.info("  Indexes created successfully")

        logger.info("")
        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("Tables created:")
        logger.info("  - chat_sessions: Tracks chat sessions for flows with chat_input triggers")
        logger.info("  - node_session_states: Stores node-level persistent state (e.g., agent session IDs)")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()

"""
Migration script to add Event Wait table:
- event_waits: Tracks paused executions waiting for application events
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
    """Create event_waits table"""
    engine = create_engine(settings.database_url)
    is_sqlite = settings.database_url.startswith("sqlite")

    if is_sqlite:
        _run_sqlite_migration(engine)
    else:
        _run_postgresql_migration(engine)


def _run_sqlite_migration(engine):
    """Create event_waits table for SQLite"""

    create_event_waits_sql = """
    CREATE TABLE IF NOT EXISTS event_waits (
        wait_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        execution_id VARCHAR(36) NOT NULL,
        flow_id VARCHAR(36) NOT NULL,
        node_id VARCHAR(100) NOT NULL,
        app_id VARCHAR(36) NOT NULL,
        event_name VARCHAR(255) NOT NULL,
        event_id VARCHAR(36),
        match_mode VARCHAR(20) NOT NULL DEFAULT 'token',
        correlation_config TEXT,
        callback_token VARCHAR(255) NOT NULL UNIQUE,
        status VARCHAR(20) NOT NULL DEFAULT 'waiting',
        timeout_at TIMESTAMP,
        timeout_action VARCHAR(30) DEFAULT 'fail',
        default_data TEXT,
        execution_snapshot TEXT,
        event_data TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        matched_at TIMESTAMP,
        metadata TEXT,
        FOREIGN KEY (execution_id) REFERENCES flow_executions(execution_id)
    );
    """

    indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_event_waits_tenant_status ON event_waits(tenant_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_app_event_status ON event_waits(app_id, event_name, status);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_callback_token ON event_waits(callback_token);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_execution ON event_waits(execution_id);",
    ]

    with engine.connect() as conn:
        logger.info("Creating event_waits table for SQLite...")
        conn.execute(text(create_event_waits_sql))

        for idx_sql in indexes_sql:
            conn.execute(text(idx_sql))

        conn.commit()
        logger.info("event_waits table created successfully for SQLite.")


def _run_postgresql_migration(engine):
    """Create event_waits table for PostgreSQL"""

    create_event_waits_sql = """
    CREATE TABLE IF NOT EXISTS ioflow.event_waits (
        wait_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        execution_id VARCHAR(36) NOT NULL REFERENCES ioflow.flow_executions(execution_id),
        flow_id VARCHAR(36) NOT NULL,
        node_id VARCHAR(100) NOT NULL,
        app_id VARCHAR(36) NOT NULL,
        event_name VARCHAR(255) NOT NULL,
        event_id VARCHAR(36),
        match_mode VARCHAR(20) NOT NULL DEFAULT 'token',
        correlation_config JSONB,
        callback_token VARCHAR(255) NOT NULL UNIQUE,
        status VARCHAR(20) NOT NULL DEFAULT 'waiting',
        timeout_at TIMESTAMP,
        timeout_action VARCHAR(30) DEFAULT 'fail',
        default_data JSONB,
        execution_snapshot JSONB,
        event_data JSONB,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        matched_at TIMESTAMP,
        metadata JSONB
    );
    """

    indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_event_waits_tenant_status ON ioflow.event_waits(tenant_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_app_event_status ON ioflow.event_waits(app_id, event_name, status);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_callback_token ON ioflow.event_waits(callback_token);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_execution ON ioflow.event_waits(execution_id);",
        "CREATE INDEX IF NOT EXISTS idx_event_waits_app_event_tenant ON ioflow.event_waits(app_id, event_name, status, tenant_id);",
    ]

    with engine.connect() as conn:
        logger.info("Creating event_waits table for PostgreSQL...")
        conn.execute(text(create_event_waits_sql))

        for idx_sql in indexes_sql:
            conn.execute(text(idx_sql))

        conn.commit()
        logger.info("event_waits table created successfully for PostgreSQL.")


if __name__ == "__main__":
    run_migration()

#!/usr/bin/env python3
"""
Migration script to create flow example ratings, favorites, and usage stats tables.
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Create flow example related tables"""
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        logger.info("Creating flow_example_ratings table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_example_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                example_id VARCHAR(100) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                tenant_id VARCHAR(36) NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                review VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                UNIQUE (example_id, user_id)
            )
        """))

        logger.info("Creating indexes for flow_example_ratings...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_example_ratings
            ON flow_example_ratings(example_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_ratings
            ON flow_example_ratings(user_id)
        """))

        logger.info("Creating flow_example_favorites table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_example_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                example_id VARCHAR(100) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                tenant_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                UNIQUE (example_id, user_id)
            )
        """))

        logger.info("Creating indexes for flow_example_favorites...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_example_favorites
            ON flow_example_favorites(example_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_favorites
            ON flow_example_favorites(user_id)
        """))

        logger.info("Creating flow_example_usage_stats table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_example_usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                example_id VARCHAR(100) UNIQUE NOT NULL,
                import_count INTEGER DEFAULT 0 NOT NULL,
                last_imported_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        logger.info("Creating indexes for flow_example_usage_stats...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_import_count
            ON flow_example_usage_stats(import_count)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_last_imported
            ON flow_example_usage_stats(last_imported_at)
        """))

        conn.commit()
        logger.info("✓ All tables created successfully!")

if __name__ == "__main__":
    run_migration()

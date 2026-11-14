"""
Migration: Add micro_saas_related_flows table

This migration creates the table for storing pre-requisite and follow-up flow relationships
between micro SaaS applications.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text, inspect
from core.config import settings


def run_migration():
    """Create the micro_saas_related_flows table"""

    engine = create_engine(settings.database_url)

    # Check if table already exists
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if 'micro_saas_related_flows' in existing_tables:
        print("Table 'micro_saas_related_flows' already exists. Skipping creation.")
        return True

    # SQLite-compatible create statement
    create_table_sql = """
    CREATE TABLE micro_saas_related_flows (
        relationship_id VARCHAR(36) PRIMARY KEY,
        frontend_app_id VARCHAR(36) NOT NULL,
        related_frontend_app_id VARCHAR(36) NOT NULL,
        relationship_type VARCHAR(20) NOT NULL,
        is_mandatory INTEGER DEFAULT 0,
        execution_order INTEGER DEFAULT 0,
        display_name VARCHAR(255),
        documentation TEXT,
        parameter_mappings TEXT,
        auto_map_enabled INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE,
        FOREIGN KEY (related_frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE,
        UNIQUE(frontend_app_id, related_frontend_app_id, relationship_type)
    )
    """

    # Create indexes for better query performance
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_related_flows_frontend_app ON micro_saas_related_flows(frontend_app_id)",
        "CREATE INDEX IF NOT EXISTS idx_related_flows_related_app ON micro_saas_related_flows(related_frontend_app_id)",
        "CREATE INDEX IF NOT EXISTS idx_related_flows_type ON micro_saas_related_flows(relationship_type)",
        "CREATE INDEX IF NOT EXISTS idx_related_flows_active ON micro_saas_related_flows(is_active)"
    ]

    try:
        with engine.connect() as conn:
            # Create the table
            conn.execute(text(create_table_sql))
            print("Created table 'micro_saas_related_flows'")

            # Create indexes
            for index_sql in create_indexes_sql:
                conn.execute(text(index_sql))
            print("Created indexes for 'micro_saas_related_flows'")

            conn.commit()

        print("Migration completed successfully!")
        return True

    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return False


def rollback_migration():
    """Drop the micro_saas_related_flows table"""

    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS micro_saas_related_flows"))
            conn.commit()

        print("Rollback completed successfully!")
        return True

    except Exception as e:
        print(f"Rollback failed: {str(e)}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migration for micro_saas_related_flows table")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")

    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()

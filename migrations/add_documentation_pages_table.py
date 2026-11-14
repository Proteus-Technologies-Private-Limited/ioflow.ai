"""
Migration script to add app_documentation_pages table for micro SaaS documentation
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
    """Create app_documentation_pages table"""
    engine = create_engine(settings.database_url)

    # SQL to create the table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS app_documentation_pages (
        page_id VARCHAR(36) PRIMARY KEY,
        frontend_app_id VARCHAR(36) NOT NULL,
        page_type VARCHAR(50) NOT NULL DEFAULT 'custom',
        page_title VARCHAR(255) NOT NULL,
        page_slug VARCHAR(255) NOT NULL,
        content TEXT NOT NULL,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_published INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE
    );
    """

    # SQL to create indexes
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_app_doc_pages ON app_documentation_pages(frontend_app_id);",
        "CREATE INDEX IF NOT EXISTS idx_doc_page_slug ON app_documentation_pages(page_slug);",
        "CREATE INDEX IF NOT EXISTS idx_doc_page_type ON app_documentation_pages(page_type);",
        "CREATE INDEX IF NOT EXISTS idx_doc_display_order ON app_documentation_pages(display_order);",
        "CREATE INDEX IF NOT EXISTS idx_app_doc_published ON app_documentation_pages(frontend_app_id, is_published);"
    ]

    try:
        with engine.connect() as conn:
            # Create table
            logger.info("Creating app_documentation_pages table...")
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
        logger.info("Documentation pages feature is now ready to use.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()

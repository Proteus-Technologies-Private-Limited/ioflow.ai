#!/usr/bin/env python3
"""
Add Landing Page Designer support:
- page_definition JSONB column on frontend_flow_applications
- landing_page_images table for uploaded images
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from sqlalchemy import create_engine, text, inspect
from core.config import settings

def run_migration():
    """Run the landing page designer migration"""
    engine = create_engine(settings.database_url)

    # Determine schema
    is_postgres = settings.database_url.startswith("postgresql")
    schema_prefix = "ioflow." if is_postgres else ""

    with engine.begin() as conn:
        print("=" * 60)
        print("Landing Page Designer Migration")
        print("=" * 60)

        inspector = inspect(engine)

        # 1. Add page_definition column to frontend_flow_applications
        print("\n1. Adding page_definition column to frontend_flow_applications...")
        existing_columns = [col['name'] for col in inspector.get_columns(
            'frontend_flow_applications', schema='ioflow' if is_postgres else None
        )]

        if 'page_definition' not in existing_columns:
            if is_postgres:
                conn.execute(text(f"""
                    ALTER TABLE {schema_prefix}frontend_flow_applications
                    ADD COLUMN page_definition JSONB DEFAULT NULL
                """))
            else:
                conn.execute(text("""
                    ALTER TABLE frontend_flow_applications
                    ADD COLUMN page_definition TEXT DEFAULT NULL
                """))
            print("   Added page_definition column")
        else:
            print("   page_definition column already exists")

        # 2. Create landing_page_images table
        print("\n2. Creating landing_page_images table...")
        existing_tables = inspector.get_table_names(schema='ioflow' if is_postgres else None)

        if 'landing_page_images' not in existing_tables:
            if is_postgres:
                conn.execute(text(f"""
                    CREATE TABLE {schema_prefix}landing_page_images (
                        image_id VARCHAR(36) PRIMARY KEY,
                        frontend_app_id VARCHAR(36) NOT NULL REFERENCES {schema_prefix}frontend_flow_applications(frontend_app_id) ON DELETE CASCADE,
                        filename VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(255) NOT NULL,
                        content_type VARCHAR(100) NOT NULL,
                        file_size INTEGER NOT NULL,
                        storage_path VARCHAR(500) NOT NULL,
                        public_url VARCHAR(500) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text(f"""
                    CREATE INDEX idx_landing_page_images_app_id
                    ON {schema_prefix}landing_page_images(frontend_app_id)
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE landing_page_images (
                        image_id VARCHAR(36) PRIMARY KEY,
                        frontend_app_id VARCHAR(36) NOT NULL REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE,
                        filename VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(255) NOT NULL,
                        content_type VARCHAR(100) NOT NULL,
                        file_size INTEGER NOT NULL,
                        storage_path VARCHAR(500) NOT NULL,
                        public_url VARCHAR(500) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            print("   Created landing_page_images table")
        else:
            print("   landing_page_images table already exists")

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    run_migration()

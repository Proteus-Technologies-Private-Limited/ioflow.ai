"""
Migration to add tenant_id_owner to applications table if it doesn't exist
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings
from db.database import get_db_engine


def run_migration():
    """Add tenant_id_owner column to applications table if it doesn't exist"""
    engine = get_db_engine()
    
    # Check if we're using SQLite or PostgreSQL
    is_sqlite = settings.database_url.startswith("sqlite")
    
    with engine.connect() as conn:
        # Check if column already exists
        if is_sqlite:
            # SQLite doesn't have a direct way to check if column exists
            # We'll try to add it and ignore if it already exists
            try:
                conn.execute(text("""
                    ALTER TABLE applications ADD COLUMN tenant_id_owner TEXT 
                    REFERENCES tenants(tenant_id)
                """))
                print("Added tenant_id_owner column to applications table")
            except Exception as e:
                print(f"Column might already exist or error occurred: {e}")
        else:
            # PostgreSQL - check if column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'ioflow' 
                AND table_name = 'applications' 
                AND column_name = 'tenant_id_owner'
            """))
            
            if not result.fetchone():
                conn.execute(text("""
                    ALTER TABLE ioflow.applications 
                    ADD COLUMN tenant_id_owner UUID 
                    REFERENCES ioflow.tenants(tenant_id)
                """))
                print("Added tenant_id_owner column to applications table")
            else:
                print("tenant_id_owner column already exists in applications table")
        
        conn.commit()


if __name__ == "__main__":
    run_migration()
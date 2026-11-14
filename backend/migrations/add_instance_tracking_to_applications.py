"""
Migration to add instance tracking fields to applications table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings


def run_migration():
    """Add instance tracking fields to applications table"""
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        # Add new columns to applications table
        columns_to_add = [
            ("parent_seed_app_id", "VARCHAR(36)"),
            ("instance_number", "INTEGER DEFAULT 1"),
            ("instance_name", "VARCHAR(255)"),
            ("is_seed_app", "BOOLEAN DEFAULT 0"),
            ("total_instances", "INTEGER DEFAULT 0")
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                conn.execute(text(f"""
                    ALTER TABLE applications 
                    ADD COLUMN {column_name} {column_type}
                """))
                print(f"✅ Added column: {column_name}")
            except Exception as e:
                # Column might already exist
                print(f"⚠️  Column {column_name} might already exist: {e}")
        
        # Create index on parent_seed_app_id for faster lookups
        try:
            conn.execute(text("""
                CREATE INDEX idx_parent_seed_app_id 
                ON applications(parent_seed_app_id)
            """))
            print("✅ Created index on parent_seed_app_id")
        except Exception as e:
            print(f"⚠️  Index might already exist: {e}")
        
        # Update existing seed applications to mark them as seed apps
        conn.execute(text("""
            UPDATE applications 
            SET is_seed_app = 1 
            WHERE seed_key IS NOT NULL 
            AND parent_seed_app_id IS NULL
        """))
        
        # Set instance_number to 1 for all existing applications
        conn.execute(text("""
            UPDATE applications 
            SET instance_number = 1 
            WHERE instance_number IS NULL
        """))
        
        print("✅ Updated existing applications with default values")
        
        # Count instances for each seed application
        result = conn.execute(text("""
            SELECT seed_key, COUNT(*) as count
            FROM applications
            WHERE seed_key IS NOT NULL
            GROUP BY seed_key
        """))
        
        for row in result:
            if row[1] > 0:
                # Update total_instances for seed applications
                conn.execute(text("""
                    UPDATE applications
                    SET total_instances = :count
                    WHERE seed_key = :seed_key
                    AND is_seed_app = 1
                """), {"count": row[1] - 1, "seed_key": row[0]})  # -1 because seed app doesn't count as instance
                
                print(f"  - Updated instance count for {row[0]}: {row[1] - 1} instances")
    
    print("✅ Migration completed successfully")


def rollback_migration():
    """Remove instance tracking fields from applications table"""
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        # Drop the index first
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_parent_seed_app_id"))
            print("✅ Dropped index: idx_parent_seed_app_id")
        except Exception as e:
            print(f"⚠️  Error dropping index: {e}")
        
        # Remove columns
        columns_to_remove = [
            "parent_seed_app_id",
            "instance_number",
            "instance_name",
            "is_seed_app",
            "total_instances"
        ]
        
        if settings.database_url.startswith("sqlite"):
            # SQLite doesn't support dropping columns easily
            print("⚠️  SQLite doesn't support dropping columns. Manual intervention required.")
        else:
            for column_name in columns_to_remove:
                try:
                    conn.execute(text(f"""
                        ALTER TABLE applications 
                        DROP COLUMN {column_name}
                    """))
                    print(f"✅ Dropped column: {column_name}")
                except Exception as e:
                    print(f"⚠️  Error dropping column {column_name}: {e}")
    
    print("✅ Rollback completed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()
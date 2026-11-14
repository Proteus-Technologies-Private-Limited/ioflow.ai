#!/usr/bin/env python3
"""
Database migration script to add category column to flows table
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config import settings

def add_category_column_sqlite():
    """Add category column to flows table in SQLite database"""
    db_path = settings.database_url.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if category column already exists
        cursor.execute("PRAGMA table_info(flows)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'category' not in columns:
            # Add the category column
            cursor.execute("ALTER TABLE flows ADD COLUMN category VARCHAR(100)")
            conn.commit()
            print("Successfully added 'category' column to flows table")
        else:
            print("Category column already exists in flows table")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error adding category column: {e}")
        return False

def main():
    """Main migration function"""
    print("Adding category column to flows table...")
    
    if settings.database_url.startswith("sqlite"):
        success = add_category_column_sqlite()
    else:
        print("PostgreSQL migration not implemented. Please add the column manually:")
        print("ALTER TABLE tenant_schema.flows ADD COLUMN category VARCHAR(100);")
        success = False
    
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
    
    return success

if __name__ == "__main__":
    main()
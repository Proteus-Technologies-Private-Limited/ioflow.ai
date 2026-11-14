"""
Manual migration script to add base_url column to applications table
"""
import sqlite3
import sys
from pathlib import Path

def add_base_url_column():
    """Add base_url column to applications table"""
    # Path to SQLite database
    db_path = Path(__file__).parent / "ioflow.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(applications)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'base_url' in column_names:
            print("Column 'base_url' already exists in applications table")
            return True
        
        # Add base_url column
        print("Adding base_url column to applications table...")
        cursor.execute("ALTER TABLE applications ADD COLUMN base_url VARCHAR(500)")
        
        conn.commit()
        print("Successfully added base_url column")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(applications)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'base_url' in column_names:
            print("Verified: base_url column has been added")
            return True
        else:
            print("Error: base_url column was not added")
            return False
            
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = add_base_url_column()
    sys.exit(0 if success else 1)
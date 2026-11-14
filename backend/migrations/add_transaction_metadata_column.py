#!/usr/bin/env python3
"""
Migration to add transaction_metadata column to balance_transactions table.
The table currently has 'metadata' but the code expects 'transaction_metadata'.
"""

import sqlite3
import sys
import os
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_migration():
    """Add transaction_metadata column to balance_transactions table"""
    
    # Connect to the database
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ioflow.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if transaction_metadata column already exists
        cursor.execute("PRAGMA table_info(balance_transactions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'transaction_metadata' in column_names:
            print("Column 'transaction_metadata' already exists")
            return True
        
        # Add the transaction_metadata column
        print("Adding transaction_metadata column to balance_transactions table...")
        cursor.execute("""
            ALTER TABLE balance_transactions 
            ADD COLUMN transaction_metadata TEXT
        """)
        
        # If there's existing data in metadata column, copy it to transaction_metadata
        if 'metadata' in column_names:
            print("Copying data from metadata to transaction_metadata column...")
            cursor.execute("""
                UPDATE balance_transactions 
                SET transaction_metadata = metadata
                WHERE metadata IS NOT NULL
            """)
        
        conn.commit()
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
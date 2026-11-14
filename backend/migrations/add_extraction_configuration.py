#!/usr/bin/env python3
"""
Add extraction_configuration column to application_events table
This allows storing parameter mappings and data extraction configurations for webhook events
"""
import sqlite3
import os
import sys

def add_extraction_configuration_column():
    """Add extraction_configuration column to application_events table"""
    
    # Path to the database
    db_path = os.path.join(os.path.dirname(__file__), '..', 'ioflow.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(application_events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'extraction_configuration' in columns:
            print("✅ extraction_configuration column already exists")
            return True
        
        print("🔧 Adding extraction_configuration column to application_events table...")
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE application_events 
            ADD COLUMN extraction_configuration TEXT
        """)
        
        conn.commit()
        print("✅ Successfully added extraction_configuration column")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(application_events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'extraction_configuration' in columns:
            print("✅ Column verified in database schema")
            return True
        else:
            print("❌ Column not found after migration")
            return False
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Main migration function"""
    print("🚀 Running extraction_configuration column migration")
    print("=" * 50)
    
    success = add_extraction_configuration_column()
    
    if success:
        print("🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Reinstall MSG91 application to populate parameter mappings")
        print("3. Check that parameter mappings are now visible in the UI")
    else:
        print("❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
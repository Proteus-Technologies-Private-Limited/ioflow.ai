#!/usr/bin/env python3
"""
Drop the unique constraint on (session_id, user_id) in collaboration_participants table
to allow the same user to join from multiple browser sessions.
"""

import sqlite3
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

def drop_unique_constraint():
    """Drop the unique constraint from collaboration_participants table"""
    
    # Connect to database
    db_path = settings.database_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='collaboration_participants'
        """)
        
        if not cursor.fetchone():
            print("Table collaboration_participants does not exist")
            return
        
        # Get the current table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='collaboration_participants'")
        create_sql = cursor.fetchone()[0]
        print(f"Current table schema:\n{create_sql}\n")
        
        # SQLite doesn't support dropping constraints directly
        # We need to recreate the table without the constraint
        
        # Create a temporary table without the unique constraint
        cursor.execute("""
            CREATE TABLE collaboration_participants_new (
                participant_id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36) NOT NULL REFERENCES collaboration_sessions(session_id),
                user_id VARCHAR(36),
                display_name VARCHAR(100) NOT NULL,
                email VARCHAR(255),
                role VARCHAR(10) DEFAULT 'EDITOR',
                can_edit BOOLEAN DEFAULT 1,
                can_delete BOOLEAN DEFAULT 1,
                can_invite BOOLEAN DEFAULT 0,
                color VARCHAR(7) NOT NULL,
                avatar_url VARCHAR(500),
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_online BOOLEAN DEFAULT 1,
                connection_id VARCHAR(255),
                cursor_position JSON,
                viewport JSON,
                selected_nodes JSON,
                selected_edges JSON,
                edit_count INTEGER DEFAULT 0
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO collaboration_participants_new 
            SELECT * FROM collaboration_participants
        """)
        
        # Drop the old table
        cursor.execute("DROP TABLE collaboration_participants")
        
        # Rename the new table
        cursor.execute("ALTER TABLE collaboration_participants_new RENAME TO collaboration_participants")
        
        # Recreate indexes (without the unique constraint)
        cursor.execute("""
            CREATE INDEX idx_collaboration_participant_session 
            ON collaboration_participants(session_id)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_collaboration_participant_user 
            ON collaboration_participants(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_collaboration_participant_online 
            ON collaboration_participants(session_id, is_online)
        """)
        
        # Commit changes
        conn.commit()
        print("Successfully removed unique constraint from collaboration_participants table")
        
        # Verify the change
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='collaboration_participants'")
        new_create_sql = cursor.fetchone()[0]
        print(f"\nNew table schema:\n{new_create_sql}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    drop_unique_constraint()
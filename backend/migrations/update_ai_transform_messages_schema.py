#!/usr/bin/env python3
"""
Migration to update ai_transform_messages table schema to match the model definition
"""

import sqlite3
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from core.config import settings

def run_migration():
    """Update ai_transform_messages table schema"""
    
    # Extract database path from SQLite URL
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "")
    else:
        print("This migration is for SQLite only")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration to update ai_transform_messages schema...")
        
        # Check if the table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ai_transform_messages'
        """)
        
        if not cursor.fetchone():
            print("Table ai_transform_messages does not exist. Creating it...")
            # Create the table with the correct schema
            cursor.execute("""
                CREATE TABLE ai_transform_messages (
                    message_id VARCHAR(36) PRIMARY KEY,
                    conversation_id VARCHAR(36) NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    message_type VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    generated_code TEXT,
                    explanation TEXT,
                    warnings TEXT,
                    test_cases TEXT,
                    ai_provider VARCHAR(50),
                    ai_model VARCHAR(100),
                    was_applied BOOLEAN DEFAULT 0,
                    applied_at TIMESTAMP,
                    generation_time_ms INTEGER,
                    token_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES ai_transform_conversations(conversation_id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX idx_message_conversation_sequence 
                ON ai_transform_messages(conversation_id, sequence_number)
            """)
            
            cursor.execute("""
                CREATE INDEX idx_message_type 
                ON ai_transform_messages(message_type)
            """)
            
            print("Table created successfully with correct schema")
        else:
            # Check if we need to migrate existing data
            cursor.execute("PRAGMA table_info(ai_transform_messages)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'sequence_number' not in column_names:
                print("Migrating existing table to new schema...")
                
                # Create a new table with the correct schema
                cursor.execute("""
                    CREATE TABLE ai_transform_messages_new (
                        message_id VARCHAR(36) PRIMARY KEY,
                        conversation_id VARCHAR(36) NOT NULL,
                        sequence_number INTEGER NOT NULL,
                        message_type VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        generated_code TEXT,
                        explanation TEXT,
                        warnings TEXT,
                        test_cases TEXT,
                        ai_provider VARCHAR(50),
                        ai_model VARCHAR(100),
                        was_applied BOOLEAN DEFAULT 0,
                        applied_at TIMESTAMP,
                        generation_time_ms INTEGER,
                        token_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES ai_transform_conversations(conversation_id) ON DELETE CASCADE
                    )
                """)
                
                # Check if there's data to migrate
                cursor.execute("SELECT COUNT(*) FROM ai_transform_messages")
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f"Migrating {count} existing messages...")
                    # Migrate existing data (map 'role' to 'message_type' and add sequence_number)
                    cursor.execute("""
                        INSERT INTO ai_transform_messages_new 
                        (message_id, conversation_id, sequence_number, message_type, content, 
                         generated_code, explanation, warnings, test_cases, ai_provider, ai_model,
                         was_applied, applied_at, generation_time_ms, token_count, created_at)
                        SELECT 
                            message_id,
                            conversation_id,
                            ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at) as sequence_number,
                            CASE 
                                WHEN role = 'user' THEN 'user_prompt'
                                WHEN role = 'assistant' THEN 'ai_response'
                                ELSE 'system_info'
                            END as message_type,
                            content,
                            CASE 
                                WHEN metadata IS NOT NULL THEN json_extract(metadata, '$.generated_code')
                                ELSE NULL
                            END as generated_code,
                            CASE 
                                WHEN metadata IS NOT NULL THEN json_extract(metadata, '$.explanation')
                                ELSE NULL
                            END as explanation,
                            CASE 
                                WHEN metadata IS NOT NULL THEN json_extract(metadata, '$.warnings')
                                ELSE NULL
                            END as warnings,
                            CASE 
                                WHEN metadata IS NOT NULL THEN json_extract(metadata, '$.test_cases')
                                ELSE NULL
                            END as test_cases,
                            NULL as ai_provider,
                            NULL as ai_model,
                            0 as was_applied,
                            NULL as applied_at,
                            tokens_used as generation_time_ms,
                            tokens_used as token_count,
                            created_at
                        FROM ai_transform_messages
                    """)
                
                # Drop the old table and rename the new one
                cursor.execute("DROP TABLE ai_transform_messages")
                cursor.execute("ALTER TABLE ai_transform_messages_new RENAME TO ai_transform_messages")
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX idx_message_conversation_sequence 
                    ON ai_transform_messages(conversation_id, sequence_number)
                """)
                
                cursor.execute("""
                    CREATE INDEX idx_message_type 
                    ON ai_transform_messages(message_type)
                """)
                
                print("Migration completed successfully")
            else:
                print("Table already has correct schema, no migration needed")
        
        # Also create the snapshots table if it doesn't exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ai_transform_snapshots'
        """)
        
        if not cursor.fetchone():
            print("Creating ai_transform_snapshots table...")
            cursor.execute("""
                CREATE TABLE ai_transform_snapshots (
                    snapshot_id VARCHAR(36) PRIMARY KEY,
                    conversation_id VARCHAR(36) NOT NULL,
                    message_id VARCHAR(36),
                    snapshot_name VARCHAR(255),
                    description TEXT,
                    transform_code TEXT NOT NULL,
                    context_snapshot TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES ai_transform_conversations(conversation_id) ON DELETE CASCADE,
                    FOREIGN KEY (message_id) REFERENCES ai_transform_messages(message_id)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX idx_snapshot_conversation 
                ON ai_transform_snapshots(conversation_id)
            """)
            
            print("Snapshots table created successfully")
        
        conn.commit()
        print("All migrations completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
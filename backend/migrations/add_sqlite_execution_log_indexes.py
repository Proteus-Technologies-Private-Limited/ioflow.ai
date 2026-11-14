"""
Add indexes to execution_logs table for SQLite database for better performance
"""
import logging
import sqlite3
import os
from core.config import settings

logger = logging.getLogger(__name__)

def add_sqlite_indexes():
    """Add indexes to execution_logs table in SQLite database"""
    
    # Only run for SQLite
    if not settings.database_url.startswith("sqlite"):
        logger.info("Not using SQLite, skipping SQLite index migration")
        return
    
    # Extract database path from URL
    db_path = settings.database_url.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='execution_logs'
        """)
        existing_indexes = {row[0] for row in cursor.fetchall()}
        
        # Create index on execution_id if not exists
        if 'idx_execution_logs_execution_id' not in existing_indexes:
            cursor.execute("""
                CREATE INDEX idx_execution_logs_execution_id 
                ON execution_logs(execution_id)
            """)
            logger.info("Created index idx_execution_logs_execution_id")
        else:
            logger.info("Index idx_execution_logs_execution_id already exists")
        
        # Create index on timestamp if not exists
        if 'idx_execution_logs_timestamp' not in existing_indexes:
            cursor.execute("""
                CREATE INDEX idx_execution_logs_timestamp 
                ON execution_logs(timestamp)
            """)
            logger.info("Created index idx_execution_logs_timestamp")
        else:
            logger.info("Index idx_execution_logs_timestamp already exists")
        
        # Create composite index on execution_id and timestamp if not exists
        if 'idx_execution_logs_exec_time' not in existing_indexes:
            cursor.execute("""
                CREATE INDEX idx_execution_logs_exec_time 
                ON execution_logs(execution_id, timestamp)
            """)
            logger.info("Created composite index idx_execution_logs_exec_time")
        else:
            logger.info("Index idx_execution_logs_exec_time already exists")
        
        # Create index on level for filtering
        if 'idx_execution_logs_level' not in existing_indexes:
            cursor.execute("""
                CREATE INDEX idx_execution_logs_level 
                ON execution_logs(level)
            """)
            logger.info("Created index idx_execution_logs_level")
        else:
            logger.info("Index idx_execution_logs_level already exists")
        
        # Also add indexes for flow_executions table for faster joins
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='flow_executions'
        """)
        exec_indexes = {row[0] for row in cursor.fetchall()}
        
        if 'idx_flow_executions_status' not in exec_indexes:
            cursor.execute("""
                CREATE INDEX idx_flow_executions_status 
                ON flow_executions(status)
            """)
            logger.info("Created index idx_flow_executions_status")
        
        if 'idx_flow_executions_flow_id' not in exec_indexes:
            cursor.execute("""
                CREATE INDEX idx_flow_executions_flow_id 
                ON flow_executions(flow_id)
            """)
            logger.info("Created index idx_flow_executions_flow_id")
        
        if 'idx_flow_executions_started' not in exec_indexes:
            cursor.execute("""
                CREATE INDEX idx_flow_executions_started 
                ON flow_executions(started_at DESC)
            """)
            logger.info("Created index idx_flow_executions_started")
        
        conn.commit()
        logger.info("Successfully added all indexes to SQLite database")
        
        # Analyze tables to update statistics
        cursor.execute("ANALYZE execution_logs")
        cursor.execute("ANALYZE flow_executions")
        logger.info("Updated table statistics")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error adding indexes to SQLite database: {e}")
        raise

def main():
    """Run the migration"""
    logging.basicConfig(level=logging.INFO)
    add_sqlite_indexes()
    print("✅ SQLite index migration completed")

if __name__ == "__main__":
    main()
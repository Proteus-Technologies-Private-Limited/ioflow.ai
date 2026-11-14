"""
Add indexes to execution_logs table for better performance
"""
import logging
from sqlalchemy import text
from db.database import get_tenant_db, engine

logger = logging.getLogger(__name__)

def add_indexes_to_tenant_schema(schema_name):
    """Add indexes to execution_logs table in a tenant schema"""
    try:
        with get_tenant_db(schema_name) as db:
            # Check if indexes already exist
            result = db.execute(text(f"""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = :schema 
                AND tablename = 'execution_logs'
                AND indexname IN ('idx_execution_logs_execution_id', 'idx_execution_logs_timestamp', 'idx_execution_logs_execution_timestamp')
            """), {"schema": schema_name})
            
            existing_indexes = {row[0] for row in result}
            
            # Create index on execution_id if not exists
            if 'idx_execution_logs_execution_id' not in existing_indexes:
                db.execute(text(f"""
                    CREATE INDEX idx_execution_logs_execution_id 
                    ON {schema_name}.execution_logs(execution_id)
                """))
                logger.info(f"Created index idx_execution_logs_execution_id in schema {schema_name}")
            
            # Create index on timestamp if not exists
            if 'idx_execution_logs_timestamp' not in existing_indexes:
                db.execute(text(f"""
                    CREATE INDEX idx_execution_logs_timestamp 
                    ON {schema_name}.execution_logs(timestamp)
                """))
                logger.info(f"Created index idx_execution_logs_timestamp in schema {schema_name}")
            
            # Create composite index on execution_id and timestamp if not exists
            if 'idx_execution_logs_execution_timestamp' not in existing_indexes:
                db.execute(text(f"""
                    CREATE INDEX idx_execution_logs_execution_timestamp 
                    ON {schema_name}.execution_logs(execution_id, timestamp)
                """))
                logger.info(f"Created composite index idx_execution_logs_execution_timestamp in schema {schema_name}")
            
            db.commit()
            logger.info(f"Successfully added indexes to schema {schema_name}")
            
    except Exception as e:
        logger.error(f"Error adding indexes to schema {schema_name}: {e}")
        raise

def main():
    """Add indexes to all tenant schemas"""
    
    with engine.connect() as conn:
        # Get all tenant schemas
        result = conn.execute(text("""
            SELECT schema_name 
            FROM ioflow.tenants 
            WHERE status = 'active'
        """))
        
        schemas = [row[0] for row in result]
        
    for schema_name in schemas:
        try:
            add_indexes_to_tenant_schema(schema_name)
            print(f"✅ Added indexes to schema: {schema_name}")
        except Exception as e:
            print(f"❌ Failed to add indexes to schema {schema_name}: {e}")
    
    print("\n✅ Migration completed")

if __name__ == "__main__":
    main()
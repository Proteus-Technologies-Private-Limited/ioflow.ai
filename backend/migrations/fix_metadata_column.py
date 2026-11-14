"""
Migration script to rename metadata column to transaction_metadata
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Rename metadata column to transaction_metadata"""
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            # Check if the table exists
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='balance_transactions'
            """))
            
            if result.fetchone():
                logger.info("Checking balance_transactions table columns...")
                
                # Get column info
                columns = conn.execute(text("PRAGMA table_info(balance_transactions)")).fetchall()
                column_names = [col[1] for col in columns]
                
                if 'metadata' in column_names and 'transaction_metadata' not in column_names:
                    logger.info("Renaming metadata column to transaction_metadata...")
                    
                    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
                    conn.execute(text("""
                        ALTER TABLE balance_transactions 
                        RENAME TO balance_transactions_old
                    """))
                    
                    # Create new table with correct column name
                    conn.execute(text("""
                        CREATE TABLE balance_transactions (
                            transaction_id VARCHAR(36) PRIMARY KEY,
                            tenant_id VARCHAR(36) NOT NULL,
                            transaction_type VARCHAR(20) NOT NULL,
                            amount DECIMAL(10, 2) NOT NULL,
                            currency VARCHAR(3) NOT NULL,
                            balance_before DECIMAL(10, 2) NOT NULL,
                            balance_after DECIMAL(10, 2) NOT NULL,
                            reference_id VARCHAR(255),
                            reference_type VARCHAR(50),
                            description TEXT,
                            payment_method VARCHAR(50),
                            payment_reference VARCHAR(255),
                            payment_status VARCHAR(20),
                            transaction_metadata TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(36),
                            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
                        )
                    """))
                    
                    # Copy data from old table
                    conn.execute(text("""
                        INSERT INTO balance_transactions 
                        SELECT 
                            transaction_id, tenant_id, transaction_type, amount, currency,
                            balance_before, balance_after, reference_id, reference_type,
                            description, payment_method, payment_reference, payment_status,
                            metadata, created_at, created_by
                        FROM balance_transactions_old
                    """))
                    
                    # Drop old table
                    conn.execute(text("DROP TABLE balance_transactions_old"))
                    
                    # Recreate indexes
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_balance_transactions_tenant 
                        ON balance_transactions(tenant_id)
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_balance_transactions_created 
                        ON balance_transactions(created_at)
                    """))
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_balance_transactions_type 
                        ON balance_transactions(transaction_type)
                    """))
                    
                    conn.commit()
                    logger.info("Successfully renamed metadata column to transaction_metadata")
                elif 'transaction_metadata' in column_names:
                    logger.info("Column already renamed to transaction_metadata")
                else:
                    logger.info("Table structure is correct")
            else:
                logger.info("balance_transactions table doesn't exist yet")
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    run_migration()
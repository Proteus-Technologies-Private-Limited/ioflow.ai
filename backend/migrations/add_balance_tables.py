"""
Migration script to add balance and transaction tables for prepaid billing system
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
    """Add balance, transaction, and usage limit tables"""
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            # Create tenant_balances table
            logger.info("Creating tenant_balances table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_balances (
                    balance_id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) UNIQUE NOT NULL,
                    current_balance DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    reserved_balance DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    available_balance DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    low_balance_threshold DECIMAL(10, 2) DEFAULT 10.00,
                    critical_balance_threshold DECIMAL(10, 2) DEFAULT 5.00,
                    auto_topup_enabled BOOLEAN DEFAULT FALSE,
                    auto_topup_amount DECIMAL(10, 2),
                    auto_topup_trigger_amount DECIMAL(10, 2),
                    daily_spending_limit DECIMAL(10, 2),
                    monthly_spending_limit DECIMAL(10, 2),
                    total_topped_up DECIMAL(10, 2) DEFAULT 0,
                    total_spent DECIMAL(10, 2) DEFAULT 0,
                    last_topup_date TIMESTAMP,
                    last_alert_sent TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                    CHECK (current_balance >= 0),
                    CHECK (reserved_balance >= 0),
                    CHECK (available_balance >= 0)
                )
            """))
            conn.commit()
            
            # Create balance_transactions table
            logger.info("Creating balance_transactions table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS balance_transactions (
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
            conn.commit()
            
            # Create index on balance_transactions
            logger.info("Creating indexes on balance_transactions...")
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
            
            # Create usage_limits table
            logger.info("Creating usage_limits table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS usage_limits (
                    limit_id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL,
                    app_id VARCHAR(36),
                    limit_type VARCHAR(50) NOT NULL,
                    limit_value DECIMAL(10, 2) NOT NULL,
                    current_usage DECIMAL(10, 2) DEFAULT 0,
                    reset_period VARCHAR(20),
                    last_reset TIMESTAMP,
                    next_reset TIMESTAMP,
                    action_on_exceed VARCHAR(20) DEFAULT 'block',
                    alert_threshold_percent INTEGER DEFAULT 80,
                    is_active BOOLEAN DEFAULT TRUE,
                    times_exceeded INTEGER DEFAULT 0,
                    last_exceeded TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY (app_id) REFERENCES applications(app_id)
                )
            """))
            conn.commit()
            
            # Add balance tracking columns to execution_cost_logs
            logger.info("Adding balance tracking columns to execution_cost_logs...")
            try:
                conn.execute(text("""
                    ALTER TABLE execution_cost_logs 
                    ADD COLUMN balance_deducted DECIMAL(10, 2)
                """))
                conn.commit()
            except Exception as e:
                logger.info(f"Column balance_deducted might already exist: {e}")
            
            try:
                conn.execute(text("""
                    ALTER TABLE execution_cost_logs 
                    ADD COLUMN payment_method VARCHAR(20)
                """))
                conn.commit()
            except Exception as e:
                logger.info(f"Column payment_method might already exist: {e}")
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    run_migration()
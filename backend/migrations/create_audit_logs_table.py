#!/usr/bin/env python3
"""
Migration script to create audit_logs table
"""

import os
import sys
import logging

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_audit_logs_table():
    """Create audit_logs table"""
    engine = create_engine(settings.database_url)
    
    try:
        with engine.connect() as conn:
            logger.info("Creating audit_logs table...")
            
            # Check if we're using SQLite or PostgreSQL
            is_sqlite = settings.database_url.startswith("sqlite")
            
            if is_sqlite:
                # SQLite creation
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        audit_id TEXT PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        user_id TEXT,
                        user_email TEXT,
                        user_role TEXT,
                        tenant_id TEXT,
                        action TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        status TEXT NOT NULL DEFAULT 'success',
                        error_message TEXT
                    )
                """))
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status)"))
                
            else:
                # PostgreSQL creation
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ioflow.audit_logs (
                        audit_id VARCHAR(36) PRIMARY KEY,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        user_id VARCHAR(36),
                        user_email VARCHAR(255),
                        user_role VARCHAR(50),
                        tenant_id VARCHAR(36),
                        action VARCHAR(100) NOT NULL,
                        resource_type VARCHAR(50) NOT NULL,
                        resource_id VARCHAR(255),
                        details TEXT,
                        ip_address VARCHAR(45),
                        user_agent VARCHAR(500),
                        status VARCHAR(20) NOT NULL DEFAULT 'success',
                        error_message TEXT
                    )
                """))
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON ioflow.audit_logs(user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON ioflow.audit_logs(tenant_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON ioflow.audit_logs(timestamp)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON ioflow.audit_logs(status)"))
            
            conn.commit()
            logger.info("audit_logs table created successfully!")
            
    except Exception as e:
        logger.error(f"Failed to create audit_logs table: {str(e)}")
        raise

if __name__ == "__main__":
    create_audit_logs_table()
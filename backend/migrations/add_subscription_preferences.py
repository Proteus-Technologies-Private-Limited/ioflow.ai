"""
Migration script to add tenant subscription preferences table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from core.config import settings
from db.subscription_preferences import TenantSubscriptionPreferences, Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add subscription preferences table"""
    engine = create_engine(settings.database_url)
    
    # Create the table if it doesn't exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if 'tenant_subscription_preferences' not in existing_tables:
        logger.info("Creating tenant_subscription_preferences table...")
        Base.metadata.create_all(engine, tables=[TenantSubscriptionPreferences.__table__])
        logger.info("Table created successfully")
        
        # Create default preferences for existing tenants
        with Session(engine) as session:
            from db.models import Tenant
            
            tenants = session.query(Tenant).all()
            for tenant in tenants:
                # Check if preferences already exist
                existing = session.query(TenantSubscriptionPreferences).filter_by(
                    tenant_id=tenant.tenant_id
                ).first()
                
                if not existing:
                    preferences = TenantSubscriptionPreferences(
                        tenant_id=tenant.tenant_id,
                        billing_preference='prepaid',
                        default_payment_method='razorpay',
                        auto_renewal_enabled=True,
                        invoice_frequency='monthly',
                        notification_preference='email',
                        low_balance_alert_enabled=True,
                        usage_alert_enabled=True,
                        enable_cost_optimization=True
                    )
                    session.add(preferences)
                    logger.info(f"Created default preferences for tenant: {tenant.tenant_name}")
            
            session.commit()
            logger.info("Default preferences created for all existing tenants")
    else:
        logger.info("Table tenant_subscription_preferences already exists")

if __name__ == "__main__":
    run_migration()
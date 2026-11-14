#!/usr/bin/env python3
"""
Migration script to add enhanced billing features
- Adds billing_mode and is_free fields to ApplicationPricing
- Creates ServicePricing table for service-level pricing
- Updates ExecutionCostLog with additional tracking fields
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the enhanced billing migration"""
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # 1. Add new fields to application_pricing table
            logger.info("Adding new fields to application_pricing table...")

            # Check if columns already exist
            existing_columns = [col['name'] for col in inspector.get_columns('application_pricing')]

            if 'is_free' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE application_pricing
                    ADD COLUMN is_free BOOLEAN DEFAULT FALSE
                """))
                logger.info("Added is_free column to application_pricing")

            if 'billing_mode' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE application_pricing
                    ADD COLUMN billing_mode VARCHAR(20) DEFAULT 'PREPAID'
                """))
                logger.info("Added billing_mode column to application_pricing")

            if 'service_pricing_enabled' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE application_pricing
                    ADD COLUMN service_pricing_enabled BOOLEAN DEFAULT FALSE
                """))
                logger.info("Added service_pricing_enabled column to application_pricing")

            # 2. Create service_pricing table if it doesn't exist
            if 'service_pricing' not in inspector.get_table_names():
                logger.info("Creating service_pricing table...")

                if settings.database_url.startswith("sqlite"):
                    conn.execute(text("""
                        CREATE TABLE service_pricing (
                            pricing_id VARCHAR(36) PRIMARY KEY,
                            service_id VARCHAR(36) NOT NULL,
                            cost_per_request DECIMAL(10,4) DEFAULT 0,
                            cost_per_kb DECIMAL(10,6) DEFAULT 0,
                            cost_per_token DECIMAL(10,6) DEFAULT 0,
                            is_free BOOLEAN DEFAULT FALSE,
                            override_app_pricing BOOLEAN DEFAULT TRUE,
                            currency VARCHAR(3) DEFAULT 'USD',
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (service_id) REFERENCES application_services(service_id)
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS service_pricing (
                            pricing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            service_id UUID NOT NULL REFERENCES application_services(service_id),
                            cost_per_request DECIMAL(10,4) DEFAULT 0,
                            cost_per_kb DECIMAL(10,6) DEFAULT 0,
                            cost_per_token DECIMAL(10,6) DEFAULT 0,
                            is_free BOOLEAN DEFAULT FALSE,
                            override_app_pricing BOOLEAN DEFAULT TRUE,
                            currency VARCHAR(3) DEFAULT 'USD',
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))

                # Create index on service_id
                conn.execute(text("""
                    CREATE INDEX idx_service_pricing_service_id
                    ON service_pricing(service_id)
                """))

                logger.info("Created service_pricing table")

            # 3. Add new fields to execution_cost_logs table
            logger.info("Adding new fields to execution_cost_logs table...")

            existing_cost_columns = [col['name'] for col in inspector.get_columns('execution_cost_logs')]

            if 'billing_mode' not in existing_cost_columns:
                conn.execute(text("""
                    ALTER TABLE execution_cost_logs
                    ADD COLUMN billing_mode VARCHAR(20) DEFAULT 'PREPAID'
                """))
                logger.info("Added billing_mode column to execution_cost_logs")

            if 'service_breakdown' not in existing_cost_columns:
                if settings.database_url.startswith("sqlite"):
                    conn.execute(text("""
                        ALTER TABLE execution_cost_logs
                        ADD COLUMN service_breakdown TEXT
                    """))
                else:
                    conn.execute(text("""
                        ALTER TABLE execution_cost_logs
                        ADD COLUMN service_breakdown JSONB
                    """))
                logger.info("Added service_breakdown column to execution_cost_logs")

            if 'error_reason' not in existing_cost_columns:
                conn.execute(text("""
                    ALTER TABLE execution_cost_logs
                    ADD COLUMN error_reason VARCHAR(255)
                """))
                logger.info("Added error_reason column to execution_cost_logs")

            if 'was_free' not in existing_cost_columns:
                conn.execute(text("""
                    ALTER TABLE execution_cost_logs
                    ADD COLUMN was_free BOOLEAN DEFAULT FALSE
                """))
                logger.info("Added was_free column to execution_cost_logs")

            # 4. Add service-specific cost fields to application_services table
            logger.info("Adding pricing fields to application_services table...")

            existing_service_columns = [col['name'] for col in inspector.get_columns('application_services')]

            if 'has_custom_pricing' not in existing_service_columns:
                conn.execute(text("""
                    ALTER TABLE application_services
                    ADD COLUMN has_custom_pricing BOOLEAN DEFAULT FALSE
                """))
                logger.info("Added has_custom_pricing column to application_services")

            if 'estimated_cost_per_call' not in existing_service_columns:
                conn.execute(text("""
                    ALTER TABLE application_services
                    ADD COLUMN estimated_cost_per_call DECIMAL(10,4)
                """))
                logger.info("Added estimated_cost_per_call column to application_services")

            # 5. Update existing pricing records to set billing_mode based on pricing_model
            logger.info("Updating existing pricing records...")
            conn.execute(text("""
                UPDATE application_pricing
                SET billing_mode = CASE
                    WHEN pricing_model = 'subscription' THEN 'SUBSCRIPTION'
                    WHEN pricing_model = 'pay_per_use' THEN 'PREPAID'
                    ELSE 'PREPAID'
                END
                WHERE billing_mode IS NULL OR billing_mode = 'PREPAID'
            """))

            # Commit transaction
            trans.commit()
            logger.info("Migration completed successfully!")

        except Exception as e:
            trans.rollback()
            logger.error(f"Migration failed: {str(e)}")
            raise

        # Create triggers for updated_at if PostgreSQL
        if not settings.database_url.startswith("sqlite"):
            try:
                # Create update trigger for service_pricing
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                """))

                conn.execute(text("""
                    DROP TRIGGER IF EXISTS update_service_pricing_updated_at ON service_pricing;
                    CREATE TRIGGER update_service_pricing_updated_at
                    BEFORE UPDATE ON service_pricing
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                """))

                logger.info("Created update triggers for service_pricing")
            except Exception as e:
                logger.warning(f"Could not create triggers (may already exist): {str(e)}")

def rollback_migration():
    """Rollback the enhanced billing migration"""
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        trans = conn.begin()

        try:
            logger.info("Rolling back enhanced billing migration...")

            # Remove columns from application_pricing
            conn.execute(text("ALTER TABLE application_pricing DROP COLUMN IF EXISTS is_free"))
            conn.execute(text("ALTER TABLE application_pricing DROP COLUMN IF EXISTS billing_mode"))
            conn.execute(text("ALTER TABLE application_pricing DROP COLUMN IF EXISTS service_pricing_enabled"))

            # Remove columns from execution_cost_logs
            conn.execute(text("ALTER TABLE execution_cost_logs DROP COLUMN IF EXISTS billing_mode"))
            conn.execute(text("ALTER TABLE execution_cost_logs DROP COLUMN IF EXISTS service_breakdown"))
            conn.execute(text("ALTER TABLE execution_cost_logs DROP COLUMN IF EXISTS error_reason"))
            conn.execute(text("ALTER TABLE execution_cost_logs DROP COLUMN IF EXISTS was_free"))

            # Remove columns from application_services
            conn.execute(text("ALTER TABLE application_services DROP COLUMN IF EXISTS has_custom_pricing"))
            conn.execute(text("ALTER TABLE application_services DROP COLUMN IF EXISTS estimated_cost_per_call"))

            # Drop service_pricing table
            conn.execute(text("DROP TABLE IF EXISTS service_pricing"))

            trans.commit()
            logger.info("Rollback completed successfully!")

        except Exception as e:
            trans.rollback()
            logger.error(f"Rollback failed: {str(e)}")
            raise

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced billing migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()
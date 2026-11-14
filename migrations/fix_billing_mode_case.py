#!/usr/bin/env python3
"""
Migration to fix billing_mode case from uppercase to lowercase
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from sqlalchemy import create_engine, text
from backend.core.config import settings

def fix_billing_mode_case():
    """Convert all billing_mode values from uppercase to lowercase"""

    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as conn:
            # Fix ApplicationPricing table
            try:
                result = conn.execute(text("""
                    UPDATE application_pricing
                    SET billing_mode = LOWER(billing_mode)
                    WHERE billing_mode IN ('FREE', 'PREPAID', 'POSTPAID', 'SUBSCRIPTION')
                """))
                conn.commit()
                print(f"✓ Updated {result.rowcount} rows in application_pricing table")
            except Exception as e:
                print(f"⚠ Could not update application_pricing: {e}")

            # Fix ExecutionCostLog table
            try:
                result = conn.execute(text("""
                    UPDATE execution_cost_log
                    SET billing_mode = LOWER(billing_mode)
                    WHERE billing_mode IN ('FREE', 'PREPAID', 'POSTPAID', 'SUBSCRIPTION')
                """))
                conn.commit()
                print(f"✓ Updated {result.rowcount} rows in execution_cost_log table")
            except Exception as e:
                print(f"⚠ Could not update execution_cost_log: {e}")

            # Verify the changes
            result = conn.execute(text("""
                SELECT DISTINCT billing_mode
                FROM application_pricing
                WHERE billing_mode IS NOT NULL
            """))
            modes = [row[0] for row in result]
            print(f"\nDistinct billing modes in database: {modes}")

            print("\n✓ Migration completed successfully!")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_billing_mode_case()
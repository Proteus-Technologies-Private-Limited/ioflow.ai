"""
Migration: add twasta_tenant_id column to tenants table.

Maps an IOFlow tenant to the twasta.ai tenant it was auto-provisioned from
by the "Authenticate with Twasta" SSO flow (POST /api/v1/auth/twasta-exchange).
Unique so one twasta tenant maps to exactly one IOFlow tenant.

Run:  cd IOFlow && python migrations/add_twasta_tenant_id.py
"""
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text, inspect
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    engine = create_engine(settings.database_url)
    is_sqlite = settings.database_url.startswith("sqlite")
    schema = None if is_sqlite else "ioflow"
    qualified = "tenants" if is_sqlite else "ioflow.tenants"

    inspector = inspect(engine)
    try:
        columns = [c["name"] for c in inspector.get_columns("tenants", schema=schema)]
    except Exception as exc:
        logger.error("Could not inspect tenants table: %s", exc)
        sys.exit(1)

    if "twasta_tenant_id" in columns:
        logger.info("twasta_tenant_id already exists on %s — nothing to do", qualified)
        return

    with engine.begin() as conn:
        logger.info("Adding twasta_tenant_id to %s ...", qualified)
        conn.execute(text(f"ALTER TABLE {qualified} ADD COLUMN twasta_tenant_id VARCHAR(36)"))
        # SQLite can't add a UNIQUE column via ALTER TABLE; use a unique index on both.
        conn.execute(text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_twasta_tenant_id "
            f"ON {qualified} (twasta_tenant_id)"
        ))
    logger.info("Migration complete.")


if __name__ == "__main__":
    run_migration()

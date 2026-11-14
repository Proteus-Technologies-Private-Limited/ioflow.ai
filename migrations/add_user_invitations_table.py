"""
Migration script to add user_invitations table for the user invitation system.
This allows admins to invite users to their organization/tenant.
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


def get_schema_prefix():
    """Get the schema prefix based on database type"""
    if settings.database_url.startswith("sqlite"):
        return ""
    else:
        return "ioflow."


def table_exists(engine, table_name, schema=None):
    """Check if a table exists"""
    inspector = inspect(engine)
    if schema:
        return table_name in inspector.get_table_names(schema=schema)
    return table_name in inspector.get_table_names()


def run_migration():
    """Create user_invitations table"""
    engine = create_engine(settings.database_url)
    is_sqlite = settings.database_url.startswith("sqlite")
    schema_prefix = get_schema_prefix()

    # Check if using PostgreSQL
    if is_sqlite:
        # SQLite version
        create_user_invitations_sql = """
        CREATE TABLE IF NOT EXISTS user_invitations (
            invitation_id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL,
            email VARCHAR(255) NOT NULL,
            invited_by VARCHAR(36) NOT NULL,
            invitation_token VARCHAR(255) UNIQUE NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'FLOW_DESIGNER',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            accepted_at TIMESTAMP,
            message TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
            FOREIGN KEY (invited_by) REFERENCES users(user_id)
        );
        """

        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_user_invitations_tenant_id ON user_invitations(tenant_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_invitations_email ON user_invitations(email);",
            "CREATE INDEX IF NOT EXISTS idx_user_invitations_token ON user_invitations(invitation_token);",
            "CREATE INDEX IF NOT EXISTS idx_user_invitations_status ON user_invitations(status);",
            "CREATE INDEX IF NOT EXISTS idx_user_invitations_expires_at ON user_invitations(expires_at);"
        ]
    else:
        # PostgreSQL version with schema
        create_user_invitations_sql = f"""
        CREATE TABLE IF NOT EXISTS {schema_prefix}user_invitations (
            invitation_id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL REFERENCES {schema_prefix}tenants(tenant_id),
            email VARCHAR(255) NOT NULL,
            invited_by VARCHAR(36) NOT NULL REFERENCES {schema_prefix}users(user_id),
            invitation_token VARCHAR(255) UNIQUE NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'FLOW_DESIGNER',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            accepted_at TIMESTAMP,
            message TEXT
        );
        """

        indexes_sql = [
            f"CREATE INDEX IF NOT EXISTS idx_user_invitations_tenant_id ON {schema_prefix}user_invitations(tenant_id);",
            f"CREATE INDEX IF NOT EXISTS idx_user_invitations_email ON {schema_prefix}user_invitations(email);",
            f"CREATE INDEX IF NOT EXISTS idx_user_invitations_token ON {schema_prefix}user_invitations(invitation_token);",
            f"CREATE INDEX IF NOT EXISTS idx_user_invitations_status ON {schema_prefix}user_invitations(status);",
            f"CREATE INDEX IF NOT EXISTS idx_user_invitations_expires_at ON {schema_prefix}user_invitations(expires_at);"
        ]

    try:
        with engine.connect() as conn:
            # Check if table already exists
            schema = 'ioflow' if not is_sqlite else None
            if table_exists(engine, 'user_invitations', schema):
                logger.info("Table user_invitations already exists. Skipping creation.")
                return

            # Create user_invitations table
            logger.info("Creating user_invitations table...")
            conn.execute(text(create_user_invitations_sql))
            conn.commit()
            logger.info("  Table user_invitations created successfully")

            # Create indexes
            logger.info("Creating indexes for user_invitations...")
            for idx_sql in indexes_sql:
                try:
                    conn.execute(text(idx_sql))
                    conn.commit()
                except Exception as e:
                    # Index might already exist
                    logger.warning(f"  Index creation warning: {e}")
            logger.info("  Indexes created successfully")

        logger.info("")
        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("Table created:")
        logger.info("  - user_invitations: Tracks pending user invitations to join organizations")
        logger.info("")
        logger.info("Features enabled:")
        logger.info("  - Admins can invite users via email")
        logger.info("  - Invitations expire after 7 days by default")
        logger.info("  - Invited users can set their name and password when accepting")
        logger.info("  - Role is pre-assigned by the inviter")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()

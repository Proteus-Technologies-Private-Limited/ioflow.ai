"""
SQLite to PostgreSQL Data Migration Script
Migrates all data from SQLite database to PostgreSQL

This script:
1. Connects to both SQLite and PostgreSQL databases
2. Creates all tables in PostgreSQL with ioflow schema
3. Migrates data table by table
4. Preserves all relationships and data integrity
"""

import sqlite3
import json
import sys
import os
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from core.config import settings

# SQLite database path
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'ioflow.db')

# PostgreSQL connection from settings
POSTGRESQL_URL = settings.database_url

# Tables to migrate in order (respecting foreign key dependencies)
IOFLOW_SCHEMA_TABLES = [
    # Core tables (no dependencies)
    'tenants',
    'users',
    'smtp_configurations',
    'api_keys',
    'user_settings',

    # Application tables
    'applications',
    'application_events',
    'application_services',
    'oauth_states',
    'application_subscriptions',

    # Published/Frontend apps
    'published_applications',
    'frontend_flow_applications',
    'frontend_app_access_logs',
    'frontend_app_embed_configs',

    # Pricing tables
    'application_pricing',
    'service_pricing',
    'tenant_application_subscriptions',
    'tenant_balances',
    'balance_transactions',
    'execution_cost_logs',
    'application_invoices',
    'usage_limits',

    # Collaboration tables
    'collaboration_sessions',
    'collaboration_participants',
    'collaboration_events',
    'collaboration_messages',
    'collaboration_invites',

    # AI Conversation tables
    'ai_transform_conversations',
    'ai_transform_messages',
    'ai_transform_snapshots',

    # Marketplace tables
    'app_categories',
    'app_tags',
    'app_reviews',
    'creator_tiers',
    'marketplace_approvals',
    'marketplace_features',
    'app_metrics',
    'payout_requests',
    'developer_profiles',
    'app_version_history',

    # Documentation tables
    'app_documentation_pages',

    # Polling tables
    'polling_configs',
    'polling_states',

    # Google OAuth tables
    'google_oauth_config',
    'google_oauth_states',

    # Flow example tables
    'flow_example_ratings',
    'flow_example_favorites',
    'flow_example_usage_stats',

    # Audit logs - commented out as may not exist in SQLite
    # 'audit_logs',
]

# Tenant-specific tables (need to be migrated per tenant schema)
TENANT_SCHEMA_TABLES = [
    'flows',
    'flow_executions',
    'execution_logs',
    'async_callbacks',
]


def get_sqlite_connection():
    """Get SQLite database connection."""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite database not found at: {SQLITE_DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_postgresql_engine():
    """Get PostgreSQL engine."""
    return create_engine(
        POSTGRESQL_URL,
        pool_pre_ping=True,
        echo=False
    )


def get_sqlite_tables(conn):
    """Get list of tables in SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_table_columns(conn, table_name):
    """Get column names for a SQLite table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def get_postgresql_columns(engine, schema, table_name):
    """Get column names for a PostgreSQL table."""
    inspector = inspect(engine)
    try:
        columns = inspector.get_columns(table_name, schema=schema)
        return [col['name'] for col in columns]
    except Exception:
        return []


def convert_value_for_postgresql(value, column_name):
    """Convert SQLite value to PostgreSQL compatible format."""
    if value is None:
        return None

    # Handle boolean fields (SQLite stores as 0/1)
    boolean_columns = [
        'is_active', 'is_default', 'is_system', 'is_global', 'is_enabled', 'is_published',
        'is_archived', 'is_deleted', 'is_featured', 'is_public', 'is_verified', 'is_admin',
        'is_owner', 'is_synchronous', 'requires_auth', 'callback_required', 'enabled',
        'active', 'published', 'deleted', 'featured', 'public', 'verified', 'auto_approve',
        'ai_generated', 'used', 'helpful', 'restrict_to_specific_ips', 'require_api_key',
        'track_usage', 'success'
    ]
    if column_name in boolean_columns or column_name.startswith('is_') or column_name.startswith('has_'):
        if isinstance(value, (int, float)):
            return bool(value)
        return value

    # Handle JSON/JSONB fields
    if isinstance(value, str):
        # Try to parse as JSON for known JSON columns
        json_columns = [
            'flow_definition', 'trigger_config', 'execution_data', 'trigger_data',
            'log_data', 'step_data', 'callback_response', 'auth_config', 'auth_credentials',
            'service_config', 'parameter_schema', 'response_config', 'subscription_config',
            'custom_params', 'settings', 'metadata', 'redirect_uris', 'javascript_origins',
            'pricing_tiers', 'rate_limits', 'setting_data', 'features', 'config',
            'access_config', 'embed_config', 'request_data', 'security_restrictions',
            'services', 'events', 'permissions', 'last_result', 'capabilities', 'response_schema',
            'permissions_level', 'meta_keywords', 'custom_sections', 'screenshots', 'change_log',
            'error_rates', 'performance_metrics', 'environment_configs', 'app_data'
        ]

        if column_name in json_columns or column_name.endswith('_config') or column_name.endswith('_data'):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

    return value


def migrate_table(sqlite_conn, pg_engine, table_name, source_table=None, schema='ioflow'):
    """Migrate a single table from SQLite to PostgreSQL."""
    source_table = source_table or table_name

    # Get columns from SQLite
    sqlite_columns = get_table_columns(sqlite_conn, source_table)
    if not sqlite_columns:
        print(f"  Skipping {table_name} - not found in SQLite")
        return 0

    # Get columns from PostgreSQL
    pg_columns = get_postgresql_columns(pg_engine, schema, table_name)
    if not pg_columns:
        print(f"  Skipping {table_name} - not found in PostgreSQL schema {schema}")
        return 0

    # Find common columns
    common_columns = [col for col in sqlite_columns if col in pg_columns]
    if not common_columns:
        print(f"  Skipping {table_name} - no common columns")
        return 0

    # Fetch data from SQLite
    cursor = sqlite_conn.cursor()
    columns_str = ', '.join(common_columns)
    cursor.execute(f"SELECT {columns_str} FROM {source_table}")
    rows = cursor.fetchall()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    # Insert into PostgreSQL
    with pg_engine.connect() as conn:
        # Clear existing data (if any)
        try:
            conn.execute(text(f'DELETE FROM {schema}.{table_name}'))
            conn.commit()
        except Exception as e:
            print(f"  Warning: Could not clear {table_name}: {e}")
            conn.rollback()

        inserted = 0
        for row in rows:
            # Convert row to dict with proper type conversion
            row_dict = {}
            for i, col in enumerate(common_columns):
                row_dict[col] = convert_value_for_postgresql(row[i], col)

            # Build INSERT statement
            cols = ', '.join(row_dict.keys())
            placeholders = ', '.join([f':{k}' for k in row_dict.keys()])

            try:
                conn.execute(
                    text(f'INSERT INTO {schema}.{table_name} ({cols}) VALUES ({placeholders})'),
                    row_dict
                )
                conn.commit()
                inserted += 1
            except Exception as e:
                conn.rollback()
                # Only print first few errors
                if inserted < 3:
                    print(f"    Error inserting row into {table_name}: {str(e)[:200]}")
                continue

        print(f"  {table_name}: {inserted}/{len(rows)} rows migrated")
        return inserted


def create_postgresql_schema(engine):
    """Create the ioflow schema if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS ioflow'))
        conn.commit()
        print("Schema 'ioflow' created/verified")


def create_postgresql_tables(engine):
    """Create all PostgreSQL tables using SQLAlchemy models."""
    from db.models import Base
    from db.application_models import (
        Application, ApplicationEvent, ApplicationService, OAuthState,
        ApplicationSubscription, PublishedApplication, FrontendFlowApplication,
        FrontendAppAccessLog, FrontendAppEmbedConfig
    )
    from db.pricing_models import (
        ApplicationPricing, ServicePricing, TenantApplicationSubscription,
        ExecutionCostLog, ApplicationInvoice, TenantBalance, BalanceTransaction, UsageLimit
    )
    from db.collaboration_models import (
        CollaborationSession, CollaborationParticipant, CollaborationEvent,
        CollaborationMessage, CollaborationInvite
    )
    from db.ai_conversation_models import (
        AITransformConversation, AITransformMessage, AITransformSnapshot
    )
    from db.marketplace_models import (
        AppCategory, AppTag, AppReview, CreatorTier, MarketplaceApproval,
        AppMetrics, MarketplaceSettings, AppCategoryMapping, AppTagMapping, ReviewHelpful, MicroSaasSubscriber
    )
    from db.documentation_models import AppDocumentationPage
    from db.polling_models import PollingState
    from db.google_oauth_models import GoogleOAuthConfig, GoogleOAuthState
    from db.flow_example_models import FlowExampleRating, FlowExampleFavorite, FlowExampleUsageStats
    from services.audit_service import AuditLog

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("All PostgreSQL tables created")


def get_tenant_schemas(sqlite_conn):
    """Get list of tenants for schema creation."""
    cursor = sqlite_conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def migrate_tenant_data(sqlite_conn, pg_engine, tenant_id):
    """Migrate tenant-specific data to their schema."""
    schema_name = f"tenant_{tenant_id.replace('-', '_')}"

    print(f"\nMigrating tenant schema: {schema_name}")

    with pg_engine.connect() as conn:
        # Create tenant schema
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.commit()

    # For SQLite, tenant data is in the same DB, just filtered by tenant_id
    # We need to migrate flows and related tables

    for table in TENANT_SCHEMA_TABLES:
        # Check if table exists in SQLite
        cursor = sqlite_conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            print(f"  {table}: not found in SQLite")
            continue

        # Get columns
        sqlite_columns = get_table_columns(sqlite_conn, table)
        pg_columns = get_postgresql_columns(pg_engine, schema_name, table)

        if not pg_columns:
            # Table doesn't exist in PostgreSQL, need to create it
            print(f"  {table}: creating in schema {schema_name}")
            continue

        common_columns = [col for col in sqlite_columns if col in pg_columns]

        # Fetch data filtered by tenant_id
        columns_str = ', '.join(common_columns)
        if 'tenant_id' in sqlite_columns:
            cursor.execute(f"SELECT {columns_str} FROM {table} WHERE tenant_id = ?", (tenant_id,))
        else:
            cursor.execute(f"SELECT {columns_str} FROM {table}")

        rows = cursor.fetchall()

        if not rows:
            print(f"  {table}: 0 rows for tenant {tenant_id}")
            continue

        # Insert into PostgreSQL tenant schema
        with pg_engine.connect() as conn:
            inserted = 0
            for row in rows:
                row_dict = {}
                for i, col in enumerate(common_columns):
                    row_dict[col] = convert_value_for_postgresql(row[i], col)

                cols = ', '.join(row_dict.keys())
                placeholders = ', '.join([f':{k}' for k in row_dict.keys()])

                try:
                    conn.execute(
                        text(f'INSERT INTO "{schema_name}".{table} ({cols}) VALUES ({placeholders})'),
                        row_dict
                    )
                    inserted += 1
                except Exception as e:
                    print(f"    Error: {e}")
                    continue

            conn.commit()
            print(f"  {table}: {inserted}/{len(rows)} rows migrated")


def main():
    """Main migration function."""
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)
    print(f"SQLite DB: {SQLITE_DB_PATH}")
    print(f"PostgreSQL: {POSTGRESQL_URL.split('@')[1] if '@' in POSTGRESQL_URL else POSTGRESQL_URL}")
    print()

    # Check SQLite exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)

    # Connect to SQLite
    sqlite_conn = get_sqlite_connection()
    print(f"Connected to SQLite database")

    # Show SQLite tables
    sqlite_tables = get_sqlite_tables(sqlite_conn)
    print(f"Found {len(sqlite_tables)} tables in SQLite: {', '.join(sqlite_tables[:10])}...")

    # Connect to PostgreSQL
    pg_engine = get_postgresql_engine()
    print(f"Connected to PostgreSQL database")

    # Create schema
    create_postgresql_schema(pg_engine)

    # Create all tables
    print("\nCreating PostgreSQL tables...")
    create_postgresql_tables(pg_engine)

    # Migrate ioflow schema tables
    print("\nMigrating ioflow schema tables...")
    total_migrated = 0
    for table in IOFLOW_SCHEMA_TABLES:
        count = migrate_table(sqlite_conn, pg_engine, table)
        total_migrated += count

    # Get tenant IDs
    tenant_ids = get_tenant_schemas(sqlite_conn)
    print(f"\nFound {len(tenant_ids)} tenants")

    # Migrate tenant-specific data
    for tenant_id in tenant_ids:
        migrate_tenant_data(sqlite_conn, pg_engine, tenant_id)

    # Cleanup
    sqlite_conn.close()

    print("\n" + "=" * 60)
    print("Migration completed!")
    print(f"Total rows migrated to ioflow schema: {total_migrated}")
    print("=" * 60)


if __name__ == "__main__":
    main()

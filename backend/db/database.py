"""
Database Connection and Session Management - PostgreSQL and SQLite
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, StaticPool
from contextlib import contextmanager
from typing import Generator
import importlib
import logging
import threading

from core.config import settings

logger = logging.getLogger(__name__)

# Use settings for DATABASE_URL
DATABASE_URL = settings.database_url

# Check if using SQLite
is_sqlite = DATABASE_URL.startswith("sqlite")

# Configure engine based on database type
if is_sqlite:
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    # Import SQLite Base
    from .models_sqlite import Base
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600
    )
    # Import PostgreSQL Base
    from .models import Base

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=True,
    bind=engine,
    expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database operations outside of FastAPI"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_schema(schema_name: str):
    """Create a new schema for a tenant (PostgreSQL only)"""
    if is_sqlite:
        # SQLite doesn't support schemas - tables are created directly
        return

    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.commit()


def create_tenant_tables(schema_name: str):
    """Create tables in a tenant schema"""
    if is_sqlite:
        # SQLite: tables are created without schema prefix
        from .models_sqlite import Flow, FlowExecution, ExecutionLog, AsyncCallback
        Base.metadata.create_all(bind=engine, tables=[
            Flow.__table__,
            FlowExecution.__table__,
            ExecutionLog.__table__,
            AsyncCallback.__table__
        ])
        return

    # PostgreSQL: create tables in tenant schema.
    #
    # IMPORTANT: do NOT mutate `model.__table__.schema` to point at the tenant
    # schema. Those Table objects are process-global and shared by every
    # request; repointing them leaks for the entire process lifetime and is
    # never restored. The failure mode is subtle and severe: existing reads
    # keep working (their compiled SQL is cached against 'ioflow'), but any
    # freshly-compiled write (flow save / activate / deactivate) then targets
    # the empty tenant `flows` table, silently matches 0 rows, and raises
    # sqlalchemy StaleDataError -> HTTP 500 on every flow update until the
    # server is restarted. Instead, translate the 'ioflow' schema to the
    # tenant schema at execution time via schema_translate_map, which affects
    # only this engine's DDL and leaves the shared models untouched.
    from .models import Flow, FlowExecution, ExecutionLog, AsyncCallback

    tenant_engine = create_engine(
        DATABASE_URL,
        connect_args={"options": f"-csearch_path={schema_name}"},
        poolclass=NullPool
    ).execution_options(schema_translate_map={"ioflow": schema_name})

    try:
        Base.metadata.create_all(bind=tenant_engine, tables=[
            Flow.__table__,
            FlowExecution.__table__,
            ExecutionLog.__table__,
            AsyncCallback.__table__
        ])
    finally:
        tenant_engine.dispose()


# One pooled engine per tenant schema, created lazily and reused for the
# process lifetime. The previous engine-per-call NullPool approach opened a
# fresh TCP connection for every session and exhausted PostgreSQL
# max_connections under load (MQTT bursts open dozens of sessions/second).
_tenant_sessionmakers: dict = {}
_tenant_engines: dict = {}
_tenant_registry_lock = threading.Lock()


def _get_tenant_sessionmaker(schema_name: str):
    maker = _tenant_sessionmakers.get(schema_name)
    if maker is None:
        with _tenant_registry_lock:
            maker = _tenant_sessionmakers.get(schema_name)
            if maker is None:
                tenant_engine = create_engine(
                    DATABASE_URL,
                    connect_args={"options": f"-csearch_path={schema_name},ioflow"},
                    pool_pre_ping=True,
                    pool_size=settings.tenant_db_pool_size,
                    max_overflow=settings.tenant_db_max_overflow,
                    pool_recycle=1800
                )
                # expire_on_commit=False matches SessionLocal (the SQLite
                # path): services read ORM attributes after commit/close,
                # which would otherwise raise DetachedInstanceError
                maker = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False,
                    bind=tenant_engine
                )
                _tenant_engines[schema_name] = tenant_engine
                _tenant_sessionmakers[schema_name] = maker
    return maker


@contextmanager
def get_tenant_db(schema_name: str) -> Generator[Session, None, None]:
    """Get a database session for a specific tenant schema"""
    if is_sqlite:
        # SQLite: just use the main session
        db = SessionLocal()
        # Consumed by cache-invalidation commit hooks (services/flow_cache.py)
        db.info['schema_name'] = schema_name
        try:
            yield db
        finally:
            db.close()
        return

    # PostgreSQL: pooled session bound to the tenant schema's search_path
    db = _get_tenant_sessionmaker(schema_name)()
    # Consumed by cache-invalidation commit hooks (services/flow_cache.py)
    db.info['schema_name'] = schema_name
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database"""
    if is_sqlite:
        # SQLite: create all tables without schema
        from .models_sqlite import User, Tenant, APIKey, Flow, FlowExecution, ExecutionLog, AsyncCallback, UserSettings, ChatSession, NodeSessionState, SMTPConfiguration
        from .application_models import (
            ApplicationSQLite, ApplicationSubscriptionSQLite, OAuthStateSQLite,
            ApplicationEventSQLite, ApplicationServiceSQLite, PublishedApplicationSQLite,
            FrontendFlowApplicationSQLite, AppDocumentationPageSQLite
        )

        Base.metadata.create_all(bind=engine)
        return

    # PostgreSQL: create ioflow schema first
    with engine.connect() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS ioflow'))
        conn.commit()

    # Create all tables
    from .models import User, Tenant, APIKey
    from .application_models import Application, ApplicationSubscription, OAuthState, ApplicationEvent, ApplicationService

    Base.metadata.create_all(bind=engine, tables=[
        User.__table__,
        Tenant.__table__,
        Application.__table__,
        ApplicationSubscription.__table__,
        OAuthState.__table__,
        APIKey.__table__
    ])

    # Then every other shared table, so a brand-new database needs no manual
    # bootstrap. Never fatal: an existing installation keeps starting exactly
    # as before even if one of these cannot be created.
    try:
        _create_remaining_shared_tables()
    except Exception as e:
        logger.error(f"Could not create the remaining shared tables: {e}", exc_info=True)


# Modules whose models register tables on Base in the shared "ioflow" schema.
_SHARED_MODEL_MODULES = [
    'db.models', 'db.application_models', 'db.ai_conversation_models',
    'db.collaboration_models', 'db.documentation_models', 'db.flow_example_models',
    'db.google_oauth_models', 'db.marketplace_models', 'db.polling_models',
    'db.pricing_models', 'db.user_settings_models',
    'services.db_message_queue', 'services.audit_service',
]


def _create_remaining_shared_tables():
    """Create any shared table that does not exist yet (PostgreSQL only).

    Idempotent: create_all checks each table first and only creates the
    missing ones, so on an established database this changes nothing.
    """
    for module_name in _SHARED_MODEL_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Skipping tables of {module_name}: {e}")

    Base.metadata.create_all(bind=engine)

    # Lock table used when Redis is unavailable; it has no ORM model.
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS ioflow.distributed_locks ("
            "lock_key TEXT PRIMARY KEY, owner_id TEXT NOT NULL, "
            "acquired_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL, metadata TEXT)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_distributed_locks_expires "
            "ON ioflow.distributed_locks(expires_at)"
        ))
        conn.commit()

"""
Migration script to add Human in the Loop (HITL) tables:
- hitl_roles: Tenant-scoped custom roles for HITL task assignment
- hitl_user_roles: Many-to-many mapping between users and HITL roles
- hitl_tasks: Task records created when human_in_loop nodes execute
- hitl_task_assignments: Tracks who is assigned to a HITL task
"""
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Create HITL tables"""
    engine = create_engine(settings.database_url)
    is_sqlite = settings.database_url.startswith("sqlite")

    if is_sqlite:
        _run_sqlite_migration(engine)
    else:
        _run_postgresql_migration(engine)


def _run_sqlite_migration(engine):
    """Create HITL tables for SQLite"""

    create_hitl_roles_sql = """
    CREATE TABLE IF NOT EXISTS hitl_roles (
        role_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        role_name VARCHAR(100) NOT NULL,
        role_description TEXT,
        created_by VARCHAR(36) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
        CONSTRAINT unique_tenant_hitl_role UNIQUE (tenant_id, role_name)
    );
    """

    create_hitl_user_roles_sql = """
    CREATE TABLE IF NOT EXISTS hitl_user_roles (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        hitl_role_id VARCHAR(36) NOT NULL,
        tenant_id VARCHAR(36) NOT NULL,
        assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        assigned_by VARCHAR(36) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (hitl_role_id) REFERENCES hitl_roles(role_id),
        CONSTRAINT unique_user_hitl_role UNIQUE (user_id, hitl_role_id)
    );
    """

    create_hitl_tasks_sql = """
    CREATE TABLE IF NOT EXISTS hitl_tasks (
        task_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        execution_id VARCHAR(36) NOT NULL,
        flow_id VARCHAR(36) NOT NULL,
        node_id VARCHAR(100) NOT NULL,
        task_token VARCHAR(255) NOT NULL UNIQUE,
        task_type VARCHAR(20) NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
        input_data TEXT,
        display_config TEXT,
        response_data TEXT,
        response_action VARCHAR(20),
        completed_by VARCHAR(36),
        completed_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        timeout_at TIMESTAMP,
        escalation_config TEXT,
        escalation_level INTEGER NOT NULL DEFAULT 0,
        execution_snapshot TEXT,
        metadata TEXT,
        FOREIGN KEY (execution_id) REFERENCES flow_executions(execution_id)
    );
    """

    create_hitl_task_assignments_sql = """
    CREATE TABLE IF NOT EXISTS hitl_task_assignments (
        id VARCHAR(36) PRIMARY KEY,
        task_id VARCHAR(36) NOT NULL,
        assignee_type VARCHAR(20) NOT NULL,
        assignee_id VARCHAR(36) NOT NULL,
        tenant_id VARCHAR(36) NOT NULL,
        notified_at TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES hitl_tasks(task_id)
    );
    """

    indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_hitl_roles_tenant ON hitl_roles(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_user_roles_user ON hitl_user_roles(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_user_roles_role ON hitl_user_roles(hitl_role_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_tenant_status ON hitl_tasks(tenant_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_execution ON hitl_tasks(execution_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_token ON hitl_tasks(task_token);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_assignments_task ON hitl_task_assignments(task_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_assignments_assignee ON hitl_task_assignments(assignee_type, assignee_id, tenant_id);",
    ]

    with engine.connect() as conn:
        logger.info("Creating HITL tables for SQLite...")
        conn.execute(text(create_hitl_roles_sql))
        conn.execute(text(create_hitl_user_roles_sql))
        conn.execute(text(create_hitl_tasks_sql))
        conn.execute(text(create_hitl_task_assignments_sql))

        for idx_sql in indexes_sql:
            conn.execute(text(idx_sql))

        conn.commit()
        logger.info("HITL tables created successfully for SQLite.")


def _run_postgresql_migration(engine):
    """Create HITL tables for PostgreSQL"""

    create_hitl_roles_sql = """
    CREATE TABLE IF NOT EXISTS ioflow.hitl_roles (
        role_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL REFERENCES ioflow.tenants(tenant_id),
        role_name VARCHAR(100) NOT NULL,
        role_description TEXT,
        created_by VARCHAR(36) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        CONSTRAINT unique_tenant_hitl_role UNIQUE (tenant_id, role_name)
    );
    """

    create_hitl_user_roles_sql = """
    CREATE TABLE IF NOT EXISTS ioflow.hitl_user_roles (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES ioflow.users(user_id),
        hitl_role_id VARCHAR(36) NOT NULL REFERENCES ioflow.hitl_roles(role_id),
        tenant_id VARCHAR(36) NOT NULL,
        assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        assigned_by VARCHAR(36) NOT NULL,
        CONSTRAINT unique_user_hitl_role UNIQUE (user_id, hitl_role_id)
    );
    """

    create_hitl_tasks_sql = """
    CREATE TABLE IF NOT EXISTS ioflow.hitl_tasks (
        task_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        execution_id VARCHAR(36) NOT NULL REFERENCES ioflow.flow_executions(execution_id),
        flow_id VARCHAR(36) NOT NULL,
        node_id VARCHAR(100) NOT NULL,
        task_token VARCHAR(255) NOT NULL UNIQUE,
        task_type VARCHAR(20) NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
        input_data JSONB,
        display_config JSONB,
        response_data JSONB,
        response_action VARCHAR(20),
        completed_by VARCHAR(36),
        completed_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        timeout_at TIMESTAMP,
        escalation_config JSONB,
        escalation_level INTEGER NOT NULL DEFAULT 0,
        execution_snapshot JSONB,
        metadata JSONB
    );
    """

    create_hitl_task_assignments_sql = """
    CREATE TABLE IF NOT EXISTS ioflow.hitl_task_assignments (
        id VARCHAR(36) PRIMARY KEY,
        task_id VARCHAR(36) NOT NULL REFERENCES ioflow.hitl_tasks(task_id),
        assignee_type VARCHAR(20) NOT NULL,
        assignee_id VARCHAR(36) NOT NULL,
        tenant_id VARCHAR(36) NOT NULL,
        notified_at TIMESTAMP
    );
    """

    indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_hitl_roles_tenant ON ioflow.hitl_roles(tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_user_roles_user ON ioflow.hitl_user_roles(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_user_roles_role ON ioflow.hitl_user_roles(hitl_role_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_tenant_status ON ioflow.hitl_tasks(tenant_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_execution ON ioflow.hitl_tasks(execution_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_tasks_token ON ioflow.hitl_tasks(task_token);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_assignments_task ON ioflow.hitl_task_assignments(task_id);",
        "CREATE INDEX IF NOT EXISTS idx_hitl_assignments_assignee ON ioflow.hitl_task_assignments(assignee_type, assignee_id, tenant_id);",
    ]

    with engine.connect() as conn:
        logger.info("Creating HITL tables for PostgreSQL...")
        conn.execute(text(create_hitl_roles_sql))
        conn.execute(text(create_hitl_user_roles_sql))
        conn.execute(text(create_hitl_tasks_sql))
        conn.execute(text(create_hitl_task_assignments_sql))

        for idx_sql in indexes_sql:
            conn.execute(text(idx_sql))

        conn.commit()
        logger.info("HITL tables created successfully for PostgreSQL.")


if __name__ == "__main__":
    run_migration()

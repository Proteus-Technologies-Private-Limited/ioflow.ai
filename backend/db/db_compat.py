"""
Database Compatibility Layer for IOFlow

This module provides a single source of truth for database-specific configuration,
allowing models to work with both PostgreSQL (with ioflow schema) and SQLite (no schema).

Usage in model files:
    from db.db_compat import (
        JSONB, schema_table_args, fk, is_sqlite
    )

    class MyModel(Base):
        __tablename__ = 'my_table'
        __table_args__ = schema_table_args(
            Index('idx_my_field', 'my_field'),
        )

        other_id = Column(String, ForeignKey(fk('other_table.id')), nullable=False)
        data = Column(JSONB)
"""

from core.config import settings

# Determine database type once at import time
is_sqlite = settings.database_url.startswith("sqlite") if hasattr(settings, 'database_url') else False

# Import the appropriate JSON type
if is_sqlite:
    from sqlalchemy.dialects.sqlite import JSON as JSONB
else:
    from sqlalchemy.dialects.postgresql import JSONB

# Schema prefix for ForeignKey references
_fk_prefix = '' if is_sqlite else 'ioflow.'


def fk(table_column: str) -> str:
    """
    Generate a ForeignKey reference with the appropriate schema prefix.

    Args:
        table_column: The table.column reference (e.g., 'users.user_id')

    Returns:
        The reference with schema prefix for PostgreSQL, or as-is for SQLite

    Example:
        ForeignKey(fk('users.user_id'))  # -> 'ioflow.users.user_id' for PostgreSQL
    """
    return f'{_fk_prefix}{table_column}'


def schema_table_args(*indexes, **kwargs):
    """
    Generate __table_args__ with the appropriate schema configuration.

    For PostgreSQL: Adds {'schema': 'ioflow'} to the table args
    For SQLite: Returns just the indexes (no schema)

    Args:
        *indexes: Index objects to include in table args
        **kwargs: Additional table args (e.g., extend_existing=True)

    Returns:
        Tuple or dict suitable for __table_args__

    Example:
        __table_args__ = schema_table_args(
            Index('idx_user_email', 'email'),
            Index('idx_user_tenant', 'tenant_id'),
        )
    """
    if is_sqlite:
        if indexes:
            if kwargs:
                return (*indexes, kwargs)
            return indexes if len(indexes) > 1 else (indexes[0],) if indexes else {}
        return kwargs if kwargs else {}
    else:
        # PostgreSQL with schema
        schema_dict = {'schema': 'ioflow', **kwargs}
        if indexes:
            return (*indexes, schema_dict)
        return schema_dict


def get_schema_dict(**kwargs):
    """
    Get a simple schema dict for __table_args__.

    For PostgreSQL: Returns {'schema': 'ioflow', **kwargs}
    For SQLite: Returns kwargs or {}

    Example:
        __table_args__ = get_schema_dict()
    """
    if is_sqlite:
        return kwargs if kwargs else {}
    return {'schema': 'ioflow', **kwargs}


def table_ref(table_name: str) -> str:
    """
    Generate a table reference with the appropriate schema prefix for raw SQL queries.

    Args:
        table_name: The table name (e.g., 'tenants')

    Returns:
        The reference with schema prefix for PostgreSQL, or as-is for SQLite

    Example:
        text(f"SELECT * FROM {table_ref('tenants')}")  # -> 'ioflow.tenants' for PostgreSQL
    """
    return f'{_fk_prefix}{table_name}'


def parse_json_field(value) -> any:
    """
    Parse a JSON field that might be a string or already a dict/list.
    SQLite JSON fields return Python dicts/lists, PostgreSQL JSONB may return strings.

    Args:
        value: The value to parse (string, dict, list, or None)

    Returns:
        Parsed Python object (dict, list) or None

    Example:
        pricing = parse_json_field(app.pricing_config)
    """
    import json as _json
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except (_json.JSONDecodeError, ValueError):
            return None
    return value


# Re-export common SQLAlchemy imports for convenience
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum, TIMESTAMP
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

# Default UUID generator
def generate_uuid():
    return str(uuid.uuid4())

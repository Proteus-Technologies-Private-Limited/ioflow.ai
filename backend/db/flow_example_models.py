"""
Database models for Flow Examples feature - PostgreSQL and SQLite
Includes ratings, favorites, and usage statistics.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
import uuid

from .models import Base
from .db_compat import schema_table_args, fk


class FlowExampleRating(Base):
    """User ratings for flow examples"""
    __tablename__ = 'flow_example_ratings'
    __table_args__ = schema_table_args(
        UniqueConstraint('example_id', 'user_id', name='unique_user_example_rating'),
        Index('idx_example_ratings', 'example_id'),
        Index('idx_user_ratings', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    example_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey(fk('users.user_id')), nullable=False)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    rating = Column(Integer, nullable=False)
    review = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class FlowExampleFavorite(Base):
    """User favorites for flow examples"""
    __tablename__ = 'flow_example_favorites'
    __table_args__ = schema_table_args(
        UniqueConstraint('example_id', 'user_id', name='unique_user_example_favorite'),
        Index('idx_example_favorites', 'example_id'),
        Index('idx_user_favorites', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    example_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey(fk('users.user_id')), nullable=False)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)


class FlowExampleUsageStats(Base):
    """Usage statistics for flow examples"""
    __tablename__ = 'flow_example_usage_stats'
    __table_args__ = schema_table_args(
        Index('idx_import_count', 'import_count'),
        Index('idx_last_imported', 'last_imported_at'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    example_id = Column(String(100), unique=True, nullable=False, index=True)
    import_count = Column(Integer, default=0, nullable=False)
    last_imported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

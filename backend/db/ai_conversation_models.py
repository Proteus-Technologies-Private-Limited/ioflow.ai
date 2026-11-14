"""
AI Conversation History Models - PostgreSQL and SQLite
Storage for AI transformation conversation chains
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, TIMESTAMP, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from .models import Base
from .db_compat import JSONB, schema_table_args, fk


class ConversationStatus(enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AITransformConversation(Base):
    """Main conversation thread for AI transformation on a transform node"""
    __tablename__ = 'ai_transform_conversations'
    __table_args__ = schema_table_args(
        Index('idx_conversation_user_flow_node', 'user_id', 'flow_id', 'node_id'),
        Index('idx_conversation_status', 'status'),
    )

    conversation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    flow_id = Column(String(36), nullable=False)
    node_id = Column(String(100), nullable=False)

    # Conversation metadata
    title = Column(String(255), nullable=True)
    status = Column(String(20), default=ConversationStatus.ACTIVE.value)

    # Context information
    flow_name = Column(String(255), nullable=True)
    node_name = Column(String(255), nullable=True)

    # Original context that started the conversation
    initial_context = Column(JSONB, nullable=True)

    # Conversation statistics
    message_count = Column(Integer, default=0)
    last_activity_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    messages = relationship('AITransformMessage', back_populates='conversation', cascade='all, delete-orphan')


class AITransformMessage(Base):
    """Individual message in an AI transformation conversation"""
    __tablename__ = 'ai_transform_messages'
    __table_args__ = schema_table_args(
        Index('idx_message_conversation_sequence', 'conversation_id', 'sequence_number'),
        Index('idx_message_type', 'message_type'),
    )

    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey(fk('ai_transform_conversations.conversation_id')), nullable=False)

    # Message ordering
    sequence_number = Column(Integer, nullable=False)

    # Message content
    message_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    # For AI responses
    generated_code = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    warnings = Column(JSONB, nullable=True)
    test_cases = Column(JSONB, nullable=True)

    # AI provider info
    ai_provider = Column(String(50), nullable=True)
    ai_model = Column(String(100), nullable=True)

    # Code application tracking
    was_applied = Column(Boolean, default=False)
    applied_at = Column(TIMESTAMP, nullable=True)

    # Performance metrics
    generation_time_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    conversation = relationship('AITransformConversation', back_populates='messages')


class AITransformSnapshot(Base):
    """Snapshots of transform node state at different points in conversation"""
    __tablename__ = 'ai_transform_snapshots'
    __table_args__ = schema_table_args(
        Index('idx_snapshot_conversation', 'conversation_id'),
    )

    snapshot_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey(fk('ai_transform_conversations.conversation_id')), nullable=False)
    message_id = Column(String(36), ForeignKey(fk('ai_transform_messages.message_id')), nullable=True)

    # Snapshot metadata
    snapshot_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Transform code at this point
    transform_code = Column(Text, nullable=False)

    # Context at this point
    context_snapshot = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    conversation = relationship('AITransformConversation')
    message = relationship('AITransformMessage')

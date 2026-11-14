"""
Collaboration models for real-time flow editing - PostgreSQL and SQLite
"""
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, TIMESTAMP, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from datetime import datetime, timedelta

from .models import Base
from .db_compat import JSONB, schema_table_args, fk


class CollaborationRole(enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class CollaborationSession(Base):
    """Represents a collaborative editing session for a flow"""
    __tablename__ = 'collaboration_sessions'
    __table_args__ = schema_table_args(
        Index('idx_collaboration_session_flow', 'flow_id'),
        Index('idx_collaboration_session_tenant', 'tenant_id'),
        Index('idx_collaboration_session_token', 'access_token'),
        Index('idx_collaboration_session_active', 'is_active', 'expires_at'),
    )

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id = Column(String(36), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)

    # Session metadata
    created_by = Column(String(36), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    expires_at = Column(TIMESTAMP, nullable=False)
    is_active = Column(Boolean, default=True)

    # Access control
    access_token = Column(String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    allow_anonymous = Column(Boolean, default=True)
    max_participants = Column(Integer, default=10)

    # Session settings
    enable_chat = Column(Boolean, default=True)
    enable_voice = Column(Boolean, default=False)
    enable_video = Column(Boolean, default=False)

    # Session state
    last_activity = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    participant_count = Column(Integer, default=0)

    # Flow snapshot at session start
    initial_flow_snapshot = Column(JSONB)

    # Relationships
    participants = relationship('CollaborationParticipant', back_populates='session', cascade='all, delete-orphan')


class CollaborationParticipant(Base):
    """Represents a participant in a collaboration session"""
    __tablename__ = 'collaboration_participants'
    __table_args__ = schema_table_args(
        Index('idx_collaboration_participant_session', 'session_id'),
        Index('idx_collaboration_participant_user', 'user_id'),
        Index('idx_collaboration_participant_online', 'session_id', 'is_online'),
    )

    participant_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey(fk('collaboration_sessions.session_id')), nullable=False)

    # User identification
    user_id = Column(String(36), nullable=True)
    display_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)

    # Participant role and permissions
    role = Column(SQLEnum(CollaborationRole), default=CollaborationRole.EDITOR)
    can_edit = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=True)
    can_invite = Column(Boolean, default=False)

    # Visual identification
    color = Column(String(7), nullable=False)
    avatar_url = Column(String(500), nullable=True)

    # Presence tracking
    joined_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_activity = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    is_online = Column(Boolean, default=True)
    connection_id = Column(String(255), nullable=True)

    # Current state in the flow
    cursor_position = Column(JSONB)
    viewport = Column(JSONB)
    selected_nodes = Column(JSONB)
    selected_edges = Column(JSONB)

    # Activity tracking
    edit_count = Column(Integer, default=0)

    # Relationships
    session = relationship('CollaborationSession', back_populates='participants')


class CollaborationEvent(Base):
    """Tracks all events in a collaboration session for replay and conflict resolution"""
    __tablename__ = 'collaboration_events'
    __table_args__ = schema_table_args(
        Index('idx_collaboration_event_session', 'session_id', 'sequence_number'),
        Index('idx_collaboration_event_timestamp', 'session_id', 'timestamp'),
        Index('idx_collaboration_event_participant', 'participant_id'),
    )

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey(fk('collaboration_sessions.session_id')), nullable=False, index=True)
    participant_id = Column(String(36), ForeignKey(fk('collaboration_participants.participant_id')), nullable=False)

    # Event metadata
    event_type = Column(String(50), nullable=False)
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    sequence_number = Column(Integer, nullable=False)

    # Event data
    target_type = Column(String(20))
    target_id = Column(String(100))
    operation = Column(JSONB)
    previous_state = Column(JSONB)
    new_state = Column(JSONB)

    # Conflict resolution
    parent_event_id = Column(String(36))
    is_conflicted = Column(Boolean, default=False)
    conflict_resolution = Column(JSONB)


class CollaborationMessage(Base):
    """Chat messages within a collaboration session"""
    __tablename__ = 'collaboration_messages'
    __table_args__ = schema_table_args(
        Index('idx_collaboration_message_session', 'session_id', 'timestamp'),
        Index('idx_collaboration_message_participant', 'participant_id'),
    )

    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey(fk('collaboration_sessions.session_id')), nullable=False, index=True)
    participant_id = Column(String(36), ForeignKey(fk('collaboration_participants.participant_id')), nullable=False)

    # Message content
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default='text')

    # Metadata
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    edited_at = Column(TIMESTAMP, nullable=True)
    is_deleted = Column(Boolean, default=False)

    # Reply threading
    reply_to_id = Column(String(36), ForeignKey(fk('collaboration_messages.message_id')), nullable=True)

    # Mentions and references
    mentions = Column(JSONB)
    node_references = Column(JSONB)


class CollaborationInvite(Base):
    """Invitations to join a collaboration session"""
    __tablename__ = 'collaboration_invites'
    __table_args__ = schema_table_args(
        Index('idx_collaboration_invite_token', 'invite_token'),
        Index('idx_collaboration_invite_session', 'session_id'),
        Index('idx_collaboration_invite_active', 'is_active', 'expires_at'),
    )

    invite_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey(fk('collaboration_sessions.session_id')), nullable=False, index=True)

    # Invite details
    invited_by = Column(String(36), nullable=False)
    invited_email = Column(String(255), nullable=True)
    invite_token = Column(String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # Invite settings
    role = Column(SQLEnum(CollaborationRole), default=CollaborationRole.EDITOR)
    expires_at = Column(TIMESTAMP, nullable=False)
    max_uses = Column(Integer, default=1)
    uses_count = Column(Integer, default=0)

    # Status
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    accepted_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, default=True)


# Helper functions
def generate_participant_color():
    """Generate a unique color for a participant"""
    import random
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2',
        '#F8B739', '#52B788', '#E56B6F', '#B56576', '#6D597A'
    ]
    return random.choice(colors)


DEFAULT_SESSION_DURATION = timedelta(hours=24)


def create_collaboration_session(flow_id: str, tenant_id: str, created_by: str, **kwargs):
    """Helper function to create a new collaboration session"""
    session = CollaborationSession(
        flow_id=flow_id,
        tenant_id=tenant_id,
        created_by=created_by,
        expires_at=datetime.utcnow() + kwargs.get('duration', DEFAULT_SESSION_DURATION),
        **{k: v for k, v in kwargs.items() if k != 'duration'}
    )
    return session

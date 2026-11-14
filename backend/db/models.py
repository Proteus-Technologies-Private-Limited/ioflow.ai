"""
IOFlow Database Models - PostgreSQL and SQLite
Automatically exports the correct models based on database configuration
"""
from core.config import settings

# Check if using SQLite
_is_sqlite = settings.database_url.startswith("sqlite") if hasattr(settings, 'database_url') else False

if _is_sqlite:
    # SQLite: Re-export all models from models_sqlite
    from .models_sqlite import (
        Base,
        UserRole, AppType, FlowStatus, ExecutionStatus, InvitationStatus,
        User, Tenant, SMTPConfiguration, Flow, FlowExecution, ExecutionLog,
        AsyncCallback, APIKey, UserSettings, ChatSession, NodeSessionState,
        UserInvitation,
        HITLRole, HITLUserRole, HITLTask, HITLTaskAssignment,
        EventWait
    )
else:
    # PostgreSQL: Define models with schema
    from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP, Text, Enum as SQLEnum, UniqueConstraint, Integer
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship
    from sqlalchemy.sql import func
    from sqlalchemy.dialects.postgresql import JSONB, UUID
    import enum
    import uuid

    Base = declarative_base()

    # ============================================================================
    # ENUMS (PostgreSQL)
    # ============================================================================

    class UserRole(enum.Enum):
        INSTANCE_ADMIN = "INSTANCE_ADMIN"
        TENANT_ADMIN = "TENANT_ADMIN"
        FLOW_DESIGNER = "FLOW_DESIGNER"
        FLOW_EXECUTOR = "FLOW_EXECUTOR"
        EXECUTION_MONITOR = "EXECUTION_MONITOR"
        APPLICATION_PROVIDER = "APPLICATION_PROVIDER"

    class AppType(enum.Enum):
        GLOBAL = "global"
        TENANT = "tenant"

    class FlowStatus(enum.Enum):
        DRAFT = "draft"
        ACTIVE = "active"
        INACTIVE = "inactive"

    class ExecutionStatus(enum.Enum):
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
        PAUSED = "paused"
        CANCELLED = "cancelled"

    # ============================================================================
    # CORE MODELS (ioflow schema) - PostgreSQL
    # ============================================================================

    class User(Base):
        __tablename__ = 'users'
        __table_args__ = {'schema': 'ioflow'}

        user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        user_name = Column(String(100), nullable=False)
        email = Column(String(255), unique=True, nullable=False)
        auth_provider = Column(String(50), nullable=False, default='email')
        pass_wd_sha = Column(String(255), nullable=False)
        status = Column(String(1), default='N')
        acct_lock = Column(String(1), default='N')
        tenant_id = Column(String(36), ForeignKey('ioflow.tenants.tenant_id'))
        activation_code = Column(String(100))
        role = Column(SQLEnum(UserRole), default=UserRole.FLOW_DESIGNER)
        is_active = Column(Boolean, default=True)
        last_login_at = Column(TIMESTAMP)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

        # Password reset fields
        reset_token = Column(String(255), nullable=True)
        reset_token_expires = Column(TIMESTAMP, nullable=True)

        # Relationships
        tenant = relationship('Tenant', back_populates='users', foreign_keys=[tenant_id])
        api_keys = relationship('APIKey', back_populates='user', cascade='all, delete-orphan')
        settings = relationship('UserSettings', back_populates='user', cascade='all, delete-orphan')

    class Tenant(Base):
        __tablename__ = 'tenants'
        __table_args__ = {'schema': 'ioflow'}

        tenant_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_name = Column(String(255), unique=True, nullable=False)
        schema_name = Column(String(63), unique=True, nullable=False)
        email_domain = Column(String(255), nullable=False)
        web_site = Column(String(255))
        gst_no = Column(String(50))
        address = Column(Text)
        user_id_own = Column(String(36))
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        status = Column(String(20), default='active')
        # Twasta SSO: the twasta tenant this IOFlow tenant was auto-provisioned
        # from ("Authenticate with Twasta"). Unique so one twasta tenant maps to
        # exactly one IOFlow tenant.
        twasta_tenant_id = Column(String(36), unique=True, nullable=True, index=True)

        # Relationships
        users = relationship('User', back_populates='tenant', foreign_keys=[User.tenant_id])
        smtp_configuration = relationship('SMTPConfiguration', back_populates='tenant', uselist=False, cascade='all, delete-orphan')

    class SMTPConfiguration(Base):
        __tablename__ = 'smtp_configuration'
        __table_args__ = {'schema': 'ioflow'}

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), ForeignKey('ioflow.tenants.tenant_id'), unique=True, nullable=False)
        smtp_host = Column(String(255), nullable=False)
        smtp_port = Column(Integer, nullable=False, default=587)
        smtp_username = Column(String(255), nullable=False)
        smtp_password = Column(String(255), nullable=False)
        smtp_from_email = Column(String(255), nullable=False)
        smtp_from_name = Column(String(255), default='IOFlow')
        use_tls = Column(Boolean, default=True)
        use_ssl = Column(Boolean, default=False)
        is_active = Column(Boolean, default=True)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

        # Relationships
        tenant = relationship('Tenant', back_populates='smtp_configuration')

    class APIKey(Base):
        """User API Keys for programmatic access"""
        __tablename__ = "api_keys"
        __table_args__ = {'schema': 'ioflow'}

        id = Column(Integer, primary_key=True, index=True)
        key_hash = Column(String(255), unique=True, index=True, nullable=False)
        key_prefix = Column(String(20), nullable=False)
        name = Column(String(255), nullable=False)
        description = Column(Text, nullable=True)

        # User relationship
        user_id = Column(String(36), ForeignKey("ioflow.users.user_id", ondelete="CASCADE"), nullable=False)
        user = relationship("User", back_populates="api_keys")

        # Permissions and scopes
        scopes = Column(Text, nullable=True)

        # Status and timestamps
        is_active = Column(Boolean, default=True, nullable=False)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=False)
        expires_at = Column(TIMESTAMP, nullable=True)
        last_used_at = Column(TIMESTAMP, nullable=True)

        # Usage tracking
        usage_count = Column(Integer, default=0, nullable=False)

        def __repr__(self):
            return f"<APIKey {self.key_prefix}... '{self.name}'>"

    class UserSettings(Base):
        """User settings table for storing various user preferences"""
        __tablename__ = 'user_settings'
        __table_args__ = (
            UniqueConstraint('user_id', 'setting_type', name='unique_user_setting_type'),
            {'schema': 'ioflow'}
        )

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        user_id = Column(String(36), ForeignKey('ioflow.users.user_id'), nullable=False)
        setting_type = Column(String(50), nullable=False)
        setting_data = Column(JSONB, nullable=False)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

        # Relationships
        user = relationship('User', back_populates='settings')

    # ============================================================================
    # FLOW MODELS (ioflow schema) - PostgreSQL
    # ============================================================================

    class Flow(Base):
        __tablename__ = 'flows'
        __table_args__ = {'schema': 'ioflow'}

        flow_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), nullable=False)
        flow_name = Column(String(255), nullable=False)
        description = Column(Text)
        category = Column(String(100), nullable=True)
        flow_scope = Column(String(50), default='user')
        trigger_config = Column(JSONB)
        flow_definition = Column(JSONB)
        status = Column(SQLEnum(FlowStatus, values_callable=lambda obj: [e.value for e in obj]), default=FlowStatus.DRAFT)
        is_synchronous = Column(Boolean, default=False)
        sync_timeout = Column(Integer, default=30)
        created_by = Column(String(36))
        last_modified_by = Column(String(36))
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

        # Relationships
        executions = relationship('FlowExecution', back_populates='flow')

    class FlowExecution(Base):
        __tablename__ = 'flow_executions'
        __table_args__ = {'schema': 'ioflow'}

        execution_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        flow_id = Column(String(36), ForeignKey('ioflow.flows.flow_id'), nullable=False)
        trigger_type = Column(String(50))
        trigger_data = Column(JSONB)
        status = Column(SQLEnum(ExecutionStatus))
        started_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        completed_at = Column(TIMESTAMP)
        current_step = Column(String(100))
        execution_data = Column(JSONB)
        result_data = Column(JSONB)
        response_status = Column(Integer)
        response_headers = Column(JSONB)
        node_outputs = Column(JSONB)

        # Relationships
        flow = relationship('Flow', back_populates='executions')
        logs = relationship('ExecutionLog', back_populates='execution')
        callbacks = relationship('AsyncCallback', back_populates='execution')

    class ExecutionLog(Base):
        __tablename__ = 'execution_logs'
        __table_args__ = {'schema': 'ioflow'}

        log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        execution_id = Column(String(36), ForeignKey('ioflow.flow_executions.execution_id'), nullable=False)
        step_id = Column(String(100))
        timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
        level = Column(String(20))
        message = Column(Text)
        data = Column(JSONB)

        # Relationships
        execution = relationship('FlowExecution', back_populates='logs')

    class AsyncCallback(Base):
        __tablename__ = 'async_callbacks'
        __table_args__ = {'schema': 'ioflow'}

        callback_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        execution_id = Column(String(36), ForeignKey('ioflow.flow_executions.execution_id'), nullable=False)
        step_id = Column(String(100))
        callback_token = Column(String(255), unique=True, default=lambda: str(uuid.uuid4()))
        status = Column(String(20), default='pending')
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        completed_at = Column(TIMESTAMP)
        response_data = Column(JSONB)

        # Relationships
        execution = relationship('FlowExecution', back_populates='callbacks')

    # ============================================================================
    # CHAT SESSION MODELS (for chat_input trigger) - PostgreSQL
    # ============================================================================

    class ChatSession(Base):
        """
        Tracks active chat sessions for flows with chat_input triggers.
        A chat session represents a conversation with a flow that can span multiple executions.
        """
        __tablename__ = 'chat_sessions'
        __table_args__ = {'schema': 'ioflow'}

        session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), nullable=False, index=True)
        flow_id = Column(String(36), nullable=False, index=True)
        user_id = Column(String(36), nullable=False, index=True)

        # Session state
        status = Column(String(20), default='active')  # 'active', 'ended', 'expired'
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        last_message_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        message_count = Column(Integer, default=0)

        # Expiration - optional per-session TTL override
        expires_at = Column(TIMESTAMP, nullable=True)

        # Relationships
        node_sessions = relationship('NodeSessionState', back_populates='chat_session', cascade='all, delete-orphan')

    class NodeSessionState(Base):
        """
        Generic session state storage for nodes that need persistence across flow executions.
        Designed to be extensible for any node type requiring stateful behavior.

        For AI Agent nodes: stores the mapping between chat_session_id and agent_session_id
        so that the ADK can continue the same conversation across multiple flow invocations.

        Primary use case: (node_id, chat_session_id) -> agent_session_id mapping
        """
        __tablename__ = 'node_session_states'
        __table_args__ = (
            UniqueConstraint('node_id', 'chat_session_id', 'tenant_id', name='unique_node_chat_session'),
            {'schema': 'ioflow'}
        )

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

        # Composite key for session lookup
        node_id = Column(String(100), nullable=False, index=True)
        chat_session_id = Column(String(36), ForeignKey('ioflow.chat_sessions.session_id'), nullable=False, index=True)
        tenant_id = Column(String(36), nullable=False, index=True)

        # Node type for extensibility - different node types can store different data
        node_type = Column(String(50), nullable=False)  # 'agent', 'transform', etc.

        # Agent-specific: ADK session ID for conversation continuity
        agent_session_id = Column(String(100), nullable=True)

        # Generic storage for node-specific state (future extensibility)
        session_data = Column(JSONB, nullable=True)

        # Tracking metadata
        user_id = Column(String(36), nullable=True)
        flow_id = Column(String(36), nullable=True)
        first_invocation_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        last_invocation_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
        invocation_count = Column(Integer, default=1)

        # Status for cleanup
        is_active = Column(Boolean, default=True)

        # Relationships
        chat_session = relationship('ChatSession', back_populates='node_sessions')

    # ============================================================================
    # USER INVITATION MODEL (ioflow schema) - PostgreSQL
    # ============================================================================

    class InvitationStatus(enum.Enum):
        PENDING = "pending"
        ACCEPTED = "accepted"
        EXPIRED = "expired"
        CANCELLED = "cancelled"

    class UserInvitation(Base):
        """
        Tracks pending user invitations to join a tenant/organization.
        Users can be invited by admins and accept via email link.
        """
        __tablename__ = 'user_invitations'
        __table_args__ = (
            UniqueConstraint('tenant_id', 'email', 'status', name='unique_pending_invitation'),
            {'schema': 'ioflow'}
        )

        invitation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), ForeignKey('ioflow.tenants.tenant_id'), nullable=False, index=True)
        email = Column(String(255), nullable=False, index=True)
        invited_by = Column(String(36), ForeignKey('ioflow.users.user_id'), nullable=False)

        # Invitation token for secure acceptance
        invitation_token = Column(String(255), unique=True, nullable=False, index=True)

        # Role to assign when user accepts
        role = Column(SQLEnum(UserRole), default=UserRole.FLOW_DESIGNER)

        # Invitation status
        status = Column(SQLEnum(InvitationStatus), default=InvitationStatus.PENDING)

        # Timestamps
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        expires_at = Column(TIMESTAMP, nullable=False)
        accepted_at = Column(TIMESTAMP, nullable=True)

        # Optional message from inviter
        message = Column(Text, nullable=True)

        # Relationships
        tenant = relationship('Tenant')
        inviter = relationship('User', foreign_keys=[invited_by])

    # ============================================================================
    # HUMAN IN THE LOOP (HITL) MODELS (ioflow schema) - PostgreSQL
    # ============================================================================

    class HITLRole(Base):
        """Tenant-scoped custom roles for HITL task assignment."""
        __tablename__ = 'hitl_roles'
        __table_args__ = (
            UniqueConstraint('tenant_id', 'role_name', name='unique_tenant_hitl_role'),
            {'schema': 'ioflow'}
        )

        role_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), ForeignKey('ioflow.tenants.tenant_id'), nullable=False, index=True)
        role_name = Column(String(100), nullable=False)
        role_description = Column(Text, nullable=True)
        created_by = Column(String(36), nullable=False)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        is_active = Column(Boolean, default=True)

        # Relationships
        user_roles = relationship('HITLUserRole', back_populates='hitl_role', cascade='all, delete-orphan')

    class HITLUserRole(Base):
        """Many-to-many mapping between users and HITL roles."""
        __tablename__ = 'hitl_user_roles'
        __table_args__ = (
            UniqueConstraint('user_id', 'hitl_role_id', name='unique_user_hitl_role'),
            {'schema': 'ioflow'}
        )

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        user_id = Column(String(36), ForeignKey('ioflow.users.user_id'), nullable=False, index=True)
        hitl_role_id = Column(String(36), ForeignKey('ioflow.hitl_roles.role_id'), nullable=False, index=True)
        tenant_id = Column(String(36), nullable=False, index=True)
        assigned_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        assigned_by = Column(String(36), nullable=False)

        # Relationships
        hitl_role = relationship('HITLRole', back_populates='user_roles')

    class HITLTask(Base):
        """Task record created when a human_in_loop node executes."""
        __tablename__ = 'hitl_tasks'
        __table_args__ = {'schema': 'ioflow'}

        task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), nullable=False, index=True)
        execution_id = Column(String(36), ForeignKey('ioflow.flow_executions.execution_id'), nullable=False, index=True)
        flow_id = Column(String(36), nullable=False)
        node_id = Column(String(100), nullable=False)
        task_token = Column(String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

        # Task configuration
        task_type = Column(String(20), nullable=False)  # 'review', 'edit', 'approve_reject'
        title = Column(String(255), nullable=False)
        description = Column(Text, nullable=True)
        status = Column(String(20), default='pending', index=True)  # 'pending', 'completed', 'expired', 'escalated', 'cancelled'
        priority = Column(String(20), default='medium')  # 'low', 'medium', 'high', 'critical'

        # Data
        input_data = Column(JSONB, nullable=True)
        display_config = Column(JSONB, nullable=True)
        response_data = Column(JSONB, nullable=True)
        response_action = Column(String(20), nullable=True)  # 'approved', 'rejected', 'edited', 'reviewed'

        # Completion
        completed_by = Column(String(36), nullable=True)
        completed_at = Column(TIMESTAMP, nullable=True)
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

        # Escalation
        timeout_at = Column(TIMESTAMP, nullable=True)
        escalation_config = Column(JSONB, nullable=True)
        escalation_level = Column(Integer, default=0)

        # Execution context snapshot for resume
        execution_snapshot = Column(JSONB, nullable=True)
        task_metadata = Column('metadata', JSONB, nullable=True)

        # Relationships
        execution = relationship('FlowExecution')
        assignments = relationship('HITLTaskAssignment', back_populates='task', cascade='all, delete-orphan')

    class HITLTaskAssignment(Base):
        """Tracks who is assigned to a HITL task."""
        __tablename__ = 'hitl_task_assignments'
        __table_args__ = {'schema': 'ioflow'}

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        task_id = Column(String(36), ForeignKey('ioflow.hitl_tasks.task_id'), nullable=False, index=True)
        assignee_type = Column(String(20), nullable=False)  # 'user' or 'hitl_role'
        assignee_id = Column(String(36), nullable=False)  # user_id or hitl_role_id
        tenant_id = Column(String(36), nullable=False, index=True)
        notified_at = Column(TIMESTAMP, nullable=True)

        # Relationships
        task = relationship('HITLTask', back_populates='assignments')

    # ============================================================================
    # EVENT WAIT MODELS (for wait_for_event node) - PostgreSQL
    # ============================================================================

    class EventWait(Base):
        """Tracks paused executions waiting for an application event."""
        __tablename__ = 'event_waits'
        __table_args__ = {'schema': 'ioflow'}

        wait_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), nullable=False, index=True)
        execution_id = Column(String(36), ForeignKey('ioflow.flow_executions.execution_id'), nullable=False, index=True)
        flow_id = Column(String(36), nullable=False)
        node_id = Column(String(100), nullable=False)

        # Event matching criteria
        app_id = Column(String(36), nullable=False, index=True)
        event_name = Column(String(255), nullable=False)
        event_id = Column(String(36), nullable=True)

        # Matching mode: 'correlation' or 'token'
        match_mode = Column(String(20), nullable=False, default='token')

        # Correlation-based matching config (JSONB)
        # e.g. {"event_field": "order_id", "flow_value": "ORD-123"}
        correlation_config = Column(JSONB, nullable=True)

        # Token-based matching (unique callback token)
        callback_token = Column(String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

        # Status: 'waiting', 'matched', 'timed_out', 'cancelled'
        status = Column(String(20), default='waiting', index=True)

        # Timeout configuration
        timeout_at = Column(TIMESTAMP, nullable=True)
        timeout_action = Column(String(30), default='fail')  # 'fail', 'continue_with_defaults', 'skip'
        default_data = Column(JSONB, nullable=True)

        # Execution context snapshot for resume
        execution_snapshot = Column(JSONB, nullable=True)

        # Event data (populated when matched)
        event_data = Column(JSONB, nullable=True)

        # Timestamps
        created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
        matched_at = Column(TIMESTAMP, nullable=True)

        # Metadata
        wait_metadata = Column('metadata', JSONB, nullable=True)

        # Relationships
        execution = relationship('FlowExecution')


# ---------------------------------------------------------------------------
# Execution-log redaction — ONE choke point for every writer.
# ExecutionLog rows are written from a dozen places (execution engine, service
# executors, debug manager, executions API); a secret reaching any of them
# (an inbound API Bearer key inside a logged service_config, an
# x-amz-access-token header, ?api_key= in a URL) must never be persisted.
# ---------------------------------------------------------------------------
def _redact_execution_log(mapper, connection, target):  # noqa: ARG001 — SQLAlchemy signature
    from utils.crypto_utils import redact_secrets, redact_text
    try:
        if target.message is not None:
            target.message = redact_text(target.message)
        if target.data is not None:
            target.data = redact_secrets(target.data)
    except Exception:  # noqa: BLE001 — never fail the log write over redaction
        pass


from sqlalchemy import event as _sa_event  # noqa: E402

_sa_event.listen(ExecutionLog, "before_insert", _redact_execution_log)
_sa_event.listen(ExecutionLog, "before_update", _redact_execution_log)

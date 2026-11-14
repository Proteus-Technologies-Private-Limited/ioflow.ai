"""
Application Management System Models - PostgreSQL and SQLite
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP, Text, Integer, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from .models import Base
from .db_compat import JSONB, schema_table_args, fk, get_schema_dict, is_sqlite


# ============================================================================
# ENUMS
# ============================================================================

class AppType(enum.Enum):
    GLOBAL = "global"
    TENANT = "tenant"


class AuthType(enum.Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN_EXCHANGE = "token_exchange"
    CUSTOM = "custom"


class TriggerType(enum.Enum):
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    POLLING = "polling"
    MANUAL = "manual"
    EMAIL = "email"
    FORM = "form"
    API_CALL = "api_call"
    MQTT = "mqtt"


class ServiceType(enum.Enum):
    WEBHOOK = "webhook"
    API_CALL = "api_call"
    EMAIL_SEND = "email_send"
    LLM_API_CALL = "llm_api_call"
    MCP_CALL = "mcp_call"
    DATABASE_QUERY = "database_query"
    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    TRANSFORM = "transform"
    ACTION = "action"
    CUSTOM = "custom"
    SMTP_SEND = "smtp_send"
    POP3_RECEIVE = "pop3_receive"
    IMAP_RECEIVE = "imap_receive"
    AI_AGENT_EXECUTE = "ai_agent_execute"


class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


class SyncMode(enum.Enum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    OPTIONAL = "optional"


class AccessType(enum.Enum):
    PUBLIC_URL = "public_url"
    ORGANIZATION = "organization"
    SPECIFIC_USERS = "specific_users"
    TENANT_LIST = "tenant_list"


class RelationshipType(enum.Enum):
    PREREQUISITE = "prerequisite"
    FOLLOWUP = "followup"


# ============================================================================
# APPLICATION MODELS - Database-agnostic using db_compat helpers
# ============================================================================

if not is_sqlite:
    # PostgreSQL-specific imports
    from sqlalchemy.dialects.postgresql import UUID


class Application(Base):
    __tablename__ = 'applications'
    __table_args__ = get_schema_dict(extend_existing=True)

    app_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id_owner = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=True)
    created_by = Column(String(36), ForeignKey(fk('users.user_id')))

    app_name = Column(String(255), nullable=False)
    app_scope = Column(String(50), nullable=False, default='global')
    app_type = Column(String(50), nullable=True)
    description = Column(Text)
    icon_url = Column(String(500))
    category = Column(String(100))
    base_url = Column(String(500))
    auth_type = Column(String(50), nullable=False)
    auth_config = Column(JSONB)
    webhook_config = Column(JSONB)
    seed_key = Column(String(100), nullable=True, index=True)

    # Instance tracking fields
    parent_seed_app_id = Column(String(36), nullable=True, index=True)
    instance_number = Column(Integer, default=1)
    instance_name = Column(String(255), nullable=True)
    is_seed_app = Column(Boolean, default=False)
    total_instances = Column(Integer, default=0)

    status = Column(String(20), default='active')
    version = Column(String(20), default='1.0.0')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    app_events = relationship('ApplicationEvent', back_populates='application', cascade='all, delete-orphan')
    app_services = relationship('ApplicationService', back_populates='application', cascade='all, delete-orphan')
    subscriptions = relationship('ApplicationSubscription', back_populates='application')


class ApplicationEvent(Base):
    __tablename__ = 'application_events'
    __table_args__ = get_schema_dict(extend_existing=True)

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey(fk('applications.app_id'), ondelete='CASCADE'), nullable=False)

    event_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    event_type = Column(String(50), nullable=False)
    event_configuration = Column(JSONB)
    extraction_configuration = Column(JSONB)
    output_schema = Column(JSONB)
    sample_payload = Column(JSONB)
    api_endpoint = Column(String(255), unique=True, nullable=True)
    sync_mode = Column(String(20), default='asynchronous')
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    application = relationship('Application', back_populates='app_events')


class ApplicationService(Base):
    __tablename__ = 'application_services'
    __table_args__ = get_schema_dict(extend_existing=True)

    service_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey(fk('applications.app_id'), ondelete='CASCADE'), nullable=False)

    service_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    service_type = Column(String(50), nullable=False)
    service_config = Column(JSONB)
    is_async = Column(Boolean, default=False)
    async_config = Column(JSONB)
    input_schema = Column(JSONB)
    output_schema = Column(JSONB)
    sample_input = Column(JSONB)
    sample_output = Column(JSONB)
    error_schema = Column(JSONB)
    retry_config = Column(JSONB)
    response_config = Column(JSONB)
    timeout_seconds = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    application = relationship('Application', back_populates='app_services')


class OAuthState(Base):
    __tablename__ = 'oauth_states'
    __table_args__ = get_schema_dict(extend_existing=True)

    state_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)
    user_id = Column(String(36), ForeignKey(fk('users.user_id')), nullable=True)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=True)

    state_token = Column(String(255), unique=True, nullable=False, index=True)
    redirect_uri = Column(String(500), nullable=False)
    code_verifier = Column(String(255), nullable=True)
    provider_params = Column(JSONB, nullable=True)
    temp_credentials = Column(JSONB, nullable=True)
    webhook_url = Column(String(500), nullable=True)
    subscription_config = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    expires_at = Column(TIMESTAMP, nullable=False)

    # Relationships
    application = relationship('Application', backref='oauth_states')


class ApplicationSubscription(Base):
    __tablename__ = 'application_subscriptions'
    __table_args__ = get_schema_dict(extend_existing=True)

    subscription_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)

    auth_credentials = Column(JSONB)
    subscription_config = Column(JSONB)
    webhook_url = Column(String(500))
    invocation_api_key = Column(String(255), unique=True, nullable=True)
    api_key_created_at = Column(TIMESTAMP, nullable=True)
    api_key_last_used_at = Column(TIMESTAMP, nullable=True)
    status = Column(String(20), default='active')
    subscribed_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    expires_at = Column(TIMESTAMP)

    # Relationships
    application = relationship('Application', back_populates='subscriptions')


class PublishedApplication(Base):
    """Model for applications published from flows"""
    __tablename__ = 'published_applications'
    __table_args__ = get_schema_dict(extend_existing=True)

    published_app_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id = Column(String(36), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)
    created_by = Column(String(36), ForeignKey(fk('users.user_id')), nullable=False)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=True)

    app_key = Column(String(255), unique=True, nullable=False)
    flow_name = Column(String(255), nullable=False)
    published_version = Column(String(20), default='1.0.0')
    flow_analysis = Column(JSONB)
    generation_config = Column(JSONB)
    parameter_mappings = Column(JSONB)
    status = Column(String(20), default='active')
    auto_update = Column(Boolean, default=False)
    last_sync_at = Column(TIMESTAMP, nullable=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    application = relationship('Application', backref='flow_published_apps')


class PublishedApplicationVersion(Base):
    """Version history for published applications"""
    __tablename__ = 'published_application_versions'
    __table_args__ = get_schema_dict(extend_existing=True)

    version_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    published_app_id = Column(String(36), ForeignKey(fk('published_applications.published_app_id')), nullable=False)

    version_number = Column(String(20), nullable=False)
    flow_definition = Column(JSONB)
    generated_application = Column(JSONB)
    changes_summary = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    published_application = relationship('PublishedApplication', backref='version_history')


class FlowApplicationDependency(Base):
    """Dependencies between flow-based applications"""
    __tablename__ = 'flow_application_dependencies'
    __table_args__ = get_schema_dict(extend_existing=True)

    dependency_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    published_app_id = Column(String(36), ForeignKey(fk('published_applications.published_app_id')), nullable=False)
    depends_on_app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)

    dependency_type = Column(String(50), nullable=False)
    dependency_name = Column(String(255), nullable=False)
    is_required = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    published_application = relationship('PublishedApplication', backref='flow_dependencies')
    dependency_application = relationship('Application', backref='flow_dependents')


class ParameterMapping(Base):
    """Parameter mappings for flow-based applications"""
    __tablename__ = 'parameter_mappings'
    __table_args__ = get_schema_dict(extend_existing=True)

    mapping_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    published_app_id = Column(String(36), ForeignKey(fk('published_applications.published_app_id')), nullable=False)
    service_id = Column(String(36), ForeignKey(fk('application_services.service_id')), nullable=True)

    parameter_name = Column(String(255), nullable=False)
    parameter_type = Column(String(50), nullable=False)
    flow_variable_path = Column(String(500), nullable=False)
    service_parameter_name = Column(String(255), nullable=False)
    transformation_rule = Column(JSONB)
    is_required = Column(Boolean, default=False)
    default_value = Column(JSONB)
    validation_schema = Column(JSONB)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    published_application = relationship('PublishedApplication', backref='parameter_mappings_config')
    service = relationship('ApplicationService', backref='flow_parameter_mappings')


class FlowExecutionBridge(Base):
    """Bridge for executing flows as applications"""
    __tablename__ = 'flow_execution_bridges'
    __table_args__ = get_schema_dict(extend_existing=True)

    bridge_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    published_app_id = Column(String(36), ForeignKey(fk('published_applications.published_app_id')), nullable=False)
    execution_id = Column(String(36), nullable=True)

    service_call_id = Column(String(255), nullable=False)
    input_parameters = Column(JSONB)
    mapped_parameters = Column(JSONB)
    execution_status = Column(String(50), default='pending')
    execution_result = Column(JSONB)
    error_details = Column(JSONB)
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)

    # Relationships
    published_application = relationship('PublishedApplication', backref='flow_executions')


class FrontendFlowApplication(Base):
    """Model for flows published as frontend/public applications"""
    __tablename__ = 'frontend_flow_applications'
    __table_args__ = get_schema_dict(extend_existing=True)

    frontend_app_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    published_app_id = Column(String(36), ForeignKey(fk('published_applications.published_app_id')), nullable=True)
    flow_id = Column(String(36), nullable=True)
    created_by = Column(String(36), ForeignKey(fk('users.user_id')), nullable=False)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=True)

    public_url_slug = Column(String(255), unique=True, nullable=False)
    frontend_app_name = Column(String(255), nullable=False)
    description = Column(Text)
    access_type = Column(String(50), nullable=False)
    access_config = Column(JSONB)
    embed_enabled = Column(Boolean, default=True)
    rate_limit_per_hour = Column(Integer, default=100)
    custom_styling = Column(JSONB)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    last_accessed_at = Column(TIMESTAMP, nullable=True)

    # Micro SaaS fields
    visibility = Column(String(20), default='private')
    billing_preference = Column(String(50), default='free')
    pricing_config = Column(JSONB, nullable=True)
    usage_limits = Column(JSONB, nullable=True)
    marketplace_enabled = Column(Boolean, default=False)

    # Marketplace approval workflow fields
    marketplace_status = Column(String(20), default='draft')
    approval_notes = Column(Text, nullable=True)
    approved_by = Column(String(36), ForeignKey(fk('users.user_id')), nullable=True)
    approved_at = Column(TIMESTAMP, nullable=True)

    # Marketplace discovery fields
    icon_url = Column(String(500), nullable=True)
    screenshots = Column(JSONB, nullable=True)
    demo_url = Column(String(500), nullable=True)
    categories = Column(JSONB, nullable=True)
    tags = Column(JSONB, nullable=True)

    # Featured and trending
    featured_rank = Column(Integer, nullable=True)
    trending_score = Column(Float, default=0.0)

    # Cached metrics
    total_subscribers = Column(Integer, default=0)
    active_subscribers = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)

    # Landing page designer
    page_definition = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    published_application = relationship('PublishedApplication', backref='frontend_applications')
    documentation_pages = relationship(
        'AppDocumentationPage',
        back_populates='app',
        cascade='all, delete-orphan',
        order_by='AppDocumentationPage.display_order'
    )
    landing_images = relationship(
        'LandingPageImage',
        back_populates='app',
        cascade='all, delete-orphan'
    )


class LandingPageImage(Base):
    """Uploaded images for landing page designer"""
    __tablename__ = 'landing_page_images'
    __table_args__ = get_schema_dict(extend_existing=True)

    image_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id'), ondelete='CASCADE'), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    public_url = Column(String(500), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    app = relationship('FrontendFlowApplication', back_populates='landing_images')


class FrontendAppAccessLog(Base):
    """Log public access attempts and executions"""
    __tablename__ = 'frontend_app_access_logs'
    __table_args__ = get_schema_dict(extend_existing=True)

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)

    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500))
    access_type = Column(String(50), nullable=False)
    execution_success = Column(Boolean, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    accessed_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    frontend_application = relationship('FrontendFlowApplication', backref='access_logs')


class FrontendAppEmbedConfig(Base):
    """Configuration for embeddable code generation"""
    __tablename__ = 'frontend_app_embed_configs'
    __table_args__ = get_schema_dict(extend_existing=True)

    config_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)

    embed_type = Column(String(50), nullable=False)
    config_name = Column(String(255), nullable=False)
    embed_settings = Column(JSONB)
    custom_css = Column(Text)
    callback_urls = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    frontend_application = relationship('FrontendFlowApplication', backref='embed_configs')


class MicroSaasRelatedFlow(Base):
    """Model for pre-requisite and follow-up flow relationships between micro SaaS applications"""
    __tablename__ = 'micro_saas_related_flows'
    __table_args__ = get_schema_dict(extend_existing=True)

    relationship_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id'), ondelete='CASCADE'), nullable=False)
    related_frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id'), ondelete='CASCADE'), nullable=False)

    relationship_type = Column(String(20), nullable=False)  # 'prerequisite' or 'followup'
    is_mandatory = Column(Boolean, default=False)  # For prerequisites: whether it must be completed first
    execution_order = Column(Integer, default=0)  # Order within the relationship type
    display_name = Column(String(255), nullable=True)  # Optional custom display name
    documentation = Column(Text, nullable=True)  # Help text shown to users
    parameter_mappings = Column(JSONB, nullable=True)  # JSON: manual parameter mapping configuration
    auto_map_enabled = Column(Boolean, default=True)  # Whether to auto-map parameters by name
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    main_app = relationship(
        'FrontendFlowApplication',
        foreign_keys=[frontend_app_id],
        backref='related_flows_as_main'
    )
    related_app = relationship(
        'FrontendFlowApplication',
        foreign_keys=[related_frontend_app_id],
        backref='related_flows_as_related'
    )


class AppDocumentationPage(Base):
    """Documentation pages for apps"""
    __tablename__ = 'app_documentation_pages'
    __table_args__ = get_schema_dict(extend_existing=True)

    page_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String(36), ForeignKey(fk('frontend_flow_applications.frontend_app_id'), ondelete='CASCADE'), nullable=False)

    title = Column(String(255), nullable=False)
    page_title = Column(String(255), nullable=True)
    slug = Column(String(255), nullable=False)
    page_slug = Column(String(255), nullable=True)
    page_type = Column(String(50), nullable=True)
    content = Column(Text, nullable=True)
    display_order = Column(Integer, default=0)
    is_published = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    app = relationship('FrontendFlowApplication', back_populates='documentation_pages')


# ============================================================================
# SQLITE ALIASES for backward compatibility
# Code that imports ApplicationSQLite etc. will now get the unified model
# ============================================================================

ApplicationSQLite = Application
ApplicationEventSQLite = ApplicationEvent
ApplicationServiceSQLite = ApplicationService
OAuthStateSQLite = OAuthState
ApplicationSubscriptionSQLite = ApplicationSubscription
PublishedApplicationSQLite = PublishedApplication
PublishedApplicationVersionSQLite = PublishedApplicationVersion
FlowApplicationDependencySQLite = FlowApplicationDependency
ParameterMappingSQLite = ParameterMapping
FlowExecutionBridgeSQLite = FlowExecutionBridge
FrontendFlowApplicationSQLite = FrontendFlowApplication
FrontendAppAccessLogSQLite = FrontendAppAccessLog
FrontendAppEmbedConfigSQLite = FrontendAppEmbedConfig
MicroSaasRelatedFlowSQLite = MicroSaasRelatedFlow
AppDocumentationPageSQLite = AppDocumentationPage
LandingPageImageSQLite = LandingPageImage

"""
Application Management System API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
import json
import uuid
import logging
import secrets
import asyncio

from db.database import get_db
from api.auth import get_current_user
from core.config import settings
from utils.sample_data_generator import generate_sample_from_schema
from utils.crypto_utils import encrypt_credentials, decrypt_credentials, encrypt_data, decrypt_data
from schemas.auth_schemas import validate_credentials, get_credential_schema, validate_auth_config, get_auth_config_schema

# Import appropriate models based on database
if settings.database_url.startswith("sqlite"):
    from db.application_models import (
        ApplicationSQLite as Application,
        ApplicationEventSQLite as ApplicationEvent,
        ApplicationServiceSQLite as ApplicationService,
        ApplicationSubscriptionSQLite as ApplicationSubscription
    )
    from db.models_sqlite import User, Tenant
else:
    from db.application_models import (
        Application, ApplicationEvent, ApplicationService, ApplicationSubscription,
        AppType, AuthType, TriggerType, ServiceType, SubscriptionStatus
    )
    from db.models import User, Tenant

from pydantic import BaseModel, Field, validator
from enum import Enum

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

logger = logging.getLogger(__name__)

# Enums for API
class AppScopeEnum(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"

class AppTypeEnum(str, Enum):
    DATABASE = "database"
    EMAIL = "email"
    API = "api"
    FILE_SYSTEM = "file_system"
    MEMORY = "memory"
    FLOW = "flow"
    AI_AGENT = "ai_agent"
    SSH = "ssh"
    MQTT = "mqtt"

class AuthTypeEnum(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN_EXCHANGE = "token_exchange"
    CUSTOM = "custom"

class EventTypeEnum(str, Enum):
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    POLLING = "polling"
    MANUAL = "manual"
    EMAIL = "email"
    FORM = "form"
    API_CALL = "api_call"
    MQTT = "mqtt"

class ServiceTypeEnum(str, Enum):
    WEBHOOK = "webhook"  # Send webhook to external system
    API_CALL = "api_call"  # Make API call to external system
    EMAIL_SEND = "email_send"  # Send email
    LLM_API_CALL = "llm_api_call"  # Call LLM API (OpenAI, Claude, etc.)
    MCP_CALL = "mcp_call"  # MCP protocol call
    DATABASE_QUERY = "database_query"  # Execute database queries
    GRAPHQL = "graphql"  # GraphQL query service
    SEARCH = "search"  # Search/query data
    CREATE = "create"  # Create new records
    UPDATE = "update"  # Update existing records
    DELETE = "delete"  # Delete records
    TRANSFORM = "transform"  # Transform/process data
    ACTION = "action"  # Generic action (legacy/backward compatibility)
    CUSTOM = "custom"  # Custom operations
    # Email service types
    SMTP_SEND = "smtp_send"  # Send email via SMTP
    POP3_RECEIVE = "pop3_receive"  # Receive email via POP3
    IMAP_RECEIVE = "imap_receive"  # Receive email via IMAP
    # File system operations
    FILE_OPERATION = "file_operation"  # File system operations (read, write, list, etc.)
    # AI Agent operations
    AI_AGENT_EXECUTE = "ai_agent_execute"  # Execute AI agent with LLM
    # SSH operations
    SSH_COMMAND = "ssh_command"  # Execute commands on remote servers via SSH

class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"

# Pydantic models
class ApplicationBase(BaseModel):
    app_name: str
    app_scope: AppScopeEnum = AppScopeEnum.GLOBAL
    app_type: Optional[AppTypeEnum] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    category: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: AuthTypeEnum
    auth_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = "active"
    version: Optional[str] = "1.0.0"

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationUpdate(BaseModel):
    app_name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    category: Optional[str] = None
    base_url: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    version: Optional[str] = None
    # Scope management (INSTANCE_ADMIN only). When app_scope is set to "tenant",
    # tenant_id_owner identifies the owning tenant; when set to "global" the owner
    # is cleared automatically.
    app_scope: Optional[AppScopeEnum] = None
    tenant_id_owner: Optional[str] = None

class ApplicationResponse(ApplicationBase):
    app_id: str
    tenant_id_owner: Optional[str] = None
    seed_key: Optional[str] = None  # Key from seed application for cross-instance portability
    parent_seed_app_id: Optional[str] = None  # References the original seed application
    instance_number: int = 1  # Instance number (1, 2, 3, etc.)
    instance_name: Optional[str] = None  # User-friendly name for this instance
    is_seed_app: bool = False  # True if this is a seed application
    total_instances: int = 0  # Count of instances (only for seed apps)
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

class SyncModeEnum(str, Enum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    OPTIONAL = "optional"

class EventBase(BaseModel):
    event_name: str
    display_name: str
    description: Optional[str] = None
    event_type: EventTypeEnum
    event_configuration: Optional[Dict[str, Any]] = None
    extraction_configuration: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    sample_payload: Optional[Dict[str, Any]] = None
    api_endpoint: Optional[str] = None
    sync_mode: Optional[SyncModeEnum] = SyncModeEnum.ASYNCHRONOUS
    is_active: Optional[bool] = True

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[EventTypeEnum] = None
    event_configuration: Optional[Dict[str, Any]] = None
    extraction_configuration: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    sample_payload: Optional[Dict[str, Any]] = None
    api_endpoint: Optional[str] = None
    sync_mode: Optional[SyncModeEnum] = None
    is_active: Optional[bool] = None

class EventResponse(EventBase):
    event_id: str
    app_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ServiceBase(BaseModel):
    service_name: str
    display_name: str
    description: Optional[str] = None
    service_type: ServiceTypeEnum
    service_config: Optional[Dict[str, Any]] = None  # Type-specific configuration
    # Legacy fields removed - all configuration is in service_config
    is_async: Optional[bool] = False
    async_config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    sample_input: Optional[Dict[str, Any]] = None
    sample_output: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    response_config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = 30
    is_active: Optional[bool] = True

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    service_name: Optional[str] = None  # Allow updating service name
    display_name: Optional[str] = None
    description: Optional[str] = None
    service_type: Optional[ServiceTypeEnum] = None  # Allow updating service type
    service_config: Optional[Dict[str, Any]] = None
    # Legacy fields removed - all configuration is in service_config
    is_async: Optional[bool] = None
    async_config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    sample_input: Optional[Dict[str, Any]] = None
    sample_output: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    response_config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceResponse(BaseModel):
    # Put service_id first for better visibility
    service_id: str
    service_name: str
    display_name: str
    description: Optional[str] = None
    service_type: ServiceTypeEnum
    app_id: str
    service_config: Optional[Dict[str, Any]] = None
    is_async: Optional[bool] = False
    async_config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    sample_input: Optional[Dict[str, Any]] = None
    sample_output: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    response_config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = 30
    is_active: Optional[bool] = True
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    app_id: str
    auth_credentials: Optional[Dict[str, Any]] = None
    subscription_config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    status: Optional[SubscriptionStatusEnum] = SubscriptionStatusEnum.ACTIVE

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    auth_credentials: Optional[Dict[str, Any]] = None
    subscription_config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    status: Optional[SubscriptionStatusEnum] = None

class SubscriptionResponse(SubscriptionBase):
    subscription_id: str
    tenant_id: str
    invocation_api_key: Optional[str] = None
    api_key_created_at: Optional[datetime] = None
    api_key_last_used_at: Optional[datetime] = None
    subscribed_at: datetime
    expires_at: Optional[datetime] = None
    application: Optional[ApplicationResponse] = None

    class Config:
        from_attributes = True


# Helper functions for JSON serialization (SQLite and PostgreSQL)
def serialize_json_field(value):
    """
    Convert dict/list to JSON string for SQLite storage.
    For PostgreSQL JSONB, return as-is since the database handles JSON natively.
    """
    if value is None:
        return None
    # Only serialize for SQLite - PostgreSQL JSONB handles dicts/lists natively
    if settings.database_url.startswith("sqlite") and isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def deserialize_json_field(value):
    """
    Convert JSON string to dict/list.
    Handles both SQLite TEXT columns (stored as JSON strings) and
    double-serialized PostgreSQL JSONB values.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return value
    return value

def merge_frontend_fields_to_config(service_data: dict) -> dict:
    """Merge frontend-specific fields into service_config"""
    service_config = service_data.get('service_config') or {}
    
    # Note: All configuration should be inside service_config already
    # Frontend should send configuration properly nested
    
    # For new service types, copy type-specific configuration
    service_type = service_data.get('service_type')
    if service_type == 'api_call':
        # Copy API call specific fields
        if 'endpoint_template' in service_data:
            service_config['endpoint_template'] = service_data.get('endpoint_template')
        if 'method' in service_data:
            service_config['method'] = service_data.get('method')
        if 'response_type' in service_data:
            service_config['response_type'] = service_data.get('response_type')
        # Don't copy headers_template to service_config - it should remain at top level only
        if 'timeout_seconds' in service_data:
            service_config['timeout_seconds'] = service_data.get('timeout_seconds')
    elif service_type == 'webhook':
        # Copy webhook specific fields
        if 'webhook_url' in service_data:
            service_config['webhook_url'] = service_data.get('webhook_url')
        if 'method' in service_data:
            service_config['method'] = service_data.get('method')
        if 'signature_method' in service_data:
            service_config['signature_method'] = service_data.get('signature_method')
        if 'signature_header' in service_data:
            service_config['signature_header'] = service_data.get('signature_header')
    elif service_type == 'email_send':
        # Copy email specific fields
        if 'from_address' in service_data:
            service_config['from_address'] = service_data.get('from_address')
        if 'from_name' in service_data:
            service_config['from_name'] = service_data.get('from_name')
        if 'subject_template' in service_data:
            service_config['subject_template'] = service_data.get('subject_template')
        if 'body_template' in service_data:
            service_config['body_template'] = service_data.get('body_template')
        if 'body_type' in service_data:
            service_config['body_type'] = service_data.get('body_type')
        if 'template_engine' in service_data:
            service_config['template_engine'] = service_data.get('template_engine')
    elif service_type == 'llm_api_call':
        # Copy LLM specific fields
        if 'provider' in service_data:
            service_config['provider'] = service_data.get('provider')
        if 'model' in service_data:
            service_config['model'] = service_data.get('model')
        if 'endpoint' in service_data:
            service_config['endpoint'] = service_data.get('endpoint')
        if 'system_prompt_template' in service_data:
            service_config['system_prompt_template'] = service_data.get('system_prompt_template')
        if 'user_prompt_template' in service_data:
            service_config['user_prompt_template'] = service_data.get('user_prompt_template')
        if 'temperature' in service_data:
            service_config['temperature'] = service_data.get('temperature')
        if 'max_tokens' in service_data:
            service_config['max_tokens'] = service_data.get('max_tokens')
        if 'response_format' in service_data:
            service_config['response_format'] = service_data.get('response_format')
    elif service_type == 'mcp_call':
        # Copy MCP specific fields
        if 'server_name' in service_data:
            service_config['server_name'] = service_data.get('server_name')
        if 'tool_name' in service_data:
            service_config['tool_name'] = service_data.get('tool_name')
        if 'connection_config' in service_data:
            service_config['connection_config'] = service_data.get('connection_config')
        if 'retry_on_failure' in service_data:
            service_config['retry_on_failure'] = service_data.get('retry_on_failure')
    
    return service_config

def mask_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive credential information for API responses"""
    if not credentials:
        return {"masked": True, "has_credentials": False, "description": "No credentials stored"}
    
    # Handle SQLite JSON string format
    credentials_to_check = credentials
    if isinstance(credentials, str):
        try:
            credentials_to_check = json.loads(credentials)
        except:
            return {"masked": True, "has_credentials": False, "description": "Invalid credential format"}
    
    # If it's encrypted, decrypt to check if credentials actually exist
    if isinstance(credentials_to_check, dict) and 'encrypted' in credentials_to_check:
        try:
            decrypted = decrypt_credentials(credentials_to_check)
            if not decrypted:
                # No actual credentials stored
                return {"masked": True, "has_credentials": False, "description": "No credentials stored"}
            
            # Check if we have valid credentials based on the type
            has_oauth_creds = bool(decrypted.get('client_id') and decrypted.get('client_secret'))
            has_api_key = bool(decrypted.get('api_key'))
            has_basic_auth = bool(decrypted.get('username') and decrypted.get('password'))
            has_access_token = bool(decrypted.get('access_token'))
            has_api_key_config = bool(decrypted.get('header_name') or decrypted.get('header_prefix'))
            
            if has_oauth_creds or has_api_key or has_basic_auth or has_access_token or has_api_key_config:
                # Credentials exist
                description = "Credentials are stored securely"
                if has_oauth_creds and not has_access_token:
                    description = "OAuth credentials configured (authorization required)"
                elif has_access_token:
                    description = "OAuth authorized and connected"
                elif has_api_key_config and not has_api_key:
                    description = "API key configuration stored (key not provided)"
                
                result = {
                    "masked": True, 
                    "has_credentials": True, 
                    "description": description,
                    "access_token": bool(decrypted.get('access_token'))
                }
                
                # Include header config for API key auth
                if has_api_key_config:
                    result["header_config"] = {
                        "header_name": decrypted.get('header_name', 'Authorization'),
                        "header_prefix": decrypted.get('header_prefix', 'Bearer')
                    }
                
                return result
            else:
                # No valid credentials found
                return {"masked": True, "has_credentials": False, "description": "No credentials stored"}
        except Exception as e:
            # Error decrypting, assume no credentials
            logger.error(f"Error in mask_credentials: {str(e)}")
            return {"masked": True, "has_credentials": False, "description": "Unable to verify credentials"}
    
    # For unencrypted credentials (legacy), mask the values
    masked = {}
    has_creds = False
    for key, value in credentials_to_check.items():
        if value:
            has_creds = True
            if isinstance(value, str) and len(value) > 4:
                # Show first 2 and last 2 characters
                masked[key] = f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
            else:
                masked[key] = "*" * len(str(value))
    
    if has_creds:
        return {
            "masked": True,
            "has_credentials": True,
            "description": "Credentials are stored (legacy format)",
            "values": masked
        }
    
    return {"masked": True, "has_credentials": False, "description": "No credentials stored"}

def get_user_role_string(user) -> str:
    """Extract role string value from user object, handling enum types"""
    if hasattr(user.role, 'value'):
        return user.role.value
    return str(user.role)

def _require_app_management_role(current_user: "User") -> None:
    """Block roles that are not permitted to manage applications or subscriptions."""
    if get_user_role_string(current_user) in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit managing applications"
        )

def extract_frontend_fields_from_config(db_service) -> None:
    """Extract frontend-specific fields from service_config for response"""
    # This function is no longer needed as all fields are in service_config
    pass

def service_to_dict(db_service) -> dict:
    """Convert service model to dict with frontend fields included"""
    import json
    
    # Extract frontend fields first
    extract_frontend_fields_from_config(db_service)
    
    # Helper function to parse JSON strings if needed
    def parse_json_field(field_value):
        if field_value is None:
            return None
        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except (json.JSONDecodeError, TypeError):
                return field_value
        return field_value
    
    # Log extracted values for debugging
    logger.debug(f"Service {db_service.service_id} - service_config: {db_service.service_config}")
    
    # Parse JSON fields that might be stored as strings
    service_config = parse_json_field(db_service.service_config)
    input_schema = parse_json_field(db_service.input_schema)
    output_schema = parse_json_field(db_service.output_schema)
    sample_input = parse_json_field(db_service.sample_input)
    sample_output = parse_json_field(db_service.sample_output)
    async_config = parse_json_field(db_service.async_config)
    error_schema = parse_json_field(db_service.error_schema)
    retry_config = parse_json_field(db_service.retry_config)
    response_config = parse_json_field(db_service.response_config)
    
    # For published flow applications, extract parameter_schema from service_config
    # and use it as input_schema for parameter mapping
    if (service_config and 
        isinstance(service_config, dict) and 
        service_config.get('flow_based') and 
        'parameter_schema' in service_config):
        
        # Use parameter_schema from service_config as input_schema for flow-based services
        input_schema = service_config['parameter_schema']
        logger.debug(f"Using parameter_schema from service_config for flow-based service {db_service.service_id}")
    
    # Build response dict
    service_dict = {
        'service_id': str(db_service.service_id),
        'app_id': str(db_service.app_id),
        'service_name': db_service.service_name,
        'display_name': db_service.display_name,
        'description': db_service.description,
        'service_type': db_service.service_type,
        'service_config': service_config,
        # Legacy fields removed - all configuration is in service_config
        'is_async': db_service.is_async,
        'async_config': async_config,
        'input_schema': input_schema,  # Use extracted schema for flow-based services
        'output_schema': output_schema,
        'sample_input': sample_input,
        'sample_output': sample_output,
        'error_schema': error_schema,
        'retry_config': retry_config,
        'response_config': response_config,
        'timeout_seconds': db_service.timeout_seconds,
        'is_active': db_service.is_active,
        'created_at': db_service.created_at
    }
    return service_dict

# Application endpoints
@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    app_scope: Optional[AppScopeEnum] = Query(None, description="Filter by application scope (global/tenant/user)"),
    app_type: Optional[AppTypeEnum] = Query(None, description="Filter by application type (database/email/api/etc)"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("updated_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all applications available to the user with search and sort capabilities
    
    Parameters:
    - app_scope: Filter by application scope (global/tenant/user)
    - app_type: Filter by application type (database/email/api/file_system/memory/flow)
    - category: Filter by category
    - status: Filter by status (default: active)
    - search: Search query for filtering by name, category, or description
    - sort_by: Field to sort by (app_name, category, updated_at, created_at)
    - sort_order: Sort order (asc or desc)
    """
    query = db.query(Application)
    
    # Filter by scope
    if app_scope:
        query = query.filter(Application.app_scope == app_scope.value if hasattr(app_scope, 'value') else app_scope)
    
    # Filter by type
    if app_type:
        query = query.filter(Application.app_type == app_type.value if hasattr(app_type, 'value') else app_type)
    
    # Filter by category
    if category:
        query = query.filter(Application.category == category)
    
    # Filter by status
    if status:
        query = query.filter(Application.status == status)
    
    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Application.app_id.ilike(search_pattern)) |
            (Application.app_name.ilike(search_pattern)) |
            (Application.category.ilike(search_pattern)) |
            (Application.description.ilike(search_pattern))
        )
    
    # Filter based on user role
    from db.models import UserRole
    if current_user.role == UserRole.INSTANCE_ADMIN:
        # Instance admin sees all applications
        pass
    elif current_user.tenant_id:
        # For tenant users, show:
        # 1. Global SEED apps (templates) - these are shared across tenants
        # 2. Apps owned by their tenant (including instances they created)
        # NOTE: Instances are tenant-specific even if created from global seed apps
        query = query.filter(
            ((Application.app_scope == "global") & (Application.is_seed_app == True)) |
            (Application.tenant_id_owner == current_user.tenant_id)
        )
    
    # Apply sorting
    order_column = None
    if sort_by == "app_name":
        order_column = Application.app_name
    elif sort_by == "category":
        order_column = Application.category
    elif sort_by == "created_at":
        order_column = Application.created_at
    else:  # Default to updated_at
        order_column = Application.updated_at
    
    if sort_order.lower() == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())
    
    applications = query.all()
    
    # Also include published flow applications that are active
    # Import published application models
    if settings.database_url.startswith("sqlite"):
        from db.application_models import PublishedApplicationSQLite as PublishedApplication
    else:
        from db.application_models import PublishedApplication
    
    # Get published applications and their corresponding regular applications
    published_query = db.query(Application).join(
        PublishedApplication,
        Application.app_id == PublishedApplication.app_id
    ).filter(
        PublishedApplication.status == "active"
    )
    
    # Apply the same filters to published applications
    if app_type:
        published_query = published_query.filter(Application.app_type == app_type)
    if category:
        published_query = published_query.filter(Application.category == category)
    if status:
        published_query = published_query.filter(Application.status == status)
    if search:
        search_pattern = f"%{search}%"
        published_query = published_query.filter(
            (Application.app_id.ilike(search_pattern)) |
            (Application.app_name.ilike(search_pattern)) |
            (Application.category.ilike(search_pattern)) |
            (Application.description.ilike(search_pattern))
        )
    
    # Apply role-based filtering for published apps
    if current_user.role == UserRole.INSTANCE_ADMIN:
        pass  # See all
    elif current_user.tenant_id:
        # Same filter as regular apps: global seed apps OR tenant-owned apps
        published_query = published_query.filter(
            ((Application.app_scope == "global") & (Application.is_seed_app == True)) |
            (Application.tenant_id_owner == current_user.tenant_id)
        )
    
    published_applications = published_query.all()
    
    # Combine regular and published applications, avoiding duplicates
    all_applications = applications.copy()
    existing_app_ids = {app.app_id for app in applications}
    
    for pub_app in published_applications:
        if pub_app.app_id not in existing_app_ids:
            all_applications.append(pub_app)
    
    # Apply sorting to the combined list
    if sort_by == "app_name":
        sort_key = lambda x: x.app_name or ""
    elif sort_by == "category":
        sort_key = lambda x: x.category or ""
    elif sort_by == "created_at":
        sort_key = lambda x: x.created_at
    else:  # Default to updated_at
        sort_key = lambda x: x.updated_at
    
    reverse_order = sort_order.lower() != "asc"
    all_applications.sort(key=sort_key, reverse=reverse_order)
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        for app in all_applications:
            app.auth_config = deserialize_json_field(app.auth_config)
            app.webhook_config = deserialize_json_field(app.webhook_config)
    
    return all_applications


@router.get("/subscribed", response_model=List[ApplicationResponse])
async def list_subscribed_applications(
    app_scope: Optional[AppScopeEnum] = Query(None, description="Filter by application scope (global/tenant/user)"),
    app_type: Optional[AppTypeEnum] = Query(None, description="Filter by application type (database/email/api/etc)"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
    search: Optional[str] = Query(None),
    app_names: Optional[str] = Query(None, description="Comma-separated application names (supports fuzzy matching)"),
    sort_by: str = Query("updated_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List only applications that the user's tenant has subscribed to

    This endpoint is specifically for MCP tools to ensure users only see
    applications their tenant has active subscriptions for.

    Parameters:
    - app_scope: Filter by application scope (global/tenant/user)
    - app_type: Filter by application type (database/email/api/file_system/memory/flow)
    - category: Filter by category
    - status: Filter by status (default: active)
    - search: Search query for filtering by name, category, or description
    - app_names: Comma-separated application names with fuzzy matching support
                 (e.g., "gmail,slack,email" matches "Gmail API", "Slack Webhook", "SMTP Email Service")
    - sort_by: Field to sort by (app_name, category, updated_at, created_at)
    - sort_order: Sort order (asc or desc)
    """
    # Import required models
    from db.application_models import ApplicationSubscription
    from db.models import UserRole

    # Base query - join with subscriptions to only show subscribed applications
    if current_user.role == UserRole.INSTANCE_ADMIN:
        # Instance admin sees all applications (no subscription filter)
        query = db.query(Application)
    elif current_user.tenant_id:
        # For tenant users, only show applications they have subscribed to
        query = db.query(Application).join(
            ApplicationSubscription,
            Application.app_id == ApplicationSubscription.app_id
        ).filter(
            ApplicationSubscription.tenant_id == current_user.tenant_id,
            ApplicationSubscription.status == "active"
        )
    else:
        # User without tenant cannot see any applications
        return []

    # Filter by scope
    if app_scope:
        query = query.filter(Application.app_scope == app_scope.value if hasattr(app_scope, 'value') else app_scope)

    # Filter by type
    if app_type:
        query = query.filter(Application.app_type == app_type.value if hasattr(app_type, 'value') else app_type)

    # Filter by category
    if category:
        query = query.filter(Application.category == category)

    # Filter by status
    if status:
        query = query.filter(Application.status == status)

    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Application.app_id.ilike(search_pattern)) |
            (Application.app_name.ilike(search_pattern)) |
            (Application.category.ilike(search_pattern)) |
            (Application.description.ilike(search_pattern))
        )

    # Apply sorting
    order_column = None
    if sort_by == "app_name":
        order_column = Application.app_name
    elif sort_by == "category":
        order_column = Application.category
    elif sort_by == "created_at":
        order_column = Application.created_at
    else:  # Default to updated_at
        order_column = Application.updated_at

    if sort_order.lower() == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    applications = query.all()

    # Apply fuzzy name matching if app_names parameter provided
    if app_names:
        from services.app_matcher import get_matcher

        # Parse comma-separated names
        query_names = [name.strip() for name in app_names.split(',') if name.strip()]

        if query_names:
            # Convert SQLAlchemy models to dicts for matching
            apps_as_dicts = [
                {
                    "app_id": app.app_id,
                    "app_name": app.app_name,
                    "category": app.category,
                    "description": app.description,
                    "_model": app  # Keep reference to original model
                }
                for app in applications
            ]

            # Perform fuzzy matching
            matcher = get_matcher(fuzzy_threshold=70)
            matched_dicts = matcher.match_applications(query_names, apps_as_dicts)

            # Extract original models from matched results
            applications = [d["_model"] for d in matched_dicts]

            logger.info(f"Fuzzy matching: {len(query_names)} queries matched {len(applications)} apps")

    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        for app in applications:
            app.auth_config = deserialize_json_field(app.auth_config)
            app.webhook_config = deserialize_json_field(app.webhook_config)

    return applications


@router.post("/", response_model=ApplicationResponse)
async def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new application"""
    _require_app_management_role(current_user)
    # Check permissions - only admins can create global apps
    if application.app_scope == AppScopeEnum.GLOBAL and get_user_role_string(current_user) != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create global applications"
        )
    
    # For tenant apps, set the owner
    tenant_id_owner = None
    if application.app_scope == AppScopeEnum.TENANT:
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to a tenant to create tenant applications"
            )
        tenant_id_owner = current_user.tenant_id
    
    # Check for duplicate
    existing = db.query(Application).filter(
        Application.app_name == application.app_name,
        Application.app_type == application.app_type,
        Application.tenant_id_owner == tenant_id_owner
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application with this name already exists"
        )
    
    # Global apps must be flagged as seed apps to be visible across tenants
    # (the list endpoint only surfaces global apps when is_seed_app is True).
    scope_value = application.app_scope.value if hasattr(application.app_scope, 'value') else application.app_scope
    is_seed_app = scope_value == AppScopeEnum.GLOBAL.value

    # Create application
    db_app = Application(
        app_id=str(uuid.uuid4()),
        app_name=application.app_name,
        app_scope=scope_value,
        app_type=application.app_type.value if hasattr(application.app_type, 'value') else application.app_type,
        tenant_id_owner=tenant_id_owner,
        is_seed_app=is_seed_app,
        description=application.description,
        icon_url=application.icon_url,
        category=application.category,
        base_url=application.base_url,
        auth_type=application.auth_type.value if hasattr(application.auth_type, 'value') else application.auth_type,
        auth_config=serialize_json_field(application.auth_config),
        webhook_config=serialize_json_field(application.webhook_config),
        status=application.status,
        version=application.version,
        created_by=current_user.user_id
    )
    
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    
    # Deserialize JSON fields for response
    if settings.database_url.startswith("sqlite"):
        db_app.auth_config = deserialize_json_field(db_app.auth_config)
        db_app.webhook_config = deserialize_json_field(db_app.webhook_config)
    
    return db_app

@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific application"""
    app = db.query(Application).filter(Application.app_id == app_id).first()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    # SECURITY: Enhanced access control with tenant isolation
    user_role = get_user_role_string(current_user)

    # Instance admins have access to everything
    if user_role == "INSTANCE_ADMIN":
        pass  # Allow access
    elif app.app_scope == "global":
        pass  # Global apps are accessible to all authenticated users
    elif app.app_scope == "tenant" or app.tenant_id_owner is not None:
        # For tenant-scoped applications, verify:
        # 1. User's tenant owns the application, OR
        # 2. User's tenant has an active subscription to this application
        has_ownership = app.tenant_id_owner == current_user.tenant_id
        has_subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.tenant_id == current_user.tenant_id,
            ApplicationSubscription.status == "active"
        ).first() is not None

        if not (has_ownership or has_subscription):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this application"
            )
    else:
        # User-scoped or other scopes
        # For now, allow access to authenticated users, but this can be tightened
        pass
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        app.auth_config = deserialize_json_field(app.auth_config)
        app.webhook_config = deserialize_json_field(app.webhook_config)
    
    return app

@router.put("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: str,
    application: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an application"""
    _require_app_management_role(current_user)
    app = db.query(Application).filter(Application.app_id == app_id).first()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    # Check permissions
    user_role = get_user_role_string(current_user)
    if app.app_scope == "global" and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update global applications"
        )

    if app.app_scope == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )

    # Update fields
    update_data = application.model_dump(exclude_unset=True)

    # Handle scope/ownership changes explicitly (INSTANCE_ADMIN only) so the
    # generic setter below does not silently change tenant isolation.
    new_scope = update_data.pop("app_scope", None)
    new_owner = update_data.pop("tenant_id_owner", None)
    owner_provided = "tenant_id_owner" in application.model_dump(exclude_unset=True)

    scope_change = new_scope is not None and new_scope != app.app_scope
    owner_change = owner_provided and new_owner != app.tenant_id_owner

    if scope_change or owner_change:
        if user_role != "INSTANCE_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change an application's scope or owner"
            )

        # Determine the effective target scope after this update.
        target_scope = new_scope.value if new_scope is not None else app.app_scope

        if target_scope == AppScopeEnum.GLOBAL.value:
            # Global apps are not owned by any tenant. They are only listed for
            # tenant users when flagged as a seed/template app (see list filter),
            # so mark it as a seed app to make it visible across tenants.
            app.tenant_id_owner = None
            app.is_seed_app = True
        elif target_scope == AppScopeEnum.TENANT.value:
            # Tenant-scoped apps must have an owner. Use the provided owner,
            # otherwise keep the existing one if present.
            resolved_owner = new_owner if owner_provided else app.tenant_id_owner
            if not resolved_owner:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="tenant_id_owner is required when scoping an application to a tenant"
                )
            if not db.query(Tenant).filter(Tenant.tenant_id == resolved_owner).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tenant '{resolved_owner}' not found"
                )
            app.tenant_id_owner = resolved_owner
            # A tenant-scoped app is not a cross-tenant template.
            app.is_seed_app = False
        else:
            # USER (or other) scope: apply owner change if explicitly provided.
            if owner_provided:
                app.tenant_id_owner = new_owner
            app.is_seed_app = False

        if new_scope is not None:
            app.app_scope = new_scope.value

    for field, value in update_data.items():
        if field in ["auth_config", "webhook_config"]:
            value = serialize_json_field(value)
        setattr(app, field, value)

    db.commit()
    db.refresh(app)
    
    # Deserialize JSON fields for response
    if settings.database_url.startswith("sqlite"):
        app.auth_config = deserialize_json_field(app.auth_config)
        app.webhook_config = deserialize_json_field(app.webhook_config)
    
    return app

@router.get("/{app_id}/has-default-oauth", response_model=Dict[str, bool])
async def check_default_oauth(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if application has default OAuth credentials configured"""
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if OAuth2 with default credentials
    if app.auth_type == "oauth2":
        auth_config = deserialize_json_field(app.auth_config) if app.auth_config else {}
        default_creds = auth_config.get("default_credentials", {})
        has_defaults = bool(default_creds.get("client_id") and default_creds.get("client_secret"))
        return {"has_default_oauth": has_defaults}
    
    return {"has_default_oauth": False}

@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an application"""
    _require_app_management_role(current_user)
    app = db.query(Application).filter(Application.app_id == app_id).first()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )

    # Check permissions
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Check if there are active subscriptions
    active_subs = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.app_id == app_id,
        ApplicationSubscription.status == "active"
    ).count()
    
    if active_subs > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete application with {active_subs} active subscriptions"
        )
    
    db.delete(app)
    db.commit()
    
    return {"message": "Application deleted successfully"}

@router.post("/{app_id}/duplicate", response_model=ApplicationResponse)
async def duplicate_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Duplicate an application with all its services and events"""
    _require_app_management_role(current_user)
    # Get the original application
    original_app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not original_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    user_role = get_user_role_string(current_user)
    if original_app.app_scope == "global" and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can duplicate global applications"
        )
    
    if original_app.app_type == "tenant" and original_app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Create new application with copy suffix
    new_app_id = str(uuid.uuid4())
    copy_num = 1
    new_app_name = f"{original_app.app_name} (Copy)"
    
    # Check if name already exists and increment copy number
    while db.query(Application).filter(Application.app_name == new_app_name).first():
        copy_num += 1
        new_app_name = f"{original_app.app_name} (Copy {copy_num})"
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        auth_config = deserialize_json_field(original_app.auth_config)
        webhook_config = deserialize_json_field(original_app.webhook_config)
    else:
        auth_config = original_app.auth_config
        webhook_config = original_app.webhook_config
    
    # Create new application
    new_app = Application(
        app_id=new_app_id,
        app_name=new_app_name,
        description=original_app.description,
        category=original_app.category,
        app_type=original_app.app_type,
        app_scope=original_app.app_scope,
        auth_type=original_app.auth_type,
        auth_config=serialize_json_field(auth_config),
        webhook_config=serialize_json_field(webhook_config),
        base_url=original_app.base_url,
        icon_url=original_app.icon_url,
        status=original_app.status if hasattr(original_app, 'status') else 'active',
        version=original_app.version,
        created_by=current_user.user_id,
        tenant_id_owner=current_user.tenant_id,
        seed_key=None,  # Clear seed_key for duplicated app
        parent_seed_app_id=None,  # Clear parent reference
        instance_number=1,
        instance_name=None,
        is_seed_app=False,
        total_instances=0
    )
    
    db.add(new_app)
    
    # Copy all events
    original_events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app_id
    ).all()
    
    for event in original_events:
        # Deserialize JSON fields for SQLite
        if settings.database_url.startswith("sqlite"):
            event_config = deserialize_json_field(event.event_configuration)
            extraction_config = deserialize_json_field(event.extraction_configuration)
            output_schema = deserialize_json_field(event.output_schema)
            sample_payload = deserialize_json_field(event.sample_payload)
        else:
            event_config = event.event_configuration
            extraction_config = event.extraction_configuration
            output_schema = event.output_schema
            sample_payload = event.sample_payload
        
        new_event = ApplicationEvent(
            event_id=str(uuid.uuid4()),
            app_id=new_app_id,
            event_name=event.event_name,
            display_name=event.display_name,
            description=event.description,
            event_type=event.event_type,
            event_configuration=serialize_json_field(event_config),
            extraction_configuration=serialize_json_field(extraction_config),
            output_schema=serialize_json_field(output_schema),
            sample_payload=serialize_json_field(sample_payload),
            api_endpoint=None,  # Clear API endpoint to avoid conflicts
            sync_mode=event.sync_mode,
            is_active=event.is_active
        )
        db.add(new_event)
    
    # Copy all services
    original_services = db.query(ApplicationService).filter(
        ApplicationService.app_id == app_id
    ).all()
    
    for service in original_services:
        # Deserialize JSON fields for SQLite
        if settings.database_url.startswith("sqlite"):
            service_config = deserialize_json_field(service.service_config)
            async_config = deserialize_json_field(service.async_config)
            input_schema = deserialize_json_field(service.input_schema)
            output_schema = deserialize_json_field(service.output_schema)
            sample_input = deserialize_json_field(service.sample_input)
            sample_output = deserialize_json_field(service.sample_output)
            error_schema = deserialize_json_field(service.error_schema)
            retry_config = deserialize_json_field(service.retry_config)
            response_config = deserialize_json_field(service.response_config)
        else:
            service_config = service.service_config
            async_config = service.async_config
            input_schema = service.input_schema
            output_schema = service.output_schema
            sample_input = service.sample_input
            sample_output = service.sample_output
            error_schema = service.error_schema
            retry_config = service.retry_config
            response_config = service.response_config
        
        new_service = ApplicationService(
            service_id=str(uuid.uuid4()),
            app_id=new_app_id,
            service_name=service.service_name,
            display_name=service.display_name,
            description=service.description,
            service_type=service.service_type,
            service_config=serialize_json_field(service_config),
            is_async=service.is_async,
            async_config=serialize_json_field(async_config),
            input_schema=serialize_json_field(input_schema),
            output_schema=serialize_json_field(output_schema),
            sample_input=serialize_json_field(sample_input),
            sample_output=serialize_json_field(sample_output),
            error_schema=serialize_json_field(error_schema),
            retry_config=serialize_json_field(retry_config),
            response_config=serialize_json_field(response_config),
            timeout_seconds=service.timeout_seconds,
            is_active=service.is_active
        )
        db.add(new_service)
    
    db.commit()
    db.refresh(new_app)
    
    # Deserialize JSON fields for response
    if settings.database_url.startswith("sqlite"):
        new_app.auth_config = deserialize_json_field(new_app.auth_config)
        new_app.webhook_config = deserialize_json_field(new_app.webhook_config)
    
    return new_app

# Event endpoints
# Full event information endpoint (returns complete event details with all schemas)
@router.get("/{app_id}/events", response_model=List[EventResponse])
async def list_application_events(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all events for an application"""
    # Verify application exists and user has access
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app_id
    ).all()

    # Deserialize JSON fields (for SQLite and legacy PostgreSQL string data)
    for event in events:
        event.event_configuration = deserialize_json_field(event.event_configuration)
        event.extraction_configuration = deserialize_json_field(event.extraction_configuration)
        event.output_schema = deserialize_json_field(event.output_schema)
        event.sample_payload = deserialize_json_field(event.sample_payload)

    return events

# Simplified event list endpoint (returns only basic info for performance)
@router.get("/{app_id}/events_list", response_model=List[Dict[str, Any]])
async def list_application_events_list(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all events for an application
    
    Args:
        app_id: Can be application UUID, seed_key, or app_name
    """
    # app_id (UUID), else seed_key / app_name among the applications the
    # caller may see, their own tenant's first (services/application_lookup).
    from services.application_lookup import find_application
    app = find_application(db, app_id, current_user)
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app.app_id
    ).all()
    
    # Return simplified event information without detailed schemas
    result = []
    for event in events:
        simplified_event = {
            "event_id": str(event.event_id),
            "event_name": event.event_name,
            "display_name": event.display_name or event.event_name,
            "description": event.description,
            "event_type": event.event_type,
            "app_id": str(event.app_id),
            "is_active": event.is_active if event.is_active is not None else True,
            "created_at": event.created_at,
            # Exclude detailed schema fields:
            # - event_configuration
            # - extraction_configuration
            # - output_schema
            # - sample_payload
        }
        result.append(simplified_event)
    
    return result

@router.post("/{app_id}/events", response_model=EventResponse)
async def create_application_event(
    app_id: str,
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new event for an application"""
    _require_app_management_role(current_user)
    # Verify application exists and user has permissions
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Check for duplicate event name
    existing = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app_id,
        ApplicationEvent.event_name == event.event_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event with this name already exists for this application"
        )
    
    # Check for duplicate API endpoint if provided
    if event.api_endpoint:
        endpoint_exists = db.query(ApplicationEvent).filter(
            ApplicationEvent.api_endpoint == event.api_endpoint
        ).first()
        
        if endpoint_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"API endpoint '{event.api_endpoint}' is already in use by another event"
            )
    
    # Create event
    # Convert empty string api_endpoint to None to avoid unique constraint violation
    api_endpoint_value = event.api_endpoint if event.api_endpoint else None

    db_event = ApplicationEvent(
        event_id=str(uuid.uuid4()),
        app_id=app_id,
        event_name=event.event_name,
        display_name=event.display_name,
        description=event.description,
        event_type=event.event_type.value if hasattr(event.event_type, 'value') else event.event_type,
        event_configuration=serialize_json_field(event.event_configuration),
        extraction_configuration=serialize_json_field(event.extraction_configuration),
        output_schema=serialize_json_field(event.output_schema),
        sample_payload=serialize_json_field(event.sample_payload),
        api_endpoint=api_endpoint_value,
        sync_mode=event.sync_mode.value if hasattr(event.sync_mode, 'value') else event.sync_mode,
        is_active=event.is_active
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Deserialize JSON fields for response (for SQLite and legacy PostgreSQL string data)
    db_event.event_configuration = deserialize_json_field(db_event.event_configuration)
    db_event.extraction_configuration = deserialize_json_field(db_event.extraction_configuration)
    db_event.output_schema = deserialize_json_field(db_event.output_schema)
    db_event.sample_payload = deserialize_json_field(db_event.sample_payload)

    return db_event

@router.put("/{app_id}/events/{event_id}", response_model=EventResponse)
async def update_application_event(
    app_id: str,
    event_id: str,
    event: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an event"""
    _require_app_management_role(current_user)
    # Verify event exists
    db_event = db.query(ApplicationEvent).filter(
        ApplicationEvent.event_id == event_id,
        ApplicationEvent.app_id == app_id
    ).first()
    
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Update fields
    update_data = event.model_dump(exclude_unset=True)
    
    # Check for duplicate API endpoint if being updated
    if 'api_endpoint' in update_data and update_data['api_endpoint']:
        endpoint_exists = db.query(ApplicationEvent).filter(
            ApplicationEvent.api_endpoint == update_data['api_endpoint'],
            ApplicationEvent.event_id != event_id  # Exclude current event
        ).first()
        
        if endpoint_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"API endpoint '{update_data['api_endpoint']}' is already in use by another event"
            )
    for field, value in update_data.items():
        if field in ["event_configuration", "extraction_configuration", "output_schema", "sample_payload"]:
            value = serialize_json_field(value)
        elif field == "sync_mode" and hasattr(value, 'value'):
            value = value.value
        elif field == "api_endpoint" and value == "":
            # Convert empty string to None to avoid unique constraint violation
            value = None
        setattr(db_event, field, value)
    
    db.commit()
    db.refresh(db_event)

    # Deserialize JSON fields for response (for SQLite and legacy PostgreSQL string data)
    db_event.event_configuration = deserialize_json_field(db_event.event_configuration)
    db_event.extraction_configuration = deserialize_json_field(db_event.extraction_configuration)
    db_event.output_schema = deserialize_json_field(db_event.output_schema)
    db_event.sample_payload = deserialize_json_field(db_event.sample_payload)

    return db_event

@router.delete("/{app_id}/events/{event_id}")
async def delete_application_event(
    app_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an event"""
    _require_app_management_role(current_user)
    # Verify event exists
    db_event = db.query(ApplicationEvent).filter(
        ApplicationEvent.event_id == event_id,
        ApplicationEvent.app_id == app_id
    ).first()
    
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    db.delete(db_event)
    db.commit()
    
    return {"message": "Event deleted successfully"}

# Service endpoints

# Full service information endpoint (returns complete service details with all schemas)
@router.get("/{app_id}/services", response_model=List[ServiceResponse])
async def list_application_services(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all services for an application
    
    Args:
        app_id: Can be application UUID, seed_key, or app_name
    """
    # app_id (UUID), else seed_key / app_name among the applications the
    # caller may see, their own tenant's first (services/application_lookup).
    from services.application_lookup import find_application
    app = find_application(db, app_id, current_user)
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{app_id}' not found"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Use the resolved app's app_id for the services query
    services = db.query(ApplicationService).filter(
        ApplicationService.app_id == app.app_id
    ).all()
    
    # Convert services to dict format with proper JSON field handling
    return [service_to_dict(service) for service in services]

# Simplified service list endpoint (returns only basic info for performance)
@router.get("/{app_id}/services_list", response_model=List[Dict[str, Any]])
async def list_application_services_list(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all services for an application
    
    Args:
        app_id: Can be application UUID, seed_key, or app_name
    """
    # app_id (UUID), else seed_key / app_name among the applications the
    # caller may see, their own tenant's first (services/application_lookup).
    from services.application_lookup import find_application
    app = find_application(db, app_id, current_user)
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{app_id}' not found"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Use the resolved app's app_id for the services query
    services = db.query(ApplicationService).filter(
        ApplicationService.app_id == app.app_id
    ).all()
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        for service in services:
            service.service_config = deserialize_json_field(service.service_config)
            # Legacy field deserialization removed
            service.async_config = deserialize_json_field(service.async_config)
            service.input_schema = deserialize_json_field(service.input_schema)
            service.output_schema = deserialize_json_field(service.output_schema)
            service.sample_input = deserialize_json_field(service.sample_input)
            service.sample_output = deserialize_json_field(service.sample_output)
            service.error_schema = deserialize_json_field(service.error_schema)
            service.retry_config = deserialize_json_field(service.retry_config)
            service.response_config = deserialize_json_field(service.response_config)
    
    # Return simplified service information without detailed schemas
    try:
        result = []
        for service in services:
            try:
                # Create simplified service response with only basic info
                simplified_service = {
                    "service_id": str(service.service_id),
                    "service_name": service.service_name,
                    "display_name": service.display_name or service.service_name,
                    "description": service.description,
                    "service_type": service.service_type,
                    "app_id": str(service.app_id),
                    "is_async": service.is_async or False,
                    "is_active": service.is_active if service.is_active is not None else True,
                    "created_at": service.created_at,
                    # Exclude detailed schema fields:
                    # - service_config
                    # - async_config
                    # - input_schema
                    # - output_schema
                    # - sample_input
                    # - sample_output
                    # - error_schema
                    # - retry_config
                    # - response_config
                    # Only include basic timeout
                    "timeout_seconds": service.timeout_seconds or 30
                }
                result.append(simplified_service)
            except Exception as e:
                logger.error(f"Error converting service {service.service_id}: {str(e)}")
                logger.error(f"Service data: {service.__dict__}")
                raise
        return result
    except Exception as e:
        logger.error(f"Error listing services for app {app_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving services: {str(e)}"
        )

@router.post("/{app_id}/services", response_model=ServiceResponse)
async def create_application_service(
    app_id: str,
    service: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new service for an application"""
    _require_app_management_role(current_user)
    # Verify application exists and user has permissions
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Check for duplicate service name
    existing = db.query(ApplicationService).filter(
        ApplicationService.app_id == app_id,
        ApplicationService.service_name == service.service_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service with this name already exists for this application"
        )
    
    # Merge frontend fields into service_config
    service_dict = service.model_dump()
    merged_config = merge_frontend_fields_to_config(service_dict)
    
    # Create service
    db_service = ApplicationService(
        service_id=str(uuid.uuid4()),
        app_id=app_id,
        service_name=service.service_name,
        display_name=service.display_name,
        description=service.description,
        service_type=service.service_type.value if hasattr(service.service_type, 'value') else service.service_type,
        service_config=serialize_json_field(merged_config),
        # Legacy fields removed - all configuration is in service_config
        is_async=service.is_async,
        async_config=serialize_json_field(service.async_config),
        input_schema=serialize_json_field(service.input_schema),
        output_schema=serialize_json_field(service.output_schema),
        error_schema=serialize_json_field(service.error_schema),
        retry_config=serialize_json_field(service.retry_config),
        response_config=serialize_json_field(merged_config.get('response_config')),
        timeout_seconds=service.timeout_seconds,
        is_active=service.is_active
    )
    
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    
    # Deserialize JSON fields for response
    if settings.database_url.startswith("sqlite"):
        db_service.service_config = deserialize_json_field(db_service.service_config)
        # Legacy field deserialization removed
        db_service.async_config = deserialize_json_field(db_service.async_config)
        db_service.input_schema = deserialize_json_field(db_service.input_schema)
        db_service.output_schema = deserialize_json_field(db_service.output_schema)
        db_service.sample_input = deserialize_json_field(db_service.sample_input)
        db_service.sample_output = deserialize_json_field(db_service.sample_output)
        db_service.error_schema = deserialize_json_field(db_service.error_schema)
        db_service.retry_config = deserialize_json_field(db_service.retry_config)
        db_service.response_config = deserialize_json_field(db_service.response_config)
    
    # Return service with frontend fields
    return ServiceResponse(**service_to_dict(db_service))

@router.put("/{app_id}/services/{service_id}", response_model=ServiceResponse)
async def update_application_service(
    app_id: str,
    service_id: str,
    service: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a service"""
    _require_app_management_role(current_user)
    logger.info(f"Update request for service {service_id} with data: {service.model_dump()}")
    
    # Verify service exists
    db_service = db.query(ApplicationService).filter(
        ApplicationService.service_id == service_id,
        ApplicationService.app_id == app_id
    ).first()
    
    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Update fields
    update_data = service.model_dump(exclude_unset=True)
    logger.info(f"Updating service {service_id} with data: {update_data}")
    
    # Get service type from update data or use existing
    service_type = update_data.get('service_type', db_service.service_type)
    if hasattr(service_type, 'value'):
        service_type = service_type.value
    
    # Get current service_config
    current_config = deserialize_json_field(db_service.service_config) or {}
    logger.info(f"Current service_config: {current_config}")
    
    # Endpoint template is now handled in service_config
    
    # Merge all type-specific fields into service_config
    type_specific_fields = ['url_pattern', 'parameters']
    
    # Add service type specific fields
    if service_type == 'api_call':
        type_specific_fields.extend(['endpoint_template', 'method', 'response_type', 'timeout_seconds'])
    elif service_type == 'webhook':
        type_specific_fields.extend(['webhook_url', 'method', 'signature_method', 'signature_header'])
    elif service_type == 'email_send':
        type_specific_fields.extend(['from_address', 'from_name', 'subject_template', 'body_type', 'template_engine'])
    elif service_type == 'llm_api_call':
        type_specific_fields.extend(['provider', 'model', 'endpoint', 'system_prompt_template', 'user_prompt_template', 'temperature', 'max_tokens', 'response_format'])
    elif service_type == 'mcp_call':
        type_specific_fields.extend(['server_name', 'tool_name', 'connection_config', 'retry_on_failure'])
    
    # Check if any type-specific fields are being updated
    if any(field in update_data for field in type_specific_fields):
        # Add service_type to update_data to ensure merge_frontend_fields_to_config works correctly
        update_data_with_type = update_data.copy()
        update_data_with_type['service_type'] = service_type
        
        # Update with new values
        merged_config = merge_frontend_fields_to_config(update_data_with_type)
        logger.info(f"Merged config from frontend fields: {merged_config}")
        # Merge with existing config
        current_config.update(merged_config)
        update_data['service_config'] = current_config
        logger.info(f"Final service_config to save: {current_config}")
    
    # Remove type-specific fields from update_data as they're now in service_config
    for field in type_specific_fields:
        update_data.pop(field, None)
    
    for field, value in update_data.items():
        if field in ["service_config", "async_config", 
                    "input_schema", "output_schema", "sample_input", "sample_output", 
                    "error_schema", "retry_config", "response_config"]:
            value = serialize_json_field(value)
        elif field == "service_type" and value is not None:
            # Convert enum to string value
            value = value.value if hasattr(value, 'value') else value
        logger.info(f"Setting {field} = {value}")
        setattr(db_service, field, value)
    
    # Configuration is now fully in service_config
    
    db.commit()
    db.refresh(db_service)
    
    # Deserialize JSON fields for response
    if settings.database_url.startswith("sqlite"):
        db_service.service_config = deserialize_json_field(db_service.service_config)
        # Legacy field deserialization removed
        db_service.async_config = deserialize_json_field(db_service.async_config)
        db_service.input_schema = deserialize_json_field(db_service.input_schema)
        db_service.output_schema = deserialize_json_field(db_service.output_schema)
        db_service.sample_input = deserialize_json_field(db_service.sample_input)
        db_service.sample_output = deserialize_json_field(db_service.sample_output)
        db_service.error_schema = deserialize_json_field(db_service.error_schema)
        db_service.retry_config = deserialize_json_field(db_service.retry_config)
        db_service.response_config = deserialize_json_field(db_service.response_config)
    
    # Return service with frontend fields
    return ServiceResponse(**service_to_dict(db_service))

@router.delete("/{app_id}/services/{service_id}")
async def delete_application_service(
    app_id: str,
    service_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a service"""
    _require_app_management_role(current_user)
    # Verify service exists
    db_service = db.query(ApplicationService).filter(
        ApplicationService.service_id == service_id,
        ApplicationService.app_id == app_id
    ).first()
    
    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if app.app_scope == "global" and user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    db.delete(db_service)
    db.commit()
    
    return {"message": "Service deleted successfully"}

# Subscription endpoints
@router.get("/subscriptions/", response_model=List[SubscriptionResponse])
async def list_my_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all subscriptions for the current user's tenant"""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant"
        )
    
    subscriptions = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.tenant_id == current_user.tenant_id
    ).options(
        joinedload(ApplicationSubscription.application)
    ).all()
    
    # Deserialize JSON fields (for SQLite and legacy PostgreSQL string data)
    for sub in subscriptions:
        sub.auth_credentials = deserialize_json_field(sub.auth_credentials)
        sub.subscription_config = deserialize_json_field(sub.subscription_config)

        # Also deserialize application JSON fields if present
        if sub.application:
            sub.application.auth_config = deserialize_json_field(sub.application.auth_config)
            sub.application.webhook_config = deserialize_json_field(sub.application.webhook_config)

    # Mask credentials in response
    for sub in subscriptions:
        if sub.auth_credentials:
            sub.auth_credentials = mask_credentials(sub.auth_credentials)
    
    return subscriptions

@router.post("/subscriptions/", response_model=SubscriptionResponse)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subscribe to an application"""
    _require_app_management_role(current_user)
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to a tenant"
        )
    
    # Verify application exists
    app = db.query(Application).filter(
        Application.app_id == subscription.app_id
    ).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if already subscribed
    existing = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.tenant_id == current_user.tenant_id,
        ApplicationSubscription.app_id == subscription.app_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already subscribed to this application"
        )
    
    # Handle auth credentials with hierarchy: tenant override -> app defaults
    encrypted_credentials = None
    using_default_credentials = False
    
    if subscription.auth_credentials:
        # Tenant is providing custom credentials
        try:
            # For API key auth, merge default header config with provided credentials
            if app.auth_type == "api_key":
                auth_config = deserialize_json_field(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
                merged_credentials = {
                    "api_key": subscription.auth_credentials.get("api_key", ""),
                    "header_name": subscription.auth_credentials.get("header_name") if "header_name" in subscription.auth_credentials else auth_config.get("header_name", "Authorization"),
                    "header_prefix": subscription.auth_credentials.get("header_prefix") if "header_prefix" in subscription.auth_credentials else auth_config.get("header_prefix", "Bearer")
                }
                # Always store the credentials, even if api_key is empty
                # This ensures header_name and header_prefix are saved
                if merged_credentials["api_key"]:
                    # Validate if API key is provided
                    validated_credentials = validate_credentials(app.auth_type, merged_credentials)
                    encrypted_credentials = encrypt_credentials(validated_credentials)
                else:
                    # Store just the header config without API key
                    encrypted_credentials = encrypt_credentials(merged_credentials)
            else:
                # Validate credentials based on application auth type
                validated_credentials = validate_credentials(app.auth_type, subscription.auth_credentials)
                encrypted_credentials = encrypt_credentials(validated_credentials)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid authentication credentials: {str(e)}"
            )
    elif app.auth_type == "oauth2":
        # Check if app has default OAuth credentials
        auth_config = deserialize_json_field(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
        default_creds = auth_config.get("default_credentials", {})
        
        if default_creds.get("client_id") and default_creds.get("client_secret"):
            # Use application default credentials
            default_oauth_creds = {
                "client_id": default_creds["client_id"],
                "client_secret": default_creds["client_secret"]
            }
            encrypted_credentials = encrypt_credentials(default_oauth_creds)
            using_default_credentials = True
    
    # Generate API key for invocation
    invocation_api_key = f"ioflow_{secrets.token_urlsafe(32)}"
    
    # Prepare subscription config with credential info
    sub_config = subscription.subscription_config or {}
    sub_config["using_default_credentials"] = using_default_credentials

    # Check if user has already provided a complete base_url in subscription_config
    # If so, use it directly without variable validation/replacement
    import re
    if app.base_url:
        # Check if user already provided a complete base_url
        if 'base_url' in sub_config and sub_config['base_url']:
            # User provided a complete base_url, use it as-is
            resolved_base_url = sub_config['base_url']
            logger.info(f"Using user-provided base_url: {resolved_base_url}")
        else:
            # Required config variables are the SINGLE-brace `{var}` placeholders.
            # A `{{auth.<field>}}` placeholder (per-connection host, e.g. Amazon
            # {{auth.endpoint}}, Shopify https://{{auth.shop_domain}}/…) is not a
            # config variable: it stays in the URL and is rendered from the
            # connection's credentials on every call. Reading it as `{auth.x`
            # rejected every such connection with a 400.
            from services.jinja_templating import (
                config_placeholders, fill_config_placeholders, missing_auth_fields,
            )
            required_vars = config_placeholders(app.base_url)

            if required_vars:
                provided_config = subscription.subscription_config or {}
                missing_vars = [var for var in required_vars if var not in provided_config]

                if missing_vars:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Missing required configuration variables: {', '.join(missing_vars)}. "
                               f"Please provide values for these variables in subscription_config."
                    )

            # Templated host: when credentials are supplied now, check every
            # {{auth.<field>}} the URL needs is among them (a connection that
            # cannot build its own URL fails every call). Without credentials
            # (e.g. an OAuth connection completed later) the check happens per
            # call, where a missing field is a clear error before any request.
            if subscription.auth_credentials:
                missing_auth = missing_auth_fields(app.base_url, subscription.auth_credentials)
                if missing_auth:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"This application's base URL ({app.base_url}) needs the connection "
                               f"credential field(s) {', '.join(missing_auth)}, which were not provided."
                    )

            # Replace {variable} with values from subscription_config; {{auth.*}}
            # is kept and rendered per call.
            config_values = {k: v for k, v in sub_config.items()
                             if k not in ("using_default_credentials", "base_url")}
            resolved_base_url = fill_config_placeholders(app.base_url, config_values)

            # Store the resolved base_url in subscription_config for use during execution
            sub_config['base_url'] = resolved_base_url
            logger.info(f"Replaced variables in base_url: {app.base_url} -> {resolved_base_url}")
    
    # Check if application has default custom parameters in auth_config
    if app.auth_config:
        auth_config = deserialize_json_field(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
        if isinstance(auth_config, dict) and "default_custom_params" in auth_config:
            # Merge default custom params with user-provided ones
            default_params = auth_config.get("default_custom_params", {})
            if "custom_params" not in sub_config:
                sub_config["custom_params"] = {}
            
            # Merge each type (header, query, body)
            for param_type in ["header", "query", "body"]:
                if param_type in default_params and default_params[param_type]:
                    if param_type not in sub_config["custom_params"]:
                        sub_config["custom_params"][param_type] = {}
                    # Default params are applied first, user params override
                    merged_params = {**default_params[param_type], **sub_config["custom_params"].get(param_type, {})}
                    if merged_params:
                        sub_config["custom_params"][param_type] = merged_params
    
    # Create subscription
    db_subscription = ApplicationSubscription(
        subscription_id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        app_id=subscription.app_id,
        auth_credentials=serialize_json_field(encrypted_credentials),
        subscription_config=serialize_json_field(sub_config),
        webhook_url=subscription.webhook_url,
        invocation_api_key=invocation_api_key,
        api_key_created_at=datetime.utcnow(),
        status=subscription.status.value if hasattr(subscription.status, 'value') else subscription.status
    )
    
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    
    # Load the application relationship
    db_subscription.application = app
    
    # Create a response object with deserialized and masked fields
    response_data = db_subscription
    
    # Deserialize JSON fields for response (work with copies to avoid modifying DB object)
    if settings.database_url.startswith("sqlite"):
        # Create copies of the credentials and config for response
        auth_creds_for_response = deserialize_json_field(db_subscription.auth_credentials)
        sub_config_for_response = deserialize_json_field(db_subscription.subscription_config)
        
        # Mask credentials in the copy
        if auth_creds_for_response:
            auth_creds_for_response = mask_credentials(auth_creds_for_response)
        
        # Create a response object with the processed data
        # We'll use a dictionary to avoid modifying the DB object
        from sqlalchemy.orm import make_transient
        make_transient(response_data)
        
        response_data.auth_credentials = auth_creds_for_response
        response_data.subscription_config = sub_config_for_response
        
        # Also deserialize application JSON fields
        if response_data.application:
            response_data.application.auth_config = deserialize_json_field(response_data.application.auth_config)
            response_data.application.webhook_config = deserialize_json_field(response_data.application.webhook_config)
    else:
        # For PostgreSQL, also deserialize JSON fields that may be stored as strings
        from sqlalchemy.orm import make_transient
        make_transient(response_data)

        # Deserialize subscription_config if it's a string
        if isinstance(response_data.subscription_config, str):
            response_data.subscription_config = deserialize_json_field(response_data.subscription_config)

        # Deserialize and mask credentials
        if response_data.auth_credentials:
            if isinstance(response_data.auth_credentials, str):
                response_data.auth_credentials = deserialize_json_field(response_data.auth_credentials)
            response_data.auth_credentials = mask_credentials(response_data.auth_credentials)

    return response_data

@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    subscription: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a subscription"""
    _require_app_management_role(current_user)
    db_subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.subscription_id == subscription_id
    ).first()

    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Verify ownership
    if db_subscription.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this subscription"
        )
    
    # Get the application to check auth type for validation
    app = db.query(Application).filter(Application.app_id == db_subscription.app_id).first()
    
    # Update fields
    update_data = subscription.model_dump(exclude_unset=True)
    using_default_credentials = False
    
    for field, value in update_data.items():
        if field == "auth_credentials":
            logger.info(f"Updating auth_credentials for subscription {subscription_id}")
            logger.info(f"Received credentials fields: {list(value.keys()) if value else 'None'}")
            if value is not None and value != {}:
                # Tenant is providing custom credentials
                try:
                    # For API key auth, merge default header config with provided credentials
                    if app.auth_type == "api_key":
                        auth_config = deserialize_json_field(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
                        
                        # Check if we should preserve existing API key
                        preserve_existing_key = False
                        if not value.get("api_key") and db_subscription.auth_credentials:
                            # If no API key provided and subscription has existing credentials, preserve them
                            try:
                                existing_creds = deserialize_json_field(db_subscription.auth_credentials)
                                if existing_creds and 'encrypted' in existing_creds:
                                    decrypted_existing = decrypt_credentials(existing_creds)
                                    if decrypted_existing and decrypted_existing.get("api_key"):
                                        preserve_existing_key = True
                                        existing_api_key = decrypted_existing["api_key"]
                            except:
                                pass
                        
                        merged_credentials = {
                            "api_key": existing_api_key if preserve_existing_key else value.get("api_key", ""),
                            "header_name": value.get("header_name") if "header_name" in value else auth_config.get("header_name", "Authorization"),
                            "header_prefix": value.get("header_prefix") if "header_prefix" in value else auth_config.get("header_prefix", "Bearer")
                        }
                        
                        # Always store the credentials, even if api_key is empty
                        # This ensures header_name and header_prefix are saved
                        if merged_credentials["api_key"]:
                            # Validate if API key is provided
                            validated_credentials = validate_credentials(app.auth_type, merged_credentials)
                            value = serialize_json_field(encrypt_credentials(validated_credentials))
                        else:
                            # Store just the header config without API key
                            value = serialize_json_field(encrypt_credentials(merged_credentials))
                    else:
                        validated_credentials = validate_credentials(app.auth_type, value)
                        value = serialize_json_field(encrypt_credentials(validated_credentials))
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid authentication credentials: {str(e)}"
                    )
            else:
                # Check if we should use default credentials
                if app.auth_type == "oauth2":
                    auth_config = deserialize_json_field(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
                    default_creds = auth_config.get("default_credentials", {})
                    
                    if default_creds.get("client_id") and default_creds.get("client_secret"):
                        # Use application default credentials
                        default_oauth_creds = {
                            "client_id": default_creds["client_id"],
                            "client_secret": default_creds["client_secret"]
                        }
                        value = serialize_json_field(encrypt_credentials(default_oauth_creds))
                        using_default_credentials = True
                    else:
                        # No default credentials and no user credentials provided
                        # Don't update the auth_credentials field
                        continue
                else:
                    # For non-OAuth2, if no credentials provided, don't update
                    continue
        elif field == "subscription_config":
            # Update the using_default_credentials flag
            config = value or {}
            config["using_default_credentials"] = using_default_credentials
            value = serialize_json_field(config)
        elif field == "status" and hasattr(value, 'value'):
            value = value.value
        setattr(db_subscription, field, value)
    
    db.commit()
    db.refresh(db_subscription)
    
    # Load the application relationship
    db_subscription.application = app
    
    # Create a response object with deserialized and masked fields
    response_data = db_subscription
    
    # Deserialize JSON fields for response (work with copies to avoid modifying DB object)
    if settings.database_url.startswith("sqlite"):
        # Create copies of the credentials and config for response
        auth_creds_for_response = deserialize_json_field(db_subscription.auth_credentials)
        sub_config_for_response = deserialize_json_field(db_subscription.subscription_config)
        
        # Mask credentials in the copy
        if auth_creds_for_response:
            auth_creds_for_response = mask_credentials(auth_creds_for_response)
        
        # Create a response object with the processed data
        # We'll use a dictionary to avoid modifying the DB object
        from sqlalchemy.orm import make_transient
        make_transient(response_data)
        
        response_data.auth_credentials = auth_creds_for_response
        response_data.subscription_config = sub_config_for_response

        # Also deserialize application JSON fields
        if response_data.application:
            response_data.application.auth_config = deserialize_json_field(response_data.application.auth_config)
            response_data.application.webhook_config = deserialize_json_field(response_data.application.webhook_config)
    else:
        # For PostgreSQL, also deserialize JSON fields that may be stored as strings
        from sqlalchemy.orm import make_transient
        make_transient(response_data)

        # Deserialize subscription_config if it's a string
        if isinstance(response_data.subscription_config, str):
            response_data.subscription_config = deserialize_json_field(response_data.subscription_config)

        # Deserialize and mask credentials
        if response_data.auth_credentials:
            if isinstance(response_data.auth_credentials, str):
                response_data.auth_credentials = deserialize_json_field(response_data.auth_credentials)
            response_data.auth_credentials = mask_credentials(response_data.auth_credentials)

    return response_data

@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a subscription"""
    _require_app_management_role(current_user)
    db_subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.subscription_id == subscription_id
    ).first()

    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Verify ownership
    if db_subscription.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this subscription"
        )
    
    db.delete(db_subscription)
    db.commit()
    
    return {"message": "Subscription deleted successfully"}

class CreateInstanceRequest(BaseModel):
    instance_name: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None

@router.post("/{app_id}/create-instance", response_model=ApplicationResponse)
async def create_application_instance(
    app_id: str,
    request: CreateInstanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new instance of an application (copy with different credentials)"""
    _require_app_management_role(current_user)
    # Find the seed application or parent application
    seed_app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not seed_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Determine if this is a seed app or already an instance
    actual_seed_app = None
    if seed_app.is_seed_app:
        parent_seed_id = app_id
        seed_key = seed_app.seed_key
        actual_seed_app = seed_app
    else:
        # If it's already an instance, get the parent seed app
        parent_seed_id = seed_app.parent_seed_app_id or app_id
        seed_key = seed_app.seed_key
        # Fetch the actual seed app to get the correct app_name
        actual_seed_app = db.query(Application).filter(
            Application.app_id == parent_seed_id
        ).first()
        if not actual_seed_app:
            actual_seed_app = seed_app  # Fallback
    
    # Get the correct base app name (from the actual seed, not an instance)
    base_app_name = actual_seed_app.app_name if actual_seed_app else seed_app.app_name
    
    # Get the next instance number for this seed app
    # Need to consider the seed app itself (instance_number = 1) and all its instances
    max_instance_from_parent = db.query(func.max(Application.instance_number)).filter(
        Application.parent_seed_app_id == parent_seed_id
    ).scalar() or 0
    
    # Also check the seed app's instance number
    seed_instance_num = actual_seed_app.instance_number if actual_seed_app else 1
    
    # The next instance number should be max + 1
    max_instance = max(max_instance_from_parent, seed_instance_num)
    next_instance_number = max_instance + 1
    
    # Use the provided instance name or create a default one
    # This will be stored directly in app_name field
    custom_app_name = request.instance_name
    if not custom_app_name:
        custom_app_name = f"{base_app_name} - Instance {next_instance_number}"
    
    # Use custom base_url if provided, otherwise use seed app's
    base_url = request.base_url or seed_app.base_url
    
    # Use custom description if provided
    description = request.description or seed_app.description or f"Instance {next_instance_number} of {base_app_name}"
    
    # Create new application instance
    # IMPORTANT: Instances are ALWAYS tenant-scoped, regardless of seed app's scope
    # Seed apps can be global (templates), but instances are tenant-specific configurations
    new_app = Application(
        app_id=str(uuid.uuid4()),
        app_name=custom_app_name,  # Store the custom name directly in app_name
        app_scope='tenant',  # Instances are always tenant-scoped (not inherited from seed)
        app_type=seed_app.app_type,
        description=description,
        icon_url=seed_app.icon_url,
        category=seed_app.category,
        base_url=base_url,
        auth_type=seed_app.auth_type,
        auth_config=seed_app.auth_config,
        webhook_config=seed_app.webhook_config,
        seed_key=seed_key,
        parent_seed_app_id=parent_seed_id,
        instance_number=next_instance_number,
        instance_name=custom_app_name,  # Store same as app_name for consistency
        is_seed_app=False,
        status='active',
        version=seed_app.version,
        created_by=current_user.user_id,
        tenant_id_owner=current_user.tenant_id  # Always set to creating user's tenant
    )
    
    db.add(new_app)
    
    # Copy all events from the seed application
    seed_events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == seed_app.app_id
    ).all()
    
    for event in seed_events:
        new_event = ApplicationEvent(
            event_id=str(uuid.uuid4()),
            app_id=new_app.app_id,
            event_name=event.event_name,
            display_name=event.display_name,
            description=event.description,
            event_type=event.event_type,
            event_configuration=event.event_configuration,
            output_schema=event.output_schema,
            sample_payload=event.sample_payload,
            api_endpoint=event.api_endpoint,
            sync_mode=event.sync_mode,
            is_active=event.is_active
        )
        db.add(new_event)
    
    # Copy all services from the seed application
    seed_services = db.query(ApplicationService).filter(
        ApplicationService.app_id == seed_app.app_id
    ).all()
    
    for service in seed_services:
        new_service = ApplicationService(
            service_id=str(uuid.uuid4()),
            app_id=new_app.app_id,
            service_name=service.service_name,
            display_name=service.display_name,
            description=service.description,
            service_type=service.service_type,
            service_config=service.service_config,
            is_async=service.is_async,
            async_config=service.async_config,
            input_schema=service.input_schema,
            output_schema=service.output_schema,
            error_schema=service.error_schema,
            retry_config=service.retry_config,
            response_config=service.response_config,
            timeout_seconds=service.timeout_seconds,
            is_active=service.is_active
        )
        db.add(new_service)
    
    # Update the total instances count for the seed application
    if seed_app.is_seed_app:
        seed_app.total_instances = (seed_app.total_instances or 0) + 1
    else:
        # Update the parent seed app's count
        parent_seed = db.query(Application).filter(
            Application.app_id == parent_seed_id
        ).first()
        if parent_seed:
            parent_seed.total_instances = (parent_seed.total_instances or 0) + 1
    
    db.commit()
    db.refresh(new_app)
    
    # Prepare response
    if settings.database_url.startswith("sqlite"):
        new_app.auth_config = deserialize_json_field(new_app.auth_config)
        new_app.webhook_config = deserialize_json_field(new_app.webhook_config)
    
    return new_app

@router.get("/{app_id}/instances", response_model=List[ApplicationResponse])
async def get_application_instances(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all instances of an application"""
    # Find the application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Determine the seed app
    if app.is_seed_app:
        seed_app = app
        parent_seed_id = app_id
    else:
        # This is an instance, find its seed app
        parent_seed_id = app.parent_seed_app_id
        seed_app = db.query(Application).filter(Application.app_id == parent_seed_id).first()
        if not seed_app:
            # Fallback: treat this app as the seed
            seed_app = app
            parent_seed_id = app_id
    
    # Get all instances - INCLUDING the seed app itself as instance #1
    all_instances = []
    
    # First, add the seed app (instance #1)
    if seed_app:
        all_instances.append(seed_app)
    
    # Then get all child instances (instance #2, #3, etc.)
    # SECURITY: Apply tenant isolation - only show instances user has access to
    # NOTE: Instances are ALWAYS tenant-scoped (unlike seed apps which can be global)
    from sqlalchemy import or_
    from db.models import UserRole

    user_role = get_user_role_string(current_user)

    if user_role == "INSTANCE_ADMIN":
        # Instance admin can see all instances
        child_instances = db.query(Application).filter(
            Application.parent_seed_app_id == parent_seed_id
        ).order_by(Application.instance_number).all()
    else:
        # Regular users can only see instances:
        # 1. Owned by their tenant (tenant_id_owner matches)
        # 2. They have active subscriptions to
        # NOTE: Removed app_scope == "global" check - instances are tenant-specific,
        # not global. Only seed apps (templates) can be global.
        subscribed_app_ids_subquery = db.query(ApplicationSubscription.app_id).filter(
            ApplicationSubscription.tenant_id == current_user.tenant_id,
            ApplicationSubscription.status == "active"
        ).subquery()

        child_instances = db.query(Application).filter(
            Application.parent_seed_app_id == parent_seed_id,
            or_(
                Application.tenant_id_owner == current_user.tenant_id,
                Application.app_id.in_(subscribed_app_ids_subquery)
            )
        ).order_by(Application.instance_number).all()

    # Add child instances to the list
    all_instances.extend(child_instances)

    instances = all_instances
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        for instance in instances:
            instance.auth_config = deserialize_json_field(instance.auth_config)
            instance.webhook_config = deserialize_json_field(instance.webhook_config)
    
    return instances

@router.delete("/{app_id}/instances/{instance_id}")
async def delete_application_instance(
    app_id: str,
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an application instance"""
    _require_app_management_role(current_user)
    # Find the instance
    instance = db.query(Application).filter(
        Application.app_id == instance_id
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found"
        )
    
    # Check if it's an instance (not a seed app)
    if instance.is_seed_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a seed application. Use uninstall instead."
        )
    
    # SECURITY: Enhanced tenant isolation for deletion
    user_role = get_user_role_string(current_user)

    # Instance admins can delete any instance
    if user_role == "INSTANCE_ADMIN":
        pass  # Allow deletion
    else:
        # Regular users can only delete instances owned by their tenant
        if instance.tenant_id_owner != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete application instances owned by your tenant"
            )

        # Check if current user's tenant has role permission to delete
        # Only tenant admins should be able to delete instances
        if user_role not in ["TENANT_ADMIN", "INSTANCE_ADMIN"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tenant administrators can delete application instances"
            )

    # Check for active subscriptions - including from other tenants
    # Count ALL subscriptions, not just from the current tenant
    subscription_count = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
        ApplicationSubscription.app_id == instance_id,
        ApplicationSubscription.status == "active"
    ).scalar() or 0
    
    if subscription_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete instance with {subscription_count} active subscriptions"
        )
    
    # Update the parent seed app's instance count
    if instance.parent_seed_app_id:
        parent_seed = db.query(Application).filter(
            Application.app_id == instance.parent_seed_app_id
        ).first()
        if parent_seed and parent_seed.total_instances > 0:
            parent_seed.total_instances -= 1
    
    # Delete the instance
    db.delete(instance)
    db.commit()
    
    return {"message": f"Instance '{instance.instance_name or instance.app_name}' deleted successfully"}

@router.patch("/{app_id}/instances/{instance_id}")
async def update_application_instance(
    app_id: str,
    instance_id: str,
    update_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an application instance (e.g., rename)"""
    _require_app_management_role(current_user)
    # Find the instance
    instance = db.query(Application).filter(
        Application.app_id == instance_id
    ).first()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found"
        )
    
    # Check permissions
    user_role = get_user_role_string(current_user)
    if instance.app_scope == "tenant" and instance.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Update allowed fields
    if "instance_name" in update_data:
        instance.instance_name = update_data["instance_name"]
    
    if "base_url" in update_data:
        instance.base_url = update_data["base_url"]
    
    if "description" in update_data:
        instance.description = update_data["description"]
    
    db.commit()
    db.refresh(instance)
    
    # Return updated instance
    return {
        "app_id": instance.app_id,
        "app_name": instance.app_name,
        "instance_name": instance.instance_name,
        "instance_number": instance.instance_number,
        "base_url": instance.base_url,
        "description": instance.description,
        "is_seed_app": instance.is_seed_app,
        "parent_seed_app_id": instance.parent_seed_app_id
    }

@router.post("/subscriptions/{subscription_id}/test-auth", response_model=Dict[str, Any])
async def test_subscription_authentication(
    subscription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test authentication using stored subscription credentials"""
    # Get subscription with application
    subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.subscription_id == subscription_id,
        ApplicationSubscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Get the application
    app = db.query(Application).filter(Application.app_id == subscription.app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        subscription.auth_credentials = deserialize_json_field(subscription.auth_credentials)
        subscription.subscription_config = deserialize_json_field(subscription.subscription_config)
        app.auth_config = deserialize_json_field(app.auth_config)
    
    # Check if subscription has credentials
    if not subscription.auth_credentials:
        return {
            "success": False,
            "error": "No credentials stored for this subscription",
            "auth_type": app.auth_type
        }
    
    # Decrypt credentials
    try:
        decrypted_credentials = decrypt_credentials(subscription.auth_credentials)
        if not decrypted_credentials:
            return {
                "success": False,
                "error": "No credentials found after decryption",
                "auth_type": app.auth_type
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to decrypt credentials: {str(e)}",
            "auth_type": app.auth_type
        }
    
    # Validate credentials
    try:
        validated_credentials = validate_credentials(app.auth_type, decrypted_credentials)
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid credentials format: {str(e)}",
            "auth_type": app.auth_type,
            "credential_keys": list(decrypted_credentials.keys()) if decrypted_credentials else []
        }
    
    return {
        "success": True,
        "message": "Credentials are valid",
        "auth_type": app.auth_type,
        "credential_fields": list(validated_credentials.keys())
    }

@router.get("/{app_id}/credential-schema", response_model=Dict[str, Any])
async def get_application_credential_schema(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the credential schema for an application based on its auth type"""
    # Verify application exists
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check access permissions
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Get credential schema based on auth type
    schema = get_credential_schema(app.auth_type)
    
    # Deserialize auth config
    auth_config = deserialize_json_field(app.auth_config) if app.auth_config else {}
    
    # Check if app has custom credentials schema (for token_exchange and other types)
    if auth_config.get("credentials_schema"):
        custom_creds_schema = auth_config["credentials_schema"]
        
        # Check if it's already in JSON Schema format (has 'type' and 'properties')
        if isinstance(custom_creds_schema, dict) and custom_creds_schema.get("type") == "object" and "properties" in custom_creds_schema:
            # It's already a proper JSON Schema, but add titles for better UI
            schema = custom_creds_schema.copy()
            
            # Add user-friendly titles to fields
            field_titles = {
                "username": "Email Address",
                "handle_type": "Handle Type",
                "password": "Password",
                "api_key": "API Key",
                "client_id": "Client ID",
                "client_secret": "Client Secret"
            }
            
            if "properties" in schema:
                for field_name, field_config in schema["properties"].items():
                    if isinstance(field_config, dict) and "title" not in field_config:
                        # Add title based on field name
                        if field_name in field_titles:
                            field_config["title"] = field_titles[field_name]
                        else:
                            # Convert snake_case to Title Case
                            field_config["title"] = field_name.replace('_', ' ').title()
            
            logger.info(f"Using custom credentials_schema for {app.app_name}: {list(custom_creds_schema.get('properties', {}).keys())}")
        else:
            # Try to convert from simplified format (field_name: {config})
            custom_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            # Convert the custom credentials_schema format to JSON schema format
            for field_name, field_config in custom_creds_schema.items():
                if isinstance(field_config, dict):
                    field_props = {
                        "type": field_config.get("type", "string"),
                        "description": field_config.get("label", field_config.get("description", field_name)),
                        "title": field_config.get("label", field_config.get("title", field_name))
                    }
                    
                    # Add format if specified
                    if field_config.get("format"):
                        field_props["format"] = field_config["format"]
                    
                    # Add enum if specified
                    if field_config.get("enum"):
                        field_props["enum"] = field_config["enum"]
                    
                    # Add default if specified
                    if "default" in field_config:
                        field_props["default"] = field_config["default"]
                    
                    # Add placeholder as description if no label
                    if not field_props.get("description") and field_config.get("placeholder"):
                        field_props["description"] = field_config["placeholder"]
                        
                    custom_schema["properties"][field_name] = field_props
                    
                    # Add to required if specified
                    if field_config.get("required", False):
                        custom_schema["required"].append(field_name)
            
            # Use custom schema if it has properties
            if custom_schema["properties"]:
                schema = custom_schema
                logger.info(f"Using converted credentials_schema for {app.app_name}: {list(custom_schema['properties'].keys())}")
    
    # Check if app has default credentials
    has_defaults = False
    default_indicator = None
    
    if app.auth_type == "oauth2":
        default_creds = auth_config.get("default_credentials", {})
        if default_creds.get("client_id") and default_creds.get("client_secret"):
            has_defaults = True
            default_indicator = "OAuth credentials are pre-configured. You can use them or provide your own."
    
    # Add optional fields for basic auth (like private_key for SFTP)
    if app.auth_type == "basic" and auth_config.get("optional_fields"):
        optional_fields = auth_config.get("optional_fields", {})
        # Tolerate the list form ["field_a", "field_b"] by treating each name
        # as a plain optional string field
        if isinstance(optional_fields, list):
            optional_fields = {name: {} for name in optional_fields if isinstance(name, str)}
        if not isinstance(optional_fields, dict):
            logger.warning(
                f"Ignoring malformed optional_fields for {app.app_name}: "
                f"expected dict or list, got {type(optional_fields).__name__}")
            optional_fields = {}
        if "properties" not in schema:
            schema["properties"] = {}

        # Add each optional field to the schema
        for field_name, field_config in optional_fields.items():
            if isinstance(field_config, dict):
                field_props = {
                    "type": field_config.get("type", "string"),
                    "description": field_config.get("help_text", field_config.get("description", "")),
                    "title": field_config.get("label", field_name.replace('_', ' ').title()),
                    "required": field_config.get("required", False)
                }
                
                # Add placeholder if provided
                if field_config.get("placeholder"):
                    field_props["placeholder"] = field_config["placeholder"]
                
                # Add format if specified
                if field_config.get("format"):
                    field_props["format"] = field_config["format"]
                
                schema["properties"][field_name] = field_props
                
                logger.info(f"Added optional field '{field_name}' to basic auth schema for {app.app_name}")
    
    return {
        "app_id": app_id,
        "app_name": app.app_name,
        "auth_type": app.auth_type,
        "credential_schema": schema,
        "auth_config": auth_config,
        "has_default_credentials": has_defaults,
        "default_credentials_message": default_indicator,
        "allow_credential_override": auth_config.get("allow_credential_override", True),
        "credential_help_text": auth_config.get("credential_help_text", "")
    }

@router.get("/{app_id}/webhook-urls", response_model=List[Dict[str, Any]])
async def get_webhook_urls(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get webhook URLs for all events of an application."""
    # Verify application exists
    db_app = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not db_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Get all events for the application
    events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app_id,
        ApplicationEvent.event_type == "webhook"
    ).all()
    
    base_url = settings.api_url
    webhook_urls = []
    
    for event in events:
        webhook_urls.append({
            "event_id": str(event.event_id),
            "event_name": event.event_name,
            "display_name": event.display_name,
            "webhook_url": f"{base_url}/webhooks/{app_id}/{event.event_name}",
            "is_active": event.is_active
        })
    
    return webhook_urls

@router.get("/{app_id}/events/{event_id}/sample", response_model=Dict[str, Any])
async def get_event_sample_data(
    app_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get sample data for an event based on its output schema"""
    # Verify event exists
    db_event = db.query(ApplicationEvent).filter(
        ApplicationEvent.event_id == event_id,
        ApplicationEvent.app_id == app_id
    ).first()
    
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        db_event.output_schema = deserialize_json_field(db_event.output_schema)
        db_event.sample_payload = deserialize_json_field(db_event.sample_payload)
    
    # If sample_payload exists, return it
    if db_event.sample_payload:
        return {
            "event_name": db_event.event_name,
            "display_name": db_event.display_name,
            "sample_data": db_event.sample_payload,
            "generated": False
        }
    
    # Otherwise generate sample data from output_schema
    if db_event.output_schema:
        sample_data = generate_sample_from_schema(db_event.output_schema)
        return {
            "event_name": db_event.event_name,
            "display_name": db_event.display_name,
            "sample_data": sample_data,
            "generated": True,
            "schema": db_event.output_schema
        }
    
    # No schema or sample available
    return {
        "event_name": db_event.event_name,
        "display_name": db_event.display_name,
        "sample_data": {},
        "generated": True,
        "message": "No output schema or sample payload defined for this event"
    }

@router.get("/{app_id}/services/{service_id}/sample", response_model=Dict[str, Any])
async def get_service_sample_data(
    app_id: str,
    service_id: str,
    sample_type: str = Query("input", pattern="^(input|output)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get sample data for a service based on its input or output schema"""
    # Verify service exists
    db_service = db.query(ApplicationService).filter(
        ApplicationService.service_id == service_id,
        ApplicationService.app_id == app_id
    ).first()
    
    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Check permissions via application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Deserialize JSON fields for SQLite
    if settings.database_url.startswith("sqlite"):
        db_service.input_schema = deserialize_json_field(db_service.input_schema)
        db_service.output_schema = deserialize_json_field(db_service.output_schema)
        db_service.sample_input = deserialize_json_field(db_service.sample_input)
        db_service.sample_output = deserialize_json_field(db_service.sample_output)
        # Legacy field deserialization removed
    
    # Generate sample based on type
    if sample_type == "input":
        if db_service.input_schema:
            sample_data = generate_sample_from_schema(db_service.input_schema)
            return {
                "service_name": db_service.service_name,
                "display_name": db_service.display_name,
                "sample_type": "input",
                "sample_data": sample_data,
                "schema": db_service.input_schema
            }
        # Body template sample generation removed
        else:
            return {
                "service_name": db_service.service_name,
                "display_name": db_service.display_name,
                "sample_type": "input",
                "sample_data": {},
                "message": "No input schema or body template defined for this service"
            }
    else:  # output
        if db_service.output_schema:
            sample_data = generate_sample_from_schema(db_service.output_schema)
            return {
                "service_name": db_service.service_name,
                "display_name": db_service.display_name,
                "sample_type": "output",
                "sample_data": sample_data,
                "schema": db_service.output_schema
            }
        else:
            return {
                "service_name": db_service.service_name,
                "display_name": db_service.display_name,
                "sample_type": "output",
                "sample_data": {},
                "message": "No output schema defined for this service"
            }

@router.post("/{app_id}/test-auth", response_model=Dict[str, Any])
async def test_application_authentication(
    app_id: str,
    test_request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test authentication credentials for an application"""
    # Verify application exists
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check access permissions
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Extract test parameters
    auth_credentials = test_request.get('auth_credentials', {})
    test_endpoint = test_request.get('test_endpoint')
    test_method = test_request.get('test_method', 'GET')
    test_service_id = test_request.get('service_id')
    
    # Validate credentials
    try:
        validated_credentials = validate_credentials(app.auth_type, auth_credentials)
    except ValueError as e:
        # Parse the error message to provide more specific guidance
        error_msg = str(e)
        
        # Add provider-specific help based on the application
        help_url = None
        if app.app_name == "Google Sheets":
            help_url = "https://console.cloud.google.com/apis/credentials"
        elif app.app_name == "GitHub":
            help_url = "https://github.com/settings/developers"
        elif app.app_name == "Slack":
            help_url = "https://api.slack.com/apps"
        
        return {
            "success": False,
            "error": error_msg,
            "auth_type": app.auth_type,
            "help_text": "You need to create OAuth2 application credentials from the service provider's developer console.",
            "help_url": help_url,
            "credential_format": {
                "client_id": "Application Client ID (not your email)",
                "client_secret": "Application Client Secret (not your password)"
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid credentials: {str(e)}",
            "auth_type": app.auth_type
        }
    
    # If a specific service is requested, use its configuration
    if test_service_id:
        service = db.query(ApplicationService).filter(
            ApplicationService.service_id == test_service_id,
            ApplicationService.app_id == app_id
        ).first()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        
        # Deserialize service config
        if settings.database_url.startswith("sqlite"):
            service.service_config = deserialize_json_field(service.service_config)
        
        # Create a simple test executor
        from services.service_executors import get_service_executor
        
        try:
            executor = get_service_executor(
                service.service_type,
                service.service_config,
                validated_credentials
            )
            
            # Execute a test call with minimal parameters
            test_params = test_request.get('test_parameters', {})
            result = await executor.execute(test_params, {})
            
            if 'error' in result and result['error']:
                return {
                    "success": False,
                    "error": result.get('message', 'Authentication failed'),
                    "status_code": result.get('status_code'),
                    "auth_type": app.auth_type,
                    "service_tested": service.service_name
                }
            else:
                return {
                    "success": True,
                    "message": "Authentication successful",
                    "auth_type": app.auth_type,
                    "service_tested": service.service_name,
                    "response_preview": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Test execution failed: {str(e)}",
                "auth_type": app.auth_type,
                "service_tested": service.service_name
            }
    
    # Otherwise, perform a simple HTTP test with the provided endpoint
    elif test_endpoint:
        import httpx
        
        # Build headers based on auth type
        headers = {}
        
        if app.auth_type == "api_key":
            header_name = validated_credentials.get('header_name', 'Authorization')
            header_prefix = validated_credentials.get('header_prefix', 'Bearer')
            if header_prefix:
                headers[header_name] = f"{header_prefix} {validated_credentials['api_key']}"
            else:
                headers[header_name] = validated_credentials['api_key']
                
        elif app.auth_type == "basic":
            import base64
            credentials = f"{validated_credentials['username']}:{validated_credentials['password']}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
            
        elif app.auth_type == "oauth2" and validated_credentials.get('access_token'):
            token_type = validated_credentials.get('token_type', 'Bearer')
            headers['Authorization'] = f"{token_type} {validated_credentials['access_token']}"
            
        elif app.auth_type == "custom" and validated_credentials.get('headers'):
            headers.update(validated_credentials['headers'])
        
        # Make test request
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=test_method,
                    url=test_endpoint,
                    headers=headers,
                    timeout=10.0
                )
                
                return {
                    "success": response.is_success,
                    "status_code": response.status_code,
                    "message": "Authentication successful" if response.is_success else "Authentication failed",
                    "auth_type": app.auth_type,
                    "endpoint_tested": test_endpoint
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Test request failed: {str(e)}",
                "auth_type": app.auth_type,
                "endpoint_tested": test_endpoint
            }
    
    else:
        # If no service or endpoint provided, just validate the credentials format
        return {
            "success": True,
            "message": "Credentials format is valid. No endpoint was tested.",
            "auth_type": app.auth_type,
            "credential_validation_only": True
        }

@router.put("/{app_id}/auth-config", response_model=Dict[str, Any])
async def update_application_auth_config(
    app_id: str,
    auth_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update authentication configuration for an application"""
    _require_app_management_role(current_user)
    # Verify application exists
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions - only admins can update auth config for global apps
    if app.app_scope == "global" and get_user_role_string(current_user) != "INSTANCE_ADMIN":
        logger.warning(f"Auth config update denied - User: {current_user.email}, Role: {current_user.role}, Role value: {get_user_role_string(current_user)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update authentication configuration for global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Extract auth type and config
    new_auth_type = auth_update.get('auth_type')
    new_auth_config = auth_update.get('auth_config', {})
    
    logger.info(f"Updating auth config for app {app_id}")
    logger.info(f"Received auth_config: {new_auth_config}")
    logger.info(f"Has default_credentials: {'default_credentials' in new_auth_config}")
    
    # If auth type is being changed, validate it
    if new_auth_type and new_auth_type != app.auth_type:
        if new_auth_type not in ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid authentication type: {new_auth_type}"
            )
    
    # Use current auth type if not changing
    auth_type_to_validate = new_auth_type or app.auth_type
    
    # Validate auth config based on type
    try:
        validated_config = validate_auth_config(auth_type_to_validate, new_auth_config)
        logger.info(f"Validated auth_config: {validated_config}")
        logger.info(f"Has default_credentials after validation: {'default_credentials' in validated_config}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authentication configuration: {str(e)}"
        )
    
    # Update application
    if new_auth_type:
        app.auth_type = new_auth_type
    app.auth_config = serialize_json_field(validated_config)
    app.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(app)
    
    # Deserialize for response
    if settings.database_url.startswith("sqlite"):
        app.auth_config = deserialize_json_field(app.auth_config)
    
    return {
        "app_id": app_id,
        "app_name": app.app_name,
        "auth_type": app.auth_type,
        "auth_config": app.auth_config,
        "updated_at": app.updated_at,
        "message": "Authentication configuration updated successfully"
    }

@router.get("/auth-types/{auth_type}/config-schema", response_model=Dict[str, Any])
async def get_auth_config_schema_by_type(
    auth_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the configuration schema for a specific authentication type"""
    # Validate auth type
    if auth_type not in ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authentication type: {auth_type}"
        )
    
    # Get configuration schema
    config_schema = get_auth_config_schema(auth_type)
    
    # Get credential schema as well
    credential_schema = get_credential_schema(auth_type)
    
    return {
        "auth_type": auth_type,
        "config_schema": config_schema,
        "credential_schema": credential_schema,
        "description": get_auth_type_description(auth_type)
    }

def get_auth_type_description(auth_type: str) -> str:
    """Get a description of the authentication type"""
    descriptions = {
        "none": "No authentication required",
        "api_key": "API Key authentication - requires an API key to be sent in headers, query params, or body",
        "oauth2": "OAuth2 authentication - supports client credentials flow with automatic token refresh",
        "basic": "Basic HTTP authentication - requires username and password",
        "token_exchange": "Token Exchange authentication - exchange username/password for JWT tokens with automatic refresh",
        "custom": "Custom authentication - allows defining custom headers, query params, or body params"
    }
    return descriptions.get(auth_type, "Unknown authentication type")

@router.post("/{app_id}/oauth2/token", response_model=Dict[str, Any])
async def test_oauth2_token_acquisition(
    app_id: str,
    oauth_request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test OAuth2 token acquisition with provided credentials"""
    # Verify application exists and has OAuth2 auth type
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    if app.auth_type != "oauth2":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for OAuth2 applications"
        )
    
    # Check access permissions
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Get auth config
    auth_config = deserialize_json_field(app.auth_config) if app.auth_config else {}
    
    # Extract OAuth2 credentials
    client_id = oauth_request.get('client_id')
    client_secret = oauth_request.get('client_secret')
    scope = oauth_request.get('scope', auth_config.get('scope'))
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id and client_secret are required"
        )
    
    # Test token acquisition
    from services.oauth2_manager import oauth2_manager
    
    token_data = await oauth2_manager._request_new_token(
        auth_config=auth_config,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope
    )
    
    if token_data:
        # Mask sensitive data in response
        masked_response = {
            "success": True,
            "token_type": token_data.get('token_type', 'Bearer'),
            "expires_in": token_data.get('expires_in'),
            "scope": token_data.get('scope'),
            "access_token": mask_credentials({"token": token_data.get('access_token')}).get('token', '***'),
            "message": "OAuth2 token acquired successfully"
        }
        
        return masked_response
    else:
        return {
            "success": False,
            "error": "Failed to acquire OAuth2 token. Check credentials and token URL.",
            "token_url": auth_config.get('token_url'),
            "auth_type": "oauth2"
        }

@router.post("/{app_id}/test-default-oauth", response_model=Dict[str, Any])
async def test_default_oauth_credentials(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test default OAuth2 credentials stored in application configuration"""
    # Verify application exists
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check access permissions (only admins can test default credentials)
    user_role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if user_role_value != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test default OAuth credentials"
        )
    
    if app.auth_type != "oauth2":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for OAuth2 applications"
        )
    
    # Get auth config
    auth_config = deserialize_json_field(app.auth_config) if app.auth_config else {}
    default_creds = auth_config.get('default_credentials', {})
    
    if not default_creds or not default_creds.get('client_id') or not default_creds.get('client_secret'):
        return {
            "success": False,
            "error": "No default OAuth2 credentials configured for this application",
            "auth_type": "oauth2"
        }
    
    # For OAuth2 apps that use authorization_code grant (like Google), we can't test credentials directly
    # We can only verify that they are formatted correctly
    grant_types = auth_config.get('grant_types', [])
    uses_auth_code = 'authorization_code' in grant_types or auth_config.get('grant_type') == 'authorization_code'
    
    # Special handling for Google OAuth2
    if app.app_name == "Google Sheets" or uses_auth_code:
        # Validate credential format
        client_id = default_creds['client_id']
        client_secret = default_creds['client_secret']
        
        # Basic validation for Google OAuth2 credentials
        if '.apps.googleusercontent.com' in client_id:
            if not client_id.endswith('.apps.googleusercontent.com'):
                return {
                    "success": False,
                    "error": "Invalid Google Client ID format. Should end with .apps.googleusercontent.com",
                    "auth_type": "oauth2"
                }
            if not client_secret.startswith('GOCSPX-'):
                return {
                    "success": False,
                    "error": "Invalid Google Client Secret format. Should start with GOCSPX-",
                    "auth_type": "oauth2"
                }
        
        return {
            "success": True,
            "message": "OAuth2 credentials are properly formatted. User authorization required for token access.",
            "auth_type": "oauth2",
            "grant_type": "authorization_code",
            "note": "These credentials can only be fully tested when a user authorizes access."
        }
    
    # For other OAuth2 apps that support client_credentials grant
    from services.oauth2_manager import oauth2_manager
    
    try:
        token_data = await oauth2_manager._request_new_token(
            auth_config=auth_config,
            client_id=default_creds['client_id'],
            client_secret=default_creds['client_secret'],
            scope=auth_config.get('scope')
        )
        
        if token_data:
            return {
                "success": True,
                "message": "Default OAuth2 credentials are valid",
                "token_type": token_data.get('token_type', 'Bearer'),
                "expires_in": token_data.get('expires_in'),
                "scope": token_data.get('scope'),
                "auth_type": "oauth2"
            }
        else:
            return {
                "success": False,
                "error": "Failed to acquire token with default credentials",
                "auth_type": "oauth2"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Token acquisition failed: {str(e)}",
            "auth_type": "oauth2"
        }

# Test Connection Request Model
class TestConnectionRequest(BaseModel):
    base_url: str = Field(..., description="Base URL for the application API")
    test_endpoint: Optional[str] = Field(default="", description="Test endpoint relative to base URL (optional for email/database connections)")
    auth_type: AuthTypeEnum = Field(..., description="Authentication type")
    auth_credentials: Optional[Dict[str, Any]] = Field(None, description="Authentication credentials")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    headers: Optional[Dict[str, str]] = None
    timeout: int = Field(default=10, ge=1, le=60)
    subscription_id: Optional[str] = Field(None, description="Subscription ID to use stored credentials")

def _extract_api_error_text(body: Any) -> Optional[str]:
    """Pull a human-readable error out of a provider's error response body."""
    if isinstance(body, str):
        text = body.strip()
        return text[:300] if text and not text.lstrip().startswith('<') else None
    if not isinstance(body, dict):
        return None

    parts = []
    for key in ('title', 'detail', 'message', 'error_description', 'reason'):
        value = body.get(key)
        if isinstance(value, str) and value.strip() and value.strip() not in parts:
            parts.append(value.strip())

    error = body.get('error')
    if isinstance(error, str) and error.strip() and error.strip() not in parts:
        parts.append(error.strip())
    elif isinstance(error, dict):
        nested = _extract_api_error_text(error)
        if nested:
            parts.append(nested)

    errors = body.get('errors')
    if isinstance(errors, list):
        for item in errors[:3]:
            nested = _extract_api_error_text(item) if isinstance(item, dict) else (item if isinstance(item, str) else None)
            if nested and nested not in parts:
                parts.append(nested)

    return ' — '.join(parts)[:500] if parts else None


def _describe_test_connection_failure(status_code: int, body: Any, url: str, method: str) -> str:
    """Build an actionable message for a test request that came back with an HTTP error."""
    hints = {
        400: "The request was rejected. Check the test endpoint and any required parameters.",
        401: "The credentials were not accepted. Check that the key/token is complete, current (not regenerated since), and that the header name and prefix are right.",
        403: "The credentials were accepted but lack access to this endpoint. Check the key's permissions, plan or project access.",
        404: "The test endpoint was not found. Check the Base URL and Test Endpoint.",
        405: "The test endpoint does not accept this method. Set a Test Endpoint that answers GET.",
        429: "Rate limit or usage cap reached. Wait and try again, or check your plan's usage.",
    }
    hint = hints.get(status_code)
    if not hint and status_code >= 500:
        hint = "The provider returned a server error. Try again later."

    lines = [f"HTTP {status_code} from {method} {url}"]
    detail = _extract_api_error_text(body)
    if detail:
        lines.append(f"Provider says: {detail}")
    if hint:
        lines.append(hint)
    return '\n'.join(lines)


@router.post("/test-connection", response_model=Dict[str, Any])
async def test_connection(
    request: TestConnectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test connection to an external application API with provided credentials"""
    import httpx
    import base64
    
    # Initialize subscription variable
    subscription = None
    
    # If subscription_id is provided, fetch and use stored credentials
    if request.subscription_id:
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.subscription_id == request.subscription_id,
            ApplicationSubscription.tenant_id == current_user.tenant_id
        ).options(joinedload(ApplicationSubscription.application)).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        # Deserialize JSON fields for SQLite
        if settings.database_url.startswith("sqlite"):
            subscription.auth_credentials = deserialize_json_field(subscription.auth_credentials)
            subscription.subscription_config = deserialize_json_field(subscription.subscription_config)
        
        # Use base_url from subscription config if available
        if subscription.subscription_config and isinstance(subscription.subscription_config, dict):
            sub_base_url = subscription.subscription_config.get('base_url')
            if sub_base_url:
                request.base_url = sub_base_url
        
        # Decrypt stored credentials
        if subscription.auth_credentials:
            try:
                decrypted_credentials = decrypt_credentials(subscription.auth_credentials)
                if decrypted_credentials:
                    request.auth_credentials = decrypted_credentials
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No valid credentials found in subscription"
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to decrypt stored credentials: {str(e)}"
                )
    
    # Validate and encrypt credentials if provided
    validated_credentials = None
    if request.auth_credentials and request.auth_type != AuthTypeEnum.NONE:
        try:
            validated_credentials = validate_credentials(request.auth_type, request.auth_credentials)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid authentication credentials: {str(e)}"
            )
    
    # Check if this is a database connection by URL pattern
    is_database_connection = request.base_url.startswith(('postgresql://', 'postgres://', 'mysql://', 'oracle://', 'sqlserver://', 'sqlite://', 'grpc://', 'grpc+tls://'))
    
    # Check if this is an email connection by URL pattern
    is_email_connection = request.base_url.startswith(('smtp://', 'smtps://', 'smtp-plain://', 'pop3://', 'pop3s://', 'imap://', 'imaps://'))

    # Check if this is an MQTT broker connection by URL pattern
    is_mqtt_connection = request.base_url.startswith(('mqtt://', 'mqtts://'))

    # If we have a subscription_id, check the application category or type
    if request.subscription_id and subscription and subscription.application:
        if subscription.application.category == 'Database':
            is_database_connection = True
        elif hasattr(subscription.application, 'app_type') and subscription.application.app_type == 'email':
            is_email_connection = True
        elif hasattr(subscription.application, 'app_type') and subscription.application.app_type == 'mqtt':
            is_mqtt_connection = True

    if is_mqtt_connection:
        # Test MQTT broker connection: attempt a real CONNECT and wait for CONNACK
        from services.mqtt_listener_service import parse_broker_url

        parsed_broker = parse_broker_url(request.base_url)
        if not parsed_broker:
            return {
                "success": False,
                "error": f"Invalid MQTT broker URL '{request.base_url}'. Expected mqtt://host:port or mqtts://host:port"
            }
        mqtt_host, mqtt_port, mqtt_tls = parsed_broker

        creds = validated_credentials or request.auth_credentials or {}
        mqtt_username = creds.get('username')
        mqtt_password = creds.get('password')

        def test_mqtt_connection():
            import paho.mqtt.client as mqtt_client
            from paho.mqtt.enums import CallbackAPIVersion
            import threading

            result = {'reason_code': None}
            connack = threading.Event()

            def on_connect(client, userdata, flags, reason_code, properties):
                result['reason_code'] = reason_code
                connack.set()

            client = mqtt_client.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id='ioflow-test-connection',
                clean_session=True,
            )
            if mqtt_username:
                client.username_pw_set(mqtt_username, mqtt_password)
            if mqtt_tls:
                client.tls_set()
            client.on_connect = on_connect

            try:
                client.connect(mqtt_host, mqtt_port, keepalive=10)
                client.loop_start()
                if not connack.wait(timeout=request.timeout):
                    return False, f"Timed out after {request.timeout}s waiting for broker response"
                rc = result['reason_code']
                is_ok = (rc == 0) if isinstance(rc, int) else (getattr(rc, 'value', -1) == 0)
                if is_ok:
                    return True, f"Connected and authenticated to MQTT broker at {mqtt_host}:{mqtt_port}"
                return False, f"Broker refused connection: {rc} (check username/password)"
            except Exception as e:
                return False, f"Could not reach broker {mqtt_host}:{mqtt_port} — {str(e)}"
            finally:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception:
                    pass

        loop = asyncio.get_event_loop()
        mqtt_success, mqtt_message = await loop.run_in_executor(None, test_mqtt_connection)

        if mqtt_success:
            return {
                "success": True,
                "message": mqtt_message,
                "connection_type": "mqtt",
                "tls": mqtt_tls,
                "connection_url": f"{mqtt_host}:{mqtt_port}"
            }
        else:
            return {
                "success": False,
                "error": f"MQTT connection failed: {mqtt_message}",
                "connection_type": "mqtt",
                "tls": mqtt_tls,
                "connection_url": f"{mqtt_host}:{mqtt_port}"
            }
    
    # Validate base URL based on connection type
    if is_database_connection:
        # For database connections, test the connection differently
        if not request.base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database connection URL is required"
            )
        
        # Test database connection
        try:
            # Get database type from auth_config or URL
            database_type = 'postgresql'  # default
            if request.auth_config and 'database_type' in request.auth_config:
                database_type = request.auth_config['database_type']
            elif request.base_url.startswith(('postgresql://', 'postgres://')):
                database_type = 'postgresql'
            elif request.base_url.startswith('mysql://'):
                database_type = 'mysql'
            elif request.base_url.startswith('oracle://'):
                database_type = 'oracle'
            elif request.base_url.startswith('sqlserver://'):
                database_type = 'sqlserver'
            elif request.base_url.startswith('sqlite://'):
                database_type = 'sqlite'
            elif request.base_url.startswith(('grpc://', 'grpc+tls://')):
                # For Arrow Flight connections
                database_type = 'arrow_flight'
            
            # Parse connection string
            from urllib.parse import urlparse
            parsed = urlparse(request.base_url)
            
            # Get credentials
            creds = validated_credentials or request.auth_credentials or {}
            username = creds.get('username') or parsed.username
            password = creds.get('password') or parsed.password
            
            # Test connection directly without pool
            logger.info(f"Testing {database_type} connection to {parsed.hostname}:{parsed.port or 5432}")
            
            # Run synchronous database connection in thread pool
            loop = asyncio.get_event_loop()
            
            def test_db_connection():
                nonlocal username, password
                conn = None
                try:
                    if database_type == 'postgresql' and HAS_POSTGRES:
                        import psycopg2
                        conn = psycopg2.connect(
                            host=parsed.hostname,
                            port=parsed.port or 5432,
                            database=parsed.path.lstrip('/'),
                            user=username,
                            password=password
                        )
                        cursor = conn.cursor()
                        cursor.execute("SELECT version()")
                        result = cursor.fetchone()
                        cursor.close()
                        return True, str(result[0] if result else "Unknown")
                    
                    elif database_type == 'mysql' and HAS_MYSQL:
                        import mysql.connector
                        conn = mysql.connector.connect(
                            host=parsed.hostname,
                            port=parsed.port or 3306,
                            database=parsed.path.lstrip('/'),
                            user=username,
                            password=password
                        )
                        cursor = conn.cursor()
                        cursor.execute("SELECT VERSION()")
                        result = cursor.fetchone()
                        cursor.close()
                        return True, str(result[0] if result else "Unknown")
                    
                    elif database_type == 'sqlite':
                        import sqlite3
                        db_path = parsed.path or ':memory:'
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT sqlite_version()")
                        result = cursor.fetchone()
                        cursor.close()
                        return True, str(result[0] if result else "Unknown")
                    
                    elif database_type == 'oracle' and HAS_ORACLE:
                        # Import Oracle driver
                        try:
                            import oracledb as oracle_driver
                            ORACLE_DRIVER = 'oracledb'
                        except ImportError:
                            import cx_Oracle as oracle_driver
                            ORACLE_DRIVER = 'cx_Oracle'
                        
                        # Initialize thick mode if using oracledb
                        if ORACLE_DRIVER == 'oracledb' and hasattr(oracle_driver, 'is_thin_mode'):
                            if oracle_driver.is_thin_mode():
                                try:
                                    # Try to initialize thick mode using LD_LIBRARY_PATH
                                    import os
                                    lib_path = os.environ.get('LD_LIBRARY_PATH', '').split(':')[0] if os.environ.get('LD_LIBRARY_PATH') else None
                                    if lib_path and os.path.exists(lib_path):
                                        oracle_driver.init_oracle_client(lib_dir=lib_path)
                                    else:
                                        # Try without lib_dir (let oracledb auto-detect)
                                        oracle_driver.init_oracle_client()
                                except:
                                    pass  # Continue with thin mode
                        
                        # Parse connection parameters
                        service_or_sid = parsed.path.lstrip('/')
                        
                        # Try connection string format first
                        connection_string = f"{username}/{password}@{parsed.hostname}:{parsed.port or 1521}/{service_or_sid}"
                        
                        try:
                            conn = oracle_driver.connect(connection_string)
                        except:
                            # Fall back to DSN format
                            dsn = oracle_driver.makedsn(
                                parsed.hostname,
                                parsed.port or 1521,
                                service_name=service_or_sid
                            )
                            conn = oracle_driver.connect(
                                user=username,
                                password=password,
                                dsn=dsn
                            )
                        
                        cursor = conn.cursor()
                        cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
                        result = cursor.fetchone()
                        cursor.close()
                        return True, str(result[0] if result else "Oracle Database")

                    elif request.base_url.startswith(('grpc://', 'grpc+tls://')):
                        # Test Arrow Flight connection
                        try:
                            import pyarrow.flight as flight
                            import pyarrow as pa
                        except ImportError:
                            return False, "Arrow Flight support not available. Install pyarrow: pip install pyarrow"

                        try:
                            # Parse endpoint for scheme and location (similar to ArrowFlightConnectionPool)
                            if request.base_url.startswith('grpc+tls://'):
                                location = request.base_url.replace('grpc+tls://', '')
                                client_url = f"grpc+tls://{location}"
                            elif request.base_url.startswith('grpc://'):
                                location = request.base_url.replace('grpc://', '')
                                client_url = f"grpc+tcp://{location}"
                            else:
                                client_url = request.base_url

                            # Create flight client
                            client = flight.FlightClient(client_url)

                            # Prepare authentication headers (same as ArrowFlightConnectionPool)
                            headers = []
                            if validated_credentials or request.auth_credentials:
                                creds = validated_credentials or request.auth_credentials
                                auth_method = request.auth_config.get('auth_method', 'pat_token') if request.auth_config else 'pat_token'

                                if (auth_method == 'pat_token' and creds.get('pat_token')) or (auth_method != 'username_password' and creds.get('pat_token')):
                                    # Personal Access Token authentication (e.g., Dremio Cloud)
                                    token = creds.get('pat_token', '')
                                    if token:
                                        headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))

                                elif creds.get('username') and creds.get('password'):
                                    # Basic authentication fallback
                                    username = creds.get('username', '')
                                    password = creds.get('password', '')
                                    if username and password:
                                        import base64
                                        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                                        headers.append((b"authorization", f"Basic {credentials}".encode("utf-8")))

                            # Create flight call options with headers
                            options = flight.FlightCallOptions(headers=headers) if headers else None

                            # Try to list flights to test connection
                            try:
                                if options:
                                    flights = list(client.list_flights(options))
                                else:
                                    flights = list(client.list_flights())
                                return True, f"Arrow Flight connection successful"
                            except flight.FlightUnauthenticatedError:
                                return False, "Authentication failed. Check your credentials."
                            except flight.FlightUnauthorizedError:
                                return False, "Authorization failed. Check your permissions."
                            except Exception as e:
                                # If list_flights fails but connection worked, it's still a success
                                if "unauthenticated" in str(e).lower():
                                    return False, "Authentication failed. Check your credentials."
                                elif "unauthorized" in str(e).lower():
                                    return False, "Authorization failed. Check your permissions."
                                else:
                                    # Connection might be successful but server doesn't support list_flights
                                    return True, f"Arrow Flight connection successful"

                        except Exception as e:
                            error_msg = str(e)
                            if "not running on tls" in error_msg.lower():
                                # Suggest the correct URL scheme
                                if request.base_url.startswith('grpc+tls://'):
                                    suggested_url = request.base_url.replace('grpc+tls://', 'grpc://')
                                    return False, f"TLS not enabled on server. Try using: {suggested_url}"
                                else:
                                    return False, f"Connection failed: {error_msg}"
                            else:
                                return False, f"Arrow Flight connection failed: {error_msg}"

                    else:
                        return False, f"Database type {database_type} not supported or driver not installed"
                    
                except Exception as e:
                    logger.error(f"Database connection test failed: {str(e)}")
                    return False, str(e)
                finally:
                    if conn:
                        try:
                            conn.close()
                        except:
                            pass
            
            # Check if drivers are available
            HAS_POSTGRES = False
            HAS_MYSQL = False
            HAS_ORACLE = False
            try:
                import psycopg2
                HAS_POSTGRES = True
            except:
                pass
            try:
                import mysql.connector
                HAS_MYSQL = True
            except:
                pass
            try:
                import oracledb
                HAS_ORACLE = True
            except:
                try:
                    import cx_Oracle
                    HAS_ORACLE = True
                except:
                    pass
            
            success, message = await loop.run_in_executor(None, test_db_connection)
            
            if success:
                return {
                    "success": True,
                    "message": "Database connection successful",
                    "database_type": database_type,
                    "version": message,
                    "connection_url": request.base_url.split('@')[-1] if '@' in request.base_url else request.base_url  # Hide credentials
                }
            else:
                return {
                    "success": False,
                    "error": f"Database connection failed: {message}",
                    "database_type": database_type,
                    "connection_url": request.base_url.split('@')[-1] if '@' in request.base_url else request.base_url
                }
                
        except Exception as e:
            logger.error(f"Database connection test error: {str(e)}")
            return {
                "success": False,
                "error": f"Database connection test error: {str(e)}",
                "database_type": database_type if 'database_type' in locals() else 'unknown',
                "connection_url": request.base_url.split('@')[-1] if '@' in request.base_url else request.base_url
            }
    elif is_email_connection:
        # Test email connection
        if not request.base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email server URL is required"
            )
        
        try:
            from urllib.parse import urlparse
            import smtplib
            import poplib
            import imaplib
            import ssl
            import socket
            
            parsed = urlparse(request.base_url)
            protocol = parsed.scheme.lower()
            host = parsed.hostname
            port = parsed.port
            
            # Get credentials
            username = validated_credentials.get('username') if validated_credentials else None
            password = validated_credentials.get('password') if validated_credentials else None
            
            if not username or not password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username and password are required for email server connection"
                )
            
            success = False
            message = ""
            server_info = {}
            
            if protocol in ['smtp', 'smtps', 'smtp-plain']:
                # Test SMTP connection
                # Determine default port and TLS/SSL settings
                if protocol == 'smtps':
                    default_port = 465
                    use_ssl = True
                    use_tls = False
                elif protocol == 'smtp-plain':
                    default_port = 25
                    use_ssl = False
                    use_tls = False
                else:  # smtp
                    default_port = 587
                    # Check if use_tls is explicitly disabled in auth_config
                    use_ssl = request.auth_config.get('use_ssl', False) if request.auth_config else False
                    use_tls = request.auth_config.get('use_tls', True) if request.auth_config else True

                port = port or default_port

                try:
                    if use_ssl:
                        # SSL connection (typically port 465)
                        context = ssl.create_default_context()
                        server = smtplib.SMTP_SSL(host, port, context=context, timeout=10)
                        logger.info(f"Testing SMTP connection with SSL to {host}:{port}")
                    else:
                        # Plain or TLS connection
                        server = smtplib.SMTP(host, port, timeout=10)
                        if use_tls:
                            context = ssl.create_default_context()
                            server.starttls(context=context)
                            logger.info(f"Testing SMTP connection with STARTTLS to {host}:{port}")
                        else:
                            logger.info(f"Testing plain SMTP connection (no encryption) to {host}:{port}")

                    # Try to login
                    server.login(username, password)
                    server.quit()

                    success = True
                    encryption = "SSL" if use_ssl else ("STARTTLS" if use_tls else "None")
                    message = f"SMTP connection successful to {host}:{port} (Encryption: {encryption})"
                    server_info = {
                        "protocol": protocol.upper(),
                        "host": host,
                        "port": port,
                        "ssl": use_ssl,
                        "tls": use_tls,
                        "encryption": encryption
                    }
                except smtplib.SMTPAuthenticationError as e:
                    success = False
                    error_code, error_msg = e.args
                    error_str = error_msg.decode() if isinstance(error_msg, bytes) else str(error_msg)
                    
                    # Parse specific Gmail/common SMTP errors
                    if '5.7.8' in error_str and 'Username and Password not accepted' in error_str:
                        if 'gmail' in host.lower():
                            # Check for specific error patterns
                            if 'Please log in via your web browser' in error_str:
                                message = (
                                    "Gmail requires browser verification. To fix:\n"
                                    "1. Visit: https://accounts.google.com/DisplayUnlockCaptcha\n"
                                    "2. Click 'Continue' to allow access\n"
                                    "3. Try connecting again within 10 minutes\n"
                                    "4. Check for security alerts in your Gmail"
                                )
                            else:
                                message = (
                                    "Gmail authentication failed. Since May 2022, Gmail requires either:\n"
                                    "\n"
                                    "Option 1: Use an App Password (Recommended)\n"
                                    "1. Enable 2-Step Verification: https://myaccount.google.com/signinoptions/two-step-verification\n"
                                    "2. Generate App Password: https://myaccount.google.com/apppasswords\n"
                                    "3. Use the 16-character app password instead of your regular password\n"
                                    "\n"
                                    "Option 2: If Mac Mail works with your password\n"
                                    "1. Your account might have special settings (Google Workspace/legacy settings)\n"
                                    "2. Try unlocking CAPTCHA: https://accounts.google.com/DisplayUnlockCaptcha\n"
                                    "3. Check security notifications: https://myaccount.google.com/notifications\n"
                                    "4. Ensure you're using your full email address as username"
                                )
                        else:
                            message = f"Authentication failed: Invalid username or password. Server response: {error_str[:200]}"
                    elif 'Application-specific password required' in error_str:
                        message = (
                            "Gmail requires an app-specific password. To fix this:\n"
                            "1. Enable 2-Step Verification in your Google Account\n"
                            "2. Go to Security → App passwords\n"
                            "3. Generate a password for 'Mail'\n"
                            "4. Use the generated password instead of your regular password"
                        )
                    else:
                        message = f"SMTP authentication failed: {error_str[:300]}"
                        
                except smtplib.SMTPConnectError as e:
                    success = False
                    message = f"Failed to connect to SMTP server {host}:{port}. Please check the server address and port."
                    
                except smtplib.SMTPServerDisconnected as e:
                    success = False
                    message = f"SMTP server {host} unexpectedly disconnected. This might be a firewall or network issue."
                    
                except socket.timeout:
                    success = False
                    message = f"Connection to {host}:{port} timed out. Please check if the server and port are correct."
                    
                except socket.gaierror as e:
                    success = False
                    message = f"Cannot resolve hostname '{host}'. Please check if the server address is correct."
                    
                except ConnectionRefusedError:
                    success = False
                    message = f"Connection refused by {host}:{port}. The server might be down or the port might be wrong."
                    
                except ssl.SSLError as e:
                    success = False
                    error_str = str(e)
                    if 'WRONG_VERSION_NUMBER' in error_str:
                        if protocol == 'smtps' and port == 587:
                            message = (
                                f"SSL/TLS protocol mismatch on port {port}.\n"
                                f"Port 587 typically uses STARTTLS (not direct SSL).\n"
                                f"Try using: smtp://{host}:587 instead of smtps://{host}:587\n"
                                f"Or use: smtps://{host}:465 for direct SSL connection"
                            )
                        elif protocol == 'smtp' and port == 465:
                            message = (
                                f"SSL/TLS protocol mismatch on port {port}.\n"
                                f"Port 465 typically uses direct SSL (not STARTTLS).\n"
                                f"Try using: smtps://{host}:465 instead of smtp://{host}:465\n"
                                f"Or use: smtp://{host}:587 for STARTTLS connection"
                            )
                        else:
                            message = (
                                f"SSL/TLS protocol mismatch detected.\n"
                                f"Current: {protocol}://{host}:{port}\n"
                                f"Common SMTP configurations:\n"
                                f"• smtp://{host}:587 (STARTTLS)\n"
                                f"• smtp://{host}:25 (Plain/STARTTLS)\n"
                                f"• smtps://{host}:465 (Direct SSL)"
                            )
                    elif 'CERTIFICATE_VERIFY_FAILED' in error_str:
                        message = (
                            f"SSL certificate verification failed for {host}.\n"
                            f"This might happen with self-signed certificates.\n"
                            f"Please verify the server's SSL certificate is valid."
                        )
                    else:
                        message = f"SSL/TLS error: {error_str}. Check your protocol and port settings."
                    
                except Exception as e:
                    success = False
                    error_str = str(e)
                    if 'STARTTLS' in error_str:
                        message = (
                            f"STARTTLS error on {host}:{port}.\n"
                            f"If using port 587, use: smtp://{host}:587\n"
                            f"If using port 465, use: smtps://{host}:465"
                        )
                    elif '[SSL: WRONG_VERSION_NUMBER]' in error_str or 'wrong version number' in error_str.lower():
                        # Catch SSL errors that might not be caught by ssl.SSLError
                        if port == 587:
                            message = (
                                f"SSL/TLS protocol mismatch on port {port}.\n"
                                f"Port 587 uses STARTTLS, not direct SSL.\n"
                                f"Use: smtp://{host}:587 (not smtps://)"
                            )
                        elif port == 465:
                            message = (
                                f"SSL/TLS protocol mismatch on port {port}.\n"
                                f"Port 465 uses direct SSL, not STARTTLS.\n"
                                f"Use: smtps://{host}:465 (not smtp://)"
                            )
                        else:
                            message = (
                                f"SSL/TLS protocol mismatch.\n"
                                f"Try these common configurations:\n"
                                f"• smtp://{host}:587 (STARTTLS)\n"
                                f"• smtps://{host}:465 (Direct SSL)"
                            )
                    else:
                        message = f"SMTP connection failed: {error_str[:300]}"
                    
            elif protocol in ['pop3', 'pop3s']:
                # Test POP3 connection
                default_port = 995 if protocol == 'pop3s' else 110
                port = port or default_port
                
                try:
                    if protocol == 'pop3s':
                        # SSL connection
                        server = poplib.POP3_SSL(host, port, timeout=10)
                    else:
                        # Plain connection
                        server = poplib.POP3(host, port, timeout=10)
                    
                    # Try to login
                    server.user(username)
                    server.pass_(password)
                    
                    # Get mailbox stats
                    num_messages = len(server.list()[1])
                    server.quit()
                    
                    success = True
                    message = f"POP3 connection successful to {host}:{port} ({num_messages} messages)"
                    server_info = {
                        "protocol": protocol.upper(),
                        "host": host,
                        "port": port,
                        "ssl": protocol == 'pop3s',
                        "message_count": num_messages
                    }
                except poplib.error_proto as e:
                    success = False
                    error_str = str(e)
                    if 'AUTH' in error_str and 'Username and password not accepted' in error_str:
                        if 'gmail' in host.lower():
                            message = (
                                "Gmail POP3 authentication failed. To fix this:\n"
                                "1. Enable POP3 in Gmail settings (Settings → Forwarding and POP/IMAP)\n"
                                "2. Use an App Password instead of your regular password\n"
                                "3. Go to Google Account → Security → 2-Step Verification → App passwords\n"
                                "4. Generate an app password for 'Mail' and use that"
                            )
                        else:
                            message = f"POP3 authentication failed: {error_str}"
                    else:
                        message = f"POP3 protocol error: {error_str}"
                        
                except socket.timeout:
                    success = False
                    message = f"Connection to {host}:{port} timed out. Please check if the server and port are correct."
                    
                except socket.gaierror:
                    success = False
                    message = f"Cannot resolve hostname '{host}'. Please check if the server address is correct."
                    
                except ConnectionRefusedError:
                    success = False
                    message = f"Connection refused by {host}:{port}. The server might be down or the port might be wrong."
                    
                except Exception as e:
                    success = False
                    message = f"POP3 connection failed: {str(e)[:300]}"
                    
            elif protocol in ['imap', 'imaps']:
                # Test IMAP connection
                default_port = 993 if protocol == 'imaps' else 143
                port = port or default_port
                
                try:
                    if protocol == 'imaps':
                        # SSL connection
                        server = imaplib.IMAP4_SSL(host, port, timeout=10)
                    else:
                        # Plain connection
                        server = imaplib.IMAP4(host, port, timeout=10)
                    
                    # Try to login
                    server.login(username, password)
                    
                    # Get folder list - wrap in try/except to handle potential errors
                    folder_count = 0
                    try:
                        list_status, folders = server.list()
                        folder_count = len(folders) if list_status == 'OK' else 0
                    except:
                        # If list fails, connection was still successful
                        folder_count = 0
                    
                    server.logout()
                    
                    success = True
                    message = f"IMAP connection successful to {host}:{port} ({folder_count} folders)"
                    server_info = {
                        "protocol": protocol.upper(),
                        "host": host,
                        "port": port,
                        "ssl": protocol == 'imaps',
                        "folder_count": folder_count
                    }
                except imaplib.IMAP4.error as e:
                    success = False
                    error_str = str(e)
                    if 'AUTHENTICATIONFAILED' in error_str or 'Invalid credentials' in error_str:
                        if 'gmail' in host.lower():
                            message = (
                                "Gmail IMAP authentication failed. To fix this:\n"
                                "1. Enable IMAP in Gmail settings (Settings → Forwarding and POP/IMAP)\n"
                                "2. Use an App Password instead of your regular password\n"
                                "3. Go to Google Account → Security → 2-Step Verification → App passwords\n"
                                "4. Generate an app password for 'Mail' and use that\n"
                                "5. If you see 'ALERT', you may need to allow less secure apps (not recommended)"
                            )
                        else:
                            message = f"IMAP authentication failed: {error_str}"
                    elif 'ALERT' in error_str:
                        message = f"IMAP server alert: {error_str}. This often means the server requires special authentication settings."
                    else:
                        message = f"IMAP error: {error_str}"
                        
                except socket.timeout:
                    success = False
                    message = f"Connection to {host}:{port} timed out. Please check if the server and port are correct."
                    
                except socket.gaierror:
                    success = False
                    message = f"Cannot resolve hostname '{host}'. Please check if the server address is correct."
                    
                except ConnectionRefusedError:
                    success = False
                    message = f"Connection refused by {host}:{port}. The server might be down or the port might be wrong."
                    
                except ssl.SSLError as e:
                    success = False
                    message = f"SSL/TLS error: {str(e)}. Try using imap:// instead of imaps:// or check your SSL settings."
                    
                except Exception as e:
                    success = False
                    error_str = str(e)
                    if 'bytes' in error_str and 'decode' in error_str:
                        # Handle bytes decoding errors
                        message = "IMAP server response could not be decoded. The server might be using an incompatible protocol."
                    else:
                        message = f"IMAP connection failed: {error_str[:300]}"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported email protocol: {protocol}"
                )
            
            if success:
                return {
                    "success": success,
                    "message": message,
                    "server_info": server_info,
                    "connection_url": f"{protocol}://{host}:{port}"
                }
            else:
                return {
                    "success": success,
                    "error": message,  # Use 'error' key for failures to match frontend expectations
                    "connection_url": f"{protocol}://{host}:{port}"
                }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Email connection test error: {str(e)}")
            return {
                "success": False,
                "error": f"Email connection test error: {str(e)}",
                "connection_url": request.base_url
            }
    # Check if this is a file protocol connection
    elif request.base_url.startswith(('file://', 'ftp://', 'ftps://', 'sftp://', 'ssh://', 'smb://', 'cifs://', 'nfs://')):
        # Handle file protocol connections
        logger.info(f"Testing file protocol connection: {request.base_url}")
        
        try:
            from services.file_protocol_executor import FileProtocolExecutor
            
            # Create executor with credentials
            service_config = {
                'base_url': request.base_url
            }
            
            # Use validated credentials or raw credentials
            auth_creds = validated_credentials or request.auth_credentials or {}
            
            executor = FileProtocolExecutor(
                service_config=service_config,
                auth_credentials=auth_creds
            )
            
            # Perform a simple test operation
            test_params = {
                'operation': 'list',  # List files to test connection
                'path': '/'  # Root directory
            }
            
            # Execute test
            result = await executor.execute(test_params, {})
            
            if result.get('success') or not result.get('error'):
                # Connection successful
                file_count = result.get('count', 0)
                return {
                    "success": True,
                    "message": f"File system connection successful. Found {file_count} items in root directory.",
                    "protocol": request.base_url.split('://')[0],
                    "connection_url": request.base_url
                }
            else:
                # Connection failed
                error_msg = result.get('message', 'Unknown error')
                
                # Provide helpful error messages
                if 'paramiko' in error_msg.lower():
                    error_msg += "\n\nNote: SFTP requires the 'paramiko' library. Install it with: pip install paramiko"
                elif 'authentication' in error_msg.lower():
                    error_msg += "\n\nCheck your username and password, or use SSH key authentication for SFTP."
                elif 'connection' in error_msg.lower() or 'refused' in error_msg.lower():
                    error_msg += "\n\nCheck that the server hostname and port are correct, and the server is accessible."
                
                return {
                    "success": False,
                    "error": error_msg,
                    "protocol": request.base_url.split('://')[0],
                    "connection_url": request.base_url
                }
                
        except ImportError as e:
            return {
                "success": False,
                "error": f"File protocol support not available: {str(e)}",
                "connection_url": request.base_url
            }
        except Exception as e:
            logger.error(f"File protocol connection test error: {str(e)}")
            return {
                "success": False,
                "error": f"File protocol connection test failed: {str(e)}",
                "connection_url": request.base_url
            }
    else:
        # Regular HTTP/HTTPS validation
        if not request.base_url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base URL must start with a valid protocol (http://, https://, file://, ftp://, sftp://, etc.)"
            )
    
    # Build test URL
    # If test_endpoint is an absolute URL, use it directly
    if request.test_endpoint and request.test_endpoint.startswith(('http://', 'https://')):
        test_url = request.test_endpoint
    elif request.test_endpoint:
        # Otherwise, append to base URL if test_endpoint is provided
        test_url = request.base_url.rstrip('/') + '/' + request.test_endpoint.lstrip('/')
    else:
        # No test endpoint provided, use base URL
        test_url = request.base_url.rstrip('/')
    
    # Prepare headers
    request_headers = request.headers or {}
    
    # Add authentication headers if needed
    if request.auth_type != AuthTypeEnum.NONE and validated_credentials:
        try:
            auth_headers = {}
            
            # API Key authentication
            if request.auth_type == AuthTypeEnum.API_KEY and 'api_key' in validated_credentials:
                auth_config = request.auth_config or {}
                header_name = auth_config.get('header_name', 'Authorization')
                header_prefix = auth_config.get('header_prefix', 'Bearer')
                
                if header_prefix:
                    auth_headers[header_name] = f"{header_prefix} {validated_credentials['api_key']}"
                else:
                    auth_headers[header_name] = validated_credentials['api_key']
            
            # Basic authentication
            elif request.auth_type == AuthTypeEnum.BASIC and 'username' in validated_credentials and 'password' in validated_credentials:
                credentials = f"{validated_credentials['username']}:{validated_credentials['password']}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                auth_headers['Authorization'] = f"Basic {encoded_credentials}"
            
            # OAuth2 authentication
            elif request.auth_type == AuthTypeEnum.OAUTH2:
                # For OAuth2, we might need to get an access token first
                # For now, we'll assume the user provides an access token directly
                if 'access_token' in validated_credentials:
                    token_type = validated_credentials.get('token_type', 'Bearer')
                    auth_headers['Authorization'] = f"{token_type} {validated_credentials['access_token']}"
                elif 'client_id' in validated_credentials and 'client_secret' in validated_credentials:
                    # Try to get access token using client credentials
                    auth_config = request.auth_config or {}
                    token_url = auth_config.get('token_url')
                    if token_url:
                        # Make a request to get access token
                        token_response = await httpx.AsyncClient().post(
                            token_url,
                            data={
                                'grant_type': 'client_credentials',
                                'client_id': validated_credentials['client_id'],
                                'client_secret': validated_credentials['client_secret']
                            }
                        )
                        if token_response.status_code == 200:
                            token_data = token_response.json()
                            access_token = token_data.get('access_token')
                            token_type = token_data.get('token_type', 'Bearer')
                            if access_token:
                                auth_headers['Authorization'] = f"{token_type} {access_token}"
            
            # Custom authentication
            elif request.auth_type == AuthTypeEnum.CUSTOM and 'headers' in validated_credentials:
                auth_headers.update(validated_credentials.get('headers', {}))
            
            request_headers.update(auth_headers)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to build auth headers: {str(e)}",
                "url": test_url,
                "method": request.method
            }
    
    # Make test request - try GET first, then POST if needed
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(request.timeout)) as client:
            # First try with the specified method (default is GET)
            response = await client.request(
                method=request.method,
                url=test_url,
                headers=request_headers
            )
            
            # If GET fails with 404 or 405, and we haven't explicitly set POST, try POST
            if (request.method == "GET" and 
                response.status_code in [404, 405] and 
                request.test_endpoint not in ['/', '']):
                
                logger.info(f"GET request failed with {response.status_code}, trying POST")
                
                # Try POST with the same headers
                post_headers = request_headers.copy()
                if 'Content-Type' not in post_headers:
                    post_headers['Content-Type'] = 'application/json'
                
                try:
                    post_response = await client.request(
                        method="POST",
                        url=test_url,
                        headers=post_headers,
                        json={}  # Empty JSON body for POST
                    )
                    
                    # If POST succeeds, use its response
                    if post_response.status_code < 400:
                        response = post_response
                        actual_method = "POST"
                    else:
                        actual_method = request.method
                except:
                    # If POST fails, stick with GET response
                    actual_method = request.method
            else:
                actual_method = request.method
            
            # Prepare response data
            response_data = {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "url": test_url,
                "method": actual_method,
                "response_headers": dict(response.headers),
                "auth_type": request.auth_type
            }
            
            # Add note if method was auto-switched
            if actual_method != request.method:
                response_data["note"] = f"Auto-switched from {request.method} to {actual_method} for successful connection"
            
            # Try to parse response body
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_data["response_body"] = response.json()
                else:
                    response_data["response_body"] = response.text[:1000]  # Limit text response
            except:
                response_data["response_body"] = "Unable to parse response body"

            if not response_data["success"]:
                response_data["error"] = _describe_test_connection_failure(
                    response.status_code, response_data.get("response_body"), test_url, actual_method
                )
                logger.warning(f"Test connection failed: {response_data['error']}")

            return response_data
            
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Request timed out after {request.timeout} seconds",
            "url": test_url,
            "method": request.method
        }
    except httpx.ConnectError as e:
        return {
            "success": False,
            "error": f"Connection failed: {str(e)}",
            "url": test_url,
            "method": request.method
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "url": test_url,
            "method": request.method
        }

@router.post("/subscriptions/{subscription_id}/regenerate-api-key", response_model=Dict[str, Any])
async def regenerate_subscription_api_key(
    subscription_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerate the invocation API key for a subscription"""
    _require_app_management_role(current_user)
    db_subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.subscription_id == subscription_id
    ).first()
    
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Verify ownership
    if db_subscription.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this subscription"
        )
    
    # Generate new API key
    new_api_key = f"ioflow_{secrets.token_urlsafe(32)}"
    
    # Update subscription
    db_subscription.invocation_api_key = new_api_key
    db_subscription.api_key_created_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_subscription)
    
    return {
        "subscription_id": subscription_id,
        "invocation_api_key": new_api_key,
        "api_key_created_at": db_subscription.api_key_created_at,
        "message": "API key regenerated successfully"
    }

@router.get("/events/check-endpoint-availability", response_model=Dict[str, Any])
async def check_endpoint_availability(
    endpoint: str = Query(..., description="The API endpoint to check"),
    exclude_event_id: Optional[str] = Query(None, description="Event ID to exclude from check"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if a custom API endpoint is available"""
    # Build query
    query = db.query(ApplicationEvent).filter(
        ApplicationEvent.api_endpoint == endpoint
    )
    
    # Exclude current event if provided (for editing)
    if exclude_event_id:
        query = query.filter(ApplicationEvent.event_id != exclude_event_id)
    
    existing = query.first()
    
    if existing:
        # Get the application name for context
        app = db.query(Application).filter(
            Application.app_id == existing.app_id
        ).first()
        
        return {
            "endpoint": endpoint,
            "available": False,
            "used_by": {
                "event_id": existing.event_id,
                "event_name": existing.event_name,
                "application_name": app.app_name if app else "Unknown"
            }
        }
    
    return {
        "endpoint": endpoint,
        "available": True,
        "message": "Endpoint is available"
    }

@router.put("/{app_id}/webhook-config", response_model=Dict[str, Any])
async def update_application_webhook_config(
    app_id: str,
    webhook_update: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update webhook configuration for an application"""
    _require_app_management_role(current_user)
    # Verify application exists
    app = db.query(Application).filter(Application.app_id == app_id).first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions - only admins can update webhook config for global apps
    if app.app_scope == "global" and get_user_role_string(current_user) != "INSTANCE_ADMIN":
        logger.warning(f"Webhook config update denied - User: {current_user.email}, Role: {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update webhook configuration for global applications"
        )
    
    user_role = get_user_role_string(current_user)
    if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this application"
        )
    
    # Extract webhook config
    new_webhook_config = webhook_update.get('webhook_config', {})
    
    logger.info(f"Updating webhook config for app {app_id}")
    logger.info(f"Received webhook_config: {new_webhook_config}")
    
    # Update application
    app.webhook_config = serialize_json_field(new_webhook_config)
    app.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(app)
    
    # Deserialize for response
    if settings.database_url.startswith("sqlite"):
        app.webhook_config = deserialize_json_field(app.webhook_config)
    
    return {
        "app_id": app_id,
        "app_name": app.app_name,
        "webhook_config": app.webhook_config,
        "updated_at": app.updated_at,
        "message": "Webhook configuration updated successfully"
    }

@router.post("/subscriptions/{subscription_id}/parameter-lookup", response_model=Dict[str, Any])
async def get_parameter_lookup_values(
    subscription_id: str,
    lookup_request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get parameter lookup values using the configured parameterLookup"""
    from services.service_executors import get_service_executor
    
    try:
        logger.info(f"Parameter lookup request for subscription {subscription_id}: {lookup_request}")
        
        # Get subscription with application and its services
        subscription = db.query(ApplicationSubscription).options(
            joinedload(ApplicationSubscription.application).joinedload(Application.app_services)
        ).filter(
            ApplicationSubscription.subscription_id == subscription_id,
            ApplicationSubscription.tenant_id == current_user.tenant_id,
            ApplicationSubscription.status.in_(["active", "trial"])
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found or access denied"
            )
        
        application = subscription.application
    
        # Extract the parameter lookup config
        parameter_name = lookup_request.get('parameter_name')
        parameter_lookup = lookup_request.get('parameter_lookup', {})
    
        if not parameter_lookup or parameter_lookup.get('type') != 'api_call':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parameter lookup configuration"
            )
    
        lookup_service_name = parameter_lookup.get('service')
        lookup_parameters = parameter_lookup.get('parameters', {})
        extract_path = parameter_lookup.get('extractPath', '')
        value_field = parameter_lookup.get('valueField', 'id')
        display_field = parameter_lookup.get('displayField', 'name')
    
        # Find the lookup service in the application's services
        lookup_service = None
        for service in application.app_services:
            if service.service_name == lookup_service_name:
                # Deserialize JSON fields for SQLite
                service_config = service.service_config
                if settings.database_url.startswith("sqlite") and isinstance(service_config, str):
                    service_config = json.loads(service_config) if service_config else {}
                
                # Use the service_config as the service definition for the executor
                lookup_service = {
                    'service_name': service.service_name,
                    'service_type': service.service_type,
                    'base_url': application.base_url,  # Add the application's base URL
                    **service_config  # Spread the service_config dictionary
                }
                break
        
        if not lookup_service:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lookup service '{lookup_service_name}' not found in application '{application.app_name}'"
            )
        
        try:
            # Deserialize and decrypt auth_credentials for SQLite
            auth_creds_to_decrypt = subscription.auth_credentials
            if settings.database_url.startswith("sqlite") and isinstance(auth_creds_to_decrypt, str):
                try:
                    auth_creds_to_decrypt = json.loads(auth_creds_to_decrypt) if auth_creds_to_decrypt else {}
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse auth_credentials: {auth_creds_to_decrypt}")
                    auth_creds_to_decrypt = {}
            
            # Decrypt the credentials before passing to service executor
            auth_credentials = decrypt_credentials(auth_creds_to_decrypt) if auth_creds_to_decrypt else {}
            logger.info(f"Decrypted auth credentials keys: {list(auth_credentials.keys()) if auth_credentials else 'None'}")
            
            # Deserialize auth_config for SQLite
            auth_config = application.auth_config
            if settings.database_url.startswith("sqlite") and isinstance(auth_config, str):
                auth_config = json.loads(auth_config) if auth_config else {}
            
            # Execute the lookup service
            executor = get_service_executor(
                lookup_service['service_type'],
                lookup_service,
                auth_credentials,
                subscription_id,
                auth_config
            )
            result = await executor.execute(lookup_parameters, {})
            
            # Log the actual API response for debugging
            logger.info(f"Google Drive API response: {json.dumps(result, indent=2)}")
            
            # Extract values based on extractPath
            # The service executor wraps the response in a 'data' object, so we need to extract from result.data first
            data = result.get('data', result) if isinstance(result, dict) else result
            if extract_path:
                for path_part in extract_path.split('.'):
                    if isinstance(data, dict):
                        data = data.get(path_part, [])
                    else:
                        data = []
                        break
            
            # Format for dropdown selection
            options = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        value = item.get(value_field, '')
                        display = item.get(display_field, value)
                        options.append({
                            'value': value,
                            'label': display,
                            'data': item  # Include full item data
                        })
            
            return {
                "parameter_name": parameter_name,
                "options": options,
                "total": len(options)
            }
            
        except Exception as e:
            logger.error(f"Error executing parameter lookup: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch parameter values: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Unexpected error in parameter lookup: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Service execution endpoint
@router.post("/services/{service_id}/execute")
async def execute_service(
    service_id: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute a service directly"""
    from services.execution_engine import ExecutionEngine
    from services.balance_enforcer import balance_enforcer
    from services.cost_calculator import cost_calculator
    from exceptions.billing_exceptions import InsufficientBalanceError, ServiceAccessDeniedError

    try:
        # Get the service
        service = db.query(ApplicationService).filter(
            ApplicationService.service_id == service_id
        ).first()

        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )

        # Get the application
        app = db.query(Application).filter(
            Application.app_id == service.app_id
        ).first()

        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Check permissions
        user_role = get_user_role_string(current_user)
        if app.app_type == "tenant" and app.tenant_id_owner != current_user.tenant_id and user_role != "INSTANCE_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this application"
            )
        
        # Get subscription
        subscription_id = request.get('subscription_id')
        if not subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="subscription_id is required"
            )
        
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.subscription_id == subscription_id,
            ApplicationSubscription.app_id == app.app_id
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        # Check subscription ownership (tenant-based)
        if subscription.tenant_id != current_user.tenant_id:
            user_role = get_user_role_string(current_user)
            if user_role != "INSTANCE_ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this subscription"
                )
        
        # Get parameters
        parameters = request.get('parameters', {})

        # Deserialize JSON fields for SQLite
        if settings.database_url.startswith("sqlite"):
            service.service_config = deserialize_json_field(service.service_config)
            service.input_schema = deserialize_json_field(service.input_schema)
            service.output_schema = deserialize_json_field(service.output_schema)
            subscription.auth_credentials = deserialize_json_field(subscription.auth_credentials)
            subscription.subscription_config = deserialize_json_field(subscription.subscription_config)

        # Create a simple execution context with a temporary execution_id
        import uuid
        execution_id = str(uuid.uuid4())
        execution_context = {
            'execution_id': execution_id,
            'user_id': current_user.user_id,
            'tenant_id': current_user.tenant_id,
            'subscription_id': subscription_id,
            'service_id': service_id,
            'app_id': app.app_id
        }

        # Check balance and reserve funds for prepaid billing
        estimated_cost = 0.0
        billing_mode = None
        try:
            # Estimate data size from parameters
            estimated_data_kb = cost_calculator.estimate_data_transfer_kb(parameters) if parameters else 0

            # Check balance (will raise InsufficientBalanceError if insufficient)
            can_execute, estimated_cost, billing_mode = balance_enforcer.check_balance_for_service(
                tenant_id=current_user.tenant_id,
                app_id=app.app_id,
                service_id=service_id,
                estimated_data_kb=estimated_data_kb,
                db=db
            )

            # Reserve funds if prepaid
            if billing_mode == 'PREPAID' and estimated_cost > 0:
                from decimal import Decimal
                balance_enforcer.reserve_funds(
                    tenant_id=current_user.tenant_id,
                    amount=Decimal(str(estimated_cost)),
                    execution_id=execution_id,
                    app_id=app.app_id,
                    service_name=service.service_name,
                    db=db
                )

        except InsufficientBalanceError as e:
            logger.warning(f"Insufficient balance for service {service_id}: {e.message}")
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": e.message,
                    "error_code": "INSUFFICIENT_BALANCE",
                    "required_amount": e.required_amount,
                    "available_amount": e.available_amount,
                    "suggested_topup": e.suggested_topup,
                    "service_name": service.service_name,
                    "app_name": app.app_name
                }
            )
        except ServiceAccessDeniedError as e:
            logger.warning(f"Service access denied for {service_id}: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": e.message,
                    "error_code": "SERVICE_ACCESS_DENIED",
                    "reason": e.reason
                }
            )

        # Execute the service. The engine takes the caller's tenant SCHEMA (not
        # a session): passing ``db`` here made every log write open a pooled
        # engine with search_path=<Session object>, which Postgres refused.
        from api.flows import get_tenant_info
        schema_name, tenant_id = get_tenant_info(current_user, db)
        execution_context['schema_name'] = schema_name
        execution_context['tenant_schema'] = schema_name
        engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

        try:
            # Execute the service
            result = await engine._execute_service_with_type(
                service,
                subscription,
                parameters,
                execution_context
            )

            # Commit reserved funds if successful and prepaid
            if billing_mode == 'PREPAID' and estimated_cost > 0:
                from decimal import Decimal
                # Calculate actual cost based on response
                response_data_kb = cost_calculator.estimate_data_transfer_kb(result) if result else 0
                actual_data_kb = estimated_data_kb + response_data_kb

                # Get actual cost (may differ from estimated)
                actual_cost_tuple = cost_calculator.calculate_execution_cost(
                    app_id=app.app_id,
                    tenant_id=current_user.tenant_id,
                    incoming_events=1,
                    outgoing_services=1,
                    data_transfer_kb=actual_data_kb,
                    db=db
                )
                actual_cost = actual_cost_tuple[0] if actual_cost_tuple else Decimal(str(estimated_cost))

                balance_enforcer.commit_reserved_funds(
                    execution_id=execution_id,
                    actual_cost=actual_cost,
                    description=f"Service execution: {service.service_name}",
                    metadata={
                        'service_id': service_id,
                        'service_name': service.service_name,
                        'app_id': app.app_id,
                        'app_name': app.app_name
                    },
                    db=db
                )

            # Track usage in cost log
            if billing_mode != 'FREE':
                cost_calculator.create_cost_log(
                    execution_id=execution_id,
                    app_id=app.app_id,
                    tenant_id=current_user.tenant_id,
                    flow_id=None,
                    flow_name=f"Direct service: {service.service_name}",
                    trigger_type='api_call',
                    incoming_events=1,
                    outgoing_services=1,
                    data_transfer_kb=actual_data_kb if 'actual_data_kb' in locals() else estimated_data_kb,
                    db=db
                )

        except Exception as e:
            # Release reserved funds if execution failed
            if billing_mode == 'PREPAID' and estimated_cost > 0:
                balance_enforcer.release_reserved_funds(execution_id, db)
            raise

        return {
            'success': True,
            'result': result,
            'service_id': service_id,
            'service_name': service.service_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing service {service_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service execution failed: {str(e)}"
        )
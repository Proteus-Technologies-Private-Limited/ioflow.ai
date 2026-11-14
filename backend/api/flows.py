from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile, Form, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator
from datetime import datetime
import json
import asyncio
import logging
import ast
import base64
import tempfile
import os
import re

from db.database import get_db, get_tenant_db
from db.db_compat import table_ref, is_sqlite
from core.auth_utils import get_current_user_required as get_current_user, get_current_user_enhanced
from typing import Union
from core.config import settings

# Import models - PostgreSQL Only
from db.models import User, Flow, FlowStatus, FlowExecution, ExecutionStatus, APIKey
from db.application_models import Application, ApplicationSubscription, ApplicationService
from services.execution_engine import ExecutionEngine
from services.flow_validator import FlowValidator
from services.scheduler import flow_scheduler  # Import the global instance
from services.file_watcher import file_watcher_service  # Import the file watcher service
from services.mqtt_listener_service import mqtt_listener_service  # Import the MQTT listener service
from services.flow_format_normalizer import FlowFormatNormalizer
from services.balance_enforcer import balance_enforcer
from exceptions.billing_exceptions import InsufficientBalanceError

router = APIRouter(prefix="/api/v1/flows", tags=["flows"])

logger = logging.getLogger(__name__)

def parse_json_field(value: Any, default: Any = None) -> Any:
    """
    Safely parse JSON field that might be a string or already parsed dict/list.
    Handles both SQLAlchemy JSON fields and string-serialized JSON.
    """
    if value is None:
        return default if default is not None else {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse JSON string: {value[:100]}")
            return default if default is not None else {}
    return value

async def get_current_user_or_collaboration(
    token: Optional[str] = Query(None, description="Collaboration token"),
    user: Optional[User] = Depends(get_current_user_enhanced),
    db: Session = Depends(get_db)
) -> Optional[Union[User, dict]]:
    """
    Get current user either through normal authentication or collaboration token.
    Returns User object for authenticated users or dict with collaboration info for anonymous participants.
    """
    # If user is authenticated, return the user
    if user:
        return user
    
    # If there's a collaboration token, validate it
    if token:
        from db.collaboration_models import CollaborationSession, CollaborationParticipant
        
        # Find session by token
        session = db.query(CollaborationSession).filter(
            CollaborationSession.access_token == token,
            CollaborationSession.is_active == True,
            CollaborationSession.expires_at > datetime.utcnow()
        ).first()
        
        if session:
            # Return collaboration context
            return {
                "is_collaboration": True,
                "session_id": session.session_id,
                "flow_id": session.flow_id,
                "tenant_id": session.tenant_id,
                "allow_anonymous": session.allow_anonymous
            }
    
    return None

# Pydantic models
class TriggerConfig(BaseModel):
    type: str  # event, schedule, manual, webhook, api_call, file_change
    app_id: Optional[str] = None
    event_name: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None
    manual_variables: Optional[List[Dict[str, Any]]] = None
    execute_immediately: Optional[bool] = None
    # File change trigger specific fields
    folder_path: Optional[str] = None
    listener_type: Optional[List[str]] = None
    file_pattern: Optional[str] = None
    recursive: Optional[bool] = None
    debounce_seconds: Optional[int] = None

    # MQTT trigger specific fields
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = None
    mqtt_tls: Optional[bool] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_client_id: Optional[str] = None
    mqtt_topic_filter: Optional[str] = None
    mqtt_qos: Optional[int] = None
    mqtt_payload_format: Optional[str] = None

    # MQTT performance & delivery fine-tuning (apply to both trigger type
    # 'mqtt' and 'event' triggers bound to an MQTT application event).
    # Resolved through: flow trigger_config > subscription_config >
    # event_configuration > env setting > hardcoded default.
    mqtt_batch_size: Optional[int] = None            # 1 = no batching
    mqtt_batch_window_seconds: Optional[float] = None  # 0 = size-only flush
    mqtt_max_rate: Optional[float] = None            # executions/sec, 0 = unlimited
    mqtt_rate_overflow: Optional[str] = None         # fold | drop
    mqtt_max_concurrent: Optional[int] = None        # 0 = bounded only by global pool
    mqtt_dedup: Optional[str] = None                 # off | payload | key
    mqtt_dedup_key: Optional[str] = None             # template, e.g. {{payload.device_id}}:{{payload.seq}}
    mqtt_dedup_window_seconds: Optional[int] = None  # Redis dedup lock TTL

    # Chat input specific fields
    system_prompt: Optional[str] = None
    placeholder_text: Optional[str] = None
    session_timeout_minutes: Optional[int] = None

    @validator('type')
    def validate_trigger_type(cls, v):
        valid_types = ['event', 'schedule', 'manual', 'webhook', 'api_call', 'api_direct', 'api_direct_sync', 'file_change', 'chat_input', 'mqtt']
        if v not in valid_types:
            raise ValueError(f"Invalid trigger type '{v}'. Must be one of: {', '.join(valid_types)}")
        return v

    @validator('mqtt_batch_size')
    def validate_mqtt_batch_size(cls, v):
        if v is not None and not (1 <= v <= 10000):
            raise ValueError("mqtt_batch_size must be between 1 and 10000")
        return v

    @validator('mqtt_batch_window_seconds')
    def validate_mqtt_batch_window(cls, v):
        if v is not None and not (0 <= v <= 3600):
            raise ValueError("mqtt_batch_window_seconds must be between 0 and 3600")
        return v

    @validator('mqtt_max_rate')
    def validate_mqtt_max_rate(cls, v):
        if v is not None and v < 0:
            raise ValueError("mqtt_max_rate must be >= 0 (0 = unlimited)")
        return v

    @validator('mqtt_rate_overflow')
    def validate_mqtt_rate_overflow(cls, v):
        if v is not None and v not in ('fold', 'drop'):
            raise ValueError("mqtt_rate_overflow must be 'fold' or 'drop'")
        return v

    @validator('mqtt_max_concurrent')
    def validate_mqtt_max_concurrent(cls, v):
        if v is not None and v < 0:
            raise ValueError("mqtt_max_concurrent must be >= 0 (0 = global pool only)")
        return v

    @validator('mqtt_dedup')
    def validate_mqtt_dedup(cls, v):
        if v is not None and v not in ('off', 'payload', 'key'):
            raise ValueError("mqtt_dedup must be 'off', 'payload' or 'key'")
        return v

    @validator('mqtt_dedup_window_seconds')
    def validate_mqtt_dedup_window(cls, v):
        if v is not None and not (1 <= v <= 86400):
            raise ValueError("mqtt_dedup_window_seconds must be between 1 and 86400")
        return v

class NodeConfig(BaseModel):
    id: str
    type: str  # trigger, action, condition, parallel
    position: Dict[str, float]
    data: Dict[str, Any]

class EdgeConfig(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None

class FlowDefinition(BaseModel):
    nodes: List[NodeConfig]
    edges: List[EdgeConfig]
    # Flow-level execution settings (execution_log_level, flow_log_sample_rate, ...).
    # Stored inside flow_definition so no schema migration is needed.
    settings: Optional[Dict[str, Any]] = None

class FlowCreate(BaseModel):
    flow_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    flow_scope: Optional[str] = 'user'  # 'global', 'tenant', 'user'
    trigger_config: TriggerConfig
    flow_definition: FlowDefinition
    is_synchronous: bool = False
    sync_timeout: int = 30

class FlowUpdate(BaseModel):
    flow_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    flow_scope: Optional[str] = None  # 'global', 'tenant', 'user'
    trigger_config: Optional[TriggerConfig] = None
    flow_definition: Optional[FlowDefinition] = None
    status: Optional[FlowStatus] = None
    is_synchronous: Optional[bool] = None
    sync_timeout: Optional[int] = None

class UserInfo(BaseModel):
    user_id: str
    user_name: str
    email: str

class FlowResponse(BaseModel):
    flow_id: str
    flow_name: str
    description: Optional[str]
    category: Optional[str]
    flow_scope: str
    trigger_config: dict
    flow_definition: dict
    status: str
    is_synchronous: bool
    sync_timeout: int
    created_by: str
    created_by_user: Optional[UserInfo] = None  # User details for creator
    last_modified_by: Optional[str] = None
    last_modified_by_user: Optional[UserInfo] = None  # User details for last modifier
    created_at: datetime
    updated_at: datetime
    execution_count: Optional[int] = 0  # Total number of executions
    last_execution_at: Optional[datetime] = None  # Last execution time
    version: Optional[int] = 1  # Flow version number
    edit_link: Optional[str] = None  # Link to edit the flow in the UI

    class Config:
        # Ensure all fields are included in response, even if None
        response_model_include_none = True

class ManualExecuteRequest(BaseModel):
    trigger_type: str = "manual"
    variables: Dict[str, Any] = {}
    is_simulation: bool = False


class ChatExecuteRequest(BaseModel):
    """Request model for chat-triggered flow execution"""
    message: str
    chat_session_id: Optional[str] = None


class ChatEndRequest(BaseModel):
    """Request model for ending a chat session"""
    chat_session_id: str


class ChatExecuteResponse(BaseModel):
    """Response model for chat-triggered flow execution"""
    execution_id: str
    chat_session_id: str
    is_first_message: bool
    response: Any
    status: str

# Helper function to generate flow edit link
def generate_flow_edit_link(flow_id: str, base_url: str = None) -> str:
    """Generate a relative link to edit the flow in the UI.

    Returns a relative path that works behind load balancers and different domains.
    """
    # Return relative path for the flow designer
    # This will work correctly regardless of the domain or load balancer configuration
    return f"/flow-designer?flowId={flow_id}"

# Helper function to get tenant schema
def get_tenant_schema(current_user: User, db: Session) -> str:
    """Get the schema name for the current user's tenant.
    For SQLite: Returns 'default' since SQLite doesn't support schemas.
    For PostgreSQL: Returns the actual schema name from the tenants table.
    """
    if is_sqlite:
        # SQLite doesn't support schemas - return a default value
        return 'default'

    result = db.execute(
        text(f"SELECT schema_name FROM {table_ref('tenants')} WHERE tenant_id = :tenant_id"),
        {"tenant_id": current_user.tenant_id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return result[0]


def get_tenant_info(current_user: User, db: Session) -> tuple[str, str]:
    """Get both schema name and tenant_id for the current user's tenant.
    Returns: (schema_name, tenant_id)
    For SQLite: Returns ('default', tenant_id) since SQLite doesn't support schemas.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if is_sqlite:
        # SQLite doesn't support schemas - return a default value
        return 'default', tenant_id

    result = db.execute(
        text(f"SELECT schema_name FROM {table_ref('tenants')} WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return result[0], tenant_id

def preprocess_variables(variables: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Preprocess variables to parse string representations of arrays/objects.
    
    This function handles cases where variables are passed as string representations
    of Python data structures (e.g., "['item1', 'item2']" instead of ['item1', 'item2'])
    """
    if not variables:
        return {}
        
    processed_vars = {}
    
    for key, value in variables.items():
        if isinstance(value, str):
            # Try to parse string representations of lists/dicts
            value_stripped = value.strip()
            if (value_stripped.startswith('[') and value_stripped.endswith(']')) or \
               (value_stripped.startswith('{') and value_stripped.endswith('}')):
                try:
                    # Use ast.literal_eval for safe evaluation of literal expressions
                    parsed_value = ast.literal_eval(value_stripped)
                    processed_vars[key] = parsed_value
                    logger.debug(f"Parsed variable '{key}' from string to {type(parsed_value).__name__}")
                except (ValueError, SyntaxError) as e:
                    # If parsing fails, keep the original string value
                    logger.debug(f"Could not parse variable '{key}': {e}")
                    processed_vars[key] = value
            else:
                processed_vars[key] = value
        else:
            processed_vars[key] = value
    
    return processed_vars

@router.get("/", response_model=List[FlowResponse])
async def list_flows(
    status: Optional[FlowStatus] = None,
    include_stats: bool = False,  # Optional parameter to include execution statistics
    include_user_info: bool = True,  # Optional parameter to include user details
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List flows based on user role and flow scope visibility rules.

    Args:
        status: Optional filter by flow status
        include_stats: If True, includes execution statistics (slower)
        include_user_info: If True, includes creator/modifier user details
    """
    schema_name = get_tenant_schema(current_user, db)
    
    # Use tenant-specific database session
    with get_tenant_db(schema_name) as tenant_db:
        query = tenant_db.query(Flow)
        
        # Apply visibility rules based on user role
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)

        from sqlalchemy import or_, and_

        if user_role == "INSTANCE_ADMIN":
            # SECURITY FIX: Instance admin can see:
            # - All global flows (across all tenants)
            # - All tenant flows (across all tenants)
            # - ONLY their own user-scoped flows (respect user privacy)
            # This ensures user-scoped (private) flows are truly private
            query = query.filter(
                or_(
                    Flow.flow_scope == 'global',
                    Flow.flow_scope == 'tenant',
                    and_(
                        Flow.flow_scope == 'user',
                        Flow.created_by == current_user.user_id
                    )
                )
            )
        elif user_role == "TENANT_ADMIN":
            # SECURITY FIX: Tenant admin can see:
            # - Global flows
            # - Tenant flows from THEIR tenant only
            # - ONLY their own user-scoped flows (respect user privacy)
            query = query.filter(
                and_(
                    Flow.tenant_id == current_user.tenant_id,
                    or_(
                        Flow.flow_scope == 'global',
                        Flow.flow_scope == 'tenant',
                        and_(
                            Flow.flow_scope == 'user',
                            Flow.created_by == current_user.user_id
                        )
                    )
                )
            )
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR", "FLOW_EXECUTOR", "EXECUTION_MONITOR"]:
            # Flow designers, executors, and execution monitors can see:
            # - Global flows (accessible to all)
            # - Tenant flows FROM THEIR TENANT ONLY (critical security fix!)
            # - Only their own user-scoped flows
            query = query.filter(
                or_(
                    Flow.flow_scope == 'global',
                    and_(
                        Flow.flow_scope == 'tenant',
                        Flow.tenant_id == current_user.tenant_id  # SECURITY: Filter by tenant!
                    ),
                    and_(
                        Flow.flow_scope == 'user',
                        Flow.created_by == current_user.user_id
                    )
                )
            )
        else:
            # Regular users cannot see flows directly - they only use published applications
            # Return empty list for regular users
            return []
        
        if status:
            query = query.filter(Flow.status == status)
        
        # Sort by updated_at in descending order (most recent first)
        query = query.order_by(Flow.updated_at.desc())
        
        flows = query.all()

        # Get user information only if requested
        users_dict = {}
        if include_user_info:
            # Get unique user IDs to fetch user info
            user_ids = set()
            for flow in flows:
                if flow.created_by:
                    user_ids.add(flow.created_by)
                if hasattr(flow, 'last_modified_by') and flow.last_modified_by:
                    user_ids.add(flow.last_modified_by)

            # Fetch user information with single query
            if user_ids:
                users = db.query(User).filter(User.user_id.in_(user_ids)).all()
                users_dict = {
                    user.user_id: UserInfo(
                        user_id=user.user_id,
                        user_name=user.user_name,
                        email=user.email
                    )
                    for user in users
                }

        # Get execution statistics only if requested (for performance)
        flow_stats = {}
        if include_stats and flows:
            # Get all flow IDs
            flow_ids = [flow.flow_id for flow in flows]

            # Use a single aggregated query for execution counts
            from sqlalchemy import func
            exec_counts = tenant_db.query(
                FlowExecution.flow_id,
                func.count(FlowExecution.execution_id).label('count'),
                func.max(FlowExecution.started_at).label('last_run')
            ).filter(
                FlowExecution.flow_id.in_(flow_ids)
            ).group_by(FlowExecution.flow_id).all()

            # Build stats dictionary
            for flow_id, count, last_run in exec_counts:
                flow_stats[flow_id] = {
                    'execution_count': count,
                    'last_execution_at': last_run
                }

        # Set default stats for flows without executions
        for flow in flows:
            if flow.flow_id not in flow_stats:
                flow_stats[flow.flow_id] = {
                    'execution_count': 0,
                    'last_execution_at': None
                }

        return [
            FlowResponse(
                flow_id=flow.flow_id,
                flow_name=flow.flow_name,
                description=flow.description,
                category=flow.category,
                flow_scope=flow.flow_scope or 'user',  # Default to 'user' for existing flows
                trigger_config=parse_json_field(flow.trigger_config, {}),
                flow_definition=parse_json_field(flow.flow_definition, {}),
                status=flow.status.value,
                is_synchronous=flow.is_synchronous,
                sync_timeout=flow.sync_timeout,
                created_by=flow.created_by,
                created_by_user=users_dict.get(flow.created_by) if flow.created_by else None,
                last_modified_by=getattr(flow, 'last_modified_by', None),
                last_modified_by_user=users_dict.get(getattr(flow, 'last_modified_by', None)) if hasattr(flow, 'last_modified_by') and flow.last_modified_by else None,
                created_at=flow.created_at,
                updated_at=flow.updated_at,
                execution_count=flow_stats.get(flow.flow_id, {}).get('execution_count', 0),
                last_execution_at=flow_stats.get(flow.flow_id, {}).get('last_execution_at'),
                version=1,  # Version tracking can be enhanced later
                edit_link=generate_flow_edit_link(flow.flow_id)
            )
            for flow in flows
        ]

@router.post("/", response_model=FlowResponse)
async def create_flow(
    flow_data: FlowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new flow."""
    # Check if user has permission to create flows
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit creating flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    # Validate that referenced applications are subscribed and inherit sync mode
    inherited_is_synchronous = flow_data.is_synchronous
    
    if flow_data.trigger_config.app_id:
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.tenant_id == current_user.tenant_id,
            ApplicationSubscription.app_id == flow_data.trigger_config.app_id
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application not subscribed"
            )
        
        # If trigger is an application event, inherit sync mode from the event by default
        if (flow_data.trigger_config.type == 'event' and 
            hasattr(flow_data.trigger_config, 'event_name') and 
            flow_data.trigger_config.event_name and
            flow_data.is_synchronous == False):  # Only inherit if not explicitly set to True
            
            # Look up the application event to get its sync_mode
            from db.application_models import ApplicationEvent
            app_event = db.query(ApplicationEvent).filter(
                ApplicationEvent.app_id == flow_data.trigger_config.app_id,
                ApplicationEvent.event_name == flow_data.trigger_config.event_name
            ).first()
            
            if app_event and app_event.sync_mode and app_event.sync_mode != 'optional':
                # Inherit synchronous mode from the application event (only if not optional)
                inherited_is_synchronous = app_event.sync_mode == 'synchronous'
                logger.info(f"Flow inheriting sync_mode '{app_event.sync_mode}' from application event '{app_event.event_name}' - setting is_synchronous to {inherited_is_synchronous}")
    
    # Use the inherited synchronous mode
    final_is_synchronous = inherited_is_synchronous
    
    # Validate flow structure for both synchronous and regular flows
    # Pass database session and tenant_id for comprehensive validation
    validator = FlowValidator(db=db, tenant_id=current_user.tenant_id)
    
    # Always perform comprehensive validation to catch rendering issues
    is_valid, errors = validator.validate_flow_comprehensive(flow_data.flow_definition.dict())
    
    # Check for critical errors that would prevent rendering
    critical_errors = [e for e in errors if e.error_type == "error"]
    if critical_errors:
        error_messages = [f"{e.node_id}: {e.message}" for e in critical_errors[:3]]  # Show first 3 errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flow validation failed: {'; '.join(error_messages)}"
        )
    
    # Additional validation for synchronous flows
    if final_is_synchronous:
        is_valid, sync_errors = validator.validate_synchronous_flow(flow_data.flow_definition.dict())
        
        if not is_valid:
            error_messages = [f"{e.message}" for e in sync_errors if e.error_type == "error"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid synchronous flow: {'; '.join(error_messages)}"
            )
    
    # Validate flow_scope permission
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if flow_data.flow_scope == 'global' and user_role != "INSTANCE_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can create global flows"
        )
    elif flow_data.flow_scope == 'tenant' and user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant admins can create tenant-level flows"
        )
    
    # Create flow in tenant schema
    with get_tenant_db(schema_name) as tenant_db:
        new_flow = Flow(
            flow_name=flow_data.flow_name,
            tenant_id=current_user.tenant_id,
            description=flow_data.description,
            category=flow_data.category,
            flow_scope=flow_data.flow_scope or 'user',
            trigger_config=flow_data.trigger_config.dict(),
            flow_definition=flow_data.flow_definition.dict(),
            status=FlowStatus.DRAFT,
            is_synchronous=final_is_synchronous,
            sync_timeout=flow_data.sync_timeout,
            created_by=current_user.user_id
        )
        
        tenant_db.add(new_flow)
        tenant_db.commit()
        tenant_db.refresh(new_flow)

        # Create user info for response
        creator_info = UserInfo(
            user_id=current_user.user_id,
            user_name=current_user.user_name,
            email=current_user.email
        )

        logger.info(f"Creating FlowResponse with creator_info: {creator_info}")

        return FlowResponse(
            flow_id=new_flow.flow_id,
            flow_name=new_flow.flow_name,
            description=new_flow.description,
            category=new_flow.category,
            flow_scope=new_flow.flow_scope or 'user',
            trigger_config=parse_json_field(new_flow.trigger_config, {}),
            flow_definition=parse_json_field(new_flow.flow_definition, {}),
            status=new_flow.status.value,
            is_synchronous=new_flow.is_synchronous,
            sync_timeout=new_flow.sync_timeout,
            created_by=new_flow.created_by,
            created_by_user=creator_info,
            last_modified_by=new_flow.created_by,  # Initially same as creator
            last_modified_by_user=creator_info,  # Initially same as creator
            created_at=new_flow.created_at,
            updated_at=new_flow.updated_at,
            execution_count=0,
            last_execution_at=None,
            version=1,
            edit_link=generate_flow_edit_link(new_flow.flow_id)
        )

@router.get("/by-name", response_model=FlowResponse)
async def get_flow_by_name(
    flow_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a flow by its name for the current user"""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        # First try to find flows created by the current user
        flow = tenant_db.query(Flow).filter(
            Flow.flow_name == flow_name,
            Flow.created_by == current_user.user_id
        ).first()

        # If not found, check for flows the user has access to based on scope
        if not flow:
            # Get user's role
            user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)

            # Query all flows with this name in the tenant
            all_flows = tenant_db.query(Flow).filter(Flow.flow_name == flow_name).all()

            # Find the first accessible flow based on scope
            for f in all_flows:
                # Check if user has access based on flow scope
                if f.flow_scope == 'global':
                    # Global flows are accessible to all users
                    flow = f
                    break
                elif f.flow_scope == 'tenant':
                    # Tenant flows are accessible to all users in the tenant
                    flow = f
                    break
                elif f.flow_scope == 'user' or f.flow_scope is None:
                    # User flows are only accessible to the creator (already checked above)
                    continue

            if not flow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Flow '{flow_name}' not found or not accessible"
                )
        return FlowResponse(
            flow_id=str(flow.flow_id),
            flow_name=flow.flow_name,
            description=flow.description,
            category=flow.category,
            flow_scope=flow.flow_scope or 'user',
            trigger_config=parse_json_field(flow.trigger_config, {}),
            flow_definition=parse_json_field(flow.flow_definition, {}),
            status=flow.status.value if hasattr(flow.status, 'value') else str(flow.status),
            is_synchronous=flow.is_synchronous,
            sync_timeout=flow.sync_timeout,
            created_by=flow.created_by,
            created_at=flow.created_at,
            updated_at=flow.updated_at,
            tenant_id=flow.tenant_id
        )

@router.get("/{flow_id}", response_model=FlowResponse)
async def get_flow(
    flow_id: str,
    current_user_or_collab: Optional[Union[User, dict]] = Depends(get_current_user_or_collaboration),
    db: Session = Depends(get_db)
):
    """Get flow details with visibility check."""
    if not current_user_or_collab:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if this is a collaboration participant
    if isinstance(current_user_or_collab, dict) and current_user_or_collab.get("is_collaboration"):
        # Collaboration participant - check if they're accessing the right flow
        if current_user_or_collab["flow_id"] != flow_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access the flow you're collaborating on"
            )
        
        # Use the tenant from the collaboration session
        tenant_id = current_user_or_collab["tenant_id"]
        schema_name = tenant_id  # For SQLite, tenant_id is the schema name
        
        with get_tenant_db(schema_name) as tenant_db:
            flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
            
            if not flow:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
            
            # Collaboration participants can view the flow they're collaborating on
            return FlowResponse(
                flow_id=flow.flow_id,
                flow_name=flow.flow_name,
                description=flow.description,
                category=flow.category,
                flow_scope=flow.flow_scope or 'user',
                trigger_config=parse_json_field(flow.trigger_config, {}),
                flow_definition=parse_json_field(flow.flow_definition, {}),
                status=flow.status.value,
                is_synchronous=flow.is_synchronous,
                sync_timeout=flow.sync_timeout,
                created_by=flow.created_by,
                created_at=flow.created_at,
                updated_at=flow.updated_at,
                edit_link=generate_flow_edit_link(flow.flow_id)
            )
    
    # Regular authenticated user flow
    current_user = current_user_or_collab
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Check if user is a collaboration participant for this flow
        from db.collaboration_models import CollaborationSession, CollaborationParticipant
        
        is_collaboration_participant = False
        active_session = db.query(CollaborationSession).filter(
            CollaborationSession.flow_id == flow_id,
            CollaborationSession.is_active == True,
            CollaborationSession.expires_at > datetime.utcnow()
        ).first()
        
        if active_session:
            # Check if current user is a participant in the active session
            participant = db.query(CollaborationParticipant).filter(
                CollaborationParticipant.session_id == active_session.session_id,
                CollaborationParticipant.user_id == str(current_user.user_id)
            ).first()
            if participant:
                is_collaboration_participant = True
        
        # Check visibility permissions
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        flow_scope = flow.flow_scope or 'user'
        
        if is_collaboration_participant:
            # Collaboration participants can access the flow regardless of their role
            pass
        elif user_role == "INSTANCE_ADMIN":
            # SECURITY FIX: Instance admin can see all flows EXCEPT other users' private flows
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view this user's private flow"
                )
        elif user_role == "TENANT_ADMIN":
            # SECURITY: Tenant admin can only see flows in their tenant
            if flow.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view flows from your tenant"
                )
            # SECURITY FIX: Respect user-scoped privacy
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view this user's private flow"
                )
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR", "FLOW_EXECUTOR", "EXECUTION_MONITOR"]:
            # SECURITY: Validate access based on flow scope
            if flow_scope == 'global':
                # Global flows are accessible to all authenticated users
                pass
            elif flow_scope == 'tenant':
                # CRITICAL FIX: Verify flow belongs to user's tenant
                if flow.tenant_id != current_user.tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to view flows from other tenants"
                    )
            elif flow_scope == 'user':
                # User flows must be created by current user
                if flow.created_by != current_user.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to view this user's flow"
                    )
        else:
            # Regular users cannot access flows directly
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Regular users can only access published applications"
            )
        
        # Get user information for response
        user_ids = set([flow.created_by])
        if hasattr(flow, 'last_modified_by') and flow.last_modified_by:
            user_ids.add(flow.last_modified_by)

        users_dict = {}
        if user_ids:
            users = db.query(User).filter(User.user_id.in_(user_ids)).all()
            users_dict = {
                user.user_id: UserInfo(
                    user_id=user.user_id,
                    user_name=user.user_name,
                    email=user.email
                )
                for user in users
            }

        # Get execution statistics
        exec_query = tenant_db.query(FlowExecution).filter(
            FlowExecution.flow_id == flow.flow_id
        )
        exec_count = exec_query.count()
        last_exec = exec_query.order_by(FlowExecution.started_at.desc()).first()

        return FlowResponse(
            flow_id=flow.flow_id,
            flow_name=flow.flow_name,
            description=flow.description,
            category=flow.category,
            flow_scope=flow_scope,
            trigger_config=parse_json_field(flow.trigger_config, {}),
            flow_definition=parse_json_field(flow.flow_definition, {}),
            status=flow.status.value,
            is_synchronous=flow.is_synchronous,
            sync_timeout=flow.sync_timeout,
            created_by=flow.created_by,
            created_by_user=users_dict.get(flow.created_by),
            last_modified_by=getattr(flow, 'last_modified_by', flow.created_by),
            last_modified_by_user=users_dict.get(getattr(flow, 'last_modified_by', flow.created_by)),
            created_at=flow.created_at,
            updated_at=flow.updated_at,
            execution_count=exec_count,
            last_execution_at=last_exec.started_at if last_exec else None,
            version=1,
            edit_link=generate_flow_edit_link(flow.flow_id)
        )

@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    flow_id: str,
    flow_data: FlowUpdate,
    current_user_or_collab: Optional[Union[User, dict]] = Depends(get_current_user_or_collaboration),
    db: Session = Depends(get_db)
):
    """Update a flow."""
    if not current_user_or_collab:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if this is a collaboration participant
    if isinstance(current_user_or_collab, dict) and current_user_or_collab.get("is_collaboration"):
        # Collaboration participant - check if they're accessing the right flow
        if current_user_or_collab["flow_id"] != flow_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update the flow you're collaborating on"
            )
        
        # Check if they have editor role in the collaboration
        from db.collaboration_models import CollaborationParticipant, CollaborationRole
        
        # For now, allow all collaboration participants to edit
        # In the future, we can check their specific role
        tenant_id = current_user_or_collab["tenant_id"]
        schema_name = tenant_id
        
        with get_tenant_db(schema_name) as tenant_db:
            flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
            
            if not flow:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
            
            # Update fields (collaboration participants can't change scope)
            if flow_data.flow_name is not None:
                flow.flow_name = flow_data.flow_name
            if flow_data.description is not None:
                flow.description = flow_data.description
            if flow_data.category is not None:
                flow.category = flow_data.category
            if flow_data.trigger_config is not None:
                flow.trigger_config = flow_data.trigger_config
            if flow_data.flow_definition is not None:
                flow.flow_definition = flow_data.flow_definition
            if flow_data.status is not None:
                flow.status = flow_data.status
            if flow_data.is_synchronous is not None:
                flow.is_synchronous = flow_data.is_synchronous
            if flow_data.sync_timeout is not None:
                flow.sync_timeout = flow_data.sync_timeout

            # Track modification by collaboration participant (anonymous)
            if hasattr(flow, 'last_modified_by'):
                flow.last_modified_by = 'collaboration_user'

            flow.updated_at = datetime.utcnow()
            
            tenant_db.commit()
            tenant_db.refresh(flow)
            
            return FlowResponse(
                flow_id=flow.flow_id,
                flow_name=flow.flow_name,
                description=flow.description,
                category=flow.category,
                flow_scope=flow.flow_scope or 'user',
                trigger_config=parse_json_field(flow.trigger_config, {}),
                flow_definition=parse_json_field(flow.flow_definition, {}),
                status=flow.status.value,
                is_synchronous=flow.is_synchronous,
                sync_timeout=flow.sync_timeout,
                created_by=flow.created_by,
                created_at=flow.created_at,
                updated_at=flow.updated_at,
                edit_link=generate_flow_edit_link(flow.flow_id)
            )
    
    # Regular authenticated user flow
    current_user = current_user_or_collab
    
    # Check permissions
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit updating flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Check if user is a collaboration participant with edit permissions
        from db.collaboration_models import CollaborationSession, CollaborationParticipant, CollaborationRole
        
        is_collaboration_editor = False
        active_session = db.query(CollaborationSession).filter(
            CollaborationSession.flow_id == flow_id,
            CollaborationSession.is_active == True,
            CollaborationSession.expires_at > datetime.utcnow()
        ).first()
        
        if active_session:
            participant = db.query(CollaborationParticipant).filter(
                CollaborationParticipant.session_id == active_session.session_id,
                CollaborationParticipant.user_id == str(current_user.user_id)
            ).first()
            if participant and participant.role == CollaborationRole.EDITOR:
                is_collaboration_editor = True
        
        # SECURITY: Check edit permissions based on role, scope, and flow ownership
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        flow_scope = flow.flow_scope or 'user'

        if is_collaboration_editor:
            # Collaboration editors have permission to edit
            pass
        elif user_role == "INSTANCE_ADMIN":
            # SECURITY FIX: Instance admin can edit all flows EXCEPT other users' private flows
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this user's private flow"
                )
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can edit flows in their tenant
            if flow.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only edit flows from your tenant"
                )
            # SECURITY FIX: Respect user-scoped privacy
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this user's private flow"
                )
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR"]:
            # SECURITY: Validate access based on flow scope
            if flow_scope == 'global':
                # Global flows can only be edited by INSTANCE_ADMIN
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only instance admins can edit global flows"
                )
            elif flow_scope == 'tenant':
                # CRITICAL FIX: Verify flow belongs to user's tenant
                if flow.tenant_id != current_user.tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to edit flows from other tenants"
                    )
                # Regular designers cannot edit tenant flows - only tenant admins can
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only tenant admins can edit tenant-level flows"
                )
            elif flow_scope == 'user':
                # User flows must be created by current user
                if flow.created_by != current_user.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only edit flows you created"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to edit flows"
            )
        
        # Validate flow_scope change permissions
        if flow_data.flow_scope is not None and flow_data.flow_scope != flow_scope:
            if flow_data.flow_scope == 'global' and user_role != "INSTANCE_ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only instance admins can make flows global"
                )
            elif flow_data.flow_scope == 'tenant' and user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only tenant admins can make flows tenant-level"
                )
        
        # Update fields
        if flow_data.flow_name is not None:
            flow.flow_name = flow_data.flow_name
        if flow_data.description is not None:
            flow.description = flow_data.description
        if flow_data.category is not None:
            flow.category = flow_data.category
        if flow_data.flow_scope is not None:
            flow.flow_scope = flow_data.flow_scope
        if flow_data.trigger_config is not None:
            flow.trigger_config = flow_data.trigger_config.dict()
        if flow_data.flow_definition is not None:
            new_definition = flow_data.flow_definition.dict()
            # Preserve existing flow-level settings when the client omits them
            # (older clients / API callers that only send nodes+edges)
            if new_definition.get('settings') is None and isinstance(flow.flow_definition, dict):
                existing_settings = flow.flow_definition.get('settings')
                if existing_settings is not None:
                    new_definition['settings'] = existing_settings
            flow.flow_definition = new_definition
        if flow_data.status is not None:
            flow.status = flow_data.status
        
        # Handle synchronous mode inheritance when updating trigger config
        if flow_data.trigger_config is not None or flow_data.is_synchronous is not None:
            # Determine final is_synchronous value
            updated_is_synchronous = flow_data.is_synchronous if flow_data.is_synchronous is not None else flow.is_synchronous
            trigger_config = flow_data.trigger_config.dict() if flow_data.trigger_config is not None else flow.trigger_config
            
            # If trigger is being updated to an application event and is_synchronous is not explicitly set to True
            if (trigger_config and trigger_config.get('type') == 'event' and 
                trigger_config.get('app_id') and trigger_config.get('event_name') and
                flow_data.is_synchronous != True):  # Only inherit if not explicitly being set to True
                
                # Look up the application event to get its sync_mode
                from db.application_models import ApplicationEvent
                app_event = db.query(ApplicationEvent).filter(
                    ApplicationEvent.app_id == trigger_config.get('app_id'),
                    ApplicationEvent.event_name == trigger_config.get('event_name')
                ).first()
                
                if app_event and app_event.sync_mode and app_event.sync_mode != 'optional':
                    # Inherit synchronous mode from the application event (only if not optional)
                    inherited_is_synchronous = app_event.sync_mode == 'synchronous'
                    if flow_data.is_synchronous is None:  # Only inherit if not explicitly provided
                        updated_is_synchronous = inherited_is_synchronous
                        logger.info(f"Flow update inheriting sync_mode '{app_event.sync_mode}' from application event '{app_event.event_name}' - setting is_synchronous to {inherited_is_synchronous}")
            
            flow.is_synchronous = updated_is_synchronous
        elif flow_data.is_synchronous is not None:
            flow.is_synchronous = flow_data.is_synchronous
            
        if flow_data.sync_timeout is not None:
            flow.sync_timeout = flow_data.sync_timeout

        # Track who modified the flow
        if hasattr(flow, 'last_modified_by'):
            flow.last_modified_by = current_user.user_id

        # Validate synchronous flow structure if needed
        final_is_synchronous = flow.is_synchronous
        final_flow_definition = flow.flow_definition
        
        if final_is_synchronous:
            validator = FlowValidator(db=db, tenant_id=current_user.tenant_id)
            is_valid, errors = validator.validate_synchronous_flow(final_flow_definition)
            
            if not is_valid:
                error_messages = [f"{e.message}" for e in errors if e.error_type == "error"]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid synchronous flow: {'; '.join(error_messages)}"
                )
        
        tenant_db.commit()
        tenant_db.refresh(flow)
        
        # Handle scheduler integration for scheduled flows
        if flow_data.status is not None and flow.trigger_config:
            tenant_id = current_user.tenant_id
            trigger_type = flow.trigger_config.get('type')
            
            if trigger_type == 'schedule':
                if flow.status == FlowStatus.ACTIVE:
                    # Schedule the flow
                    try:
                        await flow_scheduler.schedule_flow(tenant_id, schema_name, flow)
                        logger.info(f"Scheduled flow {flow_id} for tenant {tenant_id}")
                    except Exception as e:
                        logger.error(f"Failed to schedule flow: {str(e)}")
                        # Revert the status change
                        flow.status = FlowStatus.INACTIVE
                        tenant_db.commit()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to schedule flow: {str(e)}"
                        )
                else:
                    # Unschedule the flow
                    asyncio.create_task(flow_scheduler.unschedule_flow(tenant_id, flow_id))
                    logger.info(f"Unscheduled flow {flow_id} for tenant {tenant_id}")
            
            elif trigger_type == 'file_change':
                if flow.status == FlowStatus.ACTIVE:
                    # Start file watcher
                    try:
                        await file_watcher_service.watch_flow(tenant_id, schema_name, flow)
                        logger.info(f"Started file watcher for flow {flow_id} for tenant {tenant_id}")
                    except Exception as e:
                        logger.error(f"Failed to start file watcher: {str(e)}")
                        # Revert the status change
                        flow.status = FlowStatus.INACTIVE
                        tenant_db.commit()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to start file watcher: {str(e)}"
                        )
                else:
                    # Stop file watcher
                    asyncio.create_task(file_watcher_service.unwatch_flow(tenant_id, flow_id))
                    logger.info(f"Stopped file watcher for flow {flow_id} for tenant {tenant_id}")

            elif trigger_type == 'mqtt':
                if flow.status == FlowStatus.ACTIVE:
                    # Start MQTT listener
                    try:
                        await mqtt_listener_service.watch_flow(tenant_id, schema_name, flow)
                        logger.info(f"Started MQTT listener for flow {flow_id} for tenant {tenant_id}")
                    except Exception as e:
                        logger.error(f"Failed to start MQTT listener: {str(e)}")
                        # Revert the status change
                        flow.status = FlowStatus.INACTIVE
                        tenant_db.commit()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to start MQTT listener: {str(e)}"
                        )
                else:
                    # Stop MQTT listener
                    asyncio.create_task(mqtt_listener_service.unwatch_flow(tenant_id, flow_id))
                    logger.info(f"Stopped MQTT listener for flow {flow_id} for tenant {tenant_id}")

            elif trigger_type == 'event':
                # MQTT-backed application events need an immediate listener
                # attach/detach; watch_event_flow no-ops for webhook/polling events
                if flow.status == FlowStatus.ACTIVE:
                    try:
                        attached = await mqtt_listener_service.watch_event_flow(tenant_id, schema_name, flow)
                        if attached:
                            logger.info(f"Attached MQTT event listener for flow {flow_id} for tenant {tenant_id}")
                    except ValueError as e:
                        logger.error(f"Failed to attach MQTT event listener: {str(e)}")
                        # Revert the status change
                        flow.status = FlowStatus.INACTIVE
                        tenant_db.commit()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Failed to start MQTT listener: {str(e)}"
                        )
                else:
                    asyncio.create_task(mqtt_listener_service.unwatch_event_flow(tenant_id, flow_id))

        # Get user information for response
        user_ids = set([flow.created_by])
        if hasattr(flow, 'last_modified_by') and flow.last_modified_by:
            user_ids.add(flow.last_modified_by)

        users_dict = {}
        if user_ids:
            users = db.query(User).filter(User.user_id.in_(user_ids)).all()
            users_dict = {
                user.user_id: UserInfo(
                    user_id=user.user_id,
                    user_name=user.user_name,
                    email=user.email
                )
                for user in users
            }

        # Get execution statistics
        exec_query = tenant_db.query(FlowExecution).filter(
            FlowExecution.flow_id == flow.flow_id
        )
        exec_count = exec_query.count()
        last_exec = exec_query.order_by(FlowExecution.started_at.desc()).first()

        return FlowResponse(
            flow_id=flow.flow_id,
            flow_name=flow.flow_name,
            description=flow.description,
            category=flow.category,
            flow_scope=flow.flow_scope or 'user',
            trigger_config=parse_json_field(flow.trigger_config, {}),
            flow_definition=parse_json_field(flow.flow_definition, {}),
            status=flow.status.value,
            is_synchronous=flow.is_synchronous,
            sync_timeout=flow.sync_timeout,
            created_by=flow.created_by,
            created_by_user=users_dict.get(flow.created_by),
            last_modified_by=getattr(flow, 'last_modified_by', flow.created_by),
            last_modified_by_user=users_dict.get(getattr(flow, 'last_modified_by', flow.created_by)),
            created_at=flow.created_at,
            updated_at=flow.updated_at,
            execution_count=exec_count,
            last_execution_at=last_exec.started_at if last_exec else None,
            version=1,
            edit_link=generate_flow_edit_link(flow.flow_id)
        )

@router.delete("/{flow_id}")
async def delete_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a flow."""
    # Check permissions
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit deleting flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

        # SECURITY: Validate user has permission to delete this flow
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        flow_scope = flow.flow_scope or 'user'

        if user_role == "INSTANCE_ADMIN":
            # SECURITY FIX: Instance admin can delete any flow EXCEPT other users' private flows
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to delete this user's private flow"
                )
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can delete any flow in their tenant
            if flow.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only delete flows from your tenant"
                )
            # SECURITY FIX: Respect user-scoped privacy
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to delete this user's private flow"
                )
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR"]:
            # Regular users can only delete their own user-scoped flows
            if flow_scope == 'user':
                if flow.created_by != current_user.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only delete flows you created"
                    )
            else:
                # Cannot delete tenant or global flows
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Only tenant admins can delete {flow_scope}-scoped flows"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete flows"
            )

        # Don't delete active flows
        if flow.status == FlowStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete active flow. Please deactivate it first."
            )
        
        # Delete all executions associated with this flow first. Their child
        # rows (logs, callbacks, HITL tasks, event waits) FK the executions;
        # PostgreSQL enforces those FKs (SQLite did not), so delete children
        # before the executions to avoid a ForeignKeyViolation.
        from db.models import FlowExecution, ExecutionLog, AsyncCallback, HITLTask, EventWait
        exec_ids = [row[0] for row in tenant_db.query(FlowExecution.execution_id)
                    .filter(FlowExecution.flow_id == flow_id).all()]
        if exec_ids:
            for child in (ExecutionLog, AsyncCallback, HITLTask, EventWait):
                tenant_db.query(child).filter(child.execution_id.in_(exec_ids)).delete(synchronize_session=False)
        tenant_db.query(FlowExecution).filter(FlowExecution.flow_id == flow_id).delete(synchronize_session=False)

        # Now delete the flow
        tenant_db.delete(flow)
        tenant_db.commit()
        
        return {"message": "Flow deleted successfully"}

@router.post("/{flow_id}/activate")
async def activate_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Activate a flow."""
    # Check permissions — EXECUTION_MONITOR is allowed to (re)activate flows,
    # FLOW_EXECUTOR is not.
    if current_user.role.value == "FLOW_EXECUTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit activating flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        if flow.status == FlowStatus.ACTIVE:
            return {"message": "Flow is already active", "status": "active"}
        
        flow.status = FlowStatus.ACTIVE
        tenant_db.commit()
        
        # Handle trigger integrations for activated flows
        if flow.trigger_config:
            tenant_id = current_user.tenant_id
            trigger_type = flow.trigger_config.get('type')
            
            if trigger_type == 'schedule':
                try:
                    await flow_scheduler.schedule_flow(tenant_id, schema_name, flow)
                    logger.info(f"Scheduled flow {flow_id} for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to schedule flow: {str(e)}")
                    # Revert the status change
                    flow.status = FlowStatus.DRAFT
                    tenant_db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to start scheduler: {str(e)}"
                    )
            elif trigger_type == 'file_change':
                try:
                    await file_watcher_service.watch_flow(tenant_id, schema_name, flow)
                    logger.info(f"Started file watcher for flow {flow_id} for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to start file watcher: {str(e)}")
                    # Revert the status change
                    flow.status = FlowStatus.DRAFT
                    tenant_db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to start file watcher: {str(e)}"
                    )
            elif trigger_type == 'mqtt':
                try:
                    await mqtt_listener_service.watch_flow(tenant_id, schema_name, flow)
                    logger.info(f"Started MQTT listener for flow {flow_id} for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to start MQTT listener: {str(e)}")
                    # Revert the status change
                    flow.status = FlowStatus.DRAFT
                    tenant_db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to start MQTT listener: {str(e)}"
                    )
            elif trigger_type == 'event':
                # MQTT-backed application events attach a listener on activation;
                # watch_event_flow no-ops for webhook/polling events
                try:
                    attached = await mqtt_listener_service.watch_event_flow(tenant_id, schema_name, flow)
                    if attached:
                        logger.info(f"Attached MQTT event listener for flow {flow_id} for tenant {tenant_id}")
                except ValueError as e:
                    logger.error(f"Failed to attach MQTT event listener: {str(e)}")
                    # Revert the status change
                    flow.status = FlowStatus.DRAFT
                    tenant_db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to start MQTT listener: {str(e)}"
                    )

        logger.info(f"Flow {flow_id} activated by user {current_user.user_id}")
        return {"message": "Flow activated successfully", "status": "active"}

@router.post("/{flow_id}/deactivate")
async def deactivate_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate a flow (set to inactive)."""
    # Check permissions — EXECUTION_MONITOR is allowed to deactivate flows,
    # FLOW_EXECUTOR is not.
    if current_user.role.value == "FLOW_EXECUTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit deactivating flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        if flow.status == FlowStatus.INACTIVE:
            return {"message": "Flow is already inactive", "status": "inactive"}
        
        flow.status = FlowStatus.INACTIVE
        tenant_db.commit()
        
        # Handle trigger integrations for deactivated flows
        if flow.trigger_config:
            tenant_id = current_user.tenant_id
            trigger_type = flow.trigger_config.get('type')
            
            if trigger_type == 'schedule':
                asyncio.create_task(flow_scheduler.unschedule_flow(tenant_id, flow_id))
                logger.info(f"Unscheduled flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'file_change':
                asyncio.create_task(file_watcher_service.unwatch_flow(tenant_id, flow_id))
                logger.info(f"Stopped file watcher for flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'mqtt':
                asyncio.create_task(mqtt_listener_service.unwatch_flow(tenant_id, flow_id))
                logger.info(f"Stopped MQTT listener for flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'event':
                # Detach from the shared app MQTT connection (no-op for webhook/polling)
                asyncio.create_task(mqtt_listener_service.unwatch_event_flow(tenant_id, flow_id))

        logger.info(f"Flow {flow_id} deactivated by user {current_user.user_id}")
        return {"message": "Flow deactivated successfully", "status": "inactive"}

@router.post("/{flow_id}/draft")
async def set_flow_draft(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set flow back to draft status."""
    # Check permissions
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit modifying flows"
        )
    
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        if flow.status == FlowStatus.DRAFT:
            return {"message": "Flow is already in draft status", "status": "draft"}
        
        flow.status = FlowStatus.DRAFT
        tenant_db.commit()
        
        # Handle trigger integrations for draft flows
        if flow.trigger_config:
            tenant_id = current_user.tenant_id
            trigger_type = flow.trigger_config.get('type')
            
            if trigger_type == 'schedule':
                asyncio.create_task(flow_scheduler.unschedule_flow(tenant_id, flow_id))
                logger.info(f"Unscheduled flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'file_change':
                asyncio.create_task(file_watcher_service.unwatch_flow(tenant_id, flow_id))
                logger.info(f"Stopped file watcher for flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'mqtt':
                asyncio.create_task(mqtt_listener_service.unwatch_flow(tenant_id, flow_id))
                logger.info(f"Stopped MQTT listener for flow {flow_id} for tenant {tenant_id}")
            elif trigger_type == 'event':
                # Detach from the shared app MQTT connection (no-op for webhook/polling)
                asyncio.create_task(mqtt_listener_service.unwatch_event_flow(tenant_id, flow_id))

        logger.info(f"Flow {flow_id} set to draft by user {current_user.user_id}")
        return {"message": "Flow set to draft successfully", "status": "draft"}

@router.post("/{flow_id}/test")
async def test_flow(
    flow_id: str,
    test_data: Optional[Dict[str, Any]] = {},
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a flow with sample data."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # TODO: Implement flow execution engine
        # For now, just return a mock response
        return {
            "status": "success",
            "message": "Flow test initiated",
            "execution_id": "test-" + flow_id,
            "test_data": test_data
        }


@router.post("/{flow_id}/execute")
async def execute_flow_manually(
    flow_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually execute a flow with provided variables (supports both JSON and multipart/form-data)."""
    schema_name, tenant_id = get_tenant_info(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

        # SECURITY: Validate user has permission to execute this flow
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        flow_scope = flow.flow_scope or 'user'

        if user_role == "INSTANCE_ADMIN":
            # SECURITY FIX: Instance admin can execute any flow EXCEPT other users' private flows
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to execute this user's private flow"
                )
        elif user_role == "TENANT_ADMIN":
            # Tenant admin can execute flows in their tenant
            if flow.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only execute flows from your tenant"
                )
            # SECURITY FIX: Respect user-scoped privacy
            if flow_scope == 'user' and flow.created_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to execute this user's private flow"
                )
        elif user_role in ["FLOW_DESIGNER", "FLOW_EDITOR", "FLOW_EXECUTOR", "EXECUTION_MONITOR"]:
            # Validate access based on flow scope
            if flow_scope == 'global':
                # Global flows are accessible to all
                pass
            elif flow_scope == 'tenant':
                # Verify flow belongs to user's tenant
                if flow.tenant_id != current_user.tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have permission to execute flows from other tenants"
                    )
            elif flow_scope == 'user':
                # User flows must be created by current user
                if flow.created_by != current_user.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only execute flows you created"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to execute flows"
            )

        # Check if flow is active (optional - can execute draft flows too)
        if flow.status not in [FlowStatus.ACTIVE, FlowStatus.DRAFT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow must be active or in draft status to execute"
            )

        # Store flow_definition for balance check later
        flow_definition = flow.flow_definition
        flow_name = flow.flow_name

    # Create execution engine with both schema and tenant_id
    engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

    # Process input based on content type
    processed_variables = {}
    is_simulation = False

    if request and request.headers:
        content_type = request.headers.get("content-type", "")

        if "multipart/form-data" in content_type:
            # Handle multipart/form-data (with files)
            import base64
            form_data = await request.form()
            file_data = {}
            
            for field_name, field_value in form_data.items():
                # Check if this is a file upload
                if hasattr(field_value, 'read') and hasattr(field_value, 'filename'):
                    # This is a file
                    content = await field_value.read()
                    logger.info(f"Processing file upload: {field_value.filename}, size: {len(content)} bytes")
                    
                    # Store file information
                    file_info = {
                        "filename": field_value.filename,
                        "content_type": field_value.content_type,
                        "size": len(content),
                        "content": base64.b64encode(content).decode('utf-8')
                    }
                    logger.info(f"Encoded file {field_value.filename}: base64 length: {len(file_info['content'])} chars")
                    
                    # Handle multiple files with same field name
                    if field_name in file_data:
                        if not isinstance(file_data[field_name], list):
                            file_data[field_name] = [file_data[field_name]]
                        file_data[field_name].append(file_info)
                    else:
                        file_data[field_name] = file_info
                else:
                    # Regular form field
                    # Try to parse JSON strings
                    try:
                        import json
                        value = json.loads(field_value)
                    except:
                        value = field_value
                    processed_variables[field_name] = value
            
            # Add file data to variables
            processed_variables.update(file_data)
            logger.info(f"File data added to variables: {list(file_data.keys())}")
            for key, value in file_data.items():
                if isinstance(value, dict) and 'content' in value:
                    logger.info(f"  {key}: filename={value.get('filename')}, content_length={len(value.get('content', ''))}")
            
        else:
            # Handle JSON request
            try:
                body = await request.json()
                
                # Check if it's a ManualExecuteRequest format
                if isinstance(body, dict):
                    if "variables" in body:
                        raw_variables = body.get("variables", {})
                        is_simulation = body.get("is_simulation", False)
                    elif "input_data" in body:
                        raw_variables = body.get("input_data", {})
                        is_simulation = body.get("is_simulation", False)
                    else:
                        # Direct variables in body
                        raw_variables = body
                else:
                    raw_variables = {}
                    
                # Preprocess variables
                processed_variables = preprocess_variables(raw_variables) if raw_variables else {}
                
            except:
                # If JSON parsing fails, use empty variables
                processed_variables = {}
    else:
        # No request object provided
        processed_variables = {}
    
    # Prepare trigger data with processed variables
    trigger_data = {
        "trigger_type": "manual",
        "triggered_by": current_user.user_id,
        "variables": processed_variables,
        "timestamp": datetime.utcnow().isoformat(),
        "is_simulation": is_simulation
    }

    # PRE-EXECUTION BALANCE CHECK
    # Check balance BEFORE creating execution record to prevent execution if insufficient
    logger.info(f"PRE-EXECUTION BALANCE CHECK: flow_id={flow_id}, is_simulation={is_simulation}")
    try:
        # Skip balance check for simulations
        if not is_simulation:
            # Find the first action node to check balance
            nodes = flow_definition.get('nodes', [])
            first_action_node = None
            for node in nodes:
                if node.get('type') == 'action':
                    first_action_node = node
                    break

            logger.info(f"First action node found: {first_action_node is not None}")

            # Only check balance if there are action nodes (services to execute)
            if first_action_node:
                # Extract app_id and service_id from node.data
                node_data = first_action_node.get('data', {})
                app_id = node_data.get('app_id') or node_data.get('appId')
                service_id = node_data.get('service_id') or node_data.get('serviceId')

                logger.info(f"Balance check: app_id={app_id}, service_id={service_id}, tenant_id={tenant_id}")

                if app_id and service_id:
                    # Estimate data transfer size
                    try:
                        trigger_data_json = json.dumps(trigger_data)
                        estimated_data_kb = len(trigger_data_json.encode('utf-8')) / 1024.0
                    except:
                        estimated_data_kb = 0

                    # Check balance before creating execution
                    with get_tenant_db(schema_name) as tenant_db:
                        # This will raise InsufficientBalanceError if balance is insufficient
                        balance_enforcer.check_balance_for_service(
                            tenant_id=tenant_id,
                            app_id=app_id,
                            service_id=service_id,
                            estimated_data_kb=estimated_data_kb,
                            db=tenant_db
                        )
    except InsufficientBalanceError as e:
        # Return HTTP 402 Payment Required with detailed error information
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": e.message,
                "error_code": "INSUFFICIENT_BALANCE",
                "required_amount": e.required_amount,
                "available_amount": e.available_amount,
                "deficit": e.required_amount - e.available_amount,
                "suggested_topup": e.suggested_topup,
                "service_name": e.service_name,
                "app_name": e.app_name,
                "flow_name": flow_name
            }
        )

    # Create execution record first to get execution_id
    import uuid
    from db.models import FlowExecution, ExecutionStatus

    execution_id = str(uuid.uuid4())

    with get_tenant_db(schema_name) as tenant_db:
        execution = FlowExecution(
            execution_id=execution_id,
            flow_id=flow_id,
            trigger_type="manual",
            trigger_data=trigger_data,
            status=ExecutionStatus.RUNNING
        )
        tenant_db.add(execution)
        tenant_db.commit()
    
    # Check if this should be a quick validation run for immediate error feedback
    if processed_variables and len(processed_variables) > 0:
        # For manual trigger with variables, run a quick validation first
        try:
            # Quick validation: try to execute the first few nodes to catch syntax errors
            test_engine = ExecutionEngine(schema_name, tenant_id)
            # Just validate, don't actually execute
            logger.info(f"Running validation for manual trigger on flow {flow_id}")
        except Exception as e:
            # If validation fails, return error immediately instead of starting background task
            logger.error(f"Flow validation failed during manual trigger: {e}")
            with get_tenant_db(schema_name) as tenant_db:
                # Update execution status to failed
                execution = tenant_db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = str(e)
                    tenant_db.commit()
            
            # Return error information to the UI
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Flow execution failed: {str(e)}"
            )
    
    # Execute flow in background with proper async handling
    async def run_flow_execution():
        """Wrapper to ensure proper async execution"""
        # Wait for WebSocket to connect before starting execution
        # This prevents race condition where execution starts before WebSocket subscribes
        import asyncio
        logger.info(f"Waiting 500ms for WebSocket to connect for execution {execution_id}...")
        await asyncio.sleep(0.5)
        logger.info(f"Starting execution {execution_id} after WebSocket delay")

        # Log WebSocket connection stats before starting
        from services.websocket_manager import manager
        stats = manager.get_connection_stats()
        logger.info(f"WebSocket stats before execution: {stats}")

        try:
            await engine.execute_flow_with_id(
                flow_id,
                execution_id,
                trigger_data,
                "manual"
            )
        except Exception as e:
            logger.error(f"Flow execution failed: {e}", exc_info=True)
            # Update execution status in database
            with get_tenant_db(schema_name) as tenant_db:
                execution = tenant_db.query(FlowExecution).filter(
                    FlowExecution.execution_id == execution_id
                ).first()
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = str(e)
                    tenant_db.commit()

    background_tasks.add_task(run_flow_execution)
    
    return {
        "status": "success",
        "message": "Flow execution started",
        "flow_id": flow_id,
        "execution_id": execution_id,
        "trigger_type": "manual",
        "variables": processed_variables,
        "note": "Check execution logs for detailed results. Use execute-sync endpoint for immediate error feedback."
    }

@router.post("/{flow_id}/execute-with-files-legacy")
async def execute_flow_with_files_legacy(
    flow_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Execute a flow with file uploads (multipart/form-data handler)."""
    # Check if this is a multipart request
    content_type = request.headers.get("content-type", "") if request else ""
    
    if "multipart/form-data" not in content_type:
        # Not a multipart request, delegate to the main handler
        return await execute_flow_manually(
            flow_id=flow_id,
            background_tasks=background_tasks,
            request=None,  # Will be parsed from body
            current_user=current_user,
            db=db
        )
    
    # Handle multipart/form-data with files
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Check if flow is active (optional - can execute draft flows too)
        if flow.status not in [FlowStatus.ACTIVE, FlowStatus.DRAFT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow must be active or in draft status to execute"
            )
    
    # Process form data and files
    processed_variables = {}
    file_data = {}
    
    # Handle file uploads
    if files:
        for file in files:
            # Read file content
            content = await file.read()
            
            # Store file information
            file_info = {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(content),
                "content_base64": base64.b64encode(content).decode('utf-8')
            }
            
            # Group files by field name (assuming field name is passed as part of filename)
            field_name = file.filename.split('_')[0] if '_' in file.filename else 'files'
            if field_name not in file_data:
                file_data[field_name] = []
            file_data[field_name].append(file_info)
    
    # Merge file data with other variables
    processed_variables.update(file_data)
    
    # Create execution engine with both schema and tenant_id
    engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

    # Prepare trigger data with processed variables
    trigger_data = {
        "trigger_type": trigger_type,
        "triggered_by": current_user.user_id,
        "variables": processed_variables,
        "timestamp": datetime.utcnow().isoformat(),
        "has_files": bool(files)
    }
    
    # Create execution record first to get execution_id
    import uuid
    from db.models import FlowExecution, ExecutionStatus
    
    execution_id = str(uuid.uuid4())
    
    with get_tenant_db(schema_name) as tenant_db:
        execution = FlowExecution(
            execution_id=execution_id,
            flow_id=flow_id,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            status=ExecutionStatus.RUNNING,
            execution_data={}
        )
        tenant_db.add(execution)
        tenant_db.commit()
    
    # Execute flow in background
    background_tasks.add_task(
        engine.execute_flow,
        flow_id,
        trigger_data,
        execution_id
    )
    
    return {
        "status": "success",
        "message": "Flow execution started",
        "flow_id": flow_id,
        "execution_id": execution_id,
        "trigger_type": trigger_type,
        "files_processed": len(files) if files else 0
    }

@router.post("/{flow_id}/execute-sync")
async def execute_flow_sync(
    flow_id: str,
    request: ManualExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a flow synchronously and return the result."""
    schema_name, tenant_id = get_tenant_info(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        if not flow.is_synchronous:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow is not marked as synchronous"
            )
        
        # Check if flow is active
        if flow.status != FlowStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow must be active to execute"
            )
    
    # Create execution engine with both schema and tenant_id
    engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

    # Preprocess variables to handle string representations of arrays/objects
    processed_variables = preprocess_variables(request.variables)
    
    # Prepare trigger data with processed variables
    trigger_data = {
        "trigger_type": "manual",
        "triggered_by": current_user.user_id,
        "variables": processed_variables,
        "timestamp": datetime.utcnow().isoformat(),
        "is_simulation": request.is_simulation
    }
    
    try:
        # Execute flow synchronously
        result = await engine.execute_flow_sync(
            flow_id,
            trigger_data,
            "manual",
            timeout=flow.sync_timeout
        )
        
        # Return the response with proper status code and headers.
        # engine.execute_flow_sync returns different shapes depending on the
        # response node's output format: a metadata dict with status/headers
        # plus "data" (json) or "body" (html); a raw string ("text"/"xml");
        # or a raw result_data value / completion dict. Handle all of them.
        from fastapi import Response
        if isinstance(result, dict) and "status" in result and ("data" in result or "body" in result):
            body = result.get("data", result.get("body"))
            status_code = result["status"] if isinstance(result["status"], int) else 200
            headers = {k: str(v) for k, v in (result.get("headers") or {}).items()}
            content = body if isinstance(body, str) else json.dumps(body)
        else:
            status_code = 200
            headers = {}
            content = result if isinstance(result, str) else json.dumps(result)
        return Response(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type="application/json"
        )
        
    except InsufficientBalanceError as e:
        # Return HTTP 402 Payment Required with detailed error information
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": e.message,
                "error_code": "INSUFFICIENT_BALANCE",
                "required_amount": e.required_amount,
                "available_amount": e.available_amount,
                "deficit": e.required_amount - e.available_amount,
                "suggested_topup": e.suggested_topup,
                "service_name": e.service_name,
                "app_name": e.app_name
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Synchronous flow execution failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Flow execution failed"
        )

@router.post("/{flow_id}/validate")
async def validate_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate a flow structure for synchronous execution."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Only validate if flow is marked as synchronous
        if not flow.is_synchronous:
            return {
                "is_valid": True,
                "errors": [],
                "message": "Flow is not marked as synchronous, no validation needed"
            }
        
        # Validate flow structure
        validator = FlowValidator(db=db, tenant_id=current_user.tenant_id)
        is_valid, errors = validator.validate_synchronous_flow(flow.flow_definition)
        
        return {
            "is_valid": is_valid,
            "errors": [
                {
                    "node_id": error.node_id,
                    "message": error.message,
                    "type": error.error_type
                }
                for error in errors
            ],
            "message": "Flow validation complete"
        }

@router.post("/{flow_id}/validate-comprehensive")
async def validate_flow_comprehensive(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Comprehensive validation of a flow including mandatory parameters."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Validate flow structure comprehensively
        validator = FlowValidator(db=db, tenant_id=current_user.tenant_id)
        is_valid, errors = validator.validate_flow_comprehensive(flow.flow_definition)
        
        # Group errors by node for easier consumption
        errors_by_node = {}
        for error in errors:
            if error.node_id not in errors_by_node:
                errors_by_node[error.node_id] = []
            error_dict = {
                "message": error.message,
                "type": error.error_type
            }
            if hasattr(error, 'field') and error.field:
                error_dict["field"] = error.field
            if hasattr(error, 'suggestion') and error.suggestion:
                error_dict["suggestion"] = error.suggestion
            errors_by_node[error.node_id].append(error_dict)
        
        return {
            "is_valid": is_valid,
            "errors": [
                {
                    "node_id": error.node_id,
                    "message": error.message,
                    "type": error.error_type,
                    **({"field": error.field} if hasattr(error, 'field') and error.field else {}),
                    **({"suggestion": error.suggestion} if hasattr(error, 'suggestion') and error.suggestion else {})
                }
                for error in errors
            ],
            "errors_by_node": errors_by_node,
            "total_errors": sum(1 for e in errors if e.error_type == "error"),
            "total_warnings": sum(1 for e in errors if e.error_type == "warning"),
            "message": "Flow validation complete"
        }

class FlowValidationRequest(BaseModel):
    flow_definition: FlowDefinition
    
@router.post("/{flow_id}/validate-current")
async def validate_current_flow_state(
    flow_id: str,
    request: FlowValidationRequest,
    current_user_or_collab: Optional[Union[User, dict]] = Depends(get_current_user_or_collaboration),
    db: Session = Depends(get_db)
):
    """Validate the current flow state from the frontend without requiring it to be saved."""
    if not current_user_or_collab:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if this is a collaboration participant
    if isinstance(current_user_or_collab, dict) and current_user_or_collab.get("is_collaboration"):
        # Collaboration participant - check if they're accessing the right flow
        if current_user_or_collab["flow_id"] != flow_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only validate the flow you're collaborating on"
            )
        
        tenant_id = current_user_or_collab["tenant_id"]
    else:
        # Regular user
        tenant_id = current_user_or_collab.tenant_id
    
    # Validate flow structure comprehensively with database session
    validator = FlowValidator(db=db, tenant_id=tenant_id)
    is_valid, errors = validator.validate_flow_comprehensive(request.flow_definition.dict())
    
    # Group errors by node for easier consumption
    errors_by_node = {}
    for error in errors:
        if error.node_id not in errors_by_node:
            errors_by_node[error.node_id] = []
        error_dict = {
            "message": error.message,
            "type": error.error_type
        }
        if hasattr(error, 'field') and error.field:
            error_dict["field"] = error.field
        if hasattr(error, 'suggestion') and error.suggestion:
            error_dict["suggestion"] = error.suggestion
        errors_by_node[error.node_id].append(error_dict)
    
    return {
        "is_valid": is_valid,
        "errors": [
            {
                "node_id": error.node_id,
                "message": error.message,
                "type": error.error_type,
                **({"field": error.field} if hasattr(error, 'field') and error.field else {}),
                **({"suggestion": error.suggestion} if hasattr(error, 'suggestion') and error.suggestion else {})
            }
            for error in errors
        ],
        "errors_by_node": errors_by_node,
        "total_errors": sum(1 for e in errors if e.error_type == "error"),
        "total_warnings": sum(1 for e in errors if e.error_type == "warning"),
        "message": "Flow validation complete"
    }

class DebugExecuteRequest(BaseModel):
    trigger_data: Dict[str, Any] = {}
    mode: str = "step"  # "step" or "run"

@router.post("/test-post")
async def test_post_endpoint():
    """Simple test endpoint to verify POST requests work."""
    print("=== TEST POST ENDPOINT HIT ===")
    return {"message": "POST request successful", "timestamp": datetime.utcnow().isoformat()}

@router.post("/{flow_id}/execute-direct")
async def execute_flow_direct(
    flow_id: str,
    request: ManualExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a specific flow directly, bypassing application event triggers.
    
    This endpoint allows direct execution of any flow, including those with manual triggers,
    without needing to go through the application event system. The flow can be in any status
    (active, draft, or inactive) and will execute only the specified flow.
    
    If the flow is marked as synchronous (is_synchronous=true), it will execute synchronously
    and return the result. Otherwise, it executes asynchronously and returns an execution ID.
    """
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    
    # Create execution engine with both schema and tenant_id
    engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

    # Preprocess variables to handle string representations of arrays/objects
    processed_variables = preprocess_variables(request.variables)
    
    # Prepare trigger data for direct execution
    trigger_data = {
        "trigger_type": "api_direct",
        "triggered_by": current_user.user_id,
        "variables": processed_variables,
        "timestamp": datetime.utcnow().isoformat(),
        "is_simulation": request.is_simulation,
        "direct_execution": True,
        "bypass_application_trigger": True
    }
    
    # Check if flow is synchronous
    if flow.is_synchronous:
        # Execute synchronously and return the result
        try:
            # Execute flow synchronously with extended timeout for direct execution
            timeout = flow.sync_timeout if hasattr(flow, 'sync_timeout') and flow.sync_timeout else 60
            result = await engine.execute_flow_sync(
                flow_id,
                trigger_data,
                "api_direct",
                timeout=timeout
            )
            
            # Return the response with proper status code and headers
            from fastapi import Response
            
            # Handle different response types based on format
            if isinstance(result, dict):
                # Structured response (JSON, HTML format)
                if "body" in result:
                    # HTML format - return body content
                    return Response(
                        content=result["body"],
                        status_code=result["status"],
                        headers=result["headers"],
                        media_type="text/html"
                    )
                else:
                    # JSON format - return JSON structure
                    return Response(
                        content=json.dumps(result),
                        status_code=result.get("status", 200),
                        headers=result.get("headers", {}),
                        media_type="application/json"
                    )
            elif isinstance(result, str) and (result.startswith("<?xml") or result.startswith("<response>")):
                # XML format - return XML content
                return Response(
                    content=result,
                    status_code=200,
                    headers={"Content-Type": "application/xml"},
                    media_type="application/xml"
                )
            else:
                # Text format - return raw text
                return Response(
                    content=str(result),
                    status_code=200,
                    headers={"Content-Type": "text/plain"},
                    media_type="text/plain"
                )

        except InsufficientBalanceError as e:
            # Return HTTP 402 Payment Required with detailed error information
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": e.message,
                    "error_code": "INSUFFICIENT_BALANCE",
                    "required_amount": e.required_amount,
                    "available_amount": e.available_amount,
                    "deficit": e.required_amount - e.available_amount,
                    "suggested_topup": e.suggested_topup,
                    "service_name": e.service_name,
                    "app_name": e.app_name
                }
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Direct synchronous flow execution failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Direct flow execution failed"
            )
    else:
        # Execute asynchronously (original behavior)
        # Create execution record first to get execution_id
        import uuid
        from db.models import FlowExecution, ExecutionStatus
        
        execution_id = str(uuid.uuid4())
        
        with get_tenant_db(schema_name) as tenant_db:
            execution = FlowExecution(
                execution_id=execution_id,
                flow_id=flow_id,
                trigger_type="api_direct",
                trigger_data=trigger_data,
                status=ExecutionStatus.RUNNING,
                execution_data={
                    'direct_execution': True,
                    'bypass_application_trigger': True,
                    'original_trigger_type': flow.trigger_config.get('type') if flow.trigger_config else None
                }
            )
            tenant_db.add(execution)
            tenant_db.commit()
        
        # Execute flow in background with proper async handling
        async def run_direct_flow_execution():
            """Wrapper for direct flow execution"""
            # Wait for WebSocket to connect before starting execution
            # This prevents race condition where execution starts before WebSocket subscribes
            import asyncio
            logger.info(f"Waiting 500ms for WebSocket to connect for execution {execution_id}...")
            await asyncio.sleep(0.5)
            logger.info(f"Starting execution {execution_id} after WebSocket delay")

            # Log WebSocket connection stats before starting
            from services.websocket_manager import manager
            stats = manager.get_connection_stats()
            logger.info(f"WebSocket stats before execution: {stats}")

            try:
                await engine.execute_flow_with_id(
                    flow_id,
                    execution_id,
                    trigger_data,
                    "api_direct"
                )
            except Exception as e:
                logger.error(f"Direct flow execution failed: {e}", exc_info=True)

        background_tasks.add_task(run_direct_flow_execution)
        
        return {
            "status": "success",
            "message": "Flow direct execution started",
            "flow_id": flow_id,
            "execution_id": execution_id,
            "trigger_type": "api_direct",
            "variables": processed_variables,
            "direct_execution": True
        }

@router.post("/{flow_id}/execute-internal")
async def execute_flow_internal(
    flow_id: str,
    request: ManualExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Execute a flow internally from published applications without authentication.
    
    This endpoint is specifically for internal calls from published flow applications
    and bypasses user authentication. It should only be used by the internal system.
    """
    # Use the main tenant schema for internal calls
    schema_name = "main"
    tenant_id = "main"
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # For internal calls, we allow execution regardless of flow status
        logger.info(f"Internal flow execution request for {flow_id}: {flow.flow_name}")
        
        try:
            # Create execution engine for this tenant
            engine = ExecutionEngine(tenant_schema=schema_name, tenant_id=tenant_id)
            
            # Execute flow in background
            execution_id = await engine.execute_flow(
                flow_id=flow_id,
                trigger_data=request.variables,
                trigger_type="internal"
            )
            
            return {"execution_id": execution_id, "status": "started", "flow_name": flow.flow_name}
            
        except Exception as e:
            logger.error(f"Failed to execute flow {flow_id} internally: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Flow execution failed: {str(e)}"
            )

@router.post("/{flow_id}/execute-internal-sync")
async def execute_flow_internal_sync(
    flow_id: str,
    request: ManualExecuteRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Execute a flow internally (synchronously) from published applications with user context.
    
    This endpoint is specifically for internal calls from published flow applications
    and receives user context via headers to maintain access to subscriptions.
    """
    # Extract user context from headers
    tenant_id = http_request.headers.get('X-Internal-Tenant-ID', 'main')
    user_id = http_request.headers.get('X-Internal-User-ID')
    parent_execution_id = http_request.headers.get('X-Internal-Execution-ID')
    
    logger.info(f"Internal sync call with context: tenant_id={tenant_id}, user_id={user_id}, parent_execution={parent_execution_id}")
    
    # Determine schema name based on tenant
    schema_name = "main"  # You might want to map tenant_id to schema_name if using multi-tenant schemas
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # For internal calls, we allow execution regardless of flow status
        logger.info(f"Internal synchronous flow execution request for {flow_id}: {flow.flow_name}")
        
        try:
            # Create execution engine for this tenant with user context
            engine = ExecutionEngine(tenant_schema=schema_name, tenant_id=tenant_id, user_id=user_id)
            
            # Preprocess variables to handle string representations of arrays/objects
            processed_variables = preprocess_variables(request.variables)
            
            # Execute flow synchronously using the proper sync method
            # Add direct_execution flag to bypass synchronous check for internal calls
            trigger_data_with_flags = {
                "variables": processed_variables,  # Properly structure variables
                "direct_execution": True,  # Allow sync execution even for async flows
                "user_id": user_id,  # Pass user context for subscription access
                "tenant_id": tenant_id,
                "parent_execution_id": parent_execution_id
            }
            
            result = await engine.execute_flow_sync(
                flow_id=flow_id,
                trigger_data=trigger_data_with_flags,
                trigger_type="internal",
                timeout=30
            )
            
            # Handle both string and dict results
            execution_id = None
            if isinstance(result, dict):
                execution_id = result.get("execution_id")
            
            # Return the actual flow execution results
            return {
                "execution_id": execution_id,
                "status": "completed", 
                "flow_name": flow.flow_name,
                "data": result
            }
            
        except Exception as e:
            logger.error(f"Failed to execute flow {flow_id} internally (sync): {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Flow execution failed: {str(e)}"
            )

@router.post("/{flow_id}/execute-direct-sync")
async def execute_flow_direct_sync(
    flow_id: str,
    request: ManualExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a specific flow directly and synchronously.
    
    This endpoint allows direct synchronous execution of flows, including those with manual triggers.
    The flow can be in any status and will return the result immediately.
    """
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    
    # Create execution engine with both schema and tenant_id
    engine = ExecutionEngine(schema_name, tenant_id, user_id=current_user.user_id)

    # Preprocess variables to handle string representations of arrays/objects
    processed_variables = preprocess_variables(request.variables)
    
    # Prepare trigger data for direct execution
    trigger_data = {
        "trigger_type": "api_direct_sync",
        "triggered_by": current_user.user_id,
        "variables": processed_variables,
        "timestamp": datetime.utcnow().isoformat(),
        "is_simulation": request.is_simulation,
        "direct_execution": True,
        "bypass_application_trigger": True
    }
    
    try:
        # Execute flow synchronously with extended timeout for direct execution
        timeout = flow.sync_timeout if hasattr(flow, 'sync_timeout') and flow.sync_timeout else 60
        result = await engine.execute_flow_sync(
            flow_id,
            trigger_data,
            "api_direct_sync",
            timeout=timeout
        )
        
        # Return the response with proper status code and headers
        from fastapi import Response
        
        # Handle different response types based on format
        if isinstance(result, dict):
            # Structured response (JSON, HTML format)
            if "body" in result:
                # HTML format - return body content
                return Response(
                    content=result["body"],
                    status_code=result["status"],
                    headers=result["headers"],
                    media_type="text/html"
                )
            else:
                # JSON format - return JSON structure
                return Response(
                    content=json.dumps(result),
                    status_code=result.get("status", 200),
                    headers=result.get("headers", {}),
                    media_type="application/json"
                )
        elif isinstance(result, str) and (result.startswith("<?xml") or result.startswith("<response>")):
            # XML format - return XML content
            return Response(
                content=result,
                status_code=200,
                headers={"Content-Type": "application/xml"},
                media_type="application/xml"
            )
        else:
            # Text format - return raw text
            return Response(
                content=str(result),
                status_code=200,
                headers={"Content-Type": "text/plain"},
                media_type="text/plain"
            )


    except InsufficientBalanceError as e:
        # Return HTTP 402 Payment Required with detailed error information
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": e.message,
                "error_code": "INSUFFICIENT_BALANCE",
                "required_amount": e.required_amount,
                "available_amount": e.available_amount,
                "deficit": e.required_amount - e.available_amount,
                "suggested_topup": e.suggested_topup,
                "service_name": e.service_name,
                "app_name": e.app_name
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Direct synchronous flow execution failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Direct flow execution failed"
        )

@router.get("/{flow_id}/sample-code")
async def generate_sample_code(
    flow_id: str,
    language: str = "python",
    include_sync: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate sample code for executing a flow with API key authentication.
    
    Supports multiple programming languages and shows both async and sync execution examples.
    """
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        
        # Get user's API keys or create one if they don't have any
        user_api_keys = db.query(APIKey).filter(
            APIKey.user_id == current_user.user_id,
            APIKey.is_active == True
        ).limit(1).all()
        
        if not user_api_keys:
            # Auto-create an API key for the user
            import uuid
            import secrets
            import hashlib
            from datetime import datetime, timedelta
            
            raw_key = secrets.token_urlsafe(32)
            full_api_key = f"ioflow_{raw_key}"
            key_hash = hashlib.sha256(full_api_key.encode()).hexdigest()
            key_prefix = full_api_key[:12]
            
            new_api_key = APIKey(
                key_hash=key_hash,
                key_prefix=key_prefix,
                name="Auto-generated for Sample Code",
                description="Automatically created API key for flow execution",
                user_id=current_user.user_id,
                scopes=json.dumps(["read", "write", "execute"]),
                is_active=True,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),  # 1 year expiry
                usage_count=0
            )
            
            db.add(new_api_key)
            db.commit()
            db.refresh(new_api_key)
            
            api_key_example = full_api_key
            user_has_api_keys = True
        else:
            # For existing keys, we can't show the full key, so we'll create a new one anyway for samples
            import uuid
            import secrets
            import hashlib
            from datetime import datetime, timedelta
            
            raw_key = secrets.token_urlsafe(32)
            full_api_key = f"ioflow_{raw_key}"
            key_hash = hashlib.sha256(full_api_key.encode()).hexdigest()
            key_prefix = full_api_key[:12]
            
            sample_api_key = APIKey(
                key_hash=key_hash,
                key_prefix=key_prefix,
                name="Sample Code API Key",
                description="API key created for sample code generation",
                user_id=current_user.user_id,
                scopes=json.dumps(["read", "write", "execute"]),
                is_active=True,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365),
                usage_count=0
            )
            
            db.add(sample_api_key)
            db.commit()
            
            api_key_example = full_api_key
            user_has_api_keys = True
        
        # Extract trigger configuration and variables with defaults
        trigger_config = flow.trigger_config or {}
        manual_variables = trigger_config.get('manual_variables', [])
        
        # Generate variable examples using actual default values from flow configuration
        variable_examples = {}
        for var in manual_variables:
            var_name = var.get('name', 'variable')
            var_type = var.get('type', var.get('dataType', 'string'))
            ui_control = var.get('uiControl', '')
            default_value = var.get('default', var.get('defaultValue', ''))
            
            # Check if this is a file input
            is_file_input = (var_type == 'file' or ui_control == 'file')
            
            # Use the actual default value if available, otherwise provide realistic examples
            if default_value and not is_file_input:
                # Use the configured default value (except for files)
                if var_type == 'number':
                    try:
                        variable_examples[var_name] = float(default_value) if '.' in str(default_value) else int(default_value)
                    except (ValueError, TypeError):
                        variable_examples[var_name] = default_value
                elif var_type == 'boolean':
                    variable_examples[var_name] = bool(default_value) if isinstance(default_value, bool) else str(default_value).lower() in ('true', '1', 'yes')
                else:
                    variable_examples[var_name] = default_value
            elif is_file_input:
                # Generate realistic file object example for file inputs
                # Determine likely file type from validation or variable name
                validation = var.get('validation', {})
                accept_types = validation.get('accept', '.pdf,.doc,.docx')
                
                if '.pdf' in accept_types.lower():
                    mime_type = 'application/pdf'
                    file_ext = '.pdf'
                elif '.docx' in accept_types.lower():
                    mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    file_ext = '.docx'
                elif '.doc' in accept_types.lower() and '.docx' not in accept_types.lower():
                    mime_type = 'application/msword'
                    file_ext = '.doc'
                elif '.jpg' in accept_types.lower() or '.jpeg' in accept_types.lower():
                    mime_type = 'image/jpeg'
                    file_ext = '.jpg'
                elif '.png' in accept_types.lower():
                    mime_type = 'image/png'
                    file_ext = '.png'
                else:
                    mime_type = 'application/pdf'
                    file_ext = '.pdf'
                
                # Create realistic file object
                variable_examples[var_name] = {
                    "data": f"data:{mime_type};base64,JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCg==",
                    "name": f"sample-{var_name}{file_ext}",
                    "type": mime_type,
                    "size": 12345
                }
            else:
                # Provide realistic defaults based on variable name and type
                if var_type == 'string':
                    if 'phone' in var_name.lower() or 'mobile' in var_name.lower():
                        variable_examples[var_name] = "+1234567890"
                    elif 'email' in var_name.lower():
                        variable_examples[var_name] = "user@example.com"
                    elif 'name' in var_name.lower():
                        variable_examples[var_name] = "John Doe"
                    elif 'template' in var_name.lower():
                        variable_examples[var_name] = "welcome_template"
                    elif 'message' in var_name.lower():
                        variable_examples[var_name] = "Hello, this is a test message"
                    else:
                        variable_examples[var_name] = "sample_value"
                elif var_type == 'number':
                    variable_examples[var_name] = 1
                elif var_type == 'boolean':
                    variable_examples[var_name] = True
                elif var_type == 'array':
                    variable_examples[var_name] = ["item1", "item2"]
                elif var_type == 'object':
                    variable_examples[var_name] = {"key": "value"}
                else:
                    variable_examples[var_name] = "sample_value"
        
        # If no manual variables defined, add some common examples
        if not variable_examples:
            variable_examples = {
                "input_data": "Your input data here",
                "process_mode": "standard"
            }
        
        # Generate code based on language
        if language.lower() == "python":
            code = _generate_python_code(flow_id, flow.flow_name, api_key_example, variable_examples, include_sync)
        elif language.lower() == "javascript" or language.lower() == "js":
            code = _generate_javascript_code(flow_id, flow.flow_name, api_key_example, variable_examples, include_sync)
        elif language.lower() == "curl":
            code = _generate_curl_code(flow_id, flow.flow_name, api_key_example, variable_examples, flow.is_synchronous)
        elif language.lower() == "php":
            code = _generate_php_code(flow_id, flow.flow_name, api_key_example, variable_examples, include_sync)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")
        
        return {
            "flow_id": flow_id,
            "flow_name": flow.flow_name,
            "language": language,
            "trigger_type": trigger_config.get('type', 'manual'),
            "manual_variables": manual_variables,
            "variable_examples": variable_examples,
            "sample_code": code,
            "api_key_example": api_key_example,
            "user_has_api_keys": user_has_api_keys,
            "api_key_auto_generated": not user_api_keys,  # True if we created a new key
            "endpoints": {
                "async_execution": f"/api/v1/flows/{flow_id}/execute-direct",
                "sync_execution": f"/api/v1/flows/{flow_id}/execute-direct-sync"
            }
        }


@router.get("/{flow_id}/api-documentation")
async def get_flow_api_documentation(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate structured API documentation for a flow.

    Returns complete documentation including authentication, endpoints,
    parameters, response formats, error codes, and sample code in multiple languages.
    """
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

        # Extract trigger configuration
        trigger_config = flow.trigger_config or {}
        manual_variables = trigger_config.get('manual_variables', [])

        # Build parameter documentation
        parameters = []
        for var in manual_variables:
            var_name = var.get('name', 'variable')
            var_type = var.get('type', var.get('dataType', 'string'))
            ui_control = var.get('uiControl', '')
            default_value = var.get('default', var.get('defaultValue', ''))
            validation = var.get('validation', {})
            is_required = validation.get('required', False)
            is_file_input = (var_type == 'file' or ui_control == 'file')

            param_doc = {
                "name": var_name,
                "type": var_type,
                "required": is_required,
                "default": default_value if default_value else None,
                "description": var.get('description', ''),
                "is_file": is_file_input,
            }

            # Add validation rules if present
            if validation:
                rules = {}
                if validation.get('minLength'):
                    rules['min_length'] = validation['minLength']
                if validation.get('maxLength'):
                    rules['max_length'] = validation['maxLength']
                if validation.get('min') is not None:
                    rules['min'] = validation['min']
                if validation.get('max') is not None:
                    rules['max'] = validation['max']
                if validation.get('pattern'):
                    rules['pattern'] = validation['pattern']
                if validation.get('accept'):
                    rules['accepted_file_types'] = validation['accept']
                if validation.get('maxSize'):
                    rules['max_file_size'] = validation['maxSize']
                if rules:
                    param_doc['validation'] = rules

            # Add options for select/dropdown types
            options = var.get('options', [])
            if options:
                param_doc['options'] = options

            parameters.append(param_doc)

        # Build sample variable values for examples
        variable_examples = {}
        for var in manual_variables:
            var_name = var.get('name', 'variable')
            var_type = var.get('type', var.get('dataType', 'string'))
            default_value = var.get('default', var.get('defaultValue', ''))
            ui_control = var.get('uiControl', '')
            is_file_input = (var_type == 'file' or ui_control == 'file')

            if default_value and not is_file_input:
                variable_examples[var_name] = default_value
            elif is_file_input:
                variable_examples[var_name] = {
                    "data": "data:application/pdf;base64,<base64_encoded_content>",
                    "name": f"sample-{var_name}.pdf",
                    "type": "application/pdf",
                    "size": 12345
                }
            elif var_type == 'number':
                variable_examples[var_name] = 1
            elif var_type == 'boolean':
                variable_examples[var_name] = True
            elif var_type == 'array':
                variable_examples[var_name] = ["item1", "item2"]
            elif var_type == 'object':
                variable_examples[var_name] = {"key": "value"}
            else:
                if 'email' in var_name.lower():
                    variable_examples[var_name] = "user@example.com"
                elif 'phone' in var_name.lower() or 'mobile' in var_name.lower():
                    variable_examples[var_name] = "+1234567890"
                elif 'name' in var_name.lower():
                    variable_examples[var_name] = "John Doe"
                else:
                    variable_examples[var_name] = "sample_value"

        # Build the request body example
        request_body_example = {
            "trigger_type": "manual",
            "variables": variable_examples if variable_examples else {"input_data": "Your input data here"},
            "is_simulation": False
        }

        # Determine execution mode info
        is_sync = flow.is_synchronous or False
        sync_timeout = flow.sync_timeout if hasattr(flow, 'sync_timeout') and flow.sync_timeout else 30

        # Build dynamic sync response variants from Response nodes in the flow
        def _coerce_example(raw, field_type):
            """Convert a user-entered example string into a typed value."""
            if raw is None or raw == '':
                if field_type == 'number':
                    return 0
                if field_type == 'boolean':
                    return True
                if field_type == 'array':
                    return []
                if field_type == 'object':
                    return {}
                return "sample_value"
            if field_type == 'number':
                try:
                    if isinstance(raw, (int, float)):
                        return raw
                    return float(raw) if '.' in str(raw) else int(raw)
                except (ValueError, TypeError):
                    return 0
            if field_type == 'boolean':
                if isinstance(raw, bool):
                    return raw
                return str(raw).strip().lower() in ('true', '1', 'yes', 'y')
            if field_type in ('array', 'object'):
                if isinstance(raw, (list, dict)):
                    return raw
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return [] if field_type == 'array' else {}
            return str(raw)

        def _build_result_from_fields(fields):
            """Build a dict example from an outputFields list."""
            sample = {}
            for f in fields:
                name = (f.get('name') or '').strip()
                if not name:
                    continue
                sample[name] = _coerce_example(f.get('example'), f.get('type', 'string'))
            return sample

        def _wrap_sync_response(result_sample, output_format, status_code, headers):
            """Wrap the result in the shape returned by execute_flow_sync()."""
            fmt = (output_format or 'text').lower()
            hdrs = headers if isinstance(headers, dict) else {}
            if fmt == 'json':
                return {
                    "status": status_code or 200,
                    "headers": hdrs,
                    "data": result_sample if result_sample else {"key": "value"},
                    "execution_id": "<execution_uuid>"
                }
            if fmt == 'html':
                body = result_sample if isinstance(result_sample, str) else "<html>...</html>"
                return {
                    "status": status_code or 200,
                    "headers": hdrs,
                    "body": body,
                    "execution_id": "<execution_uuid>"
                }
            if fmt == 'xml':
                return "<response><result>...</result></response>"
            # default: text -> returns raw text
            if isinstance(result_sample, (dict, list)):
                return result_sample
            return result_sample if result_sample else "<flow_output_data>"

        flow_definition = flow.flow_definition or {}
        response_nodes = [n for n in flow_definition.get('nodes', []) if n.get('type') == 'response']

        sync_response_variants = []
        aggregated_output_fields = []
        seen_field_names = set()
        for idx, node in enumerate(response_nodes):
            node_data = node.get('data', {}) or {}
            fields = node_data.get('outputFields') or []
            if not isinstance(fields, list):
                fields = []
            output_format = node_data.get('outputFormat', 'text')
            try:
                node_status = int(node_data.get('statusCode', 200))
            except (ValueError, TypeError):
                node_status = 200
            raw_headers = node_data.get('headers')
            if isinstance(raw_headers, str):
                try:
                    node_headers = json.loads(raw_headers)
                except (json.JSONDecodeError, TypeError):
                    node_headers = {}
            elif isinstance(raw_headers, dict):
                node_headers = raw_headers
            else:
                node_headers = {}

            result_sample = _build_result_from_fields(fields) if fields else None
            wrapped = _wrap_sync_response(result_sample, output_format, node_status, node_headers)

            clean_fields = []
            for f in fields:
                name = (f.get('name') or '').strip()
                if not name:
                    continue
                entry = {
                    "name": name,
                    "type": f.get('type', 'string'),
                    "description": f.get('description', '') or '',
                    "example": _coerce_example(f.get('example'), f.get('type', 'string')),
                }
                clean_fields.append(entry)
                key = (name, entry['type'])
                if key not in seen_field_names:
                    seen_field_names.add(key)
                    aggregated_output_fields.append(entry)

            variant_label = node_data.get('label') or f"Response {idx + 1}"
            sync_response_variants.append({
                "label": variant_label,
                "status": node_status,
                "output_format": output_format,
                "has_schema": bool(clean_fields),
                "description": node_data.get('description') or f"Flow executed and result returned (sync mode, status {node_status}).",
                "example": wrapped,
                "fields": clean_fields,
            })

        # Fallback when no response nodes are defined
        if not sync_response_variants:
            sync_response_variants.append({
                "label": "Default",
                "status": 200,
                "output_format": "text",
                "has_schema": False,
                "description": "Flow executed and result returned (sync mode).",
                "example": {
                    "status": 200,
                    "headers": {},
                    "result": "<flow_output_data>"
                },
                "fields": [],
            })

        # Fetch the last completed execution to show as sample response
        sample_response = None
        try:
            last_execution = tenant_db.query(FlowExecution).filter(
                FlowExecution.flow_id == flow_id,
                FlowExecution.status == ExecutionStatus.COMPLETED
            ).order_by(FlowExecution.completed_at.desc()).first()

            if last_execution and last_execution.result_data:
                result_data = last_execution.result_data
                if isinstance(result_data, str):
                    try:
                        result_data = json.loads(result_data)
                    except (json.JSONDecodeError, TypeError):
                        pass

                def mask_value(value):
                    """Mask sensitive data in response values."""
                    if isinstance(value, dict):
                        return {k: mask_value(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [mask_value(item) for item in value[:3]] + (["..."] if len(value) > 3 else [])
                    if isinstance(value, str):
                        if len(value) <= 4:
                            return value
                        # Mask emails
                        if '@' in value and '.' in value:
                            parts = value.split('@')
                            return parts[0][:2] + '***@' + parts[1]
                        # Mask phone numbers
                        if value.startswith('+') and len(value) > 6:
                            return value[:4] + '****' + value[-2:]
                        # Mask long strings (tokens, keys, IDs that look sensitive)
                        if len(value) > 30 and not any(c == ' ' for c in value):
                            return value[:8] + '...' + value[-4:]
                        # Mask UUIDs
                        if len(value) == 36 and value.count('-') == 4:
                            return value[:8] + '-****-****-****-' + value[-12:]
                        return value
                    return value

                sample_response = {
                    "execution_id": last_execution.execution_id[:8] + '-****-****-****-' + last_execution.execution_id[-12:] if last_execution.execution_id and len(last_execution.execution_id) == 36 else "****",
                    "status": last_execution.status.value if hasattr(last_execution.status, 'value') else str(last_execution.status),
                    "result_data": mask_value(result_data) if isinstance(result_data, (dict, list)) else mask_value(str(result_data)),
                    "response_status": last_execution.response_status,
                }
        except Exception as e:
            logger.debug(f"Could not fetch sample execution for flow {flow_id}: {e}")

        return {
            "flow_id": flow_id,
            "flow_name": flow.flow_name,
            "description": flow.description or "",
            "status": flow.status.value if hasattr(flow.status, 'value') else str(flow.status),
            "execution_mode": {
                "is_synchronous": is_sync,
                "sync_timeout": sync_timeout,
                "description": "This flow executes synchronously and returns the result directly." if is_sync else "This flow executes asynchronously and returns an execution ID for tracking."
            },
            "authentication": {
                "methods": [
                    {
                        "name": "Access Token (Login)",
                        "type": "Bearer Token",
                        "description": "Obtain an access token by calling the login endpoint, then include it in the Authorization header.",
                        "login_endpoint": {
                            "method": "POST",
                            "path": "/api/v1/auth/login",
                            "content_type": "application/x-www-form-urlencoded",
                            "body": {
                                "username": "your_email@example.com",
                                "password": "your_password"
                            },
                            "response_example": {
                                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                                "token_type": "bearer",
                                "user_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                                "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                                "tenant_name": "Your Tenant",
                                "username": "your_name",
                                "role": "admin"
                            }
                        },
                        "header_format": "Authorization: Bearer <access_token>"
                    },
                    {
                        "name": "API Key",
                        "type": "Bearer Token",
                        "description": "Generate an API key from Settings > API Keys. Use it directly in the Authorization header without needing to call the login endpoint.",
                        "header_format": "Authorization: Bearer <YOUR_API_KEY>",
                        "key_format": "ioflow_<random_token>"
                    }
                ],
                "header": "Authorization",
                "note": "Both methods use the same Authorization header. Access tokens expire; API keys are long-lived."
            },
            "endpoints": {
                "async": {
                    "method": "POST",
                    "path": f"/api/v1/flows/{flow_id}/execute-direct",
                    "description": "Execute the flow asynchronously. Returns an execution ID immediately.",
                    "recommended": not is_sync
                },
                "sync": {
                    "method": "POST",
                    "path": f"/api/v1/flows/{flow_id}/execute-direct-sync",
                    "description": "Execute the flow synchronously. Waits for the result and returns it directly.",
                    "recommended": is_sync
                }
            },
            "request": {
                "content_type": "application/json",
                "body_schema": {
                    "trigger_type": {
                        "type": "string",
                        "required": True,
                        "default": "manual",
                        "description": "The trigger type. Use 'manual' for API calls."
                    },
                    "variables": {
                        "type": "object",
                        "required": True,
                        "description": "Key-value pairs of flow input variables."
                    },
                    "is_simulation": {
                        "type": "boolean",
                        "required": False,
                        "default": False,
                        "description": "Set to true for dry-run testing without real execution."
                    }
                },
                "example": request_body_example
            },
            "parameters": parameters,
            "responses": {
                "async_success": {
                    "status": 200,
                    "description": "Flow execution started successfully (async mode).",
                    "example": {
                        "execution_id": "<execution_uuid>",
                        "status": "running",
                        "message": "Flow execution started"
                    }
                },
                "sync_success": {
                    "status": sync_response_variants[0]["status"],
                    "description": sync_response_variants[0]["description"],
                    "example": sync_response_variants[0]["example"],
                    "fields": sync_response_variants[0]["fields"],
                    "variants": sync_response_variants,
                },
                "errors": [
                    {"status": 400, "description": "Bad Request - Invalid input variables or request format."},
                    {"status": 401, "description": "Unauthorized - Missing or invalid API key."},
                    {"status": 402, "description": "Payment Required - Insufficient account balance.", "example": {
                        "error": "Insufficient balance",
                        "error_code": "INSUFFICIENT_BALANCE",
                        "required_amount": 0.05,
                        "available_amount": 0.01,
                        "deficit": 0.04
                    }},
                    {"status": 404, "description": "Not Found - Flow ID does not exist."},
                    {"status": 500, "description": "Internal Server Error - Flow execution failed."}
                ]
            },
            "variable_examples": variable_examples,
            "trigger_type": trigger_config.get('type', 'manual'),
            "sample_response": sample_response,
            "output_fields": aggregated_output_fields,
        }


def _generate_python_code(flow_id: str, flow_name: str, api_key: str, variables: dict, include_sync: bool) -> str:
    """Generate Python sample code."""
    variables_json = json.dumps(variables, indent=8)
    
    async_code = f'''
import requests
import json

# IOFlow API Configuration
BASE_URL = "http://localhost:7001"  # Replace with your IOFlow server URL
API_KEY = "{api_key}"  # Replace with your actual API key
FLOW_ID = "{flow_id}"

def execute_flow_async():
    """Execute flow asynchronously - returns execution ID immediately"""
    
    url = f"{{BASE_URL}}/api/v1/flows/{{FLOW_ID}}/execute-direct"
    headers = {{
        "Authorization": f"Bearer {{API_KEY}}",
        "Content-Type": "application/json"
    }}
    
    payload = {{
        "trigger_type": "manual",
        "variables": {variables_json.replace("    ", "        ")},
        "is_simulation": False  # Set to True for testing without real execution
    }}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print(f"Flow execution started successfully!")
        print(f"Execution ID: {{result['execution_id']}}")
        print(f"Status: {{result['status']}}")
        
        # You can check execution status using:
        # GET /api/v1/executions/{{result['execution_id']}}
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Error executing flow: {{e}}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {{e.response.text}}")
        return None

if __name__ == "__main__":
    execute_flow_async()
'''
    
    if include_sync:
        sync_code = f'''

def execute_flow_sync():
    """Execute flow synchronously - waits for completion and returns result"""
    
    url = f"{{BASE_URL}}/api/v1/flows/{{FLOW_ID}}/execute-direct-sync"
    headers = {{
        "Authorization": f"Bearer {{API_KEY}}",
        "Content-Type": "application/json"
    }}
    
    payload = {{
        "trigger_type": "manual",
        "variables": {variables_json.replace("    ", "        ")},
        "is_simulation": False
    }}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        # Synchronous execution returns the flow result directly
        result = response.json()
        print(f"Flow executed successfully!")
        print(f"Result: {{json.dumps(result, indent=2)}}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Error executing flow: {{e}}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {{e.response.text}}")
        return None

# Uncomment to test synchronous execution:
# execute_flow_sync()
'''
        return async_code + sync_code
    
    return async_code


def _generate_javascript_code(flow_id: str, flow_name: str, api_key: str, variables: dict, include_sync: bool) -> str:
    """Generate JavaScript sample code."""
    variables_json = json.dumps(variables, indent=4)
    
    async_code = f'''
// IOFlow API Configuration
const BASE_URL = "http://localhost:7001"; // Replace with your IOFlow server URL
const API_KEY = "{api_key}"; // Replace with your actual API key
const FLOW_ID = "{flow_id}";

async function executeFlowAsync() {{
    const url = `${{BASE_URL}}/api/v1/flows/${{FLOW_ID}}/execute-direct`;
    
    const payload = {{
        trigger_type: "manual",
        variables: {variables_json},
        is_simulation: false // Set to true for testing without real execution
    }};
    
    try {{
        const response = await fetch(url, {{
            method: 'POST',
            headers: {{
                'Authorization': `Bearer ${{API_KEY}}`,
                'Content-Type': 'application/json'
            }},
            body: JSON.stringify(payload)
        }});
        
        if (!response.ok) {{
            throw new Error(`HTTP error! status: ${{response.status}}`);
        }}
        
        const result = await response.json();
        console.log('Flow execution started successfully!');
        console.log('Execution ID:', result.execution_id);
        console.log('Status:', result.status);
        
        // You can check execution status using:
        // GET /api/v1/executions/${{result.execution_id}}
        
        return result;
        
    }} catch (error) {{
        console.error('Error executing flow:', error);
        return null;
    }}
}}

// Execute the function
executeFlowAsync();
'''
    
    if include_sync:
        sync_code = f'''

async function executeFlowSync() {{
    const url = `${{BASE_URL}}/api/v1/flows/${{FLOW_ID}}/execute-direct-sync`;
    
    const payload = {{
        trigger_type: "manual",
        variables: {variables_json},
        is_simulation: false
    }};
    
    try {{
        const response = await fetch(url, {{
            method: 'POST',
            headers: {{
                'Authorization': `Bearer ${{API_KEY}}`,
                'Content-Type': 'application/json'
            }},
            body: JSON.stringify(payload),
            timeout: 60000 // 60 second timeout
        }});
        
        if (!response.ok) {{
            throw new Error(`HTTP error! status: ${{response.status}}`);
        }}
        
        const result = await response.json();
        console.log('Flow executed successfully!');
        console.log('Result:', JSON.stringify(result, null, 2));
        
        return result;
        
    }} catch (error) {{
        console.error('Error executing flow:', error);
        return null;
    }}
}}

// Uncomment to test synchronous execution:
// executeFlowSync();
'''
        return async_code + sync_code
    
    return async_code


def _generate_curl_code(flow_id: str, flow_name: str, api_key: str, variables: dict, is_synchronous: bool) -> str:
    """Generate cURL sample code - simple and ready to execute."""
    
    # Now execute-direct handles both sync and async based on flow's is_synchronous setting
    endpoint = "execute-direct"
    if is_synchronous:
        execution_type = "synchronously (waits for result)"
        result_description = "# Returns the actual flow result directly"
    else:
        execution_type = "asynchronously (returns execution ID)"
        result_description = "# Returns an execution ID to track the flow execution"
    
    # Check if any variables are file inputs
    has_file_inputs = any(isinstance(v, dict) and 'data' in v and 'name' in v and 'type' in v for v in variables.values())
    
    if has_file_inputs:
        # Generate curl with file upload instructions
        file_vars = [k for k, v in variables.items() if isinstance(v, dict) and 'data' in v]
        
        # Method 1: Simple execution with sample data
        simple_code = f'''# Execute {flow_name} flow {execution_type}
# This flow includes file inputs: {", ".join(file_vars)}

# Method 1: Direct execution with sample file data
curl -X POST "http://localhost:7001/api/v1/flows/{flow_id}/{endpoint}" \\
  -H "Authorization: Bearer {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"trigger_type": "manual", "variables": {json.dumps(variables)}, "is_simulation": false}}'

# Method 2: Replace file path in curl command (simple approach)
# 1. Set FILE_PATH variable to your actual file path
# 2. Run the command
FILE_PATH="YOUR_FILE_PATH"  # Replace with your actual file path

JSON_PAYLOAD=$(cat <<EOF
{{
  "trigger_type": "manual",
  "variables": {{
'''
        
        # Generate the JSON structure with $FILE_PATH variable
        var_parts = []
        for var_name, var_value in variables.items():
            if isinstance(var_value, dict) and 'data' in var_value:
                mime_type = var_value.get('type', 'application/pdf')
                var_parts.append(f'''    "{var_name}": {{
      "data": "data:{mime_type};base64,$(base64 -i "$FILE_PATH")",
      "name": "$(basename "$FILE_PATH")",
      "type": "{mime_type}",
      "size": $(wc -c < "$FILE_PATH")
    }}''')
            else:
                # Use clean JSON without extra escaping
                json_value = json.dumps(var_value)
                var_parts.append(f'    "{var_name}": {json_value}')
        
        simple_code += ',\n'.join(var_parts)
        simple_code += f'''
  }},
  "is_simulation": false
}}
EOF
)

curl -X POST "http://localhost:7001/api/v1/flows/{flow_id}/{endpoint}" \\
  -H "Authorization: Bearer {api_key}" \\
  -H "Content-Type: application/json" \\
  --data-raw "$JSON_PAYLOAD"

# Method 3: Helper script (recommended for multiple files)'''
        
        simple_code += f'''
#!/bin/bash
FILE_PATH="$1"
if [ ! -f "$FILE_PATH" ]; then
    echo "Usage: $0 <file_path>"
    exit 1
fi

MIME_TYPE=$(file --mime-type -b "$FILE_PATH" 2>/dev/null || echo "application/octet-stream")
BASE64_DATA=$(base64 -i "$FILE_PATH")
FILE_SIZE=$(wc -c < "$FILE_PATH")
FILE_NAME=$(basename "$FILE_PATH")

# Build JSON payload
cat > /tmp/ioflow_payload.json << 'EOF'
{{
  "trigger_type": "manual",
  "variables": {{'''
        
        # Generate clean JSON for script
        var_parts = []
        for var_name, var_value in variables.items():
            if isinstance(var_value, dict) and 'data' in var_value:
                var_parts.append(f'''    "{var_name}": {{
      "data": "data:$MIME_TYPE;base64,$BASE64_DATA",
      "name": "$FILE_NAME",
      "type": "$MIME_TYPE",
      "size": $FILE_SIZE
    }}''')
            else:
                # Use proper JSON encoding
                json_value = json.dumps(var_value)
                var_parts.append(f'    "{var_name}": {json_value}')
        
        simple_code += ',\n'.join(var_parts)
        simple_code += f'''
  }},
  "is_simulation": false
}}
EOF

curl -X POST "http://localhost:7001/api/v1/flows/{flow_id}/{endpoint}" \\
  -H "Authorization: Bearer {api_key}" \\
  -H "Content-Type: application/json" \\
  -d @/tmp/ioflow_payload.json

# Cleanup
rm -f /tmp/ioflow_payload.json

# Usage: chmod +x upload_file.sh && ./upload_file.sh path/to/your/file.pdf'''
        
    else:
        # Generate standard curl for non-file flows
        simple_code = f'''# Execute {flow_name} flow {execution_type}
{result_description}

curl -X POST "http://localhost:7001/api/v1/flows/{flow_id}/{endpoint}" \\
  -H "Authorization: Bearer {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"trigger_type": "manual", "variables": {json.dumps(variables)}, "is_simulation": false}}'
'''
    
    return simple_code


def _generate_php_code(flow_id: str, flow_name: str, api_key: str, variables: dict, include_sync: bool) -> str:
    """Generate PHP sample code."""
    variables_php = json.dumps(variables, indent=4)
    
    async_code = f'''
<?php
// IOFlow API Configuration
$BASE_URL = "http://localhost:7001"; // Replace with your IOFlow server URL
$API_KEY = "{api_key}"; // Replace with your actual API key
$FLOW_ID = "{flow_id}";

function executeFlowAsync($baseUrl, $apiKey, $flowId) {{
    $url = "$baseUrl/api/v1/flows/$flowId/execute-direct";
    
    $payload = [
        "trigger_type" => "manual",
        "variables" => json_decode('{variables_php}', true),
        "is_simulation" => false // Set to true for testing without real execution
    ];
    
    $options = [
        'http' => [
            'header' => [
                "Authorization: Bearer $apiKey",
                "Content-Type: application/json"
            ],
            'method' => 'POST',
            'content' => json_encode($payload)
        ]
    ];
    
    $context = stream_context_create($options);
    $response = file_get_contents($url, false, $context);
    
    if ($response === FALSE) {{
        echo "Error executing flow\\n";
        return null;
    }}
    
    $result = json_decode($response, true);
    echo "Flow execution started successfully!\\n";
    echo "Execution ID: " . $result['execution_id'] . "\\n";
    echo "Status: " . $result['status'] . "\\n";
    
    // You can check execution status using:
    // GET /api/v1/executions/{{$result['execution_id']}}
    
    return $result;
}}

// Execute the function
executeFlowAsync($BASE_URL, $API_KEY, $FLOW_ID);
'''
    
    if include_sync:
        sync_code = f'''

function executeFlowSync($baseUrl, $apiKey, $flowId) {{
    $url = "$baseUrl/api/v1/flows/$flowId/execute-direct-sync";
    
    $payload = [
        "trigger_type" => "manual",
        "variables" => json_decode('{variables_php}', true),
        "is_simulation" => false
    ];
    
    $options = [
        'http' => [
            'header' => [
                "Authorization: Bearer $apiKey",
                "Content-Type: application/json"
            ],
            'method' => 'POST',
            'content' => json_encode($payload),
            'timeout' => 60 // 60 second timeout
        ]
    ];
    
    $context = stream_context_create($options);
    $response = file_get_contents($url, false, $context);
    
    if ($response === FALSE) {{
        echo "Error executing flow\\n";
        return null;
    }}
    
    $result = json_decode($response, true);
    echo "Flow executed successfully!\\n";
    echo "Result: " . json_encode($result, JSON_PRETTY_PRINT) . "\\n";
    
    return $result;
}}

// Uncomment to test synchronous execution:
// executeFlowSync($BASE_URL, $API_KEY, $FLOW_ID);
?>
'''
        return async_code + sync_code
    
    return async_code


@router.post("/{flow_id}/debug")
async def start_debug_execution(
    flow_id: str,
    request: DebugExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a debug execution session for a flow using state-based approach."""
    logger.info(f"Debug request received for flow {flow_id} by user {current_user.email}")
    logger.info(f"Debug request data: {request.dict()}")
    
    schema_name, tenant_id = get_tenant_info(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    
    # Import the state-based debug manager
    from services.debug_execution_manager import DebugExecutionManager
    
    # Prepare trigger data
    trigger_data = {
        **request.trigger_data,
        "trigger_type": "manual",
        "triggered_by": current_user.user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        # Create execution record first
        import uuid
        execution_id = str(uuid.uuid4())
        
        with get_tenant_db(schema_name) as tenant_db:
            execution = FlowExecution(
                execution_id=execution_id,
                flow_id=flow_id,
                trigger_type="manual",
                trigger_data=trigger_data,
                status=ExecutionStatus.RUNNING,
                execution_data={
                    'debug_mode': True,
                    'debug_step_mode': request.mode == "step"
                }
            )
            tenant_db.add(execution)
            tenant_db.commit()
        
        # Add debug flags to trigger_data
        trigger_data_with_debug = {
            **trigger_data,
            'debug_mode': True,
            'debug_step_mode': request.mode == "step"
        }
        
        # Start debug execution and execute first node (trigger)
        result = await DebugExecutionManager.start_debug_execution(
            tenant_schema=schema_name,
            tenant_id=tenant_id,
            flow_id=flow_id,
            execution_id=execution_id,
            trigger_data=trigger_data_with_debug
        )
        
        return {
            "execution_id": execution_id,
            "mode": request.mode,
            "status": result["status"],
            "current_node": result.get("current_node"),
            "executed_nodes": result["executed_nodes"],
            "message": "Debug session started"
        }
    except Exception as e:
        logger.error(f"Failed to start debug execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start debug session"
        )

@router.get("/debug/trigger-configs")
async def debug_trigger_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check all flow trigger configurations."""
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        flows = tenant_db.query(Flow).all()
        
        return {
            "tenant_schema": schema_name,
            "total_flows": len(flows),
            "flows": [
                {
                    "flow_id": flow.flow_id,
                    "flow_name": flow.flow_name,
                    "status": flow.status.value,
                    "trigger_config": flow.trigger_config
                }
                for flow in flows
            ]
        }


@router.post("/{flow_id}/export")
async def export_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a flow with portable application references.
    Replaces instance-specific app_ids with seed_keys for portability.
    """
    schema_name = get_tenant_schema(current_user, db)
    
    with get_tenant_db(schema_name) as tenant_db:
        # Get the flow
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Get all applications to build app_id to seed_key mapping with instance info
        applications = db.query(Application).all()
        app_id_to_seed_key = {str(app.app_id): app.seed_key for app in applications if app.seed_key}
        app_id_to_name = {str(app.app_id): app.app_name for app in applications}
        app_id_to_instance = {
            str(app.app_id): {
                'instance_number': app.instance_number or 1,
                'instance_name': app.instance_name
            } for app in applications
        }
        
        # Get all services to build service_id to service_name mapping
        services = db.query(ApplicationService).all()
        service_id_to_name = {str(svc.service_id): svc.service_name for svc in services}
        service_id_to_app_id = {str(svc.service_id): str(svc.app_id) for svc in services}
        
        # Clone flow definition for export
        export_definition = json.loads(json.dumps(flow.flow_definition))
        
        # Track required applications
        required_apps = set()
        missing_seed_keys = []
        
        # Process nodes to replace app_ids with seed_keys and service_ids with service_names
        if 'nodes' in export_definition:
            for node in export_definition['nodes']:
                if node.get('type') in ['action', 'trigger'] and 'data' in node:
                    app_id = node['data'].get('appId')
                    service_id = node['data'].get('serviceId')
                    
                    if app_id:
                        seed_key = app_id_to_seed_key.get(app_id)
                        app_name = app_id_to_name.get(app_id, 'Unknown')

                        # Always keep the UUID in appId field
                        # Add seed_key and app_name as separate fields for reference
                        if seed_key:
                            node['data']['_seed_key'] = seed_key
                            node['data']['_app_reference'] = 'seed_key'
                            # Add instance information for multi-instance support
                            instance_info = app_id_to_instance.get(app_id, {})
                            node['data']['_instance_number'] = instance_info.get('instance_number', 1)
                            node['data']['_instance_name'] = instance_info.get('instance_name')
                            required_apps.add(seed_key)
                        else:
                            # Application doesn't have a seed_key (not from seed)
                            node['data']['_app_reference'] = 'custom'
                            missing_seed_keys.append({
                                'app_id': app_id,
                                'app_name': app_name,
                                'node_id': node.get('id'),
                                'node_label': node.get('data', {}).get('label', 'Unnamed')
                            })

                        # Always store the app_name for fallback resolution
                        if not node['data'].get('appName'):
                            node['data']['appName'] = app_name
                    
                    # Handle service reference
                    if service_id:
                        service_name = service_id_to_name.get(service_id)
                        if service_name:
                            # Keep the UUID in serviceId field
                            # Add service_name as separate field for reference
                            node['data']['_service_name'] = service_name
                            node['data']['_service_reference'] = 'has_name'

                            # Always store the service name for fallback resolution
                            if not node['data'].get('service'):
                                node['data']['service'] = service_name
        
        # Process trigger config
        export_trigger_config = json.loads(json.dumps(flow.trigger_config))
        if export_trigger_config.get('app_id'):
            app_id = export_trigger_config['app_id']
            seed_key = app_id_to_seed_key.get(app_id)
            app_name = app_id_to_name.get(app_id, 'Unknown')

            # Keep the UUID in app_id field
            # Add seed_key and app_name as separate fields for reference
            if seed_key:
                export_trigger_config['_seed_key'] = seed_key
                export_trigger_config['_app_reference'] = 'seed_key'
                required_apps.add(seed_key)
            else:
                export_trigger_config['_app_reference'] = 'custom'

            # Always store the app_name for fallback resolution
            if not export_trigger_config.get('app_name'):
                export_trigger_config['app_name'] = app_name
        
        # Build export package
        export_data = {
            'version': '1.0',
            'export_timestamp': datetime.utcnow().isoformat(),
            'flow': {
                'flow_name': flow.flow_name,
                'description': flow.description,
                'category': flow.category,
                'trigger_config': export_trigger_config,
                'flow_definition': export_definition,
                'is_synchronous': flow.is_synchronous,
                'sync_timeout': flow.sync_timeout
            },
            'metadata': {
                'required_applications': list(required_apps),
                'source_instance': {
                    'tenant_id': current_user.tenant_id,
                    'user_email': current_user.email
                },
                'warnings': []
            }
        }
        
        # Add warnings for missing seed keys
        if missing_seed_keys:
            export_data['metadata']['warnings'].append({
                'type': 'missing_seed_keys',
                'message': 'Some applications do not have seed keys and may need manual mapping after import',
                'applications': missing_seed_keys
            })
        
        return export_data


@router.post("/validate-import")
async def validate_flow_import(
    import_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate a flow before import by checking:
    - Required applications and their subscription status
    - Which nodes use each application
    - Required credential fields for each app
    - Connection readiness
    """
    try:
        logger.info(f"Validate flow import called by user {current_user.user_id}")

        # Normalize the format using FlowFormatNormalizer
        normalizer = FlowFormatNormalizer()
        original_format = normalizer.detect_format(import_data)

        try:
            normalized_data = normalizer.normalize_to_import_format(import_data)
            import_data = normalized_data
        except ValueError as e:
            logger.warning(f"Format normalization failed: {e}")
            # Continue with original data

        # Extract flow definition
        flow_data = import_data.get('flow', {})
        flow_definition = flow_data.get('flow_definition', {})
        nodes = flow_definition.get('nodes', [])

        # Build seed_key to app_id mapping for cross-instance resolution
        applications = db.query(Application).all()
        seed_key_to_app_id = {}
        app_name_to_app_id = {}

        for app in applications:
            if app.seed_key:
                seed_key_to_app_id[app.seed_key] = str(app.app_id)
            if app.app_name:
                app_name_to_app_id[app.app_name.lower()] = str(app.app_id)

        # Extract application IDs from nodes and track which nodes use each app
        # Also resolve seed_keys to app_ids for cross-instance imports
        app_usage = {}  # {app_id: [{"node_id": ..., "node_label": ..., "service_name": ...}]}

        for node in nodes:
            if isinstance(node, dict) and node.get('type') in ['action', 'trigger']:
                node_data = node.get('data', {})
                app_id = node_data.get('appId')

                # Try to resolve via seed_key if available
                seed_key = node_data.get('_seed_key')
                app_name = node_data.get('appName', '')

                # Resolve to local app_id
                resolved_app_id = app_id
                if seed_key and seed_key in seed_key_to_app_id:
                    resolved_app_id = seed_key_to_app_id[seed_key]
                    logger.info(f"Resolved seed_key '{seed_key}' to app_id '{resolved_app_id}'")
                elif app_name and app_name.lower() in app_name_to_app_id:
                    resolved_app_id = app_name_to_app_id[app_name.lower()]
                    logger.info(f"Resolved app_name '{app_name}' to app_id '{resolved_app_id}'")

                if resolved_app_id:
                    if resolved_app_id not in app_usage:
                        app_usage[resolved_app_id] = []

                    app_usage[resolved_app_id].append({
                        'node_id': node.get('id'),
                        'node_label': node_data.get('label', 'Unnamed Node'),
                        'service_name': node_data.get('serviceDisplayName') or node_data.get('service', 'Unknown Service'),
                        'node_type': node.get('type')
                    })

        # Check trigger config for app usage
        trigger_config = flow_data.get('trigger_config', {})
        if trigger_config.get('app_id'):
            app_id = trigger_config['app_id']

            # Try to resolve via seed_key if available
            seed_key = trigger_config.get('_seed_key')
            app_name = trigger_config.get('app_name', '')

            # Resolve to local app_id
            resolved_app_id = app_id
            if seed_key and seed_key in seed_key_to_app_id:
                resolved_app_id = seed_key_to_app_id[seed_key]
                logger.info(f"Resolved trigger seed_key '{seed_key}' to app_id '{resolved_app_id}'")
            elif app_name and app_name.lower() in app_name_to_app_id:
                resolved_app_id = app_name_to_app_id[app_name.lower()]
                logger.info(f"Resolved trigger app_name '{app_name}' to app_id '{resolved_app_id}'")

            if resolved_app_id:
                if resolved_app_id not in app_usage:
                    app_usage[resolved_app_id] = []

                app_usage[resolved_app_id].append({
                    'node_id': 'trigger',
                    'node_label': f"Trigger ({trigger_config.get('type', 'Unknown')})",
                    'service_name': trigger_config.get('trigger_type', 'Unknown Trigger'),
                    'node_type': 'trigger'
                })

        if not app_usage:
            return {
                'success': True,
                'can_import': True,
                'required_applications': [],
                'missing_applications': [],
                'message': 'No applications required for this flow'
            }

        # Get application details and check subscriptions
        required_applications = []
        missing_applications = []

        for app_id, usage_list in app_usage.items():
            # Get application details
            app = db.query(Application).filter(Application.app_id == app_id).first()

            if not app:
                # App not found in this instance - might be a cross-instance import
                logger.warning(f"Application {app_id} not found in database during validation")
                missing_applications.append({
                    'app_id': app_id,
                    'app_name': f'Unknown Application ({app_id[:8]}...)',
                    'app_type': 'unknown',
                    'description': 'This application ID is not available in your instance. The flow may have been exported from a different instance.',
                    'icon_url': None,
                    'is_subscribed': False,
                    'is_connected': False,
                    'subscription_id': None,
                    'auth_type': None,
                    'required_fields': [],
                    'documentation_url': None,
                    'used_in_nodes': usage_list,
                    'status': 'not_found'
                })
                continue

            # Check if tenant has an active subscription
            subscription = db.query(ApplicationSubscription).filter(
                ApplicationSubscription.app_id == app_id,
                ApplicationSubscription.tenant_id == current_user.tenant_id,
                ApplicationSubscription.status == "active"
            ).first()

            is_subscribed = subscription is not None

            # Determine if credentials are configured (connection ready)
            is_connected = False
            if subscription and subscription.auth_credentials:
                # Check if auth_credentials has actual data
                auth_creds = subscription.auth_credentials
                if isinstance(auth_creds, str):
                    try:
                        auth_creds = json.loads(auth_creds)
                    except:
                        pass
                is_connected = bool(auth_creds and len(auth_creds) > 0)

            # Get authentication requirements
            auth_type = app.auth_type or 'none'
            required_fields = []

            if app.auth_config:
                auth_config = app.auth_config
                if isinstance(auth_config, str):
                    try:
                        auth_config = json.loads(auth_config)
                    except:
                        auth_config = {}

                # Extract required fields from auth_config
                if auth_type == 'api_key':
                    required_fields.append({
                        'name': 'api_key',
                        'label': auth_config.get('key_name', 'API Key'),
                        'type': 'password',
                        'required': True,
                        'description': 'Your API key for authentication'
                    })
                elif auth_type == 'oauth2':
                    required_fields.append({
                        'name': 'access_token',
                        'label': 'Access Token',
                        'type': 'password',
                        'required': True,
                        'description': 'OAuth 2.0 access token'
                    })
                elif auth_type == 'basic':
                    required_fields.extend([
                        {'name': 'username', 'label': 'Username', 'type': 'text', 'required': True},
                        {'name': 'password', 'label': 'Password', 'type': 'password', 'required': True}
                    ])
                elif auth_type == 'database':
                    db_config = auth_config.get('database_config', {})
                    required_fields.extend([
                        {'name': 'host', 'label': 'Host', 'type': 'text', 'required': True},
                        {'name': 'port', 'label': 'Port', 'type': 'number', 'required': True},
                        {'name': 'database', 'label': 'Database Name', 'type': 'text', 'required': True},
                        {'name': 'username', 'label': 'Username', 'type': 'text', 'required': True},
                        {'name': 'password', 'label': 'Password', 'type': 'password', 'required': True}
                    ])
                elif auth_type == 'custom':
                    # Extract fields from auth_config
                    fields = auth_config.get('fields', [])
                    for field in fields:
                        required_fields.append({
                            'name': field.get('name'),
                            'label': field.get('label', field.get('name')),
                            'type': field.get('type', 'text'),
                            'required': field.get('required', True),
                            'description': field.get('description', '')
                        })

            # Determine status
            if not is_subscribed:
                status = 'not_subscribed'
            elif not is_connected and auth_type != 'none':
                status = 'not_connected'
            else:
                status = 'ready'

            app_requirement = {
                'app_id': str(app.app_id),
                'app_name': app.app_name,
                'app_type': app.app_type or 'api',
                'description': app.description,
                'icon_url': app.icon_url,
                'is_subscribed': is_subscribed,
                'is_connected': is_connected,
                'subscription_id': str(subscription.subscription_id) if subscription else None,
                'auth_type': auth_type,
                'required_fields': required_fields,
                'documentation_url': app.documentation_url if hasattr(app, 'documentation_url') else None,
                'used_in_nodes': usage_list,
                'status': status
            }

            required_applications.append(app_requirement)

            if status != 'ready':
                missing_applications.append(app_requirement)

        can_import = len(missing_applications) == 0

        if can_import:
            message = 'All required applications are installed and connected'
        else:
            not_subscribed = [app for app in missing_applications if app['status'] == 'not_subscribed']
            not_connected = [app for app in missing_applications if app['status'] == 'not_connected']

            message_parts = []
            if not_subscribed:
                message_parts.append(f"{len(not_subscribed)} application(s) need to be installed")
            if not_connected:
                message_parts.append(f"{len(not_connected)} application(s) need credentials")

            message = " and ".join(message_parts)

        return {
            'success': True,
            'can_import': can_import,
            'required_applications': required_applications,
            'missing_applications': missing_applications,
            'message': message,
            'flow_name': flow_data.get('flow_name', 'Untitled Flow')
        }

    except Exception as e:
        logger.error(f"Error validating flow import: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'validation_failed',
                'message': f'Error validating flow: {str(e)}'
            }
        )


@router.post("/import")
async def import_flow(
    import_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    overwrite_existing: bool = False
):
    """
    Import a flow with automatic format normalization and application reference resolution.
    Supports multiple JSON formats: export, direct, hybrid, and FlowCreate.
    Resolves seed_keys to instance-specific app_ids.

    ``overwrite_existing`` decides what happens when the tenant already has a
    flow with this name, and the right answer differs by caller:

    - **False (default, the /import screen)** — keep both. Someone importing a
      file they were sent should never silently clobber a flow they already
      have, so the incoming one is saved under a suffixed name.
    - **True (programmatic saves)** — UPDATE that flow in place and keep its
      id. An automated caller re-saving the same design means "this is the
      current version of that flow", not "make me another one". Copying is
      undetectable from the response there — it reports success either way —
      so a re-run would quietly leave two flows on the same trigger, both
      firing.
    """
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit importing flows"
        )

    try:
        logger.info(f"Import flow called by user {current_user.user_id}")
        logger.debug(f"Import data keys: {list(import_data.keys()) if isinstance(import_data, dict) else 'Not a dict'}")

        # Validate basic structure
        if not isinstance(import_data, dict):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid import file format",
                    "message": "The import data must be a JSON object",
                    "expected_structure": {
                        "version": "1.0.0",
                        "flow": {
                            "flow_name": "...",
                            "flow_definition": {"nodes": [], "edges": []},
                            "trigger_config": {}
                        },
                        "metadata": {"required_applications": []}
                    }
                }
            )

        # Try to normalize the format using FlowFormatNormalizer
        normalizer = FlowFormatNormalizer()
        original_format = normalizer.detect_format(import_data)

        try:
            # Attempt to normalize to standard import format
            normalized_data = normalizer.normalize_to_import_format(import_data)
            logger.info(f"Successfully normalized flow from {original_format} format")

            # Use the normalized data for import
            import_data = normalized_data

        except ValueError as e:
            # If normalization fails completely, try the old validation logic
            logger.warning(f"Format normalization failed: {e}, falling back to strict validation")

            # Original validation logic for backward compatibility
            if 'version' not in import_data:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Invalid import file format",
                        "message": "Missing 'version' field in import data",
                        "hint": "The import file should have a 'version' field at the top level",
                        "example": {"version": "1.0.0", "flow": {...}},
                        "detected_format": original_format,
                        "auto_normalization_failed": str(e)
                    }
                )

            if 'flow' not in import_data:
                # Check if this might be a direct flow JSON (common mistake)
                if 'flow_name' in import_data and ('nodes' in import_data or 'flow_definition' in import_data):
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "Invalid import file format",
                            "message": "Flow JSON needs to be wrapped in the import format",
                            "hint": "Your flow JSON should be inside a 'flow' field",
                            "current_structure": list(import_data.keys()),
                            "expected_structure": {
                                "version": "1.0.0",
                                "flow": import_data,  # Show how to wrap their data
                                "metadata": {
                                    "required_applications": []
                                }
                            }
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "Invalid import file format",
                            "message": "Missing 'flow' field in import data",
                            "current_fields": list(import_data.keys()),
                            "required_fields": ["version", "flow"],
                            "detected_format": original_format
                        }
                    )
        
        flow_data = import_data['flow']
        metadata = import_data.get('metadata', {})
        required_apps_raw = metadata.get('required_applications', [])
        
        # Handle both string and dict formats for required_applications
        required_apps = []  # seed_keys
        required_app_ids = []  # actual app IDs
        required_app_names = []  # app names to resolve later

        for app in required_apps_raw:
            if isinstance(app, str):
                # Check if it's a UUID (app_id) or seed_key
                try:
                    import uuid
                    uuid.UUID(app)
                    required_app_ids.append(app)
                except ValueError:
                    # Not a UUID, could be seed_key or app_name
                    # Store it temporarily, we'll resolve it later
                    required_app_names.append(app)
            elif isinstance(app, dict) and 'seed_key' in app:
                required_apps.append(app['seed_key'])
            elif isinstance(app, dict) and 'app_name' in app:
                # Try to find by app name
                required_app_names.append(app['app_name'])
        
        # Get all applications to build seed_key to app_id mapping with instance support
        applications = db.query(Application).all()
        
        # Build mappings for resolving instances
        # Map seed_key + instance_number to app_id
        seed_instance_to_app_id = {}
        seed_key_to_app_ids = {}  # Map seed_key to list of app_ids for multiple instances
        all_app_ids = set()  # Track all installed app IDs
        
        for app in applications:
            all_app_ids.add(str(app.app_id))
            if app.seed_key:
                key = (app.seed_key, app.instance_number or 1)
                seed_instance_to_app_id[key] = str(app.app_id)
                
                if app.seed_key not in seed_key_to_app_ids:
                    seed_key_to_app_ids[app.seed_key] = []
                seed_key_to_app_ids[app.seed_key].append({
                    'app_id': str(app.app_id),
                    'instance_number': app.instance_number or 1,
                    'instance_name': app.instance_name
                })
        
        # Backward compatibility: seed_key to first instance app_id
        seed_key_to_app_id = {
            seed_key: min(apps, key=lambda x: x['instance_number'])['app_id'] 
            for seed_key, apps in seed_key_to_app_ids.items()
        }
        app_name_to_id = {app.app_name: str(app.app_id) for app in applications}
        seed_key_to_name = {app.seed_key: app.app_name for app in applications if app.seed_key}

        # Now resolve the app names we collected earlier
        for app_name in required_app_names:
            # First check if it's an app name
            if app_name in app_name_to_id:
                required_app_ids.append(app_name_to_id[app_name])
                logger.info(f"Resolved app name '{app_name}' to app_id '{app_name_to_id[app_name]}'")
            # Then check if it's a seed key
            elif app_name in seed_key_to_app_id:
                required_app_ids.append(seed_key_to_app_id[app_name])
                logger.info(f"Resolved seed key '{app_name}' to app_id '{seed_key_to_app_id[app_name]}'")
            else:
                # Could not resolve - treat as seed_key for error reporting
                required_apps.append(app_name)
                logger.warning(f"Could not resolve '{app_name}' to app_id or seed_key")

        # Get all services to build service_name to service_id mapping per app
        services = db.query(ApplicationService).all()
        # Create a mapping: {app_id: {service_name: service_id}}
        app_service_mapping = {}
        for svc in services:
            app_id_str = str(svc.app_id)
            if app_id_str not in app_service_mapping:
                app_service_mapping[app_id_str] = {}
            app_service_mapping[app_id_str][svc.service_name] = str(svc.service_id)
        
        # Check for missing applications (both by seed_key and app_id)
        missing_apps = []
        missing_app_ids_list = []
        
        # Check seed keys
        for seed_key in required_apps:
            if seed_key not in seed_key_to_app_id:
                missing_apps.append(seed_key)
        
        # Check app IDs
        for app_id in required_app_ids:
            if app_id not in all_app_ids:
                missing_app_ids_list.append(app_id)
        
        if missing_apps or missing_app_ids_list:
            # Try to provide helpful information about missing apps
            from services.json_seed_manager import json_seed_manager
            available_seeds = json_seed_manager.discover_applications()
            
            missing_info = []
            
            # Handle missing seed keys
            for seed_key in missing_apps:
                if seed_key in available_seeds:
                    seed_info = available_seeds[seed_key]
                    missing_info.append({
                        'seed_key': seed_key,
                        'app_name': seed_info['application']['app_name'],
                        'available_for_install': True
                    })
                else:
                    missing_info.append({
                        'seed_key': seed_key,
                        'app_name': 'Unknown',
                        'available_for_install': False
                    })
            
            # Handle missing app IDs - try to find app names for better error messages
            for app_id in missing_app_ids_list:
                # Try to find if this app_id corresponds to a known seed application
                app_name = None
                seed_key = None
                
                # Check if we can match it to a seed application
                for key, seed_info in available_seeds.items():
                    # Note: We can't directly match app_id to seed since IDs are instance-specific
                    # But we can suggest possible applications based on the flow
                    pass
                
                missing_info.append({
                    'app_id': app_id,
                    'app_name': app_name or 'Unknown Application',
                    'available_for_install': False,
                    'note': 'Application ID not found in this instance'
                })
            
            return {
                'success': False,
                'error': 'missing_applications',
                'message': 'Some required applications are not installed',
                'missing_applications': missing_info,
                'hint': 'Install the missing applications and try importing again'
            }
        
        # Clone flow definition for import
        import_definition = json.loads(json.dumps(flow_data['flow_definition']))
        
        # Process nodes to replace seed_keys with app_ids and service_names with service_ids
        if 'nodes' in import_definition:
            for node in import_definition['nodes']:
                if 'data' in node:
                    # Always remove old parameters field if it exists alongside parameterMapping
                    if 'parameters' in node['data'] and 'parameterMapping' in node['data']:
                        del node['data']['parameters']
                        logger.info(f"Removed redundant 'parameters' field from node {node.get('id')}")

                    # Convert old-style parameters to new parameterMapping format
                    if 'parameters' in node['data'] and 'parameterMapping' not in node['data']:
                        old_params = node['data']['parameters']
                        parameter_mapping = {}

                        # Convert each parameter to the new format
                        for param_key, param_value in old_params.items():
                            if isinstance(param_value, str):
                                # Check if it's a pure variable reference (entire string is {{variable}})
                                pattern = r'^\{\{([^}]+)\}\}$'
                                match = re.match(pattern, param_value.strip())

                                if match:
                                    # It's a pure variable reference
                                    variable_path = match.group(1).strip()
                                    parameter_mapping[param_key] = {
                                        "source": "variable",
                                        "value": variable_path
                                    }
                                else:
                                    # It's either a static value or a template string with mixed content
                                    # Treat it as static (preserving any template syntax for later processing)
                                    parameter_mapping[param_key] = {
                                        "source": "static",
                                        "value": param_value
                                    }
                            else:
                                # For non-string values (numbers, booleans, objects, arrays), treat as static
                                parameter_mapping[param_key] = {
                                    "source": "static",
                                    "value": param_value
                                }

                        # Replace old parameters with new parameterMapping
                        node['data']['parameterMapping'] = parameter_mapping
                        del node['data']['parameters']
                        logger.info(f"Converted old-style parameters to parameterMapping for node {node.get('id')}")

                    # Process transform node scripts and inject external functions
                    # Transform nodes from AI agents have scripts with escaped newlines (\n) in JSON
                    # These are already correct for storage, but we should validate they're properly formatted
                    if node.get('type') == 'transform' and 'script' in node['data']:
                        script = node['data']['script']
                        if script:
                            # Check if this node uses external functions
                            functions_used = node['data'].get('functions_used', [])
                            functions_dict = flow_data.get('functions', {})

                            # Only inject functions if both functions_used AND functions dict are provided
                            if functions_used and functions_dict:
                                # First check if all required functions are present
                                missing_functions = [func for func in functions_used if func not in functions_dict]

                                if missing_functions:
                                    # Some functions are missing
                                    logger.error(f"Transform node {node.get('id')} requires functions {functions_used}, but missing: {missing_functions}")

                                    # Add detailed warning to metadata
                                    if 'warnings' not in metadata:
                                        metadata['warnings'] = []
                                    metadata['warnings'].append({
                                        'node_id': node.get('id'),
                                        'type': 'partial_functions',
                                        'message': f"Transform node '{node.get('data', {}).get('label', node.get('id'))}' is missing functions: {', '.join(missing_functions)}. Available: {', '.join(functions_dict.keys())}",
                                        'functions_needed': functions_used,
                                        'functions_provided': list(functions_dict.keys()),
                                        'functions_missing': missing_functions
                                    })

                                # Inject the external functions into the script (even if some are missing)
                                from services.transform_function_manager import TransformFunctionManager

                                combined_script = TransformFunctionManager.inject_functions(
                                    script, functions_used, functions_dict
                                )
                                node['data']['script'] = combined_script

                                # Log injection details
                                actually_injected = [func for func in functions_used if func in functions_dict]
                                if actually_injected:
                                    logger.info(f"Injected {len(actually_injected)} functions into transform node {node.get('id')}: {actually_injected}")
                                    if missing_functions:
                                        logger.warning(f"Could not inject missing functions: {missing_functions}")
                            elif functions_used and not functions_dict:
                                # functions_used is present but no functions provided - this is likely a mistake
                                # Collect all missing functions for better error reporting
                                missing_functions = functions_used
                                logger.error(f"Transform node {node.get('id')} requires functions: {missing_functions} but no functions were provided")

                                # Add detailed warning to metadata
                                if 'warnings' not in metadata:
                                    metadata['warnings'] = []
                                metadata['warnings'].append({
                                    'node_id': node.get('id'),
                                    'type': 'missing_functions',
                                    'message': f"Transform node '{node.get('data', {}).get('label', node.get('id'))}' requires functions: {', '.join(missing_functions)} but they were not provided. The flow will fail at runtime.",
                                    'functions_needed': missing_functions
                                })

                                # Remove functions_used field to avoid runtime errors
                                del node['data']['functions_used']

                            # The script should already be a single-line string with \n for newlines
                            # Just ensure it's a string and log for debugging
                            if not isinstance(node['data']['script'], str):
                                logger.warning(f"Transform node {node.get('id')} has non-string script, converting")
                                node['data']['script'] = str(node['data']['script'])
                            else:
                                # Script is already properly formatted as single-line with \n
                                # No conversion needed - it's already in the correct format for storage
                                logger.debug(f"Transform node {node.get('id')} script is properly formatted (length: {len(node['data']['script'])})")

                    # Check if parameterMapping needs format conversion (old format to new format)
                    if 'parameterMapping' in node['data']:
                        param_mapping = node['data']['parameterMapping']
                        needs_conversion = False

                        # Check if any parameter is not in the new format (should have 'source' and 'value')
                        for param_key, param_value in param_mapping.items():
                            if not isinstance(param_value, dict) or 'source' not in param_value:
                                needs_conversion = True
                                break

                        if needs_conversion:
                            new_mapping = {}
                            for param_key, param_value in param_mapping.items():
                                # If it's already in new format, keep it
                                if isinstance(param_value, dict) and 'source' in param_value:
                                    new_mapping[param_key] = param_value
                                # Otherwise convert it
                                elif isinstance(param_value, str):
                                    # Check if it's a pure variable reference
                                    pattern = r'^\{\{([^}]+)\}\}$'
                                    match = re.match(pattern, param_value.strip())

                                    if match:
                                        variable_path = match.group(1).strip()
                                        new_mapping[param_key] = {
                                            "source": "variable",
                                            "value": variable_path
                                        }
                                    else:
                                        new_mapping[param_key] = {
                                            "source": "static",
                                            "value": param_value
                                        }
                                else:
                                    # Non-string values are static
                                    new_mapping[param_key] = {
                                        "source": "static",
                                        "value": param_value
                                    }

                            node['data']['parameterMapping'] = new_mapping
                            logger.info(f"Converted old-format parameterMapping to new format for node {node.get('id')}")

                if node.get('type') in ['action', 'trigger'] and 'data' in node:
                    app_ref = node['data'].get('appId')
                    service_ref = node['data'].get('serviceId')
                    resolved_app_id = None
                    
                    # Resolve application reference
                    if app_ref and node['data'].get('_app_reference') == 'seed_key':
                        # New format: appId is already a UUID, but we have seed_key for cross-instance resolution
                        seed_key = node['data'].get('_seed_key')
                        if seed_key:
                            # This is the new format with seed_key stored separately
                            instance_number = node['data'].get('_instance_number', 1)

                            # First try to resolve with specific instance number
                            resolved_app_id = seed_instance_to_app_id.get((seed_key, instance_number))

                            if not resolved_app_id and instance_number > 1:
                                # Instance doesn't exist yet, use default instance
                                base_app_id = seed_key_to_app_id.get(seed_key)
                                if base_app_id:
                                    logger.info(f"Instance {instance_number} for {seed_key} not found, will use instance 1")
                                    resolved_app_id = base_app_id
                            elif not resolved_app_id:
                                # Fall back to default instance
                                resolved_app_id = seed_key_to_app_id.get(seed_key)
                        else:
                            # Old format: appId contains seed_key directly (backward compatibility)
                            instance_number = node['data'].get('_instance_number', 1)
                            resolved_app_id = seed_instance_to_app_id.get((app_ref, instance_number))

                            if not resolved_app_id:
                                resolved_app_id = seed_key_to_app_id.get(app_ref)

                        if resolved_app_id:
                            node['data']['appId'] = resolved_app_id
                            # Remove temporary fields
                            node['data'].pop('_app_reference', None)
                            node['data'].pop('_seed_key', None)
                            node['data'].pop('_original_appId', None)
                            node['data'].pop('_instance_number', None)
                            node['data'].pop('_instance_name', None)
                    elif app_ref and (not node['data'].get('_app_reference') or node['data'].get('_app_reference') == 'custom'):
                        # Cross-instance import or custom app
                        # Resolution priority:
                        # 1. First check if the UUID exists in current instance (same instance import)
                        # 2. If not and seed_key exists, try to match by seed_key (cross-instance with seed apps)
                        # 3. Finally, try to match by app name (fallback for custom apps)

                        app_exists = any(str(app.app_id) == app_ref for app in applications)

                        if app_exists:
                            # App ID is valid in this instance - keep it
                            resolved_app_id = app_ref
                            logger.info(f"App ID {app_ref} exists in current instance for node {node.get('id')}")
                        else:
                            # App ID doesn't exist - try alternative resolution
                            resolved_app_id = None

                            # First try seed_key if available
                            seed_key = node['data'].get('_seed_key')
                            if seed_key and seed_key in seed_key_to_app_id:
                                resolved_app_id = seed_key_to_app_id[seed_key]
                                logger.info(f"Resolved app by seed_key for node {node.get('id')}: '{seed_key}' -> {resolved_app_id}")
                                node['data']['appId'] = resolved_app_id
                                # Clean up temporary fields
                                node['data'].pop('_seed_key', None)
                                node['data'].pop('_app_reference', None)
                            else:
                                # No seed_key match - try app name as last resort
                                app_name = node['data'].get('appName')
                                if app_name and app_name in app_name_to_id:
                                    logger.info(f"Resolved app by name for node {node.get('id')}: '{app_name}' -> {app_name_to_id[app_name]} (original ID: {app_ref})")
                                    resolved_app_id = app_name_to_id[app_name]
                                    node['data']['appId'] = resolved_app_id
                                else:
                                    logger.warning(f"App ID {app_ref} not found, no seed_key match, and no matching app name '{app_name}' in node {node.get('id')}")
                                    # Clear invalid app ID to prevent errors
                                    node['data']['appId'] = None
                                    resolved_app_id = None
                    else:
                        # Already has the correct app_id or no reference
                        resolved_app_id = app_ref
                    
                    # Resolve service reference if we have a resolved app_id
                    if service_ref and node['data'].get('_service_reference') == 'has_name' and resolved_app_id:
                        # New format: serviceId is UUID, _service_name has the name
                        service_name = node['data'].get('_service_name')
                        if service_name and resolved_app_id in app_service_mapping:
                            # Try to resolve by name first
                            service_id = app_service_mapping[resolved_app_id].get(service_name)
                            if service_id:
                                node['data']['serviceId'] = service_id
                                logger.info(f"Resolved service by name: '{service_name}' -> {service_id}")
                            else:
                                # Service not found - this is an error condition
                                error_msg = f"Service '{service_name}' not found for application {resolved_app_id} in node {node.get('id')}. Please verify the service name and try again."
                                logger.error(error_msg)
                                raise HTTPException(
                                    status_code=400,
                                    detail={
                                        "error": "Service resolution failed",
                                        "message": error_msg,
                                        "node_id": node.get('id'),
                                        "service_name": service_name,
                                        "app_id": resolved_app_id
                                    }
                                )
                        else:
                            # No service name or app has no services
                            node['data']['serviceId'] = None

                        # Remove temporary fields
                        node['data'].pop('_service_reference', None)
                        node['data'].pop('_service_name', None)
                        node['data'].pop('_original_serviceId', None)

                    elif service_ref and node['data'].get('_service_reference') == 'service_name' and resolved_app_id:
                        # Old format: serviceId contains the service name directly
                        if resolved_app_id in app_service_mapping:
                            service_id = app_service_mapping[resolved_app_id].get(service_ref)
                            if service_id:
                                node['data']['serviceId'] = service_id
                                # Remove temporary fields
                                node['data'].pop('_service_reference', None)
                                node['data'].pop('_original_serviceId', None)
                            else:
                                # Service not found - this is an error condition
                                error_msg = f"Service '{service_ref}' not found for application {resolved_app_id} in node {node.get('id')}. Please verify the service name and try again."
                                logger.error(error_msg)
                                raise HTTPException(
                                    status_code=400,
                                    detail={
                                        "error": "Service resolution failed",
                                        "message": error_msg,
                                        "node_id": node.get('id'),
                                        "service_name": service_ref,
                                        "app_id": resolved_app_id
                                    }
                                )
                        else:
                            # App has no services - clear the serviceId
                            node['data']['serviceId'] = None
                    elif service_ref and resolved_app_id:
                        # No _service_reference marker - this could be a legacy import or cross-instance import
                        # Validate that the serviceId belongs to the resolved app
                        service_belongs_to_app = False
                        
                        if resolved_app_id in app_service_mapping:
                            # Check if this serviceId belongs to this app
                            for svc_name, svc_id in app_service_mapping[resolved_app_id].items():
                                if svc_id == service_ref:
                                    service_belongs_to_app = True
                                    break
                        
                        if not service_belongs_to_app:
                            # ServiceId doesn't belong to this app
                            # This happens when importing across different IOFlow instances
                            # Try to resolve by service name
                            service_name = node['data'].get('service')  # The service name field if present
                            
                            if service_name and resolved_app_id in app_service_mapping:
                                # Try to find the service by name in this app
                                correct_service_id = app_service_mapping[resolved_app_id].get(service_name)
                                
                                if correct_service_id:
                                    logger.info(f"Resolved service for node {node.get('id')}: '{service_name}' -> {correct_service_id} (was {service_ref})")
                                    node['data']['serviceId'] = correct_service_id
                                else:
                                    # No matching service found by name
                                    error_msg = f"Service '{service_name}' not found for application {resolved_app_id} in node {node.get('id')}. The serviceId '{service_ref}' from the imported flow doesn't match any service in this instance."
                                    logger.error(error_msg)
                                    raise HTTPException(
                                        status_code=400,
                                        detail={
                                            "error": "Service resolution failed",
                                            "message": error_msg,
                                            "node_id": node.get('id'),
                                            "service_name": service_name,
                                            "app_id": resolved_app_id,
                                            "original_service_id": service_ref
                                        }
                                    )
                            else:
                                # No service name to match against
                                logger.warning(f"ServiceId {service_ref} doesn't belong to app {resolved_app_id} and no service name available for fallback")
                                node['data']['serviceId'] = None
        
        # Process trigger config
        import_trigger_config = json.loads(json.dumps(flow_data['trigger_config']))
        if import_trigger_config.get('_app_reference') == 'seed_key':
            # New format: app_id is UUID, _seed_key has the seed key
            seed_key = import_trigger_config.get('_seed_key')
            if not seed_key:
                # Old format: app_id contains seed_key directly
                seed_key = import_trigger_config.get('app_id')

            if seed_key:
                app_id = seed_key_to_app_id.get(seed_key)
                if app_id:
                    import_trigger_config['app_id'] = app_id
                    import_trigger_config.pop('_app_reference', None)
                    import_trigger_config.pop('_seed_key', None)
                    import_trigger_config.pop('_original_app_id', None)
        elif import_trigger_config.get('app_id') and (not import_trigger_config.get('_app_reference') or import_trigger_config.get('_app_reference') == 'custom'):
            # Cross-instance or custom app - check if UUID is valid, otherwise try seed_key, then name
            app_id = import_trigger_config.get('app_id')
            app_exists = app_id in all_app_ids

            if not app_exists:
                # Resolution priority: seed_key first, then app name
                resolved_app_id = None

                # First try seed_key if available
                seed_key = import_trigger_config.get('_seed_key')
                if seed_key and seed_key in seed_key_to_app_id:
                    resolved_app_id = seed_key_to_app_id[seed_key]
                    import_trigger_config['app_id'] = resolved_app_id
                    logger.info(f"Resolved trigger app by seed_key: '{seed_key}' -> {resolved_app_id}")
                else:
                    # No seed_key match - try app name as last resort
                    app_name = import_trigger_config.get('app_name')
                    if app_name and app_name in app_name_to_id:
                        import_trigger_config['app_id'] = app_name_to_id[app_name]
                        logger.info(f"Resolved trigger app by name: '{app_name}' -> {app_name_to_id[app_name]}")
                    else:
                        # Clear invalid app_id
                        import_trigger_config['app_id'] = None
                        logger.warning(f"Trigger app ID {app_id} not found, no seed_key match, and no matching app name '{app_name}'")

            # Clean up temp fields
            import_trigger_config.pop('_app_reference', None)
            import_trigger_config.pop('_seed_key', None)
        
        # Create the flow
        schema_name = get_tenant_schema(current_user, db)
        tenant_id = current_user.tenant_id
        
        with get_tenant_db(schema_name) as tenant_db:
            # Remembered before any suffixing, so the response can say whether
            # what got saved is what was asked for.
            requested_flow_name = flow_data['flow_name']

            # Check if flow name already exists
            existing_flow = tenant_db.query(Flow).filter(
                Flow.flow_name == flow_data['flow_name']
            ).first()
            
            if existing_flow and overwrite_existing:
                # Same design, saved again: update in place so the flow keeps
                # its id, its history and anything already pointing at it.
                existing_flow.description = flow_data.get('description')
                existing_flow.category = flow_data.get('category')
                existing_flow.trigger_config = import_trigger_config
                existing_flow.flow_definition = import_definition
                existing_flow.is_synchronous = flow_data.get('is_synchronous', False)
                existing_flow.sync_timeout = flow_data.get('sync_timeout', 30)
                existing_flow.last_modified_by = current_user.user_id
                tenant_db.commit()

                return {
                    'success': True,
                    'flow_id': str(existing_flow.flow_id),
                    'flow_name': existing_flow.flow_name,
                    'updated': True,
                    'message': 'Flow updated successfully',
                    'import_summary': {
                        'resolved_applications': len(required_apps),
                        'warnings': metadata.get('warnings', [])
                    }
                }

            if existing_flow:
                # Append timestamp to make it unique
                flow_data['flow_name'] = f"{flow_data['flow_name']} (Imported {datetime.now().strftime('%Y-%m-%d %H:%M')})"

            # Create new flow
            new_flow = Flow(
                flow_name=flow_data['flow_name'],
                description=flow_data.get('description'),
                category=flow_data.get('category'),
                trigger_config=import_trigger_config,
                flow_definition=import_definition,
                status=FlowStatus.INACTIVE,
                is_synchronous=flow_data.get('is_synchronous', False),
                sync_timeout=flow_data.get('sync_timeout', 30),
                created_by=current_user.user_id,
                tenant_id=tenant_id
            )
            
            tenant_db.add(new_flow)
            tenant_db.commit()
            
            return {
                'success': True,
                'flow_id': str(new_flow.flow_id),
                # The PERSISTED name — it may have been suffixed just above,
                # and a caller that is told the name it asked for cannot tell.
                'flow_name': new_flow.flow_name,
                'updated': False,
                'renamed': new_flow.flow_name != requested_flow_name,
                'message': 'Flow imported successfully',
                'import_summary': {
                    'resolved_applications': len(required_apps),
                    'warnings': metadata.get('warnings', [])
                }
            }
    
    except HTTPException:
        # Re-raise HTTPException with detailed error info
        raise
    except Exception as e:
        logger.error(f"Failed to import flow: {str(e)}", exc_info=True)
        logger.error(f"Import data type: {type(import_data)}")
        logger.error(f"Import data keys: {list(import_data.keys()) if isinstance(import_data, dict) else 'Not a dict'}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import flow: {str(e)}"
        )


# ============================================================================
# Flow Editor Endpoints - For editing existing flows
# ============================================================================

@router.put("/{flow_id}/nodes/{node_id}")
async def replace_node_in_flow(
    flow_id: str,
    node_id: str,
    node_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Replace a specific node in an existing flow"""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )

        # Check permissions
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not permit editing flow structure"
            )
        if flow.created_by != current_user.user_id:
            if user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this flow"
                )
        # Find and replace the node
        flow_definition = flow.flow_definition
        nodes = flow_definition.get('nodes', [])
        node_found = False

        for i, node in enumerate(nodes):
            if node.get('id') == node_id:
                nodes[i] = node_data
                node_found = True
                break

        if not node_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id}' not found in flow"
            )

        # Update flow definition
        flow_definition['nodes'] = nodes
        flow.flow_definition = flow_definition
        flow.updated_at = datetime.utcnow()

        # Force SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(flow, 'flow_definition')

        tenant_db.commit()

        return {
            "success": True,
            "message": f"Node '{node_id}' replaced successfully",
            "flow_id": str(flow.flow_id),
            "flow_definition": flow_definition
        }


@router.post("/{flow_id}/nodes")
async def add_node_to_flow(
    flow_id: str,
    node_data: dict,
    position: str = "after_last",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new node to an existing flow

    Args:
        flow_id: Flow ID
        node_data: Complete node configuration
        position: Where to add the node - "after_last", "after_trigger", or a specific node_id
    """
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )

        # Check permissions
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not permit editing flow structure"
            )
        if flow.created_by != current_user.user_id:
            if user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this flow"
                )
        # Add the node
        flow_definition = flow.flow_definition
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])

        # Validate node has required fields
        if 'id' not in node_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Node data must include 'id' field"
            )

        nodes.append(node_data)

        # Auto-connect based on position
        new_node_id = node_data['id']

        if position == "after_last" and len(nodes) > 1:
            # Find the last non-trigger node
            last_node = None
            for node in reversed(nodes[:-1]):  # Exclude the just-added node
                if node.get('type') != 'trigger':
                    last_node = node
                    break

            if last_node:
                edges.append({
                    "id": f"e_{last_node['id']}_{new_node_id}",
                    "source": last_node['id'],
                    "target": new_node_id,
                    "sourceHandle": None,
                    "targetHandle": None
                })

        elif position == "after_trigger":
            # Find trigger node
            trigger_node = next((n for n in nodes if n.get('type') == 'trigger'), None)
            if trigger_node:
                edges.append({
                    "id": f"e_{trigger_node['id']}_{new_node_id}",
                    "source": trigger_node['id'],
                    "target": new_node_id,
                    "sourceHandle": None,
                    "targetHandle": None
                })

        elif position != "after_last":
            # Position is a node_id
            source_node = next((n for n in nodes if n.get('id') == position), None)
            if source_node:
                edges.append({
                    "id": f"e_{position}_{new_node_id}",
                    "source": position,
                    "target": new_node_id,
                    "sourceHandle": None,
                    "targetHandle": None
                })

        # Update flow definition
        flow_definition['nodes'] = nodes
        flow_definition['edges'] = edges
        flow.flow_definition = flow_definition
        flow.updated_at = datetime.utcnow()

        # Force SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(flow, 'flow_definition')

        tenant_db.commit()

        return {
            "success": True,
            "message": f"Node '{new_node_id}' added successfully",
            "flow_id": str(flow.flow_id),
            "flow_definition": flow_definition
        }


@router.delete("/{flow_id}/nodes/{node_id}")
async def remove_node_from_flow(
    flow_id: str,
    node_id: str,
    reconnect: bool = Query(True, description="Auto-reconnect edges after removing node"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a node from an existing flow"""
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )

        # Check permissions
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not permit editing flow structure"
            )
        if flow.created_by != current_user.user_id:
            if user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this flow"
                )
        # Remove the node
        flow_definition = flow.flow_definition
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])

        # Check if node is trigger
        node_to_remove = next((n for n in nodes if n.get('id') == node_id), None)
        if not node_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id}' not found in flow"
            )

        if node_to_remove.get('type') == 'trigger':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove trigger node. Every flow must have a trigger."
            )

        # Remove node
        nodes = [n for n in nodes if n.get('id') != node_id]

        # Handle edges
        incoming_edges = [e for e in edges if e.get('target') == node_id]
        outgoing_edges = [e for e in edges if e.get('source') == node_id]

        if reconnect and incoming_edges and outgoing_edges:
            # Reconnect: connect all incoming edges to all outgoing targets
            for in_edge in incoming_edges:
                for out_edge in outgoing_edges:
                    new_edge = {
                        "id": f"e_{in_edge['source']}_{out_edge['target']}",
                        "source": in_edge['source'],
                        "target": out_edge['target'],
                        "sourceHandle": in_edge.get('sourceHandle'),
                        "targetHandle": out_edge.get('targetHandle')
                    }
                    # Only add if this connection doesn't already exist
                    if not any(e.get('source') == new_edge['source'] and e.get('target') == new_edge['target'] for e in edges):
                        edges.append(new_edge)

        # Remove all edges connected to this node
        edges = [e for e in edges if e.get('source') != node_id and e.get('target') != node_id]

        # Update flow definition
        flow_definition['nodes'] = nodes
        flow_definition['edges'] = edges
        flow.flow_definition = flow_definition
        flow.updated_at = datetime.utcnow()

        # Force SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(flow, 'flow_definition')

        tenant_db.commit()

        return {
            "success": True,
            "message": f"Node '{node_id}' removed successfully",
            "flow_id": str(flow.flow_id),
            "reconnected": reconnect and len(incoming_edges) > 0 and len(outgoing_edges) > 0,
            "flow_definition": flow_definition
        }


@router.put("/{flow_id}/edges")
async def update_edge_in_flow(
    flow_id: str,
    edge_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update or add an edge connection in the flow

    Args:
        flow_id: Flow ID
        edge_data: Edge configuration with source, target, sourceHandle, targetHandle
    """
    schema_name = get_tenant_schema(current_user, db)

    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()

        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )

        # Check permissions
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not permit editing flow structure"
            )
        if flow.created_by != current_user.user_id:
            if user_role not in ["INSTANCE_ADMIN", "TENANT_ADMIN"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this flow"
                )

        # Validate edge_data
        if 'source' not in edge_data or 'target' not in edge_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Edge data must include 'source' and 'target' fields"
            )
        # Generate edge ID if not provided
        if 'id' not in edge_data:
            edge_data['id'] = f"e_{edge_data['source']}_{edge_data['target']}"

        flow_definition = flow.flow_definition
        edges = flow_definition.get('edges', [])

        # Check if edge already exists
        existing_edge_index = None
        for i, edge in enumerate(edges):
            if edge.get('id') == edge_data['id']:
                existing_edge_index = i
                break

        if existing_edge_index is not None:
            # Update existing edge
            edges[existing_edge_index] = edge_data
            action = "updated"
        else:
            # Add new edge
            edges.append(edge_data)
            action = "added"

        # Update flow definition
        flow_definition['edges'] = edges
        flow.flow_definition = flow_definition
        flow.updated_at = datetime.utcnow()

        # Force SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(flow, 'flow_definition')

        tenant_db.commit()

        return {
            "success": True,
            "message": f"Edge {action} successfully",
            "flow_id": str(flow.flow_id),
            "edge_id": edge_data['id'],
            "flow_definition": flow_definition
        }


# ============================================================================
# Chat Input Trigger Endpoints
# ============================================================================

@router.post("/{flow_id}/chat", response_model=ChatExecuteResponse)
async def execute_flow_chat(
    flow_id: str,
    request: ChatExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute a flow with chat_input trigger type.

    Maintains conversation context across multiple invocations.
    Returns chat_session_id for subsequent messages.
    """
    schema_name = get_tenant_schema(current_user, db)
    tenant_id = current_user.tenant_id

    with get_tenant_db(schema_name) as tenant_db:
        # Get flow and validate it has chat_input trigger
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

        trigger_config = parse_json_field(flow.trigger_config)
        if trigger_config.get('type') != 'chat_input':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint is only for flows with chat_input trigger type"
            )

    # Import the chat session service
    from services.node_session_service import get_chat_session_service

    chat_service = get_chat_session_service()

    # Get session timeout from trigger config (default 24 hours)
    session_timeout_minutes = trigger_config.get('session_timeout_minutes', 1440)
    ttl_hours = session_timeout_minutes / 60

    # Create or get chat session
    chat_session_id = request.chat_session_id
    is_first_message = False

    if not chat_session_id:
        # Create new session
        chat_session_id = chat_service.create_session(
            tenant_id=tenant_id,
            flow_id=flow_id,
            user_id=current_user.user_id,
            ttl_hours=int(ttl_hours),
            schema_name=schema_name
        )
        is_first_message = True
        logger.info(f"Created new chat session: {chat_session_id[:8]}... for flow {flow_id[:8]}...")
    else:
        # Validate and update existing session
        session_info = chat_service.get_session(chat_session_id, tenant_id, schema_name)
        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or expired"
            )
        if session_info.get('status') != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chat session is {session_info.get('status')}"
            )
        chat_service.update_session_activity(chat_session_id, tenant_id, schema_name)

    try:
        # Execute the flow with chat context
        engine = ExecutionEngine(schema_name, tenant_id, current_user.user_id)

        # Build trigger data with chat context
        trigger_data = {
            'trigger_type': 'chat_input',
            'variables': {
                'message': request.message,
                'session_id': chat_session_id,
                'is_first_message': is_first_message
            },
            'chat_session_id': chat_session_id,
            'user_id': current_user.user_id
        }

        # Execute flow synchronously
        result = await engine.execute_flow_sync(
            flow_id=flow_id,
            trigger_data=trigger_data,
            trigger_type='chat_input'
        )

        # Extract response from result
        response_data = result
        if isinstance(result, dict):
            response_data = result.get('data') or result.get('result_data') or result

        return ChatExecuteResponse(
            execution_id=result.get('execution_id', '') if isinstance(result, dict) else '',
            chat_session_id=chat_session_id,
            is_first_message=is_first_message,
            response=response_data,
            status='completed'
        )

    except Exception as e:
        logger.error(f"Chat flow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat flow execution failed: {str(e)}"
        )


@router.post("/{flow_id}/chat/end")
async def end_chat_session(
    flow_id: str,
    request: ChatEndRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    End a chat session and cleanup all associated node states.
    """
    schema_name = get_tenant_schema(current_user, db)
    tenant_id = current_user.tenant_id

    # Import the chat session service
    from services.node_session_service import get_chat_session_service

    chat_service = get_chat_session_service()

    # End the session
    success = chat_service.end_session(request.chat_session_id, tenant_id, schema_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )

    logger.info(f"Ended chat session: {request.chat_session_id[:8]}...")

    return {
        "status": "ended",
        "chat_session_id": request.chat_session_id
    }

# ============================================================================
# Usage & cost of a flow's external calls (services/flow_usage.py)
# ============================================================================

class FlowBudgetUpdate(BaseModel):
    """``daily`` = the most the flow may spend per UTC day; null/0 removes it."""
    daily: Optional[float] = None
    currency: Optional[str] = None


@router.get("/{flow_id}/usage")
async def get_flow_usage(
    flow_id: str,
    days: int = Query(30, ge=1, le=366),
    runs: int = Query(20, ge=0, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """What the flow's external calls used and cost: totals, per UTC day, per
    step and meter, per run — estimated from each response and the connector's
    (or the connection's own) prices."""
    from services import flow_usage
    schema_name = get_tenant_schema(current_user, db)
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        definition = parse_json_field(flow.flow_definition, {})
    try:
        return await asyncio.to_thread(flow_usage.summary, schema_name, flow_id, definition, days, runs)
    except Exception as e:
        logger.exception("Reading usage of flow %s failed", flow_id)
        raise HTTPException(status_code=500, detail=f"Could not read the flow's usage: {e}")


@router.put("/{flow_id}/budget")
async def set_flow_budget(
    flow_id: str,
    body: FlowBudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set or remove the flow's daily budget (``flow_definition.settings.budget``).
    Once a UTC day's metered cost reaches it, new runs and further metered calls
    stop with the reason until the next UTC day."""
    from services import flow_usage
    from sqlalchemy.orm.attributes import flag_modified
    if body.daily is not None and not (0 <= body.daily <= 1_000_000):
        raise HTTPException(status_code=422, detail="A daily budget must be between 0 and 1,000,000")
    schema_name = get_tenant_schema(current_user, db)
    with get_tenant_db(schema_name) as tenant_db:
        flow = tenant_db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
        if user_role in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Your role does not permit changing a flow's budget")
        if flow.created_by != current_user.user_id and user_role not in ("INSTANCE_ADMIN", "TENANT_ADMIN"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the flow's owner or an administrator can change its budget")
        definition = dict(parse_json_field(flow.flow_definition, {}))
        flow_settings = dict(definition.get('settings') or {})
        if body.daily:
            flow_settings['budget'] = {"daily": round(float(body.daily), 4),
                                       "currency": (body.currency or "USD").strip().upper()[:8] or "USD"}
        else:
            flow_settings.pop('budget', None)
        definition['settings'] = flow_settings
        flow.flow_definition = definition
        flow.last_modified_by = current_user.user_id
        flow.updated_at = datetime.utcnow()
        flag_modified(flow, 'flow_definition')
        tenant_db.commit()
    return {"flow_id": flow_id, "budget": flow_usage.budget_of(definition)}

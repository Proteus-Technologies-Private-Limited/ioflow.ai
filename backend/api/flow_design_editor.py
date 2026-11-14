"""
Flow Design Editor API - Endpoints for Editing Existing Flow Designs

This module provides API endpoints for editing existing flow designs with:
- Load existing flow designs
- Modify nodes and connections
- Update trigger configurations
- Edit action parameters
- Save modified flows
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from db.database import get_db
from api.auth import get_current_user
from db.models import User
from core.config import settings

# Import Flow Design Editor components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.flow_design_editor.core.session_manager import get_session_manager, SessionStatus
from agent.flow_design_editor.core.context_manager import get_context_manager
from agent.flow_design_editor.core.cache_manager import get_cache_manager
from agent.flow_design_editor.builders.trigger_builder import get_trigger_builder
from agent.flow_design_editor.builders.action_builder import get_action_builder

# Import database models - PostgreSQL Only
from db.application_models import (
    Application, ApplicationService, ApplicationEvent
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flow-design-editor", tags=["Flow Design Editor"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SessionCreateRequest(BaseModel):
    """Request to create a new flow design session"""
    name: str = Field(..., description="Flow name")
    description: str = Field(default="", description="Flow description")
    ttl_minutes: int = Field(default=30, description="Session TTL in minutes")


class SessionResponse(BaseModel):
    """Session information response"""
    session_id: str
    name: str
    status: str
    nodes_count: int
    edges_count: int
    created_at: str
    updated_at: str
    expires_at: Optional[str]


class NodeAddRequest(BaseModel):
    """Request to add a node to session"""
    node_type: str = Field(..., description="Node type (trigger, action, transform, etc.)")
    position: Dict[str, int] = Field(..., description="Node position {x, y}")
    data: Dict[str, Any] = Field(..., description="Node data")


class EdgeAddRequest(BaseModel):
    """Request to add an edge to session"""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    source_handle: Optional[str] = Field(None, description="Source handle")
    target_handle: Optional[str] = Field(None, description="Target handle")


class TriggerCreateRequest(BaseModel):
    """Request to create trigger node"""
    trigger_type: str = Field(..., description="Trigger type (manual, webhook, etc.)")
    config: Dict[str, Any] = Field(..., description="Trigger configuration")
    position: Optional[Dict[str, int]] = None


class ActionCreateRequest(BaseModel):
    """Request to create action node"""
    app_id: str = Field(..., description="Application ID")
    service_id: str = Field(..., description="Service ID")
    parameters: Dict[str, Any] = Field(..., description="Service parameters")
    position: Optional[Dict[str, int]] = None


class ApplicationSummary(BaseModel):
    """Lightweight application summary"""
    id: str
    name: str
    type: str
    category: Optional[str]
    services_count: int
    events_count: int


class ServiceSummary(BaseModel):
    """Lightweight service summary"""
    id: str
    name: str
    display_name: str
    type: str
    description: Optional[str]
    has_parameters: bool


# ============================================================================
# Discovery Endpoints (Cached, Lightweight)
# ============================================================================

@router.get("/discover/applications", response_model=List[ApplicationSummary])
async def discover_applications(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get lightweight list of applications.

    Returns minimal data, uses caching for performance.
    """
    cache = get_cache_manager()

    # Try cache first
    cache_key = f"apps_list_{category or 'all'}_{search or 'all'}"
    cached = cache.get_applications_list()

    if cached:
        logger.debug(f"Cache hit for applications list")
        return cached

    # Query database
    query = db.query(Application)

    if category:
        query = query.filter(Application.category == category)

    if search:
        query = query.filter(Application.name.ilike(f"%{search}%"))

    apps = query.all()

    # Build lightweight response
    result = []
    for app in apps:
        services_count = db.query(ApplicationService).filter(
            ApplicationService.app_id == app.id
        ).count()

        events_count = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == app.id
        ).count()

        result.append(ApplicationSummary(
            id=str(app.id),
            name=app.name,
            type=app.type,
            category=app.category,
            services_count=services_count,
            events_count=events_count
        ))

    # Cache the result
    cache.set_applications_list([r.dict() for r in result])

    logger.info(f"Discovered {len(result)} applications")
    return result


@router.get("/discover/services/{app_id}", response_model=List[ServiceSummary])
async def discover_services(
    app_id: str,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get lightweight list of services for an application.

    Returns minimal data without full schemas.
    """
    cache = get_cache_manager()

    # Try cache first
    cache_key = f"services_{app_id}"
    cached = cache.get_service(cache_key)

    if cached:
        logger.debug(f"Cache hit for services list: {app_id}")
        return cached

    # Query database
    query = db.query(ApplicationService).filter(
        ApplicationService.app_id == app_id
    )

    if search:
        query = query.filter(ApplicationService.name.ilike(f"%{search}%"))

    services = query.all()

    # Build lightweight response
    result = []
    for service in services:
        result.append(ServiceSummary(
            id=str(service.id),
            name=service.name,
            display_name=service.display_name or service.name,
            type=service.type,
            description=service.description,
            has_parameters=bool(service.parameters)
        ))

    # Cache the result
    cache.set_service(cache_key, [r.dict() for r in result])

    logger.info(f"Discovered {len(result)} services for app {app_id}")
    return result


@router.get("/discover/events/{app_id}")
async def discover_events(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get lightweight list of events for an application."""
    cache = get_cache_manager()

    # Try cache first
    cache_key = f"events_{app_id}"
    cached = cache.get_service(cache_key)  # Reuse service cache

    if cached:
        return {"events": cached}

    # Query database
    events = db.query(ApplicationEvent).filter(
        ApplicationEvent.app_id == app_id
    ).all()

    # Build lightweight response
    result = [
        {
            "id": str(event.event_id),
            "name": event.event_name,
            "display_name": event.display_name or event.event_name,
            "event_type": event.event_type,
            "description": event.description
        }
        for event in events
    ]

    # Cache the result
    cache.set_service(cache_key, result)

    return {"events": result}


# ============================================================================
# Session Management Endpoints
# ============================================================================

@router.post("/session/create", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a new flow design session."""
    session_mgr = get_session_manager()

    session_id = session_mgr.create_session(
        name=request.name,
        description=request.description,
        ttl_minutes=request.ttl_minutes
    )

    # Get session state
    state = session_mgr.get_session_state(session_id)

    logger.info(f"Created session {session_id} for user {current_user.email}")

    return SessionResponse(**state)


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get session state."""
    session_mgr = get_session_manager()

    state = session_mgr.get_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(**state)


@router.post("/session/{session_id}/node")
async def add_node(
    session_id: str,
    request: NodeAddRequest,
    current_user: User = Depends(get_current_user)
):
    """Add a node to the session."""
    session_mgr = get_session_manager()

    node_id = session_mgr.add_node(
        session_id=session_id,
        node_type=request.node_type,
        position=request.position,
        data=request.data
    )

    if not node_id:
        raise HTTPException(status_code=404, detail="Session not found or inactive")

    logger.info(f"Added node {node_id} to session {session_id}")

    return {"node_id": node_id, "session_id": session_id}


@router.post("/session/{session_id}/edge")
async def add_edge(
    session_id: str,
    request: EdgeAddRequest,
    current_user: User = Depends(get_current_user)
):
    """Add an edge to the session."""
    session_mgr = get_session_manager()

    edge_id = session_mgr.add_edge(
        session_id=session_id,
        source=request.source,
        target=request.target,
        source_handle=request.source_handle,
        target_handle=request.target_handle
    )

    if not edge_id:
        raise HTTPException(status_code=404, detail="Session not found or invalid nodes")

    logger.info(f"Added edge {edge_id} to session {session_id}")

    return {"edge_id": edge_id, "session_id": session_id}


@router.post("/session/{session_id}/checkpoint")
async def create_checkpoint(
    session_id: str,
    label: str = Query(default="", description="Checkpoint label"),
    current_user: User = Depends(get_current_user)
):
    """Create a checkpoint for the session."""
    session_mgr = get_session_manager()

    checkpoint_id = session_mgr.create_checkpoint(session_id, label)
    if not checkpoint_id:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"Created checkpoint {checkpoint_id} for session {session_id}")

    return {"checkpoint_id": checkpoint_id, "session_id": session_id}


@router.post("/session/{session_id}/restore/{checkpoint_id}")
async def restore_checkpoint(
    session_id: str,
    checkpoint_id: str,
    current_user: User = Depends(get_current_user)
):
    """Restore session from a checkpoint."""
    session_mgr = get_session_manager()

    success = session_mgr.restore_checkpoint(session_id, checkpoint_id)
    if not success:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    logger.info(f"Restored session {session_id} from checkpoint {checkpoint_id}")

    return {"restored": True, "session_id": session_id, "checkpoint_id": checkpoint_id}


@router.post("/session/{session_id}/complete")
async def complete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Complete the session and generate final flow JSON."""
    session_mgr = get_session_manager()

    flow_json = session_mgr.complete_session(session_id)
    if not flow_json:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"Completed session {session_id}")

    return flow_json


# ============================================================================
# Builder Endpoints (Node Creation Helpers)
# ============================================================================

@router.post("/builder/trigger")
async def build_trigger(
    request: TriggerCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Build a trigger node configuration."""
    trigger_builder = get_trigger_builder()

    try:
        if request.trigger_type == "manual":
            node_data, trigger_config = trigger_builder.create_manual_trigger(
                variables=request.config.get("variables", []),
                position=request.position
            )
        elif request.trigger_type == "webhook":
            node_data, trigger_config = trigger_builder.create_webhook_trigger(
                webhook_path=request.config.get("webhook_path", "/webhook"),
                method=request.config.get("method", "POST"),
                position=request.position
            )
        elif request.trigger_type == "schedule":
            node_data, trigger_config = trigger_builder.create_schedule_trigger(
                cron_expression=request.config.get("cron_expression"),
                timezone=request.config.get("timezone", "UTC"),
                position=request.position
            )
        elif request.trigger_type == "application_event":
            node_data, trigger_config = trigger_builder.create_application_event_trigger(
                app_id=request.config.get("app_id"),
                event_id=request.config.get("event_id"),
                app_name=request.config.get("app_name", ""),
                event_name=request.config.get("event_name", ""),
                position=request.position
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown trigger type: {request.trigger_type}")

        return {
            "node_data": node_data,
            "trigger_config": trigger_config
        }
    except Exception as e:
        logger.error(f"Error building trigger: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/builder/action")
async def build_action(
    request: ActionCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Build an action node configuration."""
    action_builder = get_action_builder()

    try:
        # Get service info from cache/db
        cache = get_cache_manager()
        service_info = cache.get_service(request.service_id)

        if not service_info:
            # Fetch from database
            # This would be implemented based on your DB structure
            service_info = {"name": "Service", "display_name": "Service"}

        node_data = action_builder.create_action_node(
            app_id=request.app_id,
            service_id=request.service_id,
            parameters=request.parameters,
            service_name=service_info.get("display_name", "Service"),
            position=request.position
        )

        return {"node_data": node_data}
    except Exception as e:
        logger.error(f"Error building action: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Parameter Template Endpoints
# ============================================================================

@router.get("/params/template/{service_id}")
async def get_parameter_template(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get parameter template for a service (minimal, cached)."""
    cache = get_cache_manager()

    # Try cache
    cached = cache.get_parameter_schema(service_id)
    if cached:
        return {"service_id": service_id, "template": cached}

    # Fetch from database
    service = db.query(ApplicationService).filter(
        ApplicationService.id == service_id
    ).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Extract minimal template
    schema = service.parameters or {}
    template = {
        "required": schema.get("required", []),
        "properties": {
            name: {
                "type": prop.get("type"),
                "description": prop.get("description", "")[:100]  # Truncate
            }
            for name, prop in schema.get("properties", {}).items()
        }
    }

    # Cache it
    cache.set_parameter_schema(service_id, template)

    return {"service_id": service_id, "template": template}


@router.get("/params/examples/{service_type}")
async def get_parameter_examples(
    service_type: str,
    current_user: User = Depends(get_current_user)
):
    """Get parameter examples for common service types."""
    examples = {
        "google_sheets": {
            "append_values": {
                "spreadsheetId": "{{input.sheet_id}}",
                "range": "Sheet1!A1",
                "valueInputOption": "USER_ENTERED",
                "values": "{{node_outputs.prepare_data.rows}}"
            }
        },
        "google_gemini": {
            "generate_content": {
                "model": "gemini-2.5-flash",
                "contents": [{"parts": [{"text": "{{input.prompt}}"}]}]
            }
        },
        "openai": {
            "chat_completion": {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "{{input.message}}"}]
            }
        }
    }

    result = examples.get(service_type, {})
    return {"service_type": service_type, "examples": result}


# ============================================================================
# Statistics and Monitoring
# ============================================================================

@router.get("/stats/cache")
async def get_cache_stats(
    current_user: User = Depends(get_current_user)
):
    """Get cache statistics."""
    cache = get_cache_manager()
    return cache.get_stats()


@router.get("/stats/context")
async def get_context_stats(
    current_user: User = Depends(get_current_user)
):
    """Get context manager statistics."""
    context = get_context_manager()
    return context.get_context_stats()


@router.post("/admin/cleanup")
async def cleanup_expired(
    current_user: User = Depends(get_current_user)
):
    """Clean up expired sessions and cache entries."""
    session_mgr = get_session_manager()
    cache = get_cache_manager()

    sessions_cleaned = session_mgr.cleanup_expired_sessions()
    cache_cleaned = cache.cleanup()

    return {
        "sessions_cleaned": sessions_cleaned,
        "cache_entries_cleaned": cache_cleaned
    }
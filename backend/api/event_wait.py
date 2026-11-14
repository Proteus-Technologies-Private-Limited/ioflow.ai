"""
Event Wait API Routes.
Handles event wait monitoring, cancellation, and token-based completion.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
import json

from db.database import get_db, get_tenant_db
from db.models import EventWait, FlowExecution, Flow, User
from db.application_models import Application
from core.auth_utils import get_current_user_required as get_current_user
from api.flows import get_tenant_schema
from schemas.event_wait_schemas import (
    EventWaitResponse, EventWaitCompleteRequest, EventWaitListResponse,
)
from services.event_wait_service import event_wait_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/event-waits", tags=["event-waits"])


def _deserialize_json(value):
    """Deserialize JSON field for SQLite compatibility."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _build_wait_response(event_wait: EventWait, db: Session) -> EventWaitResponse:
    """Build a response object from an EventWait record."""
    # Get flow name
    flow_name = None
    flow = db.query(Flow).filter(Flow.flow_id == event_wait.flow_id).first()
    if flow:
        flow_name = flow.flow_name

    # Get app name
    app_name = None
    try:
        app = db.query(Application).filter(Application.app_id == event_wait.app_id).first()
        if app:
            app_name = app.app_name
    except Exception:
        pass

    metadata = _deserialize_json(event_wait.wait_metadata) if isinstance(event_wait.wait_metadata, str) else event_wait.wait_metadata

    return EventWaitResponse(
        wait_id=event_wait.wait_id,
        tenant_id=event_wait.tenant_id,
        execution_id=event_wait.execution_id,
        flow_id=event_wait.flow_id,
        node_id=event_wait.node_id,
        app_id=event_wait.app_id,
        event_name=event_wait.event_name,
        event_id=event_wait.event_id,
        match_mode=event_wait.match_mode,
        correlation_config=_deserialize_json(event_wait.correlation_config) if isinstance(event_wait.correlation_config, str) else event_wait.correlation_config,
        callback_token=event_wait.callback_token,
        status=event_wait.status,
        timeout_at=event_wait.timeout_at,
        timeout_action=event_wait.timeout_action or 'fail',
        default_data=_deserialize_json(event_wait.default_data) if isinstance(event_wait.default_data, str) else event_wait.default_data,
        event_data=_deserialize_json(event_wait.event_data) if isinstance(event_wait.event_data, str) else event_wait.event_data,
        created_at=event_wait.created_at,
        matched_at=event_wait.matched_at,
        metadata=metadata,
        flow_name=flow_name or (metadata or {}).get('flow_name'),
        app_name=app_name or (metadata or {}).get('app_name'),
    )


@router.get("/pending", response_model=EventWaitListResponse)
async def list_pending_waits(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending event waits for the current tenant."""
    schema_name = get_tenant_schema(current_user, db)
    waits, total = event_wait_service.get_pending_waits(
        tenant_id=current_user.tenant_id,
        schema_name=schema_name,
        limit=limit,
        offset=offset,
    )

    with get_tenant_db(schema_name) as tenant_db:
        wait_responses = [_build_wait_response(w, tenant_db) for w in waits]

    return EventWaitListResponse(
        waits=wait_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{wait_id}", response_model=EventWaitResponse)
async def get_wait_detail(
    wait_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific event wait."""
    schema_name = get_tenant_schema(current_user, db)
    event_wait = event_wait_service.get_wait_detail(
        wait_id=wait_id,
        tenant_id=current_user.tenant_id,
        schema_name=schema_name,
    )
    if not event_wait:
        raise HTTPException(status_code=404, detail="Event wait not found")

    with get_tenant_db(schema_name) as tenant_db:
        return _build_wait_response(event_wait, tenant_db)


@router.get("/execution/{execution_id}")
async def get_waits_for_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all event waits for a specific execution."""
    schema_name = get_tenant_schema(current_user, db)
    waits = event_wait_service.get_waits_by_execution(
        execution_id=execution_id,
        schema_name=schema_name,
    )

    with get_tenant_db(schema_name) as tenant_db:
        return [_build_wait_response(w, tenant_db) for w in waits]


@router.post("/{wait_id}/cancel")
async def cancel_wait(
    wait_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a waiting event wait and fail its execution."""
    schema_name = get_tenant_schema(current_user, db)
    try:
        event_wait_service.cancel_wait(
            wait_id=wait_id,
            tenant_id=current_user.tenant_id,
            schema_name=schema_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Event wait cancelled successfully"}


@router.post("/token/{callback_token}/complete")
async def complete_wait_by_token(
    callback_token: str,
    data: EventWaitCompleteRequest,
):
    """Complete an event wait using a callback token (no auth required)."""
    # Find the wait by token to determine schema
    from db.database import get_db as get_main_db
    main_db = next(get_main_db())
    try:
        event_wait = main_db.query(EventWait).filter(
            EventWait.callback_token == callback_token
        ).first()
        if not event_wait:
            raise HTTPException(status_code=404, detail="Invalid callback token")

        from db.models import Tenant
        tenant = main_db.query(Tenant).filter(
            Tenant.tenant_id == event_wait.tenant_id
        ).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        schema_name = tenant.schema_name
    finally:
        main_db.close()

    try:
        await event_wait_service.complete_wait_by_token(
            callback_token=callback_token,
            event_data=data.event_data,
            schema_name=schema_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Event wait completed successfully"}

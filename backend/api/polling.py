"""
API endpoints for managing polling configurations
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from db.database import get_db, get_tenant_db
from db.models import User, Flow
from db.application_models import ApplicationEvent, ApplicationService, Application
from db.polling_models import PollingState
from api.auth import get_current_user
from api.flows import get_tenant_schema
from services.generic_polling_service import GenericPollingService
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/polling", tags=["polling"])


class PollingConfigRequest(BaseModel):
    """Request model for configuring polling"""
    polling_service: str
    polling_interval: int = 300  # Default 5 minutes
    polling_parameters: Dict[str, Any] = {}
    change_detection: Dict[str, Any] = {
        "method": "new_items",
        "identifier_field": "id"
    }


class PollingStateResponse(BaseModel):
    """Response model for polling state"""
    polling_state_id: str
    flow_id: str
    app_id: str
    event_name: str
    last_poll_timestamp: Optional[datetime]
    last_successful_poll: Optional[datetime]
    items_processed_count: int
    consecutive_errors: int
    last_error: Optional[str]


class TestPollingRequest(BaseModel):
    """Request model for testing polling configuration"""
    app_id: str
    service_name: str
    parameters: Dict[str, Any] = {}


@router.get("/states", response_model=List[PollingStateResponse])
async def get_polling_states(
    flow_id: Optional[str] = Query(None),
    app_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get polling states for the current tenant"""
    try:
        # Build query filters
        filters = [PollingState.tenant_id == current_user.tenant_id]
        
        if flow_id:
            filters.append(PollingState.flow_id == flow_id)
        if app_id:
            filters.append(PollingState.app_id == app_id)
        
        # Get polling states
        states = db.query(PollingState).filter(and_(*filters)).all()
        
        return [
            PollingStateResponse(
                polling_state_id=str(state.polling_state_id),
                flow_id=str(state.flow_id),
                app_id=str(state.app_id),
                event_name=state.event_name,
                last_poll_timestamp=state.last_poll_timestamp,
                last_successful_poll=state.last_successful_poll,
                items_processed_count=state.items_processed_count or 0,
                consecutive_errors=state.consecutive_errors or 0,
                last_error=state.last_error
            )
            for state in states
        ]
        
    except Exception as e:
        logger.error(f"Error getting polling states: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configure/{event_id}")
async def configure_polling_event(
    event_id: str,
    config: PollingConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Configure polling for an application event"""
    try:
        # Get the event
        event = db.query(ApplicationEvent).filter(
            ApplicationEvent.event_id == event_id
        ).first()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Verify the service exists
        service = db.query(ApplicationService).filter(
            and_(
                ApplicationService.app_id == event.app_id,
                ApplicationService.service_name == config.polling_service
            )
        ).first()
        
        if not service:
            raise HTTPException(
                status_code=400, 
                detail=f"Service '{config.polling_service}' not found for this application"
            )
        
        # Update event configuration
        event.event_type = "polling"
        event.event_configuration = {
            "polling_service": config.polling_service,
            "polling_interval": config.polling_interval,
            "polling_parameters": config.polling_parameters,
            "change_detection": config.change_detection
        }
        
        db.commit()
        
        return {
            "success": True,
            "message": "Polling configuration updated successfully",
            "event_id": str(event.event_id),
            "configuration": event.event_configuration
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring polling: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_polling_configuration(
    request: TestPollingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a polling configuration without saving it"""
    try:
        # Get the service
        service = db.query(ApplicationService).filter(
            and_(
                ApplicationService.app_id == request.app_id,
                ApplicationService.service_name == request.service_name
            )
        ).first()
        
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Get subscription
        from db.application_models import ApplicationSubscription
        subscription = db.query(ApplicationSubscription).filter(
            and_(
                ApplicationSubscription.tenant_id == current_user.tenant_id,
                ApplicationSubscription.app_id == request.app_id,
                ApplicationSubscription.status == 'active'
            )
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=400, 
                detail="No active subscription for this application"
            )
        
        # Execute the service
        from services.service_executors import ServiceExecutor
        executor = ServiceExecutor()
        
        result = await executor.execute_service(
            service=service,
            subscription=subscription,
            parameters=request.parameters,
            db=db
        )
        
        # Analyze the result for polling suitability
        analysis = {
            "success": result.get("success", False),
            "data_type": type(result.get("data")).__name__ if result.get("data") else None,
            "is_array": isinstance(result.get("data"), list),
            "item_count": len(result.get("data")) if isinstance(result.get("data"), list) else 1,
            "sample_data": None
        }
        
        # Get sample data
        if result.get("data"):
            if isinstance(result["data"], list) and len(result["data"]) > 0:
                analysis["sample_data"] = result["data"][0]
            elif isinstance(result["data"], dict):
                analysis["sample_data"] = result["data"]
        
        # Suggest identifier fields
        if analysis["sample_data"] and isinstance(analysis["sample_data"], dict):
            potential_ids = []
            for key in analysis["sample_data"].keys():
                if any(id_hint in key.lower() for id_hint in ["id", "uid", "key", "uuid"]):
                    potential_ids.append(key)
            
            analysis["suggested_identifier_fields"] = potential_ids
        
        return {
            "success": True,
            "analysis": analysis,
            "raw_response": result if result.get("success") else None,
            "recommendations": {
                "suitable_for_polling": analysis["is_array"] or analysis["data_type"] == "dict",
                "suggested_method": "new_items" if analysis["is_array"] else "hash_comparison",
                "suggested_identifier": analysis.get("suggested_identifier_fields", [None])[0]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing polling configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/state/{polling_state_id}")
async def reset_polling_state(
    polling_state_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset or delete a polling state"""
    try:
        # Get the polling state
        state = db.query(PollingState).filter(
            and_(
                PollingState.polling_state_id == polling_state_id,
                PollingState.tenant_id == current_user.tenant_id
            )
        ).first()
        
        if not state:
            raise HTTPException(status_code=404, detail="Polling state not found")
        
        # Delete the state (it will be recreated on next poll)
        db.delete(state)
        db.commit()
        
        return {
            "success": True,
            "message": "Polling state reset successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting polling state: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-services/{app_id}")
async def get_available_polling_services(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get services available for polling from an application"""
    try:
        # Get all services for the application
        services = db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id
        ).all()
        
        # Filter services suitable for polling (GET requests typically)
        polling_suitable = []
        
        for service in services:
            request_config = service.request_config or {}
            method = request_config.get("method", "GET").upper()
            
            # Services suitable for polling are typically GET requests
            # that return lists or have parameters for filtering
            if method == "GET":
                polling_suitable.append({
                    "service_id": str(service.service_id),
                    "service_name": service.service_name,
                    "description": service.description,
                    "parameters": service.parameter_schema,
                    "suggested_for_polling": True
                })
            elif method == "POST" and "search" in service.service_name.lower():
                # Some search endpoints use POST
                polling_suitable.append({
                    "service_id": str(service.service_id),
                    "service_name": service.service_name,
                    "description": service.description,
                    "parameters": service.parameter_schema,
                    "suggested_for_polling": True
                })
        
        return {
            "app_id": app_id,
            "services": polling_suitable,
            "total_services": len(services),
            "polling_suitable": len(polling_suitable)
        }
        
    except Exception as e:
        logger.error(f"Error getting available services: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class PollingLogResponse(BaseModel):
    """Response model for polling logs"""
    polling_state_id: str
    flow_id: str
    flow_name: str
    app_id: str
    app_name: str
    event_name: str
    last_poll_timestamp: Optional[datetime]
    last_successful_poll: Optional[datetime]
    items_processed_count: int
    consecutive_errors: int
    last_error: Optional[str]
    last_error_timestamp: Optional[datetime]
    is_active: bool
    last_poll_state: Optional[Dict[str, Any]]


@router.get("/logs", response_model=List[PollingLogResponse])
async def get_polling_logs(
    show_errors_only: bool = Query(False, description="Show only entries with errors"),
    flow_id: Optional[str] = Query(None, description="Filter by flow ID"),
    app_id: Optional[str] = Query(None, description="Filter by app ID"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get polling logs with detailed information"""
    try:
        # Build base query
        query = db.query(
            PollingState,
            Flow.flow_name,
            Application.app_name
        ).join(
            Flow, Flow.flow_id == PollingState.flow_id
        ).join(
            Application, Application.app_id == PollingState.app_id
        ).filter(
            PollingState.tenant_id == current_user.tenant_id
        )
        
        # Apply filters
        if show_errors_only:
            query = query.filter(PollingState.consecutive_errors > 0)
        
        if flow_id:
            query = query.filter(PollingState.flow_id == flow_id)
        
        if app_id:
            query = query.filter(PollingState.app_id == app_id)
        
        # Order by most recent activity
        query = query.order_by(
            PollingState.last_poll_timestamp.desc().nullsfirst(),
            PollingState.consecutive_errors.desc()
        ).limit(limit)
        
        results = query.all()
        
        logs = []
        for state, flow_name, app_name in results:
            # Parse JSON fields if they're strings
            import json
            last_poll_state = state.last_poll_state
            if isinstance(last_poll_state, str):
                try:
                    last_poll_state = json.loads(last_poll_state)
                except (json.JSONDecodeError, TypeError):
                    last_poll_state = None
            
            logs.append(PollingLogResponse(
                polling_state_id=str(state.polling_state_id),
                flow_id=str(state.flow_id),
                flow_name=flow_name,
                app_id=str(state.app_id),
                app_name=app_name,
                event_name=state.event_name,
                last_poll_timestamp=state.last_poll_timestamp,
                last_successful_poll=state.last_successful_poll,
                items_processed_count=state.items_processed_count or 0,
                consecutive_errors=state.consecutive_errors or 0,
                last_error=state.last_error,
                last_error_timestamp=state.last_error_timestamp,
                is_active=state.consecutive_errors < 10 if state.consecutive_errors else True,
                last_poll_state=last_poll_state
            ))
        
        return logs
        
    except Exception as e:
        logger.error(f"Error getting polling logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{polling_state_id}", response_model=PollingLogResponse)
async def get_polling_log_detail(
    polling_state_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific polling state"""
    try:
        result = db.query(
            PollingState,
            Flow.flow_name,
            Application.app_name
        ).join(
            Flow, Flow.flow_id == PollingState.flow_id
        ).join(
            Application, Application.app_id == PollingState.app_id
        ).filter(
            and_(
                PollingState.polling_state_id == polling_state_id,
                PollingState.tenant_id == current_user.tenant_id
            )
        ).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Polling state not found")
        
        state, flow_name, app_name = result
        
        # Parse JSON fields if they're strings
        import json
        last_poll_state = state.last_poll_state
        if isinstance(last_poll_state, str):
            try:
                last_poll_state = json.loads(last_poll_state)
            except (json.JSONDecodeError, TypeError):
                last_poll_state = None
        
        return PollingLogResponse(
            polling_state_id=str(state.polling_state_id),
            flow_id=str(state.flow_id),
            flow_name=flow_name,
            app_id=str(state.app_id),
            app_name=app_name,
            event_name=state.event_name,
            last_poll_timestamp=state.last_poll_timestamp,
            last_successful_poll=state.last_successful_poll,
            items_processed_count=state.items_processed_count or 0,
            consecutive_errors=state.consecutive_errors or 0,
            last_error=state.last_error,
            last_error_timestamp=state.last_error_timestamp,
            is_active=state.consecutive_errors < 10 if state.consecutive_errors else True,
            last_poll_state=last_poll_state
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting polling log detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/{polling_state_id}/clear-errors")
async def clear_polling_errors(
    polling_state_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear errors for a polling state to allow it to resume"""
    try:
        state = db.query(PollingState).filter(
            and_(
                PollingState.polling_state_id == polling_state_id,
                PollingState.tenant_id == current_user.tenant_id
            )
        ).first()
        
        if not state:
            raise HTTPException(status_code=404, detail="Polling state not found")
        
        # Clear error state
        state.consecutive_errors = 0
        state.last_error = None
        state.last_error_timestamp = None
        
        db.commit()
        
        return {
            "success": True,
            "message": "Errors cleared successfully",
            "polling_state_id": str(state.polling_state_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing polling errors: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
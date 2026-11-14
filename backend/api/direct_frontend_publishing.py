"""
Direct Frontend Publishing API

Handles direct publishing of flows as frontend applications without creating reusable applications.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime
import uuid
import json

from db.database import get_db
from core.auth_utils import get_current_user
from services.frontend_app_service import FrontendAppService
from core.config import settings

# Import models - PostgreSQL Only
from db.models import User, Tenant, Flow
from db.application_models import FrontendFlowApplication

logger = logging.getLogger(__name__)
router = APIRouter()
frontend_app_service = FrontendAppService()

class DirectFrontendPublishRequest(BaseModel):
    flow_id: str
    frontend_app_name: str
    description: Optional[str] = None
    access_type: str = "public_url"
    access_config: Optional[Dict[str, Any]] = None
    rate_limit_per_hour: int = 100
    custom_styling: Optional[Dict[str, Any]] = None

class DirectFrontendPublishResponse(BaseModel):
    success: bool
    frontend_app_id: str
    public_url: str
    message: str

@router.post("/publish-frontend-direct", response_model=DirectFrontendPublishResponse)
async def publish_frontend_direct(
    request: DirectFrontendPublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Publish a flow directly as a frontend application without creating a reusable application.
    """
    try:
        # Verify the flow exists and user has access
        flow = db.query(Flow).filter(Flow.flow_id == request.flow_id).first()
        
        if not flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow not found"
            )
        
        # Check if user has permission to publish this flow
        # Users can publish:
        # 1. Their own flows (created_by matches)
        # 2. Any flow in their tenant if they are TENANT_ADMIN or INSTANCE_ADMIN
        has_permission = (
            flow.created_by == current_user.user_id or  # User owns the flow
            (flow.tenant_id == current_user.tenant_id and 
             current_user.role.value in ["INSTANCE_ADMIN", "TENANT_ADMIN"])  # Admin in same tenant
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to publish this flow"
            )
        
        # Generate unique frontend app ID and URL slug
        frontend_app_id = str(uuid.uuid4())
        public_url_slug = f"{flow.flow_name.lower().replace(' ', '-')}-{frontend_app_id[:8]}"
        
        # Create frontend application directly in database
        frontend_app = FrontendFlowApplication(
            frontend_app_id=frontend_app_id,
            published_app_id=None,  # No published app for direct frontend publishing
            flow_id=request.flow_id,  # Direct reference to flow
            frontend_app_name=request.frontend_app_name,
            description=request.description or f"Public interface for {flow.flow_name}",
            public_url_slug=public_url_slug,
            access_type=request.access_type,
            access_config=json.dumps(request.access_config or {}),
            rate_limit_per_hour=request.rate_limit_per_hour,
            custom_styling=json.dumps(request.custom_styling or {}),
            is_active=True,
            usage_count=0,
            created_by=current_user.user_id,
            tenant_id=current_user.tenant_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(frontend_app)
        db.commit()
        db.refresh(frontend_app)
        
        # Generate public URL
        public_url = f"{settings.base_url}/public-app/{public_url_slug}"
        
        logger.info(f"Created direct frontend application {frontend_app_id} for flow {request.flow_id}")
        
        return DirectFrontendPublishResponse(
            success=True,
            frontend_app_id=frontend_app_id,
            public_url=public_url,
            message=f"Frontend application '{request.frontend_app_name}' published successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing frontend application directly: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish frontend application: {str(e)}"
        )
"""
Frontend Applications API Endpoints

API endpoints for managing frontend/public flow applications, handling access control,
embed code generation, and application management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import logging

from db.database import get_db, get_tenant_db
from core.auth_utils import get_current_user_required as get_current_user
from core.config import settings

# Import models - PostgreSQL Only
from db.models import User
from db.application_models import (
    PublishedApplication, FrontendFlowApplication, FrontendAppAccessLog
)

from services.frontend_app_service import FrontendAppService, FrontendAppError
from services.embed_code_generator import EmbedCodeGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/frontend-applications", tags=["frontend-applications"])

@router.get("/debug-config")
async def debug_config():
    """Debug endpoint to check configuration"""
    import os
    return {
        "settings.base_url": settings.base_url,
        "settings.server_url": settings.server_url,
        "env.BASE_URL": os.environ.get("BASE_URL", "NOT SET"),
        "env.SERVER_URL": os.environ.get("SERVER_URL", "NOT SET"),
        "cwd": os.getcwd()
    }

# Initialize services
frontend_app_service = FrontendAppService()
embed_generator = EmbedCodeGenerator()

# Pydantic models for API

class CreateFrontendAppRequest(BaseModel):
    published_app_id: str = Field(..., description="ID of the published application")
    frontend_app_name: str = Field(..., description="Display name for the frontend app")
    access_type: str = Field(..., description="Access control type")
    access_config: Optional[Dict[str, Any]] = Field(None, description="Access configuration")
    public_url_slug: Optional[str] = Field(None, description="Custom URL slug")
    description: Optional[str] = Field(None, description="Application description")
    rate_limit_per_hour: int = Field(100, description="Rate limit per IP per hour")
    custom_styling: Optional[Dict[str, Any]] = Field(None, description="Custom styling configuration")
    embed_enabled: bool = Field(True, description="Enable embed functionality")
    
    @validator('access_type')
    def validate_access_type(cls, v):
        valid_types = ["public_url", "organization", "specific_users", "tenant_list"]
        if v not in valid_types:
            raise ValueError(f"access_type must be one of: {valid_types}")
        return v


class UpdateFrontendAppRequest(BaseModel):
    frontend_app_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="Description")
    access_type: Optional[str] = Field(None, description="Access control type")
    access_config: Optional[Dict[str, Any]] = Field(None, description="Access configuration")
    rate_limit_per_hour: Optional[int] = Field(None, description="Rate limit")
    custom_styling: Optional[Dict[str, Any]] = Field(None, description="Custom styling")
    is_active: Optional[bool] = Field(None, description="Active status")


class EmbedCodeRequest(BaseModel):
    embed_type: str = Field("widget", description="Type of embed code")
    theme: str = Field("light", description="UI theme")
    width: str = Field("100%", description="Width")
    height: str = Field("auto", description="Height")
    custom_css: Optional[str] = Field(None, description="Custom CSS")
    callback_config: Optional[Dict[str, str]] = Field(None, description="Callback configuration")
    
    @validator('embed_type')
    def validate_embed_type(cls, v):
        valid_types = ["widget", "iframe", "modal"]
        if v not in valid_types:
            raise ValueError(f"embed_type must be one of: {valid_types}")
        return v
    
    @validator('theme')
    def validate_theme(cls, v):
        valid_themes = ["light", "dark", "custom"]
        if v not in valid_themes:
            raise ValueError(f"theme must be one of: {valid_themes}")
        return v


class FrontendApplicationResponse(BaseModel):
    frontend_app_id: str
    published_app_id: Optional[str]
    frontend_app_name: str
    public_url_slug: str
    public_url: str
    access_type: str
    description: Optional[str]
    is_active: bool
    usage_count: int
    rate_limit_per_hour: int
    created_at: str
    updated_at: str


class EmbedCodeResponse(BaseModel):
    embed_type: str
    html: str
    css: str
    javascript: str
    sdk_code: Optional[str] = None


@router.post("/create", response_model=Dict[str, Any])
async def create_frontend_application(
    request: CreateFrontendAppRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new frontend flow application from a published application
    """
    if getattr(current_user.role, 'value', str(current_user.role)) in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit creating frontend applications"
        )
    try:
        result = frontend_app_service.create_frontend_application(
            db=db,
            published_app_id=request.published_app_id,
            user_id=current_user.user_id,
            frontend_app_name=request.frontend_app_name,
            access_type=request.access_type,
            access_config=request.access_config,
            public_url_slug=request.public_url_slug,
            description=request.description,
            rate_limit_per_hour=request.rate_limit_per_hour,
            custom_styling=request.custom_styling
        )
        
        return result
        
    except FrontendAppError as e:
        logger.error(f"Frontend app creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during frontend app creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during creation"
        )


@router.post("/from-published-app", response_model=Dict[str, Any])
async def create_frontend_from_published_app(
    request: CreateFrontendAppRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new frontend flow application from a published application (alias for /create)
    """
    if getattr(current_user.role, 'value', str(current_user.role)) in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit creating frontend applications"
        )
    try:
        result = frontend_app_service.create_frontend_application(
            db=db,
            published_app_id=request.published_app_id,
            frontend_app_name=request.frontend_app_name,
            user_id=current_user.user_id,
            access_type=request.access_type,
            access_config=request.access_config,
            public_url_slug=request.public_url_slug,
            description=request.description,
            rate_limit_per_hour=request.rate_limit_per_hour,
            custom_styling=request.custom_styling
        )
        
        return result
        
    except FrontendAppError as e:
        logger.error(f"Frontend app creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during frontend app creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during creation"
        )


@router.get("/published-app/{published_app_id}", response_model=List[FrontendApplicationResponse])
async def get_frontend_applications_for_published_app(
    published_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all frontend applications for a published application
    """
    try:
        frontend_apps = frontend_app_service.get_frontend_applications_for_published_app(
            db=db,
            published_app_id=published_app_id
        )
        
        result = []
        for app in frontend_apps:
            result.append(FrontendApplicationResponse(
                frontend_app_id=app["frontend_app_id"],
                published_app_id=published_app_id,
                frontend_app_name=app["frontend_app_name"],
                public_url_slug=app["public_url_slug"],
                public_url=app["public_url"],
                access_type=app["access_type"],
                description=None,  # Not included in the service response
                is_active=app["is_active"],
                usage_count=app["usage_count"],
                rate_limit_per_hour=100,  # Default, could be retrieved from DB
                created_at=app["created_at"],
                updated_at=app["created_at"]  # Using created_at as fallback
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving frontend applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve frontend applications"
        )

@router.get("/direct", response_model=List[FrontendApplicationResponse])
async def get_direct_frontend_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all direct frontend applications (published without reusable apps)
    """
    try:
        # Get direct frontend applications (where published_app_id is NULL)
        direct_apps = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.published_app_id.is_(None),
            FrontendFlowApplication.created_by == current_user.user_id
        ).all()
        
        result = []
        logger.info(f"DEBUG get_direct_frontend_applications: settings.base_url = {settings.base_url}")
        for app in direct_apps:
            # Generate public URL
            public_url = f"{settings.base_url}/public-app/{app.public_url_slug}"
            logger.info(f"DEBUG: Generated public_url for direct app {app.frontend_app_name} = {public_url}")
            
            result.append(FrontendApplicationResponse(
                frontend_app_id=app.frontend_app_id,
                published_app_id=None,  # Direct frontend apps have no published app
                frontend_app_name=app.frontend_app_name,
                public_url_slug=app.public_url_slug,
                public_url=public_url,
                access_type=app.access_type,
                description=app.description,
                is_active=app.is_active,
                usage_count=app.usage_count,
                rate_limit_per_hour=app.rate_limit_per_hour or 100,
                created_at=app.created_at.isoformat() if app.created_at else None,
                updated_at=app.updated_at.isoformat() if app.updated_at else None
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving direct frontend applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve direct frontend applications"
        )


@router.get("/{frontend_app_id}", response_model=Dict[str, Any])
async def get_frontend_application(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific frontend application
    """
    try:
        frontend_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()
        
        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frontend application {frontend_app_id} not found"
            )
        
        # Check permissions (user should be able to see their own apps)
        if frontend_app.created_by != current_user.user_id:
            # Could add role-based permission check here
            pass
        
        import json
        
        return {
            "frontend_app_id": frontend_app.frontend_app_id,
            "published_app_id": frontend_app.published_app_id,
            "frontend_app_name": frontend_app.frontend_app_name,
            "public_url_slug": frontend_app.public_url_slug,
            "public_url": f"{settings.base_url}/public-app/{frontend_app.public_url_slug}",
            "description": frontend_app.description,
            "access_type": frontend_app.access_type,
            "access_config": json.loads(frontend_app.access_config) if frontend_app.access_config else {},
            "custom_styling": json.loads(frontend_app.custom_styling) if frontend_app.custom_styling else {},
            "embed_enabled": frontend_app.embed_enabled,
            "rate_limit_per_hour": frontend_app.rate_limit_per_hour,
            "is_active": frontend_app.is_active,
            "usage_count": frontend_app.usage_count,
            "last_accessed_at": frontend_app.last_accessed_at.isoformat() if frontend_app.last_accessed_at else None,
            "created_at": frontend_app.created_at.isoformat(),
            "updated_at": frontend_app.updated_at.isoformat(),
            "published_application": {
                "flow_id": frontend_app.published_application.flow_id,
                "flow_name": frontend_app.published_application.flow_name,
                "app_key": frontend_app.published_application.app_key
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting frontend application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve frontend application"
        )


@router.put("/{frontend_app_id}", response_model=Dict[str, Any])
async def update_frontend_application(
    frontend_app_id: str,
    request: UpdateFrontendAppRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a frontend application
    """
    if getattr(current_user.role, 'value', str(current_user.role)) in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit updating frontend applications"
        )
    try:
        # Filter out None values
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        result = frontend_app_service.update_frontend_application(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            **updates
        )
        
        return result
        
    except FrontendAppError as e:
        logger.error(f"Update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during update"
        )


@router.delete("/{frontend_app_id}")
async def delete_frontend_application(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a frontend application
    """
    if getattr(current_user.role, 'value', str(current_user.role)) in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit deleting frontend applications"
        )
    try:
        result = frontend_app_service.delete_frontend_application(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id
        )
        
        return result
        
    except FrontendAppError as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during delete: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during delete"
        )


@router.post("/{frontend_app_id}/embed-code", response_model=EmbedCodeResponse)
async def generate_embed_code(
    frontend_app_id: str,
    request: EmbedCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate embed code for a frontend application
    """
    try:
        # Get the frontend application
        frontend_app_data = frontend_app_service.get_frontend_application_by_slug(
            db=db,
            public_url_slug=""  # We need to get by ID, not slug
        )
        
        # Alternative approach: get directly from DB
        frontend_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()
        
        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frontend application {frontend_app_id} not found"
            )
        
        # Check permissions
        if frontend_app.created_by != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to generate embed code for this application"
            )
        
        # Prepare frontend app data for embed generator
        import json
        frontend_app_data = {
            "frontend_app_id": frontend_app.frontend_app_id,
            "frontend_app_name": frontend_app.frontend_app_name,
            "public_url_slug": frontend_app.public_url_slug,
            "description": frontend_app.description,
            "access_type": frontend_app.access_type,
            "access_config": json.loads(frontend_app.access_config) if frontend_app.access_config else {},
            "custom_styling": json.loads(frontend_app.custom_styling) if frontend_app.custom_styling else {}
        }
        
        # Generate embed code
        embed_code = embed_generator.generate_embed_code(
            frontend_app=frontend_app_data,
            embed_type=request.embed_type,
            theme=request.theme,
            width=request.width,
            height=request.height,
            custom_css=request.custom_css,
            callback_config=request.callback_config
        )
        
        # Generate SDK code if requested
        sdk_code = None
        if request.embed_type == "widget":
            sdk_code = embed_generator.generate_sdk_code(frontend_app.public_url_slug)
        
        return EmbedCodeResponse(
            embed_type=embed_code["type"],
            html=embed_code["html"],
            css=embed_code["css"],
            javascript=embed_code["javascript"],
            sdk_code=sdk_code
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embed code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embed code"
        )


@router.get("/{frontend_app_id}/analytics")
async def get_frontend_application_analytics(
    frontend_app_id: str,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get analytics for a frontend application
    """
    try:
        # Get the frontend application
        frontend_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()
        
        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frontend application {frontend_app_id} not found"
            )
        
        # Check permissions
        if frontend_app.created_by != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view analytics for this application"
            )
        
        # Get analytics data from access logs
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Total views and executions
        total_views = db.query(FrontendAppAccessLog).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.access_type == 'view',
                FrontendAppAccessLog.accessed_at >= since_date
            )
        ).count()
        
        total_executions = db.query(FrontendAppAccessLog).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.access_type == 'execute',
                FrontendAppAccessLog.accessed_at >= since_date
            )
        ).count()
        
        # Success rate
        successful_executions = db.query(FrontendAppAccessLog).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.access_type == 'execute',
                FrontendAppAccessLog.execution_success == True,
                FrontendAppAccessLog.accessed_at >= since_date
            )
        ).count()
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        
        # Top IP addresses
        top_ips = db.query(
            FrontendAppAccessLog.ip_address,
            func.count(FrontendAppAccessLog.log_id).label('count')
        ).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.accessed_at >= since_date
            )
        ).group_by(FrontendAppAccessLog.ip_address).order_by(
            func.count(FrontendAppAccessLog.log_id).desc()
        ).limit(10).all()
        
        # Daily usage
        daily_usage = db.query(
            func.date(FrontendAppAccessLog.accessed_at).label('date'),
            func.count(FrontendAppAccessLog.log_id).label('count')
        ).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.accessed_at >= since_date
            )
        ).group_by(func.date(FrontendAppAccessLog.accessed_at)).order_by('date').all()
        
        return {
            "period_days": days,
            "total_views": total_views,
            "total_executions": total_executions,
            "success_rate": round(success_rate, 2),
            "successful_executions": successful_executions,
            "failed_executions": total_executions - successful_executions,
            "top_ip_addresses": [{"ip": ip, "count": count} for ip, count in top_ips],
            "daily_usage": [{"date": str(date), "count": count} for date, count in daily_usage]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )
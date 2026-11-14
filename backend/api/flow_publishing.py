"""
Flow Publishing API Endpoints

API endpoints for publishing flows as applications, managing published applications,
and handling version control.
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
    PublishedApplication, PublishedApplicationVersion,
    FlowApplicationDependency, ParameterMapping, FlowExecutionBridge
)

from services.flow_publisher import FlowPublisher, PublishingError
from services.micro_saas_service import MicroSaasService, MicroSaasError
from schemas.micro_saas_schemas import VisibilityEnum, BillingPreferenceEnum, PricingConfig, UsageLimits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/flow-publishing", tags=["flow-publishing"])

# Pydantic models for API

class PublishFlowRequest(BaseModel):
    flow_id: str = Field(..., description="ID of the flow to publish")
    app_key: str = Field(..., description="Unique key for the application")
    app_name: Optional[str] = Field(None, description="Name for the application")
    description: Optional[str] = Field(None, description="Application description")
    category: str = Field("Flow Applications", description="Application category")
    app_scope: str = Field("tenant", description="Application scope: global, tenant, or user")
    icon_url: Optional[str] = Field(None, description="URL to application icon")
    auto_update: bool = Field(False, description="Auto-update when flow changes")
    generation_config: Optional[Dict[str, Any]] = Field(None, description="Generation configuration")

    # Micro SaaS specific fields (optional for reusable apps, used for Micro SaaS apps)
    publish_as_micro_saas: bool = Field(False, description="Publish as Micro SaaS app instead of reusable app")
    visibility: Optional[VisibilityEnum] = Field(None, description="Marketplace visibility (for Micro SaaS apps)")
    billing_preference: Optional[BillingPreferenceEnum] = Field(None, description="Billing model (for Micro SaaS apps)")
    pricing_config: Optional[PricingConfig] = Field(None, description="Pricing configuration (for Micro SaaS apps)")
    usage_limits: Optional[UsageLimits] = Field(None, description="Usage limits (for Micro SaaS apps)")

    # Frontend/access control fields (for Micro SaaS apps)
    access_type: Optional[str] = Field(None, description="Access control type (for Micro SaaS apps)")
    access_config: Optional[Dict[str, Any]] = Field(None, description="Access configuration (for Micro SaaS apps)")
    public_url_slug: Optional[str] = Field(None, description="Custom URL slug (for Micro SaaS apps)")
    rate_limit_per_hour: Optional[int] = Field(None, description="Rate limit per hour (for Micro SaaS apps)")
    custom_styling: Optional[Dict[str, Any]] = Field(None, description="Custom styling (for Micro SaaS apps)")
    embed_enabled: bool = Field(True, description="Enable embed functionality (for Micro SaaS apps)")
    marketplace_enabled: bool = Field(False, description="Enable in marketplace (for future use)")

    @validator('app_key')
    def validate_app_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("app_key cannot be empty")
        # Check for valid characters (alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("app_key can only contain alphanumeric characters, underscores, and hyphens")
        return v.strip()

    @validator('access_type')
    def validate_access_type(cls, v):
        if v is not None:
            valid_types = ["public_url", "organization", "specific_users", "tenant_list"]
            if v not in valid_types:
                raise ValueError(f"access_type must be one of: {valid_types}")
        return v


class UpdatePublishedAppRequest(BaseModel):
    force_update: bool = Field(False, description="Force update even if no changes detected")


class PublishedApplicationResponse(BaseModel):
    published_app_id: str
    flow_id: str
    flow_name: str
    app_key: str
    app_id: str  # Add the missing app_id field
    app_name: str
    version: str
    status: str
    auto_update: bool
    usage_count: int
    created_at: str
    updated_at: str
    last_sync_at: Optional[str]


class PublishingPreviewResponse(BaseModel):
    success: bool
    preview: Optional[Dict[str, Any]]
    analysis: Optional[Dict[str, Any]]
    error: Optional[str] = None


class PublishingResultResponse(BaseModel):
    success: bool
    message: str
    published_app_id: Optional[str] = None
    app_id: Optional[str] = None
    app_key: Optional[str] = None
    version: Optional[str] = None
    services_created: Optional[int] = None
    events_created: Optional[int] = None
    warnings: Optional[List[str]] = None
    error: Optional[str] = None


class VersionResponse(BaseModel):
    version_id: str
    version_number: str
    is_active: bool
    created_at: str
    changes_summary: Optional[Dict[str, Any]]


class DependencyResponse(BaseModel):
    dependency_id: str
    depends_on_app_name: str
    dependency_type: str
    dependency_name: str
    is_required: bool
    created_at: str


class ParameterMappingResponse(BaseModel):
    mapping_id: str
    parameter_name: str
    parameter_type: str
    flow_variable_path: str
    service_parameter_name: str
    is_required: bool
    description: Optional[str]


# Initialize services
flow_publisher = FlowPublisher()
micro_saas_service = MicroSaasService()


@router.get("/preview", response_model=PublishingPreviewResponse)
async def preview_flow_publishing(
    flow_id: str = Query(..., description="Flow ID to preview"),
    app_key: str = Query(..., description="Desired application key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview what would be created when publishing a flow as an application
    """
    try:
        result = flow_publisher.get_publishing_preview(
            db=db,
            flow_id=flow_id,
            app_key=app_key
        )
        
        return PublishingPreviewResponse(
            success=result["success"],
            preview=result.get("preview"),
            analysis=result.get("analysis"),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Error generating publishing preview: {str(e)}")
        return PublishingPreviewResponse(
            success=False,
            error=str(e)
        )


@router.post("/publish", response_model=PublishingResultResponse)
async def publish_flow(
    request: PublishFlowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Publish a flow as an application

    This endpoint supports two publishing modes:
    1. Reusable Application (default): Publishes as a reusable flow component
    2. Micro SaaS App: Publishes as a monetizable frontend application with marketplace visibility

    Set publish_as_micro_saas=True to create a Micro SaaS app with billing and access control.
    """
    try:
        # Check if this is a Micro SaaS publishing request
        if request.publish_as_micro_saas:
            logger.info(f"Publishing flow {request.flow_id} as Micro SaaS app")

            # Use MicroSaasService to create a Micro SaaS app
            result = micro_saas_service.create_micro_saas_app(
                db=db,
                flow_id=request.flow_id,
                user_id=current_user.user_id,
                app_key=request.app_key,
                app_name=request.app_name,
                description=request.description,
                category=request.category,
                icon_url=request.icon_url,
                visibility=request.visibility.value if request.visibility else "private",
                billing_preference=request.billing_preference.value if request.billing_preference else "free",
                pricing_config=request.pricing_config.dict() if request.pricing_config else None,
                usage_limits=request.usage_limits.dict() if request.usage_limits else None,
                access_type=request.access_type or "public_url",
                access_config=request.access_config,
                public_url_slug=request.public_url_slug,
                rate_limit_per_hour=request.rate_limit_per_hour or 100,
                custom_styling=request.custom_styling,
                auto_update=request.auto_update,
                embed_enabled=request.embed_enabled,
                marketplace_enabled=request.marketplace_enabled
            )

            return PublishingResultResponse(**result)

        else:
            # Traditional reusable application publishing
            logger.info(f"Publishing flow {request.flow_id} as reusable application")

            result = flow_publisher.publish_flow(
                db=db,
                flow_id=request.flow_id,
                app_key=request.app_key,
                user_id=current_user.user_id,
                app_name=request.app_name,
                description=request.description,
                category=request.category,
                app_scope=request.app_scope,
                icon_url=request.icon_url,
                auto_update=request.auto_update,
                generation_config=request.generation_config
            )

            return PublishingResultResponse(**result)

    except (PublishingError, MicroSaasError) as e:
        logger.error(f"Publishing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during publishing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during publishing"
        )


@router.get("/applications", response_model=List[PublishedApplicationResponse])
async def list_published_applications(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    flow_id: Optional[str] = Query(None, description="Filter by flow ID"),
    my_apps_only: bool = Query(False, description="Show only current user's applications"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List published applications with optional filters
    """
    try:
        user_filter = current_user.user_id if my_apps_only else None
        
        published_apps = flow_publisher.get_published_applications(
            db=db,
            user_id=user_filter,
            status=status_filter,
            flow_id=flow_id
        )
        
        return [PublishedApplicationResponse(**app) for app in published_apps]
        
    except Exception as e:
        logger.error(f"Error listing published applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve published applications"
        )


@router.get("/applications/{published_app_id}", response_model=PublishedApplicationResponse)
async def get_published_application(
    published_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific published application
    """
    try:
        published_app = db.query(PublishedApplication).filter(
            PublishedApplication.published_app_id == published_app_id
        ).first()
        
        if not published_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Published application {published_app_id} not found"
            )
        
        return PublishedApplicationResponse(
            published_app_id=published_app.published_app_id,
            flow_id=published_app.flow_id,
            flow_name=published_app.flow_name,
            app_key=published_app.app_key,
            app_id=published_app.app_id,
            app_name=published_app.application.app_name,
            version=published_app.published_version,
            status=published_app.status,
            auto_update=published_app.auto_update,
            usage_count=published_app.usage_count,
            created_at=published_app.created_at.isoformat(),
            updated_at=published_app.updated_at.isoformat(),
            last_sync_at=published_app.last_sync_at.isoformat() if published_app.last_sync_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting published application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve published application"
        )


@router.put("/applications/{published_app_id}/update", response_model=PublishingResultResponse)
async def update_published_application(
    published_app_id: str,
    request: UpdatePublishedAppRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a published application from its source flow
    """
    try:
        result = flow_publisher.update_published_application(
            db=db,
            published_app_id=published_app_id,
            user_id=current_user.user_id,
            force_update=request.force_update
        )
        
        return PublishingResultResponse(**result)
        
    except PublishingError as e:
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


@router.delete("/applications/{published_app_id}")
async def unpublish_application(
    published_app_id: str,
    keep_seed_file: bool = Query(False, description="Keep seed application file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unpublish an application (remove from system)
    """
    try:
        result = flow_publisher.unpublish_application(
            db=db,
            published_app_id=published_app_id,
            user_id=current_user.user_id,
            keep_seed_file=keep_seed_file
        )
        
        return result
        
    except PublishingError as e:
        logger.error(f"Unpublish error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during unpublish: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during unpublish"
        )


@router.get("/applications/{published_app_id}/versions", response_model=List[VersionResponse])
async def get_published_application_versions(
    published_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get version history for a published application
    """
    try:
        versions = db.query(PublishedApplicationVersion).filter(
            PublishedApplicationVersion.published_app_id == published_app_id
        ).order_by(PublishedApplicationVersion.created_at.desc()).all()
        
        return [
            VersionResponse(
                version_id=version.version_id,
                version_number=version.version_number,
                is_active=version.is_active,
                created_at=version.created_at.isoformat(),
                changes_summary=version.changes_summary if isinstance(version.changes_summary, dict) 
                              else eval(version.changes_summary) if version.changes_summary else None
            )
            for version in versions
        ]
        
    except Exception as e:
        logger.error(f"Error getting application versions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application versions"
        )


@router.get("/applications/{published_app_id}/dependencies", response_model=List[DependencyResponse])
async def get_published_application_dependencies(
    published_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dependencies for a published application
    """
    try:
        dependencies = db.query(FlowApplicationDependency).join(
            PublishedApplication.application
        ).filter(
            FlowApplicationDependency.published_app_id == published_app_id
        ).all()
        
        return [
            DependencyResponse(
                dependency_id=dep.dependency_id,
                depends_on_app_name=dep.dependency_application.app_name,
                dependency_type=dep.dependency_type,
                dependency_name=dep.dependency_name,
                is_required=dep.is_required,
                created_at=dep.created_at.isoformat()
            )
            for dep in dependencies
        ]
        
    except Exception as e:
        logger.error(f"Error getting application dependencies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application dependencies"
        )


@router.get("/applications/{published_app_id}/parameters", response_model=List[ParameterMappingResponse])
async def get_published_application_parameters(
    published_app_id: str,
    parameter_type: Optional[str] = Query(None, description="Filter by parameter type (input/output)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get parameter mappings for a published application
    """
    try:
        query = db.query(ParameterMapping).filter(
            ParameterMapping.published_app_id == published_app_id
        )
        
        if parameter_type:
            query = query.filter(ParameterMapping.parameter_type == parameter_type)
        
        parameters = query.all()
        
        return [
            ParameterMappingResponse(
                mapping_id=param.mapping_id,
                parameter_name=param.parameter_name,
                parameter_type=param.parameter_type,
                flow_variable_path=param.flow_variable_path,
                service_parameter_name=param.service_parameter_name,
                is_required=param.is_required,
                description=param.description
            )
            for param in parameters
        ]
        
    except Exception as e:
        logger.error(f"Error getting application parameters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application parameters"
        )


@router.get("/applications/{published_app_id}/analysis")
async def get_published_application_analysis(
    published_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the flow analysis data for a published application
    """
    try:
        published_app = db.query(PublishedApplication).filter(
            PublishedApplication.published_app_id == published_app_id
        ).first()
        
        if not published_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Published application {published_app_id} not found"
            )
        
        # Parse the flow analysis JSON
        import json
        analysis_data = json.loads(published_app.flow_analysis) if published_app.flow_analysis else {}
        
        return {
            "success": True,
            "analysis": analysis_data,
            "generation_config": json.loads(published_app.generation_config) if published_app.generation_config else {}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application analysis"
        )


@router.get("/statistics")
async def get_publishing_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics about published applications
    """
    try:
        total_published = db.query(PublishedApplication).count()
        active_published = db.query(PublishedApplication).filter(
            PublishedApplication.status == 'active'
        ).count()
        
        user_published = db.query(PublishedApplication).filter(
            PublishedApplication.created_by == current_user.user_id
        ).count()
        
        # Get most used applications
        popular_apps = db.query(PublishedApplication).order_by(
            PublishedApplication.usage_count.desc()
        ).limit(10).all()
        
        # Get recent applications
        recent_apps = db.query(PublishedApplication).order_by(
            PublishedApplication.created_at.desc()
        ).limit(10).all()
        
        return {
            "total_published_applications": total_published,
            "active_published_applications": active_published,
            "user_published_applications": user_published,
            "most_popular": [
                {
                    "app_key": app.app_key,
                    "app_name": app.application.app_name,
                    "usage_count": app.usage_count
                }
                for app in popular_apps
            ],
            "recently_published": [
                {
                    "app_key": app.app_key,
                    "app_name": app.application.app_name,
                    "created_at": app.created_at.isoformat()
                }
                for app in recent_apps
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting publishing statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve publishing statistics"
        )


@router.post("/applications/{published_app_id}/toggle-auto-update")
async def toggle_auto_update(
    published_app_id: str,
    enable: bool = Query(..., description="Enable or disable auto-update"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle auto-update setting for a published application
    """
    try:
        published_app = db.query(PublishedApplication).filter(
            PublishedApplication.published_app_id == published_app_id
        ).first()
        
        if not published_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Published application {published_app_id} not found"
            )
        
        # Check if user has permission to modify this application
        if published_app.created_by != current_user.user_id:
            # TODO: Add role-based permission check
            pass
        
        published_app.auto_update = enable
        published_app.updated_at = datetime.now()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Auto-update {'enabled' if enable else 'disabled'} for application {published_app.app_key}",
            "auto_update": enable
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling auto-update: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle auto-update setting"
        )
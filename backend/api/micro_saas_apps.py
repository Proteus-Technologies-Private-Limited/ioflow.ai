"""
Micro SaaS Applications API Endpoints

API endpoints for managing Micro SaaS applications, including creation, settings management,
billing configuration, analytics, and subscriber management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, File, UploadFile
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import traceback
import uuid
import os
import json

from db.database import get_db
from core.auth_utils import get_current_user_required as get_current_user
from core.config import settings

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import User
else:
    from db.models import User

from services.micro_saas_service import MicroSaasService, MicroSaasError
from db.application_models import FrontendFlowApplication, LandingPageImage
from schemas.micro_saas_schemas import (
    MicroSaasAppCreate,
    MicroSaasAppUpdate,
    MicroSaasVisibilityUpdate,
    MicroSaasBillingUpdate,
    MicroSaasUsageLimitsUpdate,
    MicroSaasAppResponse,
    MicroSaasAppListResponse,
    MicroSaasAnalytics,
    SubscriberListResponse,
    BillingHistoryResponse,
    GrantAccessRequest,
    RevokeAccessRequest,
    AccessManagementResponse,
    TopUpRequest,
    TopUpResponse,
    MicroSaasPublishingResult,
    # Related flows schemas
    RelatedFlowCreate,
    RelatedFlowUpdate,
    RelatedFlowResponse,
    RelatedFlowsListResponse,
    ReorderRelatedFlowsRequest,
    AvailableAppsForLinkingResponse
)
from services.related_flows_service import RelatedFlowsService, RelatedFlowsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/micro-saas-apps", tags=["micro-saas-apps"])

# Initialize services
micro_saas_service = MicroSaasService()
related_flows_service = RelatedFlowsService()


@router.get("/validate-flow/{flow_id}")
async def validate_flow_for_micro_saas(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate if a flow can be published as a Micro SaaS app
    Returns 200 if valid, 400 if already published
    """
    try:
        # Check if this flow is already published as a Micro SaaS app by this tenant
        existing_app = micro_saas_service.check_existing_micro_saas_app(
            db=db,
            flow_id=flow_id,
            user_id=current_user.user_id
        )

        if existing_app:
            error_msg = f"This flow is already published as a Micro SaaS app: '{existing_app['app_name']}'. Please unpublish or delete the existing app before creating a new one."
            logger.error(f"Flow validation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        logger.info(f"Flow {flow_id} validation passed - can be published as Micro SaaS app")
        return {"valid": True, "message": "Flow can be published as Micro SaaS app"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating flow for Micro SaaS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while validating the flow"
        )


@router.post("/create", response_model=MicroSaasPublishingResult)
async def create_micro_saas_app(
    app_data: MicroSaasAppCreate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Micro SaaS application from a flow

    This endpoint:
    1. Publishes the flow as a reusable application
    2. Creates a frontend application with Micro SaaS specific settings
    3. Sets up billing configuration
    4. Returns public URL and admin URL
    """
    try:
        # Log incoming request for debugging
        logger.info(f"Creating Micro SaaS app - User: {current_user.email}, Flow ID: {app_data.flow_id}, App Key: {app_data.app_key}")
        logger.debug(f"Request data: access_type={app_data.access_type}, access_config={app_data.access_config}")

        # Get base URL from request
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"

        result = micro_saas_service.create_micro_saas_app(
            db=db,
            flow_id=app_data.flow_id,
            user_id=current_user.user_id,
            app_key=app_data.app_key,
            app_name=app_data.app_name,
            description=app_data.description,
            category=app_data.category,
            icon_url=app_data.icon_url,
            visibility=app_data.visibility.value if app_data.visibility else "private",
            billing_preference=app_data.billing_preference.value if app_data.billing_preference else "free",
            pricing_config=app_data.pricing_config.model_dump() if app_data.pricing_config else None,
            usage_limits=app_data.usage_limits.model_dump() if app_data.usage_limits else None,
            access_type=app_data.access_type,
            access_config=app_data.access_config,
            public_url_slug=app_data.public_url_slug,
            rate_limit_per_hour=100,  # Default
            custom_styling=app_data.custom_styling,
            auto_update=app_data.auto_update,
            embed_enabled=app_data.embed_enabled,
            marketplace_enabled=app_data.marketplace_enabled,
            base_url=base_url
        )

        logger.info(f"Successfully created Micro SaaS app - Frontend App ID: {result.get('frontend_app_id')}")
        return MicroSaasPublishingResult(**result)

    except IntegrityError as e:
        # Handle database constraint violations (duplicate keys, etc.)
        logger.error(f"Database integrity error: {str(e)}")
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)

        if 'app_key' in error_msg or 'UNIQUE constraint failed' in error_msg:
            detail = f"Application key '{app_data.app_key}' is already in use. Please choose a different key."
        elif 'public_url_slug' in error_msg:
            detail = f"URL slug is already in use. Please try a different application name."
        else:
            detail = f"A database constraint was violated: {error_msg}"

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )
    except MicroSaasError as e:
        logger.error(f"Micro SaaS app creation error for user {current_user.email}: {str(e)}")
        logger.error(f"Request details - app_key: {app_data.app_key}, access_type: {app_data.access_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        # Handle validation errors from the service layer
        logger.error(f"Validation error: {str(e)}")
        logger.error(f"Request data: {app_data.dict()}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        # Log full traceback for unexpected errors
        logger.error(f"Unexpected error during Micro SaaS app creation for user {current_user.email}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"Request data: {app_data.dict()}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during creation: {str(e)}"
        )


@router.get("", response_model=MicroSaasAppListResponse)
async def list_micro_saas_apps(
    http_request: Request,
    include_inactive: bool = Query(False, description="Include inactive apps"),
    visibility: Optional[str] = Query(None, description="Filter by visibility"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all Micro SaaS apps for the current user
    """
    try:
        # Get base URL from request
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"

        apps = micro_saas_service.get_user_micro_saas_apps(
            db=db,
            user_id=current_user.user_id,
            include_inactive=include_inactive,
            visibility_filter=visibility,
            base_url=base_url
        )

        return {
            "total": len(apps),
            "apps": apps
        }

    except Exception as e:
        logger.error(f"Error listing Micro SaaS apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing apps"
        )


@router.get("/{frontend_app_id}", response_model=MicroSaasAppResponse)
async def get_micro_saas_app(
    frontend_app_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific Micro SaaS app
    """
    try:
        # Get base URL from request
        base_url = f"{http_request.url.scheme}://{http_request.url.netloc}"

        app = micro_saas_service.get_micro_saas_app(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            base_url=base_url
        )

        return app

    except MicroSaasError as e:
        logger.error(f"Error getting Micro SaaS app: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching app details"
        )


@router.put("/{frontend_app_id}/settings", response_model=MicroSaasAppResponse)
async def update_app_settings(
    frontend_app_id: str,
    request: MicroSaasAppUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update all settings for a Micro SaaS app

    This endpoint allows updating any combination of settings including:
    - General settings (name, description, icon)
    - Visibility settings
    - Billing configuration
    - Access control
    - Usage limits
    - Styling
    """
    try:
        # Convert request to dict, excluding None values
        updates = request.dict(exclude_none=True)

        # Convert enum values to strings
        if 'visibility' in updates and hasattr(updates['visibility'], 'value'):
            updates['visibility'] = updates['visibility'].value
        if 'billing_preference' in updates and hasattr(updates['billing_preference'], 'value'):
            updates['billing_preference'] = updates['billing_preference'].value

        # Convert nested Pydantic models to dicts
        if 'pricing_config' in updates and updates['pricing_config']:
            updates['pricing_config'] = updates['pricing_config'].dict() if hasattr(updates['pricing_config'], 'dict') else updates['pricing_config']
        if 'usage_limits' in updates and updates['usage_limits']:
            updates['usage_limits'] = updates['usage_limits'].dict() if hasattr(updates['usage_limits'], 'dict') else updates['usage_limits']

        result = micro_saas_service.update_app_settings(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            updates=updates
        )

        return result

    except MicroSaasError as e:
        logger.error(f"Error updating app settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating settings"
        )


@router.put("/{frontend_app_id}/visibility", response_model=MicroSaasAppResponse)
async def update_visibility(
    frontend_app_id: str,
    request: MicroSaasVisibilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update visibility setting for a Micro SaaS app

    Visibility options:
    - public: Anyone with IOFlow account can see in marketplace
    - private: Only creator can see (useful during testing)
    - granted_access: Only users with access can see in marketplace
    """
    try:
        result = micro_saas_service.update_visibility(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            visibility=request.visibility.value
        )

        return result

    except MicroSaasError as e:
        logger.error(f"Error updating visibility: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating visibility"
        )


@router.put("/{frontend_app_id}/billing", response_model=MicroSaasAppResponse)
async def update_billing_config(
    frontend_app_id: str,
    request: MicroSaasBillingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update billing configuration for a Micro SaaS app

    Billing preferences:
    - per_user_per_month: Monthly subscription per user
    - per_execution: Pay per execution/usage
    - free: Free to use
    """
    try:
        result = micro_saas_service.update_billing_config(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            billing_preference=request.billing_preference.value,
            pricing_config=request.pricing_config.dict() if request.pricing_config else None,
            usage_limits=request.usage_limits.dict() if request.usage_limits else None
        )

        return result

    except MicroSaasError as e:
        logger.error(f"Error updating billing config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating billing configuration"
        )


@router.put("/{frontend_app_id}/usage-limits", response_model=MicroSaasAppResponse)
async def update_usage_limits(
    frontend_app_id: str,
    request: MicroSaasUsageLimitsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update usage limits and quotas for a Micro SaaS app
    """
    try:
        updates = {
            "usage_limits": request.usage_limits.dict()
        }

        result = micro_saas_service.update_app_settings(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            updates=updates
        )

        return result

    except MicroSaasError as e:
        logger.error(f"Error updating usage limits: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating usage limits"
        )


@router.get("/{frontend_app_id}/debug/logs")
async def debug_access_logs(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint to see all access logs for an app
    """
    from db.application_models import FrontendAppAccessLog

    logs = db.query(FrontendAppAccessLog).filter(
        FrontendAppAccessLog.frontend_app_id == frontend_app_id
    ).all()

    return {
        "total_logs": len(logs),
        "logs": [
            {
                "log_id": log.log_id,
                "access_type": log.access_type,
                "execution_success": log.execution_success,
                "execution_time_ms": log.execution_time_ms,
                "error_message": log.error_message,
                "accessed_at": log.accessed_at.isoformat() if log.accessed_at else None
            }
            for log in logs
        ]
    }


@router.get("/{frontend_app_id}/analytics", response_model=MicroSaasAnalytics)
async def get_app_analytics(
    frontend_app_id: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive analytics for a Micro SaaS app

    Includes:
    - Execution metrics (total, successful, failed, avg time, cost)
    - Executions by day
    - Revenue metrics (if paid app)
    - Subscriber metrics
    - Top subscribers by usage
    - Popular execution hours
    """
    try:
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        analytics = micro_saas_service.get_app_analytics(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            start_date=start_dt,
            end_date=end_dt
        )

        return analytics

    except MicroSaasError as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use ISO format (YYYY-MM-DD)"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating analytics"
        )


@router.get("/{frontend_app_id}/subscribers", response_model=SubscriberListResponse)
async def get_app_subscribers(
    frontend_app_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of subscribers for a Micro SaaS app

    Includes:
    - Subscriber details (name, email, status)
    - Billing information
    - Usage statistics
    - Payment history
    """
    try:
        subscribers = micro_saas_service.get_subscribers(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            status_filter=status_filter
        )

        return {
            "total": len(subscribers),
            "subscribers": subscribers
        }

    except MicroSaasError as e:
        logger.error(f"Error getting subscribers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching subscribers"
        )


@router.get("/{frontend_app_id}/billing-history", response_model=BillingHistoryResponse)
async def get_billing_history(
    frontend_app_id: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get billing history for a Micro SaaS app

    Includes:
    - All transactions (payments, charges, top-ups, refunds)
    - Execution costs breakdown
    - Prepaid balance information
    - Total revenue and costs
    """
    try:
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        history = micro_saas_service.get_billing_history(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            start_date=start_dt,
            end_date=end_dt
        )

        return history

    except MicroSaasError as e:
        logger.error(f"Error getting billing history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use ISO format (YYYY-MM-DD)"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching billing history"
        )


@router.post("/{frontend_app_id}/grant-access", response_model=AccessManagementResponse)
async def grant_access(
    frontend_app_id: str,
    request: GrantAccessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Grant access to specific users for a Micro SaaS app

    Adds users to the allowed list for apps with 'specific_users' access type
    """
    try:
        # This would be implemented to add users to access_config
        # For now, return a placeholder response
        return {
            "success": True,
            "message": f"Access granted to {len(request.user_emails)} users",
            "affected_count": len(request.user_emails),
            "errors": None
        }

    except Exception as e:
        logger.error(f"Error granting access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while granting access"
        )


@router.post("/{frontend_app_id}/revoke-access", response_model=AccessManagementResponse)
async def revoke_access(
    frontend_app_id: str,
    request: RevokeAccessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke access from specific subscribers for a Micro SaaS app
    """
    try:
        # This would be implemented to remove subscribers
        # For now, return a placeholder response
        return {
            "success": True,
            "message": f"Access revoked from {len(request.subscriber_ids)} subscribers",
            "affected_count": len(request.subscriber_ids),
            "errors": None
        }

    except Exception as e:
        logger.error(f"Error revoking access: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking access"
        )


@router.post("/{frontend_app_id}/top-up", response_model=TopUpResponse)
async def top_up_prepaid_balance(
    frontend_app_id: str,
    request: TopUpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Top up prepaid balance for a Micro SaaS app

    For prepaid billing mode, this endpoint processes a payment and adds
    the amount to the app's prepaid balance for usage-based billing.
    """
    try:
        # This would integrate with payment gateway (Razorpay, Stripe, etc.)
        # For now, return a placeholder response
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"

        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount": request.amount,
            "new_balance": request.amount,  # Would fetch actual balance
            "currency": request.currency,
            "payment_gateway_transaction_id": None
        }

    except Exception as e:
        logger.error(f"Error processing top-up: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing top-up"
        )


@router.delete("/{frontend_app_id}")
async def delete_micro_saas_app(
    frontend_app_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (true) or deactivate (false)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a Micro SaaS app

    This will:
    - By default: Deactivate the app (soft delete) to preserve billing history
    - With hard_delete=true: Permanently delete the app and all related data
    """
    try:
        result = micro_saas_service.delete_micro_saas_app(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=current_user.user_id,
            hard_delete=hard_delete
        )
        return result

    except Exception as e:
        logger.error(f"Error deleting app: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the app"
        )


# Import uuid for transaction ID generation
import uuid


# ============================================================================
# Related Flows Endpoints (Pre-requisites and Follow-ups)
# ============================================================================

@router.get("/{frontend_app_id}/related-flows", response_model=RelatedFlowsListResponse)
async def get_related_flows(
    frontend_app_id: str,
    include_inactive: bool = Query(False, description="Include inactive relationships"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all related flows (prerequisites and follow-ups) for a Micro SaaS app.

    Returns both prerequisites and follow-ups with their configuration and
    details about the related apps including input/output schemas.
    """
    try:
        result = related_flows_service.get_related_flows(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=str(current_user.user_id),
            include_inactive=include_inactive
        )
        return result

    except RelatedFlowsError as e:
        logger.error(f"Error getting related flows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting related flows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching related flows"
        )


@router.post("/{frontend_app_id}/related-flows", response_model=RelatedFlowResponse)
async def add_related_flow(
    frontend_app_id: str,
    config: RelatedFlowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a new related flow (prerequisite or follow-up) to a Micro SaaS app.

    - Prerequisites: Flows that should/must run before the main flow
    - Follow-ups: Flows that can run after the main flow completes
    """
    try:
        result = related_flows_service.add_related_flow(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=str(current_user.user_id),
            config=config.dict()
        )
        return result

    except RelatedFlowsError as e:
        logger.error(f"Error adding related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error adding related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding related flow"
        )


@router.put("/{frontend_app_id}/related-flows/{relationship_id}", response_model=RelatedFlowResponse)
async def update_related_flow(
    frontend_app_id: str,
    relationship_id: str,
    updates: RelatedFlowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing related flow relationship.

    Allows updating:
    - is_mandatory: Whether prerequisite must be completed
    - execution_order: Order within the relationship type
    - display_name: Custom display name
    - documentation: Help text shown to users
    - parameter_mappings: Manual parameter mapping configuration
    - auto_map_enabled: Whether to auto-map parameters by name
    - is_active: Whether the relationship is active
    """
    try:
        result = related_flows_service.update_related_flow(
            db=db,
            relationship_id=relationship_id,
            user_id=str(current_user.user_id),
            updates=updates.dict(exclude_unset=True)
        )
        return result

    except RelatedFlowsError as e:
        logger.error(f"Error updating related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating related flow"
        )


@router.delete("/{frontend_app_id}/related-flows/{relationship_id}")
async def remove_related_flow(
    frontend_app_id: str,
    relationship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a related flow relationship.

    This permanently deletes the relationship between the apps.
    """
    try:
        result = related_flows_service.remove_related_flow(
            db=db,
            relationship_id=relationship_id,
            user_id=str(current_user.user_id)
        )
        return {"success": result, "message": "Related flow removed successfully"}

    except RelatedFlowsError as e:
        logger.error(f"Error removing related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error removing related flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while removing related flow"
        )


@router.put("/{frontend_app_id}/related-flows/reorder")
async def reorder_related_flows(
    frontend_app_id: str,
    request: ReorderRelatedFlowsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reorder related flows within a relationship type.

    Allows drag-drop reordering of prerequisites or follow-ups.
    """
    try:
        result = related_flows_service.reorder_related_flows(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=str(current_user.user_id),
            relationship_type=request.relationship_type.value,
            ordered_ids=request.ordered_ids
        )
        return {"success": result, "message": "Related flows reordered successfully"}

    except RelatedFlowsError as e:
        logger.error(f"Error reordering related flows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error reordering related flows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while reordering related flows"
        )


@router.get("/{frontend_app_id}/available-apps", response_model=AvailableAppsForLinkingResponse)
async def get_available_apps_for_linking(
    frontend_app_id: str,
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    search: Optional[str] = Query(None, description="Search term"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get apps available for linking as prerequisites or follow-ups.

    Returns apps that are:
    - Active
    - Not already linked with the specified relationship type
    - Either same tenant, public, or marketplace approved
    """
    try:
        result = related_flows_service.get_available_apps_for_linking(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=str(current_user.user_id),
            relationship_type=relationship_type,
            search=search
        )
        return result

    except RelatedFlowsError as e:
        logger.error(f"Error getting available apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting available apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching available apps"
        )


@router.post("/{frontend_app_id}/preview-mapping")
async def preview_auto_mapping(
    frontend_app_id: str,
    source_outputs: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview auto-mapping for all follow-up flows of an app.

    Given the outputs from a main flow execution, this endpoint returns
    how those outputs would be mapped to each follow-up flow's inputs.
    """
    try:
        result = related_flows_service.preview_auto_mapping(
            db=db,
            frontend_app_id=frontend_app_id,
            source_outputs=source_outputs
        )
        return {"previews": result}

    except RelatedFlowsError as e:
        logger.error(f"Error previewing auto-mapping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error previewing auto-mapping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while previewing auto-mapping"
        )


# ============================================================================
# LANDING PAGE DESIGNER ENDPOINTS
# ============================================================================

LANDING_IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "landing-pages")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/svg+xml", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGES_PER_APP = 50


@router.get("/{frontend_app_id}/page-definition")
async def get_page_definition(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the landing page definition for a Micro SaaS app"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    raw = app.page_definition
    if raw and isinstance(raw, str):
        raw = json.loads(raw)
    return {"page_definition": raw}


@router.put("/{frontend_app_id}/page-definition")
async def update_page_definition(
    frontend_app_id: str,
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save or update the landing page definition"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    page_definition = body.get("page_definition")
    if not page_definition or not isinstance(page_definition, dict):
        raise HTTPException(status_code=400, detail="page_definition must be a valid JSON object")

    app.page_definition = page_definition
    db.commit()
    db.refresh(app)
    return {"success": True, "page_definition": app.page_definition}


@router.delete("/{frontend_app_id}/page-definition")
async def delete_page_definition(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reset landing page to default layout"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    app.page_definition = None
    db.commit()
    return {"success": True, "message": "Page definition reset to default"}


@router.post("/{frontend_app_id}/landing-images/upload")
async def upload_landing_image(
    frontend_app_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload an image for the landing page designer"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Validate content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed. Allowed: JPEG, PNG, GIF, SVG, WebP")

    # Check image count limit
    existing_count = db.query(LandingPageImage).filter(
        LandingPageImage.frontend_app_id == frontend_app_id
    ).count()
    if existing_count >= MAX_IMAGES_PER_APP:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES_PER_APP} images per app")

    # Read file content
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    image_id = str(uuid.uuid4())
    filename = f"{image_id}{ext}"

    # Create directory if needed
    app_dir = os.path.join(LANDING_IMAGES_DIR, frontend_app_id)
    os.makedirs(app_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(app_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Build public URL
    public_url = f"/uploads/landing-pages/{frontend_app_id}/{filename}"

    # Save to database
    image = LandingPageImage(
        image_id=image_id,
        frontend_app_id=frontend_app_id,
        filename=filename,
        original_filename=file.filename or "image",
        content_type=file.content_type,
        file_size=len(content),
        storage_path=file_path,
        public_url=public_url
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    return {
        "image_id": image.image_id,
        "filename": image.original_filename,
        "public_url": image.public_url,
        "content_type": image.content_type,
        "file_size": image.file_size
    }


@router.get("/{frontend_app_id}/landing-images")
async def list_landing_images(
    frontend_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all uploaded images for a landing page"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    images = db.query(LandingPageImage).filter(
        LandingPageImage.frontend_app_id == frontend_app_id
    ).order_by(LandingPageImage.created_at.desc()).all()

    return {
        "images": [
            {
                "image_id": img.image_id,
                "filename": img.original_filename,
                "public_url": img.public_url,
                "content_type": img.content_type,
                "file_size": img.file_size,
                "created_at": img.created_at.isoformat() if img.created_at else None
            }
            for img in images
        ],
        "total": len(images),
        "max_allowed": MAX_IMAGES_PER_APP
    }


@router.delete("/{frontend_app_id}/landing-images/{image_id}")
async def delete_landing_image(
    frontend_app_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an uploaded landing page image"""
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Permission denied")

    image = db.query(LandingPageImage).filter(
        LandingPageImage.image_id == image_id,
        LandingPageImage.frontend_app_id == frontend_app_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Delete file from disk
    try:
        if os.path.exists(image.storage_path):
            os.remove(image.storage_path)
    except Exception as e:
        logger.warning(f"Failed to delete image file {image.storage_path}: {e}")

    db.delete(image)
    db.commit()
    return {"success": True, "message": "Image deleted"}

"""
API endpoints for application pricing management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from db.database import get_db
from db.models import User, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, PricingModel, BillingCycle, 
    UsageMetricType, CurrencyType
)
from schemas.pricing_schemas import (
    PricingCreate, PricingUpdate, PricingResponse,
    PricingListResponse
)
from .auth import get_current_user
from services.razorpay_service import razorpay_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/applications", tags=["pricing"])


def check_application_provider_permission(
    current_user: User,
    application: Application,
    db: Session
) -> bool:
    """Check if user has permission to manage application pricing"""
    # Admin can manage any application
    if current_user.role == UserRole.INSTANCE_ADMIN:
        return True
    
    # Application provider can manage their own tenant's applications
    if current_user.role == UserRole.APPLICATION_PROVIDER:
        return application.tenant_id_owner == current_user.tenant_id
    
    # Application creator can manage their own applications
    if str(application.created_by) == str(current_user.user_id):
        return True
    
    return False


@router.post("/{app_id}/pricing", response_model=PricingResponse)
async def create_pricing(
    app_id: str,
    pricing_data: PricingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create pricing for an application"""
    # Get application
    application = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    if not check_application_provider_permission(current_user, application, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage pricing for this application"
        )
    
    # Validate pricing model requirements
    if pricing_data.pricing_model == PricingModel.SUBSCRIPTION:
        if not pricing_data.billing_cycle or not pricing_data.base_subscription_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription pricing requires billing_cycle and base_subscription_cost"
            )
    
    if pricing_data.pricing_model == PricingModel.PAY_PER_USE:
        if not pricing_data.usage_metric_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pay-per-use pricing requires usage_metric_type"
            )
    
    # Check if active pricing already exists
    existing_pricing = db.query(ApplicationPricing).filter(
        ApplicationPricing.app_id == app_id,
        ApplicationPricing.is_active == True
    ).first()
    
    if existing_pricing:
        # Deactivate existing pricing
        existing_pricing.is_active = False
        db.commit()
    
    # Create new pricing
    pricing = ApplicationPricing(
        app_id=app_id,
        pricing_model=pricing_data.pricing_model.value,
        billing_cycle=pricing_data.billing_cycle.value if pricing_data.billing_cycle else None,
        usage_metric_type=pricing_data.usage_metric_type.value if pricing_data.usage_metric_type else None,
        incoming_event_cost=pricing_data.incoming_event_cost,
        outgoing_service_cost=pricing_data.outgoing_service_cost,
        base_subscription_cost=pricing_data.base_subscription_cost,
        cost_per_kb=pricing_data.cost_per_kb,
        cost_per_token=pricing_data.cost_per_token,
        currency=pricing_data.currency.value,
        is_active=True,
        # Enhanced billing fields
        billing_mode=pricing_data.billing_mode.value if pricing_data.billing_mode else "prepaid",
        is_free=pricing_data.is_free,
        service_pricing_enabled=pricing_data.service_pricing_enabled
    )
    
    # Create Razorpay plan if subscription model
    if pricing_data.pricing_model == PricingModel.SUBSCRIPTION:
        try:
            plan_id = razorpay_service.create_subscription_plan(
                pricing=pricing,
                app_name=application.app_name
            )
            if plan_id:
                pricing.razorpay_plan_id = plan_id
            else:
                logger.warning(f"Failed to create Razorpay plan for app {app_id}")
        except Exception as e:
            logger.error(f"Error creating Razorpay plan: {str(e)}")
    
    db.add(pricing)
    db.commit()
    db.refresh(pricing)
    
    return pricing


@router.get("/{app_id}/pricing", response_model=PricingListResponse)
async def get_pricing(
    app_id: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get pricing for an application"""
    # Get application
    application = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Build query
    query = db.query(ApplicationPricing).filter(
        ApplicationPricing.app_id == app_id
    )
    
    if not include_inactive:
        query = query.filter(ApplicationPricing.is_active == True)
    
    pricing_list = query.order_by(ApplicationPricing.created_at.desc()).all()
    
    return {
        "pricing_plans": pricing_list,
        "total": len(pricing_list)
    }


@router.put("/{app_id}/pricing/{pricing_id}", response_model=PricingResponse)
async def update_pricing(
    app_id: str,
    pricing_id: str,
    pricing_update: PricingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update pricing for an application"""
    # Get application
    application = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    if not check_application_provider_permission(current_user, application, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage pricing for this application"
        )
    
    # Get pricing
    pricing = db.query(ApplicationPricing).filter(
        ApplicationPricing.pricing_id == pricing_id,
        ApplicationPricing.app_id == app_id
    ).first()
    
    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pricing not found"
        )
    
    # Update fields if provided
    update_data = pricing_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(pricing, field):
            # Convert enums to values
            if field in ['pricing_model', 'billing_cycle', 'usage_metric_type', 'currency']:
                setattr(pricing, field, value.value if value else None)
            else:
                setattr(pricing, field, value)
    
    pricing.updated_at = datetime.utcnow()
    
    # Update Razorpay plan if needed
    if pricing.pricing_model == PricingModel.SUBSCRIPTION.value and not pricing.razorpay_plan_id:
        try:
            plan_id = razorpay_service.create_subscription_plan(
                pricing=pricing,
                app_name=application.app_name
            )
            if plan_id:
                pricing.razorpay_plan_id = plan_id
        except Exception as e:
            logger.error(f"Error creating Razorpay plan: {str(e)}")
    
    db.commit()
    db.refresh(pricing)
    
    return pricing


@router.delete("/{app_id}/pricing/{pricing_id}")
async def deactivate_pricing(
    app_id: str,
    pricing_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate pricing for an application"""
    # Get application
    application = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check permissions
    if not check_application_provider_permission(current_user, application, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage pricing for this application"
        )
    
    # Get pricing
    pricing = db.query(ApplicationPricing).filter(
        ApplicationPricing.pricing_id == pricing_id,
        ApplicationPricing.app_id == app_id
    ).first()
    
    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pricing not found"
        )
    
    # Deactivate pricing
    pricing.is_active = False
    pricing.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Pricing deactivated successfully"}
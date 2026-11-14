"""
API endpoints for managing tenant subscription preferences
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pydantic import BaseModel, Field
from decimal import Decimal

from db.database import get_db
from db.models import User, UserRole
from api.auth import get_current_user
from services.subscription_preference_service import subscription_preference_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/subscription-preferences",
    tags=["subscription-preferences"]
)


class SubscriptionPreferencesUpdate(BaseModel):
    """Model for updating subscription preferences"""
    billing_preference: Optional[str] = Field(None, description="Billing preference: prepaid, postpaid, hybrid")
    default_payment_method: Optional[str] = Field(None, description="Default payment method")
    
    # Auto-renewal and top-up
    auto_renewal_enabled: Optional[bool] = Field(None, description="Enable auto-renewal")
    auto_topup_enabled: Optional[bool] = Field(None, description="Enable auto top-up")
    auto_topup_amount: Optional[float] = Field(None, description="Amount to top up automatically")
    auto_topup_trigger_amount: Optional[float] = Field(None, description="Trigger top-up when balance falls below this")
    
    # Spending limits
    monthly_spending_limit: Optional[float] = Field(None, description="Maximum monthly spending")
    daily_spending_limit: Optional[float] = Field(None, description="Maximum daily spending")
    per_execution_limit: Optional[float] = Field(None, description="Maximum cost per execution")
    
    # Invoice preferences
    invoice_frequency: Optional[str] = Field(None, description="Invoice frequency: weekly, monthly, quarterly, yearly")
    invoice_email: Optional[str] = Field(None, description="Email for invoices")
    send_detailed_invoice: Optional[bool] = Field(None, description="Include detailed usage in invoice")
    
    # Notification preferences
    notification_preference: Optional[str] = Field(None, description="Notification preference: email, sms, both, none")
    low_balance_alert_enabled: Optional[bool] = Field(None, description="Enable low balance alerts")
    usage_alert_enabled: Optional[bool] = Field(None, description="Enable usage alerts")
    alert_threshold_percentage: Optional[int] = Field(None, ge=1, le=100, description="Alert threshold percentage")
    
    # Cost optimization
    prefer_cached_results: Optional[bool] = Field(None, description="Prefer cached results to save costs")
    max_retry_on_failure: Optional[int] = Field(None, ge=0, le=10, description="Maximum retries on failure")
    enable_cost_optimization: Optional[bool] = Field(None, description="Enable cost optimization suggestions")
    
    # Subscription defaults
    default_subscription_tier: Optional[str] = Field(None, description="Default subscription tier for new apps")
    auto_subscribe_new_apps: Optional[bool] = Field(None, description="Auto-subscribe to new applications")
    
    # Budget alerts
    budget_alert_contacts: Optional[list] = Field(None, description="Contacts for budget alerts")
    additional_preferences: Optional[dict] = Field(None, description="Additional preferences")


@router.get("/")
async def get_subscription_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get subscription preferences for the current tenant"""
    try:
        preferences = subscription_preference_service.get_preferences(
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription preferences not found"
            )
        
        return subscription_preference_service._serialize_preferences(preferences)
        
    except Exception as e:
        logger.error(f"Error fetching subscription preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching subscription preferences: {str(e)}"
        )


@router.put("/")
async def update_subscription_preferences(
    preferences_update: SubscriptionPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update subscription preferences for the current tenant"""
    
    # Check if user has permission (must be TENANT_ADMIN or INSTANCE_ADMIN)
    if current_user.role not in [UserRole.TENANT_ADMIN, UserRole.INSTANCE_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant admins can update subscription preferences"
        )
    
    try:
        # Convert the update model to dict, excluding None values
        update_data = preferences_update.dict(exclude_none=True)
        
        result = subscription_preference_service.update_preferences(
            tenant_id=current_user.tenant_id,
            preferences_data=update_data,
            user_id=str(current_user.user_id),
            db=db
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update preferences")
            )
        
        return result["preferences"]
        
    except Exception as e:
        logger.error(f"Error updating subscription preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating subscription preferences: {str(e)}"
        )


@router.get("/spending-status")
async def get_spending_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current spending status against configured limits"""
    try:
        from db.pricing_models import BalanceTransaction, TransactionType
        from sqlalchemy import func, and_
        from datetime import datetime
        
        preferences = subscription_preference_service.get_preferences(
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        if not preferences:
            return {
                "daily_spent": 0,
                "monthly_spent": 0,
                "daily_limit": None,
                "monthly_limit": None,
                "within_limits": True
            }
        
        # Calculate daily spending
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_spent = db.query(
            func.sum(BalanceTransaction.amount)
        ).filter(
            and_(
                BalanceTransaction.tenant_id == current_user.tenant_id,
                BalanceTransaction.transaction_type == TransactionType.DEBIT.value,
                BalanceTransaction.created_at >= today_start
            )
        ).scalar() or Decimal(0)
        
        # Calculate monthly spending
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_spent = db.query(
            func.sum(BalanceTransaction.amount)
        ).filter(
            and_(
                BalanceTransaction.tenant_id == current_user.tenant_id,
                BalanceTransaction.transaction_type == TransactionType.DEBIT.value,
                BalanceTransaction.created_at >= month_start
            )
        ).scalar() or Decimal(0)
        
        # Check if within limits
        within_daily = True
        within_monthly = True
        
        if preferences.daily_spending_limit:
            within_daily = daily_spent <= preferences.daily_spending_limit
        
        if preferences.monthly_spending_limit:
            within_monthly = monthly_spent <= preferences.monthly_spending_limit
        
        return {
            "daily_spent": float(daily_spent),
            "monthly_spent": float(monthly_spent),
            "daily_limit": float(preferences.daily_spending_limit) if preferences.daily_spending_limit else None,
            "monthly_limit": float(preferences.monthly_spending_limit) if preferences.monthly_spending_limit else None,
            "daily_percentage": float((daily_spent / preferences.daily_spending_limit) * 100) if preferences.daily_spending_limit else None,
            "monthly_percentage": float((monthly_spent / preferences.monthly_spending_limit) * 100) if preferences.monthly_spending_limit else None,
            "within_limits": within_daily and within_monthly,
            "within_daily_limit": within_daily,
            "within_monthly_limit": within_monthly
        }
        
    except Exception as e:
        logger.error(f"Error fetching spending status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching spending status: {str(e)}"
        )


@router.post("/validate-spending")
async def validate_spending(
    amount: float,
    limit_type: str = "execution",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate if a spending amount is within configured limits"""
    try:
        is_valid = subscription_preference_service.validate_spending_limits(
            tenant_id=current_user.tenant_id,
            amount=Decimal(str(amount)),
            limit_type=limit_type,
            db=db
        )
        
        return {
            "valid": is_valid,
            "amount": amount,
            "limit_type": limit_type
        }
        
    except Exception as e:
        logger.error(f"Error validating spending: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating spending: {str(e)}"
        )


@router.get("/cost-optimization-settings")
async def get_cost_optimization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get cost optimization settings for the current tenant"""
    try:
        settings = subscription_preference_service.get_cost_optimization_settings(
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        return settings
        
    except Exception as e:
        logger.error(f"Error fetching cost optimization settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cost optimization settings: {str(e)}"
        )
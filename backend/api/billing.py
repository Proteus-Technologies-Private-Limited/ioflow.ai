"""
API endpoints for billing and subscription management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import uuid

from db.database import get_db
from db.models import User, Tenant, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ApplicationInvoice, ExecutionCostLog, PricingModel,
    TenantBalance, BalanceTransaction, UsageLimit
)
from schemas.pricing_schemas import (
    SubscriptionCreate, SubscriptionResponse,
    UsageSummaryResponse, ExecutionCostResponse,
    InvoiceResponse, InvoiceListResponse,
    PaymentWebhookData
)
from .auth import get_current_user
from services.razorpay_service import razorpay_service
from services.cost_calculator import cost_calculator
from services.topup_service import topup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["billing"])


@router.post("/applications/{app_id}/subscribe", response_model=SubscriptionResponse)
async def subscribe_to_application(
    app_id: str,
    subscription_data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subscribe tenant to an application"""
    # Get application
    application = db.query(Application).filter(
        Application.app_id == app_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if user has permission (must be admin or from the tenant)
    if current_user.role != UserRole.INSTANCE_ADMIN and current_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to subscribe to applications"
        )
    
    # Get pricing
    pricing = db.query(ApplicationPricing).filter(
        ApplicationPricing.pricing_id == subscription_data.pricing_id,
        ApplicationPricing.app_id == app_id,
        ApplicationPricing.is_active == True
    ).first()
    
    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active pricing not found"
        )
    
    # Check if already subscribed
    existing_sub = db.query(TenantApplicationSubscription).filter(
        TenantApplicationSubscription.app_id == app_id,
        TenantApplicationSubscription.tenant_id == current_user.tenant_id,
        TenantApplicationSubscription.status == 'active'
    ).first()
    
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already subscribed to this application"
        )
    
    # Get tenant
    tenant = db.query(Tenant).filter(
        Tenant.tenant_id == current_user.tenant_id
    ).first()
    
    # Create Razorpay customer if not exists
    razorpay_customer_id = None
    if pricing.pricing_model == PricingModel.SUBSCRIPTION.value:
        razorpay_customer_id = razorpay_service.create_customer(
            tenant=tenant,
            email=current_user.email
        )
    
    # Create subscription
    subscription = TenantApplicationSubscription(
        tenant_id=current_user.tenant_id,
        app_id=app_id,
        pricing_id=subscription_data.pricing_id,
        razorpay_customer_id=razorpay_customer_id,
        auth_credentials=subscription_data.auth_credentials,
        webhook_url=subscription_data.webhook_url,
        subscription_config=subscription_data.subscription_config,
        subscription_start_date=datetime.utcnow(),
        status='pending',  # Will be activated after payment
        invocation_api_key=generate_api_key(),
        api_key_created_at=datetime.utcnow()
    )
    
    # Create Razorpay subscription if subscription model
    if pricing.pricing_model == PricingModel.SUBSCRIPTION.value and pricing.razorpay_plan_id:
        razorpay_sub = razorpay_service.create_subscription(
            plan_id=pricing.razorpay_plan_id,
            customer_id=razorpay_customer_id,
            notes={
                "tenant_id": str(tenant.tenant_id),
                "app_id": str(app_id),
                "subscription_id": str(subscription.subscription_id)
            }
        )
        
        if razorpay_sub:
            subscription.razorpay_subscription_id = razorpay_sub['id']
            subscription.next_billing_date = datetime.fromtimestamp(
                razorpay_sub.get('charge_at', 0)
            )
    else:
        # For pay-per-use, activate immediately
        subscription.status = 'active'
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    return subscription


@router.post("/applications/{app_id}/unsubscribe")
async def unsubscribe_from_application(
    app_id: str,
    cancel_immediately: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel subscription to an application"""
    # Get active subscription
    subscription = db.query(TenantApplicationSubscription).filter(
        TenantApplicationSubscription.app_id == app_id,
        TenantApplicationSubscription.tenant_id == current_user.tenant_id,
        TenantApplicationSubscription.status == 'active'
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active subscription not found"
        )
    
    # Cancel Razorpay subscription if exists
    if subscription.razorpay_subscription_id:
        success = razorpay_service.cancel_subscription(
            subscription_id=subscription.razorpay_subscription_id,
            cancel_at_cycle_end=not cancel_immediately
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel subscription with payment provider"
            )
    
    if cancel_immediately:
        subscription.status = 'cancelled'
        subscription.subscription_end_date = datetime.utcnow()
    else:
        subscription.status = 'pending_cancellation'
    
    db.commit()
    
    return {"message": "Subscription cancelled successfully"}


@router.get("/tenant/subscriptions", response_model=List[SubscriptionResponse])
async def get_tenant_subscriptions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all subscriptions for the current tenant"""
    query = db.query(TenantApplicationSubscription).filter(
        TenantApplicationSubscription.tenant_id == current_user.tenant_id
    )
    
    if status:
        query = query.filter(TenantApplicationSubscription.status == status)
    
    subscriptions = query.all()
    return subscriptions


@router.get("/tenant/usage-costs", response_model=UsageSummaryResponse)
async def get_usage_costs(
    app_id: Optional[str] = None,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage cost summary for the tenant"""
    # Default to current month if no dates provided
    if not start_date:
        start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    if not end_date:
        end_date = datetime.utcnow()
    
    summary = cost_calculator.get_tenant_usage_summary(
        tenant_id=current_user.tenant_id,
        app_id=app_id,
        start_date=start_date,
        end_date=end_date,
        db=db
    )
    
    summary['period_start'] = start_date
    summary['period_end'] = end_date
    
    return summary


@router.get("/executions/{execution_id}/cost", response_model=ExecutionCostResponse)
async def get_execution_cost(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get cost details for a specific execution"""
    cost_log = db.query(ExecutionCostLog).filter(
        ExecutionCostLog.execution_id == execution_id,
        ExecutionCostLog.tenant_id == current_user.tenant_id
    ).first()
    
    if not cost_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cost log not found for this execution"
        )
    
    # Build cost breakdown
    cost_breakdown = {
        "incoming_events": cost_log.incoming_event_cost,
        "outgoing_services": cost_log.outgoing_service_cost,
        "data_transfer": cost_log.data_transfer_cost,
        "tokens": cost_log.token_cost
    }
    
    response = ExecutionCostResponse(
        **cost_log.__dict__,
        cost_breakdown=cost_breakdown
    )
    
    return response


@router.get("/tenant/invoices", response_model=InvoiceListResponse)
async def get_invoices(
    app_id: Optional[str] = None,
    payment_status: Optional[str] = None,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get invoices for the tenant"""
    query = db.query(ApplicationInvoice).filter(
        ApplicationInvoice.tenant_id == current_user.tenant_id
    )
    
    if app_id:
        query = query.filter(ApplicationInvoice.app_id == app_id)
    
    if payment_status:
        query = query.filter(ApplicationInvoice.payment_status == payment_status)
    
    if start_date:
        query = query.filter(ApplicationInvoice.invoice_date >= start_date)
    
    if end_date:
        query = query.filter(ApplicationInvoice.invoice_date <= end_date)
    
    invoices = query.order_by(ApplicationInvoice.invoice_date.desc()).all()
    
    total_amount = sum(invoice.total_amount for invoice in invoices)
    currency = invoices[0].currency if invoices else 'USD'
    
    return {
        "invoices": invoices,
        "total": len(invoices),
        "total_amount": total_amount,
        "currency": currency
    }


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific invoice"""
    invoice = db.query(ApplicationInvoice).filter(
        ApplicationInvoice.invoice_id == invoice_id,
        ApplicationInvoice.tenant_id == current_user.tenant_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.get("/tenant/balance")
async def get_tenant_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current balance and transaction history for tenant"""
    return topup_service.get_balance_summary(
        tenant_id=current_user.tenant_id,
        db=db
    )


from pydantic import BaseModel
from decimal import Decimal

class TopupRequest(BaseModel):
    amount: float
    payment_method: str = "manual"

@router.post("/tenant/balance/topup")
async def topup_balance(
    request: TopupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Top up tenant balance"""
    # Check permission
    if current_user.role not in [UserRole.INSTANCE_ADMIN, UserRole.TENANT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and tenant admins can top up balance"
        )
    
    if request.payment_method == "razorpay":
        result = topup_service.process_razorpay_topup(
            tenant_id=current_user.tenant_id,
            amount=Decimal(str(request.amount)),
            user_id=str(current_user.user_id),
            db=db
        )
    else:
        # For manual/test top-ups
        result = topup_service.process_topup(
            tenant_id=current_user.tenant_id,
            amount=Decimal(str(request.amount)),
            payment_method=request.payment_method,
            description=f"Manual top-up by {current_user.email}",
            user_id=str(current_user.user_id),
            db=db
        )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to process top-up")
        )
    
    return result


@router.post("/tenant/balance/confirm-payment")
async def confirm_payment(
    order_id: str,
    payment_id: str,
    signature: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm Razorpay payment and update balance"""
    success = topup_service.confirm_razorpay_payment(
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to confirm payment"
        )
    
    return {"status": "success", "message": "Balance updated successfully"}


@router.get("/tenant/balance/transactions")
async def get_balance_transactions(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get balance transaction history"""
    query = db.query(BalanceTransaction).filter(
        BalanceTransaction.tenant_id == current_user.tenant_id
    )
    
    if transaction_type:
        query = query.filter(BalanceTransaction.transaction_type == transaction_type)
    
    if start_date:
        query = query.filter(BalanceTransaction.created_at >= start_date)
    
    if end_date:
        query = query.filter(BalanceTransaction.created_at <= end_date)
    
    total = query.count()
    transactions = query.order_by(
        BalanceTransaction.created_at.desc()
    ).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "transactions": [
            {
                "transaction_id": str(t.transaction_id),
                "type": t.transaction_type,
                "amount": float(t.amount),
                "currency": t.currency,
                "balance_before": float(t.balance_before),
                "balance_after": float(t.balance_after),
                "description": t.description,
                "reference_id": t.reference_id,
                "reference_type": t.reference_type,
                "payment_status": t.payment_status,
                "created_at": t.created_at.isoformat()
            }
            for t in transactions
        ]
    }


@router.put("/tenant/balance/settings")
async def update_balance_settings(
    low_balance_threshold: Optional[float] = None,
    critical_balance_threshold: Optional[float] = None,
    auto_topup_enabled: Optional[bool] = None,
    auto_topup_amount: Optional[float] = None,
    auto_topup_trigger_amount: Optional[float] = None,
    daily_spending_limit: Optional[float] = None,
    monthly_spending_limit: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update balance settings and thresholds"""
    # Check permission
    if current_user.role not in [UserRole.INSTANCE_ADMIN, UserRole.PROJECT_OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and project owners can update balance settings"
        )
    
    balance = topup_service.get_or_create_balance(current_user.tenant_id, db)
    
    # Update settings
    if low_balance_threshold is not None:
        balance.low_balance_threshold = low_balance_threshold
    if critical_balance_threshold is not None:
        balance.critical_balance_threshold = critical_balance_threshold
    if auto_topup_enabled is not None:
        balance.auto_topup_enabled = auto_topup_enabled
    if auto_topup_amount is not None:
        balance.auto_topup_amount = auto_topup_amount
    if auto_topup_trigger_amount is not None:
        balance.auto_topup_trigger_amount = auto_topup_trigger_amount
    if daily_spending_limit is not None:
        balance.daily_spending_limit = daily_spending_limit
    if monthly_spending_limit is not None:
        balance.monthly_spending_limit = monthly_spending_limit
    
    db.commit()
    db.refresh(balance)
    
    return {
        "low_balance_threshold": float(balance.low_balance_threshold) if balance.low_balance_threshold else None,
        "critical_balance_threshold": float(balance.critical_balance_threshold) if balance.critical_balance_threshold else None,
        "auto_topup_enabled": balance.auto_topup_enabled,
        "auto_topup_amount": float(balance.auto_topup_amount) if balance.auto_topup_amount else None,
        "auto_topup_trigger_amount": float(balance.auto_topup_trigger_amount) if balance.auto_topup_trigger_amount else None,
        "daily_spending_limit": float(balance.daily_spending_limit) if balance.daily_spending_limit else None,
        "monthly_spending_limit": float(balance.monthly_spending_limit) if balance.monthly_spending_limit else None
    }


@router.post("/webhooks/razorpay")
async def handle_razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Razorpay webhooks"""
    try:
        # Get webhook data
        webhook_body = await request.body()
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        
        # Verify signature
        if not razorpay_service.verify_webhook_signature(
            webhook_body.decode('utf-8'),
            webhook_signature
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse webhook data
        webhook_data = await request.json()
        event_type = webhook_data.get('event')
        payload = webhook_data.get('payload')
        
        logger.info(f"Received Razorpay webhook: {event_type}")
        
        # Process based on event type
        if event_type.startswith('subscription.'):
            razorpay_service.process_subscription_webhook(
                event_type=event_type,
                payload=payload,
                db=db
            )
        elif event_type.startswith('payment.'):
            razorpay_service.process_payment_webhook(
                event_type=event_type,
                payload=payload,
                db=db
            )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )
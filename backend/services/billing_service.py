"""
Billing Service for invoice generation and management
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from db.database import get_db
from db.models import Tenant
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ApplicationInvoice, ExecutionCostLog, PricingModel
)
from services.razorpay_service import razorpay_service

logger = logging.getLogger(__name__)


class BillingService:
    """Service for handling billing and invoice generation"""
    
    def generate_monthly_invoices(self, db: Session = None) -> List[ApplicationInvoice]:
        """
        Generate monthly invoices for all active subscriptions
        Should be run at the beginning of each month
        """
        if not db:
            db = next(get_db())
        
        generated_invoices = []
        
        try:
            # Get current date and last month's date range
            now = datetime.utcnow()
            last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            last_month_end = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(seconds=1)
            
            # Get all active subscriptions
            subscriptions = db.query(TenantApplicationSubscription).filter(
                TenantApplicationSubscription.status == 'active'
            ).all()
            
            for subscription in subscriptions:
                try:
                    invoice = self._generate_invoice_for_subscription(
                        subscription=subscription,
                        billing_start=last_month_start,
                        billing_end=last_month_end,
                        db=db
                    )
                    if invoice:
                        generated_invoices.append(invoice)
                except Exception as e:
                    logger.error(f"Error generating invoice for subscription {subscription.subscription_id}: {str(e)}")
            
            return generated_invoices
            
        except Exception as e:
            logger.error(f"Error generating monthly invoices: {str(e)}")
            return []
    
    def _generate_invoice_for_subscription(
        self,
        subscription: TenantApplicationSubscription,
        billing_start: datetime,
        billing_end: datetime,
        db: Session
    ) -> Optional[ApplicationInvoice]:
        """Generate invoice for a specific subscription"""
        try:
            # Get pricing details
            pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.pricing_id == subscription.pricing_id
            ).first()
            
            if not pricing:
                logger.error(f"Pricing not found for subscription {subscription.subscription_id}")
                return None
            
            # Calculate charges
            subscription_charges = Decimal(0)
            usage_charges = Decimal(0)
            usage_details = {}
            
            # Subscription charges (if applicable)
            if pricing.pricing_model == PricingModel.SUBSCRIPTION.value:
                # Calculate prorated amount if needed
                if subscription.subscription_start_date > billing_start:
                    # Prorate for partial month
                    days_in_period = (billing_end - billing_start).days + 1
                    days_subscribed = (billing_end - subscription.subscription_start_date).days + 1
                    prorate_factor = Decimal(days_subscribed) / Decimal(days_in_period)
                    subscription_charges = pricing.base_subscription_cost * prorate_factor
                else:
                    subscription_charges = pricing.base_subscription_cost or Decimal(0)
            
            # Usage charges
            usage_logs = db.query(ExecutionCostLog).filter(
                and_(
                    ExecutionCostLog.tenant_id == subscription.tenant_id,
                    ExecutionCostLog.app_id == subscription.app_id,
                    ExecutionCostLog.timestamp >= billing_start,
                    ExecutionCostLog.timestamp <= billing_end
                )
            ).all()
            
            # Aggregate usage
            total_executions = len(usage_logs)
            total_incoming_events = sum(log.incoming_event_count for log in usage_logs)
            total_outgoing_services = sum(log.outgoing_service_count for log in usage_logs)
            total_data_kb = sum(log.data_transfer_kb for log in usage_logs)
            total_tokens = sum(log.token_count for log in usage_logs)
            
            # Calculate usage costs
            for log in usage_logs:
                usage_charges += log.total_cost
            
            usage_details = {
                "executions": total_executions,
                "incoming_events": total_incoming_events,
                "outgoing_services": total_outgoing_services,
                "data_transfer_kb": total_data_kb,
                "tokens_used": total_tokens,
                "cost_breakdown": {
                    "incoming_events": sum(log.incoming_event_cost for log in usage_logs),
                    "outgoing_services": sum(log.outgoing_service_cost for log in usage_logs),
                    "data_transfer": sum(log.data_transfer_cost for log in usage_logs),
                    "tokens": sum(log.token_cost for log in usage_logs)
                }
            }
            
            # Calculate totals
            subtotal = subscription_charges + usage_charges
            tax_amount = Decimal(0)  # Implement tax calculation based on region
            total_amount = subtotal + tax_amount
            
            # Skip if no charges
            if total_amount <= 0:
                logger.info(f"No charges for subscription {subscription.subscription_id}, skipping invoice")
                return None
            
            # Generate invoice number
            invoice_number = self._generate_invoice_number(db)
            
            # Create invoice
            invoice = ApplicationInvoice(
                tenant_id=subscription.tenant_id,
                app_id=subscription.app_id,
                subscription_id=subscription.subscription_id,
                invoice_number=invoice_number,
                invoice_date=datetime.utcnow(),
                billing_period_start=billing_start,
                billing_period_end=billing_end,
                subscription_charges=subscription_charges,
                usage_charges=usage_charges,
                usage_details=usage_details,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                currency=pricing.currency,
                payment_status='pending'
            )
            
            # Create Razorpay invoice if needed
            if subscription.razorpay_customer_id:
                tenant = db.query(Tenant).filter(
                    Tenant.tenant_id == subscription.tenant_id
                ).first()
                
                app = db.query(Application).filter(
                    Application.app_id == subscription.app_id
                ).first()
                
                line_items = []
                
                if subscription_charges > 0:
                    line_items.append({
                        "name": f"{app.app_name} Subscription",
                        "description": f"{pricing.billing_cycle} subscription",
                        "amount": int(subscription_charges * 100),  # Convert to paise
                        "currency": pricing.currency,
                        "quantity": 1
                    })
                
                if usage_charges > 0:
                    line_items.append({
                        "name": f"{app.app_name} Usage Charges",
                        "description": f"Usage from {billing_start.date()} to {billing_end.date()}",
                        "amount": int(usage_charges * 100),
                        "currency": pricing.currency,
                        "quantity": 1
                    })
                
                razorpay_invoice = razorpay_service.create_invoice_for_charges(
                    customer_id=subscription.razorpay_customer_id,
                    amount=int(total_amount * 100),
                    currency=pricing.currency,
                    description=f"Invoice for {app.app_name} - {invoice_number}",
                    line_items=line_items
                )
                
                if razorpay_invoice:
                    invoice.razorpay_invoice_id = razorpay_invoice['id']
            
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
            
            # Update subscription
            subscription.last_invoice_id = str(invoice.invoice_id)
            subscription.total_usage_cost = Decimal(0)  # Reset for new billing period
            db.commit()
            
            logger.info(f"Generated invoice {invoice_number} for subscription {subscription.subscription_id}")
            return invoice
            
        except Exception as e:
            logger.error(f"Error generating invoice: {str(e)}")
            db.rollback()
            return None
    
    def _generate_invoice_number(self, db: Session) -> str:
        """Generate unique invoice number"""
        # Format: INV-YYYYMM-XXXX
        now = datetime.utcnow()
        prefix = f"INV-{now.strftime('%Y%m')}-"
        
        # Get count of invoices this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        count = db.query(ApplicationInvoice).filter(
            ApplicationInvoice.created_at >= month_start
        ).count()
        
        return f"{prefix}{count + 1:04d}"
    
    def process_payment(
        self,
        invoice_id: str,
        payment_id: str,
        payment_method: str = "razorpay",
        db: Session = None
    ) -> bool:
        """Mark invoice as paid"""
        if not db:
            db = next(get_db())
        
        try:
            invoice = db.query(ApplicationInvoice).filter(
                ApplicationInvoice.invoice_id == invoice_id
            ).first()
            
            if not invoice:
                logger.error(f"Invoice {invoice_id} not found")
                return False
            
            invoice.payment_status = 'paid'
            invoice.payment_date = datetime.utcnow()
            invoice.razorpay_payment_id = payment_id
            
            db.commit()
            logger.info(f"Invoice {invoice.invoice_number} marked as paid")
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            db.rollback()
            return False
    
    def get_pending_invoices(self, tenant_id: str, db: Session = None) -> List[ApplicationInvoice]:
        """Get all pending invoices for a tenant"""
        if not db:
            db = next(get_db())
        
        return db.query(ApplicationInvoice).filter(
            and_(
                ApplicationInvoice.tenant_id == tenant_id,
                ApplicationInvoice.payment_status == 'pending'
            )
        ).order_by(ApplicationInvoice.invoice_date.desc()).all()
    
    def get_invoice_summary(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        db: Session = None
    ) -> Dict:
        """Get invoice summary for a tenant"""
        if not db:
            db = next(get_db())
        
        query = db.query(ApplicationInvoice).filter(
            ApplicationInvoice.tenant_id == tenant_id
        )
        
        if start_date:
            query = query.filter(ApplicationInvoice.invoice_date >= start_date)
        if end_date:
            query = query.filter(ApplicationInvoice.invoice_date <= end_date)
        
        invoices = query.all()
        
        return {
            "total_invoices": len(invoices),
            "paid_invoices": len([i for i in invoices if i.payment_status == 'paid']),
            "pending_invoices": len([i for i in invoices if i.payment_status == 'pending']),
            "total_amount": sum(i.total_amount for i in invoices),
            "paid_amount": sum(i.total_amount for i in invoices if i.payment_status == 'paid'),
            "pending_amount": sum(i.total_amount for i in invoices if i.payment_status == 'pending'),
            "currency": invoices[0].currency if invoices else 'USD'
        }


# Singleton instance
billing_service = BillingService()
"""
Razorpay Integration Service for handling subscriptions and payments
"""
import razorpay
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import uuid
import json

from core.config import settings
from db.database import get_db
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription, 
    ApplicationInvoice, PricingModel, BillingCycle
)
from db.models import Tenant
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RazorpayService:
    def __init__(self):
        # Initialize Razorpay client with credentials from settings
        self.client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            )
        )
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    
    def create_subscription_plan(
        self, 
        pricing: ApplicationPricing,
        app_name: str
    ) -> Optional[str]:
        """
        Create a Razorpay subscription plan for an application pricing
        Returns the Razorpay plan ID
        """
        try:
            # Convert billing cycle to Razorpay period
            period_map = {
                BillingCycle.DAILY.value: "daily",
                BillingCycle.MONTHLY.value: "monthly",
                BillingCycle.YEARLY.value: "yearly"
            }
            
            # Calculate total amount (base + estimated usage)
            amount = int(pricing.base_subscription_cost * 100)  # Convert to paise/cents
            
            plan_data = {
                "period": period_map.get(pricing.billing_cycle, "monthly"),
                "interval": 1,
                "item": {
                    "name": f"{app_name} - {pricing.billing_cycle} Plan",
                    "description": f"Subscription plan for {app_name}",
                    "amount": amount,
                    "currency": pricing.currency
                },
                "notes": {
                    "app_id": str(pricing.app_id),
                    "pricing_id": str(pricing.pricing_id)
                }
            }
            
            plan = self.client.plan.create(data=plan_data)
            logger.info(f"Created Razorpay plan: {plan['id']}")
            return plan['id']
            
        except Exception as e:
            logger.error(f"Error creating Razorpay plan: {str(e)}")
            return None
    
    def create_customer(
        self, 
        tenant: Tenant,
        email: str
    ) -> Optional[str]:
        """
        Create a Razorpay customer for a tenant
        Returns the Razorpay customer ID
        """
        try:
            customer_data = {
                "name": tenant.tenant_name,
                "email": email,
                "fail_existing": "0",  # Don't fail if customer exists
                "notes": {
                    "tenant_id": str(tenant.tenant_id)
                }
            }
            
            customer = self.client.customer.create(data=customer_data)
            logger.info(f"Created Razorpay customer: {customer['id']}")
            return customer['id']
            
        except Exception as e:
            logger.error(f"Error creating Razorpay customer: {str(e)}")
            return None
    
    def create_subscription(
        self,
        plan_id: str,
        customer_id: str,
        total_count: Optional[int] = None,
        notes: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Create a Razorpay subscription
        Returns subscription details
        """
        try:
            subscription_data = {
                "plan_id": plan_id,
                "customer_id": customer_id,
                "quantity": 1,
                "notes": notes or {}
            }
            
            if total_count:
                subscription_data["total_count"] = total_count
            
            subscription = self.client.subscription.create(data=subscription_data)
            logger.info(f"Created Razorpay subscription: {subscription['id']}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating Razorpay subscription: {str(e)}")
            return None
    
    def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_cycle_end: bool = True
    ) -> bool:
        """
        Cancel a Razorpay subscription
        """
        try:
            if cancel_at_cycle_end:
                self.client.subscription.cancel(subscription_id, data={
                    "cancel_at_cycle_end": 1
                })
            else:
                self.client.subscription.cancel(subscription_id)
            
            logger.info(f"Cancelled Razorpay subscription: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling Razorpay subscription: {str(e)}")
            return False
    
    def create_addon(
        self,
        subscription_id: str,
        amount: int,
        currency: str,
        description: str
    ) -> Optional[Dict]:
        """
        Create an addon charge for usage-based billing
        """
        try:
            addon_data = {
                "item": {
                    "name": "Usage Charges",
                    "amount": amount,  # In paise/cents
                    "currency": currency,
                    "description": description
                },
                "quantity": 1
            }
            
            addon = self.client.subscription.createAddon(
                subscription_id, 
                data=addon_data
            )
            logger.info(f"Created addon for subscription {subscription_id}")
            return addon
            
        except Exception as e:
            logger.error(f"Error creating addon: {str(e)}")
            return None
    
    def fetch_subscription(self, subscription_id: str) -> Optional[Dict]:
        """
        Fetch subscription details from Razorpay
        """
        try:
            subscription = self.client.subscription.fetch(subscription_id)
            return subscription
        except Exception as e:
            logger.error(f"Error fetching subscription: {str(e)}")
            return None
    
    def create_invoice_for_charges(
        self,
        customer_id: str,
        amount: int,
        currency: str,
        description: str,
        line_items: List[Dict]
    ) -> Optional[Dict]:
        """
        Create a one-time invoice for usage charges
        """
        try:
            invoice_data = {
                "type": "invoice",
                "customer_id": customer_id,
                "line_items": line_items,
                "currency": currency,
                "description": description
            }
            
            invoice = self.client.invoice.create(data=invoice_data)
            logger.info(f"Created Razorpay invoice: {invoice['id']}")
            return invoice
            
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return None
    
    def verify_webhook_signature(
        self,
        webhook_body: str,
        webhook_signature: str
    ) -> bool:
        """
        Verify Razorpay webhook signature
        """
        try:
            self.client.utility.verify_webhook_signature(
                webhook_body,
                webhook_signature,
                self.webhook_secret
            )
            return True
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
    
    def process_subscription_webhook(
        self,
        event_type: str,
        payload: Dict,
        db: Session
    ) -> bool:
        """
        Process subscription-related webhooks
        """
        try:
            subscription = payload.get("subscription", {})
            subscription_id = subscription.get("id")
            
            if not subscription_id:
                logger.error("No subscription ID in webhook payload")
                return False
            
            # Find the subscription in our database
            tenant_subscription = db.query(TenantApplicationSubscription).filter(
                TenantApplicationSubscription.razorpay_subscription_id == subscription_id
            ).first()
            
            if not tenant_subscription:
                logger.error(f"Subscription {subscription_id} not found in database")
                return False
            
            if event_type == "subscription.activated":
                tenant_subscription.status = "active"
                tenant_subscription.subscription_start_date = datetime.now()
                
            elif event_type == "subscription.charged":
                # Update next billing date
                if subscription.get("charge_at"):
                    tenant_subscription.next_billing_date = datetime.fromtimestamp(
                        subscription["charge_at"]
                    )
                
            elif event_type == "subscription.cancelled":
                tenant_subscription.status = "cancelled"
                tenant_subscription.subscription_end_date = datetime.now()
                
            elif event_type == "subscription.paused":
                tenant_subscription.status = "paused"
                
            elif event_type == "subscription.resumed":
                tenant_subscription.status = "active"
            
            db.commit()
            logger.info(f"Processed webhook {event_type} for subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing subscription webhook: {str(e)}")
            db.rollback()
            return False
    
    def process_payment_webhook(
        self,
        event_type: str,
        payload: Dict,
        db: Session
    ) -> bool:
        """
        Process payment-related webhooks
        """
        try:
            payment = payload.get("payment", {})
            invoice_id = payment.get("invoice_id")
            
            if not invoice_id:
                logger.error("No invoice ID in payment webhook")
                return False
            
            # Find the invoice in our database
            invoice = db.query(ApplicationInvoice).filter(
                ApplicationInvoice.razorpay_invoice_id == invoice_id
            ).first()
            
            if not invoice:
                logger.error(f"Invoice {invoice_id} not found in database")
                return False
            
            if event_type == "payment.captured":
                invoice.payment_status = "paid"
                invoice.payment_date = datetime.now()
                invoice.razorpay_payment_id = payment.get("id")
                
            elif event_type == "payment.failed":
                invoice.payment_status = "failed"
            
            db.commit()
            logger.info(f"Processed webhook {event_type} for invoice {invoice_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment webhook: {str(e)}")
            db.rollback()
            return False


# Singleton instance
razorpay_service = RazorpayService()
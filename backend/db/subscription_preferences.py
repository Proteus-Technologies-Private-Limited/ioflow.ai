"""
Subscription Preferences Model for Tenant Organizations
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP, Text, Integer, Enum as SQLEnum, Numeric
from sqlalchemy.sql import func
import enum
import uuid

from core.config import settings

# Import appropriate Base based on database
if settings.database_url.startswith("sqlite"):
    from .models import Base
    UUID_TYPE = String(36)
    JSON_TYPE = Text
    NUMERIC_TYPE = Numeric(precision=10, scale=2)
else:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    Base = declarative_base()
    UUID_TYPE = UUID(as_uuid=True)
    JSON_TYPE = JSONB
    NUMERIC_TYPE = Numeric(precision=10, scale=2)


# Subscription Preference Enums
class BillingPreference(enum.Enum):
    PREPAID = "prepaid"  # Pay in advance (current balance system)
    POSTPAID = "postpaid"  # Pay after usage with monthly invoice
    HYBRID = "hybrid"  # Mix of prepaid credits and postpaid for overages

class PaymentMethod(enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    UPI = "upi"
    WALLET = "wallet"
    BANK_TRANSFER = "bank_transfer"
    RAZORPAY = "razorpay"

class InvoiceFrequency(enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class NotificationPreference(enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"
    NONE = "none"


class TenantSubscriptionPreferences(Base):
    """
    Stores subscription and billing preferences for each tenant organization
    """
    __tablename__ = 'tenant_subscription_preferences'
    __table_args__ = {'extend_existing': True}
    
    if settings.database_url.startswith("sqlite"):
        preference_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        tenant_id = Column(String(36), ForeignKey('tenants.tenant_id'), unique=True, nullable=False)
    else:
        preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        tenant_id = Column(UUID(as_uuid=True), ForeignKey('ioflow.tenants.tenant_id'), unique=True, nullable=False)
    
    # Billing Preferences
    billing_preference = Column(String(20), nullable=False, default=BillingPreference.PREPAID.value)
    default_payment_method = Column(String(50), nullable=False, default=PaymentMethod.RAZORPAY.value)
    
    # Auto-renewal and top-up settings
    auto_renewal_enabled = Column(Boolean, default=True)
    auto_topup_enabled = Column(Boolean, default=False)
    auto_topup_amount = Column(NUMERIC_TYPE, nullable=True)  # Amount to top up when balance is low
    auto_topup_trigger_amount = Column(NUMERIC_TYPE, nullable=True)  # Trigger top-up when balance falls below this
    
    # Spending limits
    monthly_spending_limit = Column(NUMERIC_TYPE, nullable=True)  # Maximum monthly spend
    daily_spending_limit = Column(NUMERIC_TYPE, nullable=True)  # Maximum daily spend
    per_execution_limit = Column(NUMERIC_TYPE, nullable=True)  # Maximum cost per execution
    
    # Invoice preferences
    invoice_frequency = Column(String(20), nullable=False, default=InvoiceFrequency.MONTHLY.value)
    invoice_email = Column(String(255), nullable=True)  # Separate email for invoices
    send_detailed_invoice = Column(Boolean, default=True)  # Include detailed usage in invoice
    
    # Notification preferences
    notification_preference = Column(String(20), nullable=False, default=NotificationPreference.EMAIL.value)
    low_balance_alert_enabled = Column(Boolean, default=True)
    usage_alert_enabled = Column(Boolean, default=True)
    alert_threshold_percentage = Column(Integer, default=20)  # Alert when balance/limit reaches this %
    
    # Cost optimization preferences
    prefer_cached_results = Column(Boolean, default=False)  # Use cached results when available to save costs
    max_retry_on_failure = Column(Integer, default=3)  # Maximum retries for failed executions
    enable_cost_optimization = Column(Boolean, default=True)  # Allow system to suggest cost optimizations
    
    # Default subscription plans for new applications
    default_subscription_tier = Column(String(50), nullable=True)  # e.g., 'basic', 'pro', 'enterprise'
    auto_subscribe_new_apps = Column(Boolean, default=False)  # Automatically subscribe to new applications
    
    # Budget alerts
    budget_alert_contacts = Column(JSON_TYPE, nullable=True)  # List of emails/phones for budget alerts
    
    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    updated_by = Column(String(36), nullable=True)  # User ID who last updated preferences
    
    # Additional preferences as JSON for flexibility
    additional_preferences = Column(JSON_TYPE, nullable=True)
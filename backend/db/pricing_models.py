"""
Pricing and Billing Models for Application Subscription System - PostgreSQL and SQLite
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP, Text, Integer, Numeric, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from .models import Base
from .db_compat import JSONB, schema_table_args, fk


# Pricing Enums
class PricingModel(enum.Enum):
    SUBSCRIPTION = "subscription"
    PAY_PER_USE = "pay_per_use"


class BillingMode(enum.Enum):
    FREE = "free"
    PREPAID = "prepaid"
    POSTPAID = "postpaid"
    SUBSCRIPTION = "subscription"


class BillingCycle(enum.Enum):
    DAILY = "daily"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class UsageMetricType(enum.Enum):
    PER_REQUEST = "per_request"
    PER_KB = "per_kb"
    PER_TOKEN = "per_token"


class CurrencyType(enum.Enum):
    USD = "USD"
    INR = "INR"
    EUR = "EUR"
    GBP = "GBP"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionType(enum.Enum):
    TOPUP = "topup"
    DEBIT = "debit"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    BONUS = "bonus"


NUMERIC_TYPE = Numeric(precision=10, scale=2)


class ApplicationPricing(Base):
    __tablename__ = 'application_pricing'
    __table_args__ = schema_table_args(
        CheckConstraint('incoming_event_cost >= 0', name='check_incoming_cost_positive'),
        CheckConstraint('outgoing_service_cost >= 0', name='check_outgoing_cost_positive'),
        extend_existing=True
    )

    pricing_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)

    pricing_model = Column(String(50), nullable=False)
    billing_cycle = Column(String(50), nullable=True)
    usage_metric_type = Column(String(50), nullable=True)

    # New fields for enhanced billing
    billing_mode = Column(String(20), nullable=False, default='prepaid')
    is_free = Column(Boolean, default=False)
    service_pricing_enabled = Column(Boolean, default=False)

    # Cost configuration
    incoming_event_cost = Column(NUMERIC_TYPE, nullable=False, default=0)
    outgoing_service_cost = Column(NUMERIC_TYPE, nullable=False, default=0)
    base_subscription_cost = Column(NUMERIC_TYPE, nullable=True)

    # Additional usage-based costs
    cost_per_kb = Column(NUMERIC_TYPE, nullable=True)
    cost_per_token = Column(NUMERIC_TYPE, nullable=True)

    currency = Column(String(3), nullable=False, default='USD')

    # Razorpay plan ID (for subscription model)
    razorpay_plan_id = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships - unified model works for both PostgreSQL and SQLite
    application = relationship('Application', backref='pricing_plans')


class ServicePricing(Base):
    """Service-specific pricing configuration"""
    __tablename__ = 'service_pricing'
    __table_args__ = schema_table_args(extend_existing=True)

    pricing_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String(36), ForeignKey(fk('application_services.service_id')), nullable=False)

    # Cost configuration
    cost_per_request = Column(NUMERIC_TYPE, nullable=False, default=0)
    cost_per_kb = Column(NUMERIC_TYPE, nullable=True)
    cost_per_token = Column(NUMERIC_TYPE, nullable=True)

    # Pricing control
    is_free = Column(Boolean, default=False)
    override_app_pricing = Column(Boolean, default=True)

    currency = Column(String(3), nullable=False, default='USD')
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships - unified model works for both PostgreSQL and SQLite
    service = relationship('ApplicationService', backref='custom_pricing')


class TenantApplicationSubscription(Base):
    __tablename__ = 'tenant_application_subscriptions'
    __table_args__ = schema_table_args(extend_existing=True)

    subscription_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)
    pricing_id = Column(String(36), ForeignKey(fk('application_pricing.pricing_id')), nullable=False)

    # Razorpay integration
    razorpay_subscription_id = Column(String(255), nullable=True)
    razorpay_customer_id = Column(String(255), nullable=True)

    # Subscription details
    subscription_start_date = Column(TIMESTAMP, nullable=False)
    subscription_end_date = Column(TIMESTAMP, nullable=True)
    next_billing_date = Column(TIMESTAMP, nullable=True)

    # Usage tracking
    total_usage_cost = Column(NUMERIC_TYPE, default=0)
    last_invoice_id = Column(String(36), nullable=True)

    # Auth and webhook config
    auth_credentials = Column(JSONB)
    subscription_config = Column(JSONB)
    webhook_url = Column(String(500))
    invocation_api_key = Column(String(255), unique=True, nullable=True)
    api_key_created_at = Column(TIMESTAMP, nullable=True)
    api_key_last_used_at = Column(TIMESTAMP, nullable=True)

    status = Column(String(20), default='active')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    pricing = relationship('ApplicationPricing', backref='subscriptions')


class ExecutionCostLog(Base):
    __tablename__ = 'execution_cost_logs'
    __table_args__ = schema_table_args(extend_existing=True)

    cost_log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)

    # Event tracking
    incoming_event_count = Column(Integer, default=0)
    outgoing_service_count = Column(Integer, default=0)

    # Cost calculation
    incoming_event_cost = Column(NUMERIC_TYPE, default=0)
    outgoing_service_cost = Column(NUMERIC_TYPE, default=0)

    # Usage metrics
    data_transfer_kb = Column(Integer, default=0)
    data_transfer_cost = Column(NUMERIC_TYPE, default=0)
    token_count = Column(Integer, default=0)
    token_cost = Column(NUMERIC_TYPE, default=0)

    # Total cost
    total_cost = Column(NUMERIC_TYPE, nullable=False)
    currency = Column(String(3), nullable=False)

    # Balance tracking
    balance_deducted = Column(NUMERIC_TYPE, nullable=True)
    payment_method = Column(String(20), nullable=True)

    # Enhanced billing fields
    billing_mode = Column(String(20), nullable=True, default='prepaid')
    service_breakdown = Column(JSONB, nullable=True)
    error_reason = Column(String(255), nullable=True)
    was_free = Column(Boolean, default=False)

    # Metadata
    flow_id = Column(String(36), nullable=True)
    flow_name = Column(String(255), nullable=True)
    trigger_type = Column(String(50), nullable=True)

    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships - unified model works for both PostgreSQL and SQLite
    application = relationship('Application', backref='execution_costs')


class ApplicationInvoice(Base):
    __tablename__ = 'application_invoices'
    __table_args__ = schema_table_args(extend_existing=True)

    invoice_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=False)
    subscription_id = Column(String(36), ForeignKey(fk('tenant_application_subscriptions.subscription_id')), nullable=True)

    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False)
    invoice_date = Column(TIMESTAMP, nullable=False)
    billing_period_start = Column(TIMESTAMP, nullable=False)
    billing_period_end = Column(TIMESTAMP, nullable=False)

    # Charges breakdown
    subscription_charges = Column(NUMERIC_TYPE, default=0)
    usage_charges = Column(NUMERIC_TYPE, default=0)

    # Usage details
    usage_details = Column(JSONB)

    # Totals
    subtotal = Column(NUMERIC_TYPE, nullable=False)
    tax_amount = Column(NUMERIC_TYPE, default=0)
    total_amount = Column(NUMERIC_TYPE, nullable=False)
    currency = Column(String(3), nullable=False)

    # Payment details
    payment_status = Column(String(20), default='pending')
    payment_date = Column(TIMESTAMP, nullable=True)

    # Razorpay integration
    razorpay_invoice_id = Column(String(255), nullable=True)
    razorpay_payment_id = Column(String(255), nullable=True)
    razorpay_order_id = Column(String(255), nullable=True)

    # Additional info
    notes = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships - unified model works for both PostgreSQL and SQLite
    subscription = relationship('TenantApplicationSubscription', backref='invoices')
    application = relationship('Application', backref='invoices')


class TenantBalance(Base):
    """Prepaid balance for tenant to manage usage costs"""
    __tablename__ = 'tenant_balances'
    __table_args__ = schema_table_args(
        CheckConstraint('current_balance >= 0', name='check_current_balance_positive'),
        CheckConstraint('reserved_balance >= 0', name='check_reserved_balance_positive'),
        CheckConstraint('available_balance >= 0', name='check_available_balance_positive'),
        extend_existing=True
    )

    balance_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), unique=True, nullable=False)

    # Balance details
    current_balance = Column(NUMERIC_TYPE, nullable=False, default=0)
    reserved_balance = Column(NUMERIC_TYPE, nullable=False, default=0)
    available_balance = Column(NUMERIC_TYPE, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default='USD')

    # Alert thresholds
    low_balance_threshold = Column(NUMERIC_TYPE, nullable=True, default=10.00)
    critical_balance_threshold = Column(NUMERIC_TYPE, nullable=True, default=5.00)

    # Auto top-up configuration
    auto_topup_enabled = Column(Boolean, default=False)
    auto_topup_amount = Column(NUMERIC_TYPE, nullable=True)
    auto_topup_trigger_amount = Column(NUMERIC_TYPE, nullable=True)

    # Usage limits
    daily_spending_limit = Column(NUMERIC_TYPE, nullable=True)
    monthly_spending_limit = Column(NUMERIC_TYPE, nullable=True)

    # Statistics
    total_topped_up = Column(NUMERIC_TYPE, default=0)
    total_spent = Column(NUMERIC_TYPE, default=0)
    last_topup_date = Column(TIMESTAMP, nullable=True)
    last_alert_sent = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    tenant = relationship('Tenant', backref='balance')


class BalanceTransaction(Base):
    """Audit trail for all balance transactions"""
    __tablename__ = 'balance_transactions'
    __table_args__ = schema_table_args(extend_existing=True)

    transaction_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)

    # Transaction details
    transaction_type = Column(String(20), nullable=False)
    amount = Column(NUMERIC_TYPE, nullable=False)
    currency = Column(String(3), nullable=False)

    # Balance snapshot
    balance_before = Column(NUMERIC_TYPE, nullable=False)
    balance_after = Column(NUMERIC_TYPE, nullable=False)

    # Reference information
    reference_id = Column(String(255), nullable=True)
    reference_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)

    # Payment details (for top-ups)
    payment_method = Column(String(50), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    payment_status = Column(String(20), nullable=True)

    # Additional metadata
    transaction_metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    created_by = Column(String(36), nullable=True)

    # Relationships
    tenant = relationship('Tenant', backref='balance_transactions')


class UsageLimit(Base):
    """Usage limits and controls for tenants"""
    __tablename__ = 'usage_limits'
    __table_args__ = schema_table_args(extend_existing=True)

    limit_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey(fk('tenants.tenant_id')), nullable=False)
    app_id = Column(String(36), ForeignKey(fk('applications.app_id')), nullable=True)

    # Limit configuration
    limit_type = Column(String(50), nullable=False)
    limit_value = Column(NUMERIC_TYPE, nullable=False)
    current_usage = Column(NUMERIC_TYPE, default=0)

    # Reset configuration
    reset_period = Column(String(20), nullable=True)
    last_reset = Column(TIMESTAMP, nullable=True)
    next_reset = Column(TIMESTAMP, nullable=True)

    # Action configuration
    action_on_exceed = Column(String(20), default='block')
    alert_threshold_percent = Column(Integer, default=80)

    # Status
    is_active = Column(Boolean, default=True)
    times_exceeded = Column(Integer, default=0)
    last_exceeded = Column(TIMESTAMP, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships - unified model works for both PostgreSQL and SQLite
    tenant = relationship('Tenant', backref='usage_limits')
    application = relationship('Application', backref='usage_limits')

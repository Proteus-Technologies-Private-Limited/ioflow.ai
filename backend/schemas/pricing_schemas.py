"""
Pydantic schemas for pricing and billing
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal
from enum import Enum

from db.pricing_models import (
    PricingModel, BillingCycle, UsageMetricType,
    CurrencyType, PaymentStatus, BillingMode
)


class PricingCreate(BaseModel):
    pricing_model: PricingModel
    billing_cycle: Optional[BillingCycle] = None
    usage_metric_type: Optional[UsageMetricType] = None
    incoming_event_cost: Decimal = Field(default=Decimal('0'), ge=0)
    outgoing_service_cost: Decimal = Field(default=Decimal('0'), ge=0)
    base_subscription_cost: Optional[Decimal] = Field(default=None, ge=0)
    cost_per_kb: Optional[Decimal] = Field(default=None, ge=0)
    cost_per_token: Optional[Decimal] = Field(default=None, ge=0)
    currency: CurrencyType = CurrencyType.USD
    # Enhanced billing fields
    billing_mode: Optional[BillingMode] = BillingMode.PREPAID  # Will use "prepaid" as value
    is_free: bool = False
    service_pricing_enabled: bool = False


class PricingUpdate(BaseModel):
    pricing_model: Optional[PricingModel] = None
    billing_cycle: Optional[BillingCycle] = None
    usage_metric_type: Optional[UsageMetricType] = None
    incoming_event_cost: Optional[Decimal] = Field(default=None, ge=0)
    outgoing_service_cost: Optional[Decimal] = Field(default=None, ge=0)
    base_subscription_cost: Optional[Decimal] = Field(default=None, ge=0)
    cost_per_kb: Optional[Decimal] = Field(default=None, ge=0)
    cost_per_token: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[CurrencyType] = None
    is_active: Optional[bool] = None


class PricingResponse(BaseModel):
    pricing_id: str
    app_id: str
    pricing_model: str
    billing_cycle: Optional[str]
    usage_metric_type: Optional[str]
    incoming_event_cost: Decimal
    outgoing_service_cost: Decimal
    base_subscription_cost: Optional[Decimal]
    cost_per_kb: Optional[Decimal]
    cost_per_token: Optional[Decimal]
    currency: str
    razorpay_plan_id: Optional[str]
    is_active: bool
    # Enhanced billing fields
    billing_mode: Optional[str] = "PREPAID"
    is_free: bool = False
    service_pricing_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PricingListResponse(BaseModel):
    pricing_plans: List[PricingResponse]
    total: int


class SubscriptionCreate(BaseModel):
    app_id: str
    pricing_id: str
    auth_credentials: Optional[Dict] = None
    webhook_url: Optional[str] = None
    subscription_config: Optional[Dict] = None


class SubscriptionResponse(BaseModel):
    subscription_id: str
    tenant_id: str
    app_id: str
    pricing_id: str
    razorpay_subscription_id: Optional[str]
    razorpay_customer_id: Optional[str]
    subscription_start_date: datetime
    subscription_end_date: Optional[datetime]
    next_billing_date: Optional[datetime]
    total_usage_cost: Decimal
    status: str
    invocation_api_key: Optional[str]
    webhook_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UsageSummaryResponse(BaseModel):
    total_executions: int
    total_cost: Decimal
    incoming_events: int
    outgoing_services: int
    data_transfer_kb: int
    tokens_used: int
    cost_breakdown: Dict[str, Decimal]
    currency: str
    period_start: Optional[datetime]
    period_end: Optional[datetime]


class ExecutionCostResponse(BaseModel):
    cost_log_id: str
    execution_id: str
    app_id: str
    tenant_id: str
    flow_name: str
    trigger_type: str
    incoming_event_count: int
    outgoing_service_count: int
    data_transfer_kb: int
    token_count: int
    total_cost: Decimal
    currency: str
    timestamp: datetime
    cost_breakdown: Dict[str, Decimal]
    
    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    invoice_id: str
    invoice_number: str
    tenant_id: str
    app_id: str
    subscription_id: Optional[str]
    invoice_date: datetime
    billing_period_start: datetime
    billing_period_end: datetime
    subscription_charges: Decimal
    usage_charges: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    payment_status: str
    payment_date: Optional[datetime]
    razorpay_invoice_id: Optional[str]
    razorpay_payment_id: Optional[str]
    usage_details: Optional[Dict]
    notes: Optional[str]
    
    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total: int
    total_amount: Decimal
    currency: str


class PaymentWebhookData(BaseModel):
    event: str
    payload: Dict
    signature: Optional[str] = None
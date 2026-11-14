"""
Pydantic schemas for Micro SaaS Applications

Schemas for Micro SaaS app management, billing configuration, analytics,
subscriber management, and usage tracking.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums

class VisibilityEnum(str, Enum):
    """Marketplace visibility options for Micro SaaS Apps"""
    PUBLIC = "public"  # Anyone with IOFlow account can see in marketplace
    PRIVATE = "private"  # Only creator can see (useful during testing)
    GRANTED_ACCESS = "granted_access"  # Only users with access can see


class BillingPreferenceEnum(str, Enum):
    """Billing basis for Micro SaaS Apps"""
    PER_USER_PER_MONTH = "per_user_per_month"  # Monthly subscription per user
    PER_EXECUTION = "per_execution"  # Pay per execution/usage
    FREE = "free"  # Free to use


class SubscriptionStatusEnum(str, Enum):
    """Status of a subscription"""
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TransactionTypeEnum(str, Enum):
    """Types of billing transactions"""
    SUBSCRIPTION_PAYMENT = "subscription_payment"
    EXECUTION_CHARGE = "execution_charge"
    TOP_UP = "top_up"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class TransactionStatusEnum(str, Enum):
    """Status of a transaction"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pricing Configuration Schemas

class PerUserPerMonthConfig(BaseModel):
    """Configuration for per-user-per-month billing"""
    monthly_price: float = Field(..., description="Monthly price per user", ge=0)
    currency: str = Field(default="USD", max_length=3)
    trial_period_days: int = Field(default=0, ge=0, le=365, description="Free trial period in days")
    minimum_users: int = Field(default=1, ge=1, description="Minimum number of users")
    maximum_users: Optional[int] = Field(None, ge=1, description="Maximum number of users (null = unlimited)")
    volume_discounts: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Volume discounts: [{user_threshold: int, discount_percent: float}]"
    )


class PerExecutionConfig(BaseModel):
    """Configuration for per-execution billing"""
    price_per_execution: float = Field(..., description="Price per execution", ge=0)
    currency: str = Field(default="USD", max_length=3)
    free_executions_per_month: int = Field(default=0, ge=0, description="Free executions included")
    bulk_discounts: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Bulk discounts: [{execution_threshold: int, discount_percent: float}]"
    )
    minimum_charge: Optional[float] = Field(None, ge=0, description="Minimum monthly charge")


class PricingConfig(BaseModel):
    """Unified pricing configuration"""
    billing_preference: BillingPreferenceEnum
    per_user_config: Optional[PerUserPerMonthConfig] = None
    per_execution_config: Optional[PerExecutionConfig] = None

    @validator('per_user_config')
    def validate_per_user_config(cls, v, values):
        billing_pref = values.get('billing_preference')
        if billing_pref == BillingPreferenceEnum.PER_USER_PER_MONTH and not v:
            raise ValueError("per_user_config is required when billing_preference is per_user_per_month")
        return v

    @validator('per_execution_config')
    def validate_per_execution_config(cls, v, values):
        billing_pref = values.get('billing_preference')
        if billing_pref == BillingPreferenceEnum.PER_EXECUTION and not v:
            raise ValueError("per_execution_config is required when billing_preference is per_execution")
        return v


# Usage Limits Configuration

class UsageLimits(BaseModel):
    """Usage limits and quotas for Micro SaaS Apps"""
    max_executions_per_day: Optional[int] = Field(None, ge=1, description="Max executions per day per subscriber")
    max_executions_per_month: Optional[int] = Field(None, ge=1, description="Max executions per month per subscriber")
    max_users: Optional[int] = Field(None, ge=1, description="Maximum number of users/subscribers")
    max_concurrent_executions: Optional[int] = Field(None, ge=1, description="Max concurrent executions")
    quota_reset_period: str = Field(default="monthly", description="Quota reset period: daily, weekly, monthly")
    rate_limit_per_hour: int = Field(default=100, ge=1, le=10000, description="Rate limit per hour per IP")

    @validator('quota_reset_period')
    def validate_quota_reset(cls, v):
        valid_periods = ["daily", "weekly", "monthly"]
        if v not in valid_periods:
            raise ValueError(f"quota_reset_period must be one of: {valid_periods}")
        return v


# Micro SaaS App Schemas

class MicroSaasAppCreate(BaseModel):
    """Schema for creating a Micro SaaS application"""
    flow_id: str = Field(..., description="ID of the flow to publish")
    app_key: str = Field(..., description="Unique key for the application")
    app_name: Optional[str] = Field(None, description="Name for the application")
    description: Optional[str] = Field(None, description="Application description")
    category: str = Field("Micro SaaS Apps", description="Application category")
    icon_url: Optional[str] = Field(None, description="URL to application icon")

    # Micro SaaS specific fields
    visibility: VisibilityEnum = Field(default=VisibilityEnum.PRIVATE, description="Marketplace visibility")
    billing_preference: BillingPreferenceEnum = Field(default=BillingPreferenceEnum.FREE, description="Billing model")
    pricing_config: Optional[PricingConfig] = Field(None, description="Pricing configuration")
    usage_limits: Optional[UsageLimits] = Field(None, description="Usage limits and quotas")

    # Access control fields
    access_type: str = Field("public_url", description="Access control type")
    access_config: Optional[Dict[str, Any]] = Field(None, description="Access configuration")
    public_url_slug: Optional[str] = Field(None, description="Custom URL slug")

    # Additional settings
    auto_update: bool = Field(False, description="Auto-update when flow changes")
    embed_enabled: bool = Field(True, description="Enable embed functionality")
    custom_styling: Optional[Dict[str, Any]] = Field(None, description="Custom styling")
    marketplace_enabled: bool = Field(False, description="Enable in marketplace (for future use)")

    @validator('app_key')
    def validate_app_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("app_key cannot be empty")
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("app_key can only contain alphanumeric characters, underscores, and hyphens")
        return v.strip()

    @validator('access_type')
    def validate_access_type(cls, v):
        valid_types = ["public_url", "organization", "specific_users", "tenant_list"]
        if v not in valid_types:
            raise ValueError(f"access_type must be one of: {valid_types}")
        return v


class MicroSaasAppUpdate(BaseModel):
    """Schema for updating Micro SaaS application settings"""
    frontend_app_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="Description")
    icon_url: Optional[str] = Field(None, description="Icon URL")
    visibility: Optional[VisibilityEnum] = Field(None, description="Marketplace visibility")
    billing_preference: Optional[BillingPreferenceEnum] = Field(None, description="Billing model")
    pricing_config: Optional[PricingConfig] = Field(None, description="Pricing configuration")
    usage_limits: Optional[UsageLimits] = Field(None, description="Usage limits and quotas")
    access_type: Optional[str] = Field(None, description="Access control type")
    access_config: Optional[Dict[str, Any]] = Field(None, description="Access configuration")
    rate_limit_per_hour: Optional[int] = Field(None, description="Rate limit")
    custom_styling: Optional[Dict[str, Any]] = Field(None, description="Custom styling")
    is_active: Optional[bool] = Field(None, description="Active status")
    embed_enabled: Optional[bool] = Field(None, description="Enable embed functionality")
    marketplace_enabled: Optional[bool] = Field(None, description="Enable in marketplace")
    page_definition: Optional[Dict[str, Any]] = Field(None, description="Landing page designer definition")

    @validator('access_type')
    def validate_access_type(cls, v):
        if v is not None:
            valid_types = ["public_url", "organization", "specific_users", "tenant_list"]
            if v not in valid_types:
                raise ValueError(f"access_type must be one of: {valid_types}")
        return v


class MicroSaasVisibilityUpdate(BaseModel):
    """Schema for updating visibility only"""
    visibility: VisibilityEnum


class MicroSaasBillingUpdate(BaseModel):
    """Schema for updating billing configuration"""
    billing_preference: BillingPreferenceEnum
    pricing_config: Optional[PricingConfig] = None
    usage_limits: Optional[UsageLimits] = None


class MicroSaasUsageLimitsUpdate(BaseModel):
    """Schema for updating usage limits"""
    usage_limits: UsageLimits


# Response Schemas

class MicroSaasAppResponse(BaseModel):
    """Response schema for Micro SaaS application"""
    frontend_app_id: str
    published_app_id: Optional[str]
    flow_id: Optional[str]  # Optional for apps that don't have an associated flow
    frontend_app_name: str
    description: Optional[str]
    public_url_slug: str
    public_url: str

    # Micro SaaS specific fields
    visibility: str
    billing_preference: str
    pricing_config: Optional[Dict[str, Any]]
    usage_limits: Optional[Dict[str, Any]]

    # Access control
    access_type: str
    access_config: Optional[Dict[str, Any]]

    # Status and usage
    is_active: bool
    usage_count: int
    rate_limit_per_hour: int
    embed_enabled: bool
    marketplace_enabled: bool

    # Landing page designer
    page_definition: Optional[Dict[str, Any]] = None

    # Creator and tenant information
    creator_username: Optional[str] = Field(None, description="Username of the creator")
    creator_email: Optional[str] = Field(None, description="Email of the creator")
    tenant_name: Optional[str] = Field(None, description="Tenant name")

    # Timestamps
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str]


class MicroSaasAppListResponse(BaseModel):
    """Response schema for listing Micro SaaS apps"""
    total: int
    apps: List[MicroSaasAppResponse]


# Analytics Schemas

class ExecutionMetrics(BaseModel):
    """Execution metrics for a time period"""
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_execution_time_ms: float
    total_cost_incurred: float


class RevenueMetrics(BaseModel):
    """Revenue metrics"""
    total_revenue: float
    revenue_this_month: float
    revenue_last_month: float
    currency: str


class SubscriberMetrics(BaseModel):
    """Subscriber metrics"""
    total_subscribers: int
    active_subscribers: int
    new_subscribers_this_month: int
    cancelled_this_month: int


class MicroSaasAnalytics(BaseModel):
    """Comprehensive analytics for a Micro SaaS app"""
    frontend_app_id: str
    app_name: str

    # Execution metrics
    execution_metrics: ExecutionMetrics
    executions_by_day: List[Dict[str, Any]]  # [{date: str, count: int, cost: float}]

    # Revenue metrics (if paid)
    revenue_metrics: Optional[RevenueMetrics] = None

    # Subscriber metrics
    subscriber_metrics: SubscriberMetrics

    # Top subscribers by usage
    top_subscribers: List[Dict[str, Any]]  # [{subscriber_id, name, execution_count, total_paid}]

    # Geographic distribution
    usage_by_country: Optional[List[Dict[str, Any]]] = None

    # Time-based patterns
    popular_execution_hours: List[Dict[str, Any]]  # [{hour: int, count: int}]


# Subscriber Schemas

class SubscriberInfo(BaseModel):
    """Information about a subscriber"""
    subscriber_id: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    subscriber_name: str
    subscriber_email: str
    subscription_status: str

    # Billing information
    billing_cycle_start: Optional[str]
    billing_cycle_end: Optional[str]
    last_payment_date: Optional[str]
    last_payment_amount: Optional[float]
    total_paid: float

    # Usage information
    execution_count: int
    last_execution_date: Optional[str]

    # Timestamps
    subscribed_at: str
    updated_at: str


class SubscriberListResponse(BaseModel):
    """Response schema for listing subscribers"""
    total: int
    subscribers: List[SubscriberInfo]


class SubscriberPaymentInfo(BaseModel):
    """Detailed payment information for a subscriber"""
    subscriber_id: str
    subscriber_name: str

    # Current billing cycle
    current_cycle_start: str
    current_cycle_end: str
    current_cycle_amount: float
    current_cycle_paid: bool

    # Payment history
    payment_history: List[Dict[str, Any]]  # [{date, amount, status, transaction_id}]

    # Outstanding balance
    outstanding_balance: float

    # Next billing date
    next_billing_date: Optional[str]


# Billing Transaction Schemas

class BillingTransaction(BaseModel):
    """Billing transaction record"""
    transaction_id: str
    frontend_app_id: str
    subscriber_id: Optional[str]
    subscriber_name: Optional[str]
    transaction_type: str
    amount: float
    currency: str
    description: Optional[str]
    payment_gateway: Optional[str]
    payment_gateway_transaction_id: Optional[str]
    status: str
    metadata: Optional[Dict[str, Any]]
    created_at: str
    completed_at: Optional[str]


class BillingTransactionListResponse(BaseModel):
    """Response schema for listing transactions"""
    total: int
    transactions: List[BillingTransaction]
    total_amount: float
    currency: str


class BillingHistoryResponse(BaseModel):
    """Flow-specific billing history"""
    frontend_app_id: str
    app_name: str

    # Summary
    total_transactions: int
    total_revenue: float
    total_costs: float
    net_revenue: float
    currency: str

    # Transactions
    transactions: List[BillingTransaction]

    # Usage breakdown
    execution_costs: List[Dict[str, Any]]  # [{date, executions, cost}]

    # Prepaid balance information
    prepaid_balance: Optional[float] = None
    prepaid_transactions: Optional[List[Dict[str, Any]]] = None  # Top-up history


# Top-up Schemas

class TopUpRequest(BaseModel):
    """Request to top up prepaid balance"""
    amount: float = Field(..., gt=0, description="Amount to add to prepaid balance")
    currency: str = Field(default="USD", max_length=3)
    payment_method: str = Field(..., description="Payment method identifier")
    payment_gateway: str = Field(..., description="Payment gateway to use")


class TopUpResponse(BaseModel):
    """Response after top-up"""
    success: bool
    transaction_id: str
    amount: float
    new_balance: float
    currency: str
    payment_gateway_transaction_id: Optional[str]


# Grant/Revoke Access Schemas

class GrantAccessRequest(BaseModel):
    """Request to grant access to specific users"""
    user_emails: List[str] = Field(..., description="List of user emails to grant access")


class RevokeAccessRequest(BaseModel):
    """Request to revoke access from specific users"""
    subscriber_ids: List[str] = Field(..., description="List of subscriber IDs to revoke access")


class AccessManagementResponse(BaseModel):
    """Response for access management operations"""
    success: bool
    message: str
    affected_count: int
    errors: Optional[List[str]] = None


# Publishing Result Schema (extends base)

class MicroSaasPublishingResult(BaseModel):
    """Result of publishing a Micro SaaS app"""
    success: bool
    message: str

    # Application IDs
    published_app_id: Optional[str] = None
    frontend_app_id: Optional[str] = None
    app_id: Optional[str] = None
    app_key: Optional[str] = None

    # URLs
    public_url: Optional[str] = None
    admin_url: Optional[str] = None

    # Metadata
    version: Optional[str] = None
    services_created: Optional[int] = None
    events_created: Optional[int] = None

    # Warnings and errors
    warnings: Optional[List[str]] = None
    error: Optional[str] = None


# Related Flows Schemas (Pre-requisites and Follow-ups)

class RelationshipTypeEnum(str, Enum):
    """Type of relationship between micro SaaS apps"""
    PREREQUISITE = "prerequisite"
    FOLLOWUP = "followup"


class ParameterMappingItem(BaseModel):
    """Single parameter mapping configuration"""
    source_param: str = Field(..., description="Source parameter name (from main flow output)")
    target_param: str = Field(..., description="Target parameter name (in related flow input)")
    transform: Optional[str] = Field(None, description="Optional transformation expression")
    is_required: bool = Field(default=True, description="Whether this mapping is required")


class ParameterMappingsConfig(BaseModel):
    """Configuration for parameter mappings between flows"""
    mappings: List[ParameterMappingItem] = Field(default_factory=list, description="List of parameter mappings")
    pass_all_outputs: bool = Field(default=False, description="Pass all outputs from main flow")


class RelatedFlowCreate(BaseModel):
    """Schema for creating a related flow relationship"""
    related_frontend_app_id: str = Field(..., description="ID of the related micro SaaS app")
    relationship_type: RelationshipTypeEnum = Field(..., description="Type: prerequisite or followup")
    is_mandatory: bool = Field(default=False, description="For prerequisites: whether it must be completed first")
    execution_order: int = Field(default=0, ge=0, description="Order of execution within relationship type")
    display_name: Optional[str] = Field(None, description="Custom display name for the relationship")
    documentation: Optional[str] = Field(None, description="Help text shown to users")
    parameter_mappings: Optional[ParameterMappingsConfig] = Field(None, description="Manual parameter mapping config")
    auto_map_enabled: bool = Field(default=True, description="Auto-map parameters by name match")


class RelatedFlowUpdate(BaseModel):
    """Schema for updating a related flow relationship"""
    is_mandatory: Optional[bool] = Field(None, description="For prerequisites: whether it must be completed first")
    execution_order: Optional[int] = Field(None, ge=0, description="Order of execution")
    display_name: Optional[str] = Field(None, description="Custom display name")
    documentation: Optional[str] = Field(None, description="Help text shown to users")
    parameter_mappings: Optional[ParameterMappingsConfig] = Field(None, description="Manual parameter mapping config")
    auto_map_enabled: Optional[bool] = Field(None, description="Auto-map parameters by name match")
    is_active: Optional[bool] = Field(None, description="Whether the relationship is active")


class RelatedFlowResponse(BaseModel):
    """Response schema for a related flow relationship"""
    relationship_id: str
    frontend_app_id: str
    related_frontend_app_id: str
    relationship_type: str
    is_mandatory: bool
    execution_order: int
    display_name: Optional[str]
    documentation: Optional[str]
    parameter_mappings: Optional[Dict[str, Any]]
    auto_map_enabled: bool
    is_active: bool
    created_at: str
    updated_at: str

    # Related app details (populated from joined data)
    related_app_name: Optional[str] = Field(None, description="Name of the related app")
    related_app_description: Optional[str] = Field(None, description="Description of the related app")
    related_app_public_url_slug: Optional[str] = Field(None, description="Public URL slug of the related app")
    related_app_icon_url: Optional[str] = Field(None, description="Icon URL of the related app")
    related_app_input_schema: Optional[Dict[str, Any]] = Field(None, description="Input schema of the related flow")
    related_app_output_schema: Optional[Dict[str, Any]] = Field(None, description="Output schema of the related flow")


class RelatedFlowsListResponse(BaseModel):
    """Response schema for listing all related flows of an app"""
    prerequisites: List[RelatedFlowResponse] = Field(default_factory=list)
    followups: List[RelatedFlowResponse] = Field(default_factory=list)
    total_prerequisites: int = 0
    total_followups: int = 0


class ReorderRelatedFlowsRequest(BaseModel):
    """Request to reorder related flows"""
    relationship_type: RelationshipTypeEnum
    ordered_ids: List[str] = Field(..., description="List of relationship IDs in desired order")


class AvailableAppForLinking(BaseModel):
    """An app available to be linked as prerequisite or followup"""
    frontend_app_id: str
    frontend_app_name: str
    description: Optional[str]
    public_url_slug: str
    icon_url: Optional[str]
    visibility: str
    has_input_parameters: bool = Field(default=False)
    has_output_parameters: bool = Field(default=False)
    input_parameter_names: List[str] = Field(default_factory=list)
    output_parameter_names: List[str] = Field(default_factory=list)


class AvailableAppsForLinkingResponse(BaseModel):
    """Response listing apps available for linking"""
    apps: List[AvailableAppForLinking]
    total: int


# Public execution related schemas for related flows

class PublicRelatedFlowInfo(BaseModel):
    """Information about a related flow for public execution page"""
    relationship_id: str
    related_frontend_app_id: str
    relationship_type: str
    is_mandatory: bool
    execution_order: int
    display_name: Optional[str]
    documentation: Optional[str]
    auto_map_enabled: bool

    # App details
    app_name: str
    app_description: Optional[str]
    public_url_slug: str
    icon_url: Optional[str]

    # Input/output info for mapping preview
    input_parameters: List[Dict[str, Any]] = Field(default_factory=list)
    output_parameters: List[Dict[str, Any]] = Field(default_factory=list)

    # Configured mappings
    parameter_mappings: Optional[Dict[str, Any]] = None


class PublicRelatedFlowsResponse(BaseModel):
    """Response with related flows info for public execution page"""
    prerequisites: List[PublicRelatedFlowInfo] = Field(default_factory=list)
    followups: List[PublicRelatedFlowInfo] = Field(default_factory=list)
    mandatory_prerequisites_count: int = 0
    optional_prerequisites_count: int = 0


class AutoMappedParameter(BaseModel):
    """A parameter that was auto-mapped from source to target"""
    source_name: str
    target_name: str
    source_value: Any
    match_type: str = Field(description="exact, partial, or manual")


class AutoMappingPreview(BaseModel):
    """Preview of auto-mapped parameters for a follow-up flow"""
    followup_app_id: str
    followup_app_name: str
    auto_mapped: List[AutoMappedParameter]
    unmapped_required: List[str] = Field(default_factory=list, description="Required inputs with no mapping")
    unmapped_optional: List[str] = Field(default_factory=list, description="Optional inputs with no mapping")

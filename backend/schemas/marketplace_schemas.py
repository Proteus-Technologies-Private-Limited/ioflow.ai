"""
Pydantic schemas for Marketplace API
Handles validation for marketplace apps, reviews, categories, tags, and approvals
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class MarketplaceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class CreatorTierLevel(str, Enum):
    NEW = "new"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    PARTNER = "partner"


class ReviewSortBy(str, Enum):
    RECENT = "recent"
    HELPFUL = "helpful"
    RATING_HIGH = "rating_high"
    RATING_LOW = "rating_low"


class AppSortBy(str, Enum):
    RECENT = "recent"
    POPULAR = "popular"
    TRENDING = "trending"
    RATING = "rating"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    category_id: str
    created_at: datetime
    app_count: Optional[int] = 0  # Number of apps in this category

    class Config:
        from_attributes = True


# Tag Schemas
class TagBase(BaseModel):
    name: str
    slug: str
    color: Optional[str] = "#6366f1"
    is_active: bool = True


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class TagResponse(TagBase):
    tag_id: str
    usage_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# Review Schemas
class ReviewCreate(BaseModel):
    app_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    title: Optional[str] = Field(None, max_length=200)
    review_text: Optional[str] = Field(None, max_length=2000)

    @validator('rating')
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Rating must be between 1 and 5')
        return v


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    review_text: Optional[str] = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    review_id: str
    app_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    rating: int
    title: Optional[str] = None
    review_text: Optional[str] = None
    helpful_count: int = 0
    verified_subscriber: bool = False
    is_visible: bool = True
    is_edited: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_found_helpful: Optional[bool] = False  # Did current user mark as helpful?

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    """Summary statistics for app reviews"""
    total_reviews: int = 0
    avg_rating: float = 0.0
    rating_distribution: Dict[str, int] = Field(default_factory=lambda: {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0})


# Marketplace App Schemas
class MarketplaceAppListItem(BaseModel):
    """Lightweight app info for marketplace browse/search"""
    frontend_app_id: str
    public_url_slug: str
    frontend_app_name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    creator_name: Optional[str] = None
    creator_id: str

    # Pricing
    billing_preference: str
    pricing_config: Optional[Dict[str, Any]] = None

    # Metrics
    avg_rating: float = 0.0
    total_reviews: int = 0
    total_subscribers: int = 0
    trending_score: float = 0.0

    # Discovery
    categories: Optional[List[str]] = []
    tags: Optional[List[str]] = []

    # Featured
    featured_rank: Optional[int] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MarketplaceAppDetail(MarketplaceAppListItem):
    """Full app details for app detail page"""
    screenshots: Optional[List[str]] = []
    demo_url: Optional[str] = None
    usage_limits: Optional[Dict[str, Any]] = None

    # Access info
    access_type: str
    visibility: str

    # Metrics (expanded)
    active_subscribers: int = 0
    usage_count: int = 0

    # Review summary
    review_summary: Optional[ReviewSummary] = None
    recent_reviews: Optional[List[ReviewResponse]] = []

    # Creator info
    creator_tier: Optional[str] = None
    creator_total_apps: Optional[int] = 0

    class Config:
        from_attributes = True


class MarketplaceFilters(BaseModel):
    """Filters for marketplace browse/search"""
    search: Optional[str] = None
    category_id: Optional[str] = None
    category_slug: Optional[str] = None
    tags: Optional[List[str]] = []
    min_rating: Optional[float] = None
    max_price: Optional[float] = None
    billing_preference: Optional[str] = None  # 'free', 'per_user_per_month', 'per_execution'
    sort_by: AppSortBy = AppSortBy.POPULAR
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class MarketplaceAppList(BaseModel):
    """Paginated list of marketplace apps"""
    apps: List[MarketplaceAppListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# Subscription Schemas
class SubscriptionCreate(BaseModel):
    """Request to subscribe to a marketplace app"""
    app_id: str
    subscription_config: Optional[Dict[str, Any]] = None
    auth_credentials: Optional[Dict[str, Any]] = None


class SubscriptionRequirements(BaseModel):
    """Required applications and their connection status"""
    app_id: str
    app_name: str
    required_applications: List[Dict[str, Any]]  # List of required apps with their status
    missing_applications: List[str]  # App IDs that need to be installed/connected
    ready_to_subscribe: bool


class UserSubscriptionInfo(BaseModel):
    """User's subscription to a marketplace app"""
    subscription_id: str
    app_id: str
    app_name: str
    description: Optional[str] = None
    public_url_slug: str
    icon_url: Optional[str] = None

    # Ratings
    avg_rating: float = 0.0
    total_reviews: int = 0

    # Subscription info
    subscription_status: str  # active, paused, expired
    subscribed_at: datetime
    expires_at: Optional[datetime] = None

    # Usage info
    usage_count: int = 0
    usage_limits: Optional[Dict[str, Any]] = None

    # Billing info
    billing_preference: str
    pricing_config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# Creator Tier Schemas
class CreatorTierCreate(BaseModel):
    user_id: str
    tier_level: CreatorTierLevel
    auto_approve: bool = False
    notes: Optional[str] = None


class CreatorTierUpdate(BaseModel):
    tier_level: Optional[CreatorTierLevel] = None
    auto_approve: Optional[bool] = None
    notes: Optional[str] = None


class CreatorTierResponse(BaseModel):
    tier_id: str
    user_id: str
    tier_level: str
    auto_approve: bool
    total_apps_created: int = 0
    total_subscribers: int = 0
    avg_app_rating: float = 0.0
    total_revenue: float = 0.0
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Approval Schemas
class ApprovalCreate(BaseModel):
    """Submit app for marketplace approval"""
    app_id: str
    submission_notes: Optional[str] = None


class ApprovalReview(BaseModel):
    """Admin review of marketplace submission"""
    status: MarketplaceStatus  # approved, rejected
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    approval_id: str
    app_id: str
    app_name: Optional[str] = None
    status: str
    submitted_by: str
    submitted_by_name: Optional[str] = None
    submitted_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    version: int = 1

    class Config:
        from_attributes = True


# App Publishing/Update for Marketplace
class MarketplaceAppPublish(BaseModel):
    """Publish/update app for marketplace"""
    app_id: str
    marketplace_enabled: bool = True
    icon_url: Optional[str] = None
    screenshots: Optional[List[str]] = []
    demo_url: Optional[str] = None
    categories: Optional[List[str]] = []  # Category IDs
    tags: Optional[List[str]] = []  # Tag IDs


class MarketplaceAppUpdate(BaseModel):
    """Update marketplace-specific fields"""
    frontend_app_name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    screenshots: Optional[List[str]] = None
    demo_url: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    billing_preference: Optional[str] = None
    pricing_config: Optional[Dict[str, Any]] = None
    usage_limits: Optional[Dict[str, Any]] = None


# Featured Apps
class FeaturedAppUpdate(BaseModel):
    """Update featured status of app"""
    app_id: str
    featured_rank: Optional[int] = None  # NULL = remove from featured
    featured_until: Optional[datetime] = None


# Analytics/Stats
class MarketplaceStats(BaseModel):
    """Overall marketplace statistics"""
    total_apps: int = 0
    total_active_apps: int = 0
    total_subscribers: int = 0
    total_reviews: int = 0
    avg_app_rating: float = 0.0
    total_executions: int = 0
    top_categories: List[Dict[str, Any]] = []
    trending_apps: List[MarketplaceAppListItem] = []
    featured_apps: List[MarketplaceAppListItem] = []


# Helper Response
class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None

"""
Marketplace-specific database models for IOFlow - PostgreSQL and SQLite
Handles categories, tags, reviews, ratings, creator tiers, and approval workflows
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
import uuid

from .models import Base
from .db_compat import JSONB, schema_table_args, fk


class AppCategory(Base):
    """Categories for organizing marketplace apps"""
    __tablename__ = "app_categories"
    __table_args__ = schema_table_args(
        Index('idx_category_slug', 'slug'),
        Index('idx_category_active', 'is_active'),
    )

    category_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AppTag(Base):
    """Tags for flexible app classification"""
    __tablename__ = "app_tags"
    __table_args__ = schema_table_args(
        Index('idx_tag_slug', 'slug'),
        Index('idx_tag_usage', 'usage_count'),
    )

    tag_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True)
    color = Column(String)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppCategoryMapping(Base):
    """Many-to-many relationship between apps and categories"""
    __tablename__ = "app_category_mapping"
    __table_args__ = schema_table_args(
        Index('idx_app_category', 'app_id', 'category_id'),
        Index('idx_category_apps', 'category_id'),
    )

    mapping_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)
    category_id = Column(String, ForeignKey(fk('app_categories.category_id')), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppTagMapping(Base):
    """Many-to-many relationship between apps and tags"""
    __tablename__ = "app_tag_mapping"
    __table_args__ = schema_table_args(
        Index('idx_app_tag', 'app_id', 'tag_id'),
        Index('idx_tag_apps', 'tag_id'),
    )

    mapping_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)
    tag_id = Column(String, ForeignKey(fk('app_tags.tag_id')), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppReview(Base):
    """User reviews and ratings for marketplace apps"""
    __tablename__ = "app_reviews"
    __table_args__ = schema_table_args(
        Index('idx_review_app', 'app_id'),
        Index('idx_review_user', 'user_id'),
        Index('idx_review_rating', 'rating'),
        Index('idx_review_created', 'created_at'),
        Index('idx_unique_user_app_review', 'app_id', 'user_id', unique=True),
    )

    review_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)
    user_id = Column(String, ForeignKey(fk('users.user_id')), nullable=False)
    tenant_id = Column(String, ForeignKey(fk('tenants.tenant_id')), nullable=False)

    rating = Column(Integer, nullable=False)
    title = Column(String)
    review_text = Column(Text)

    # Review metadata
    helpful_count = Column(Integer, default=0)
    verified_subscriber = Column(Boolean, default=False)

    # Status
    is_visible = Column(Boolean, default=True)
    is_edited = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ReviewHelpful(Base):
    """Track which users found reviews helpful"""
    __tablename__ = "review_helpful"
    __table_args__ = schema_table_args(
        Index('idx_helpful_review', 'review_id'),
        Index('idx_unique_helpful', 'review_id', 'user_id', unique=True),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String, ForeignKey(fk('app_reviews.review_id')), nullable=False)
    user_id = Column(String, ForeignKey(fk('users.user_id')), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CreatorTier(Base):
    """Creator trust levels for approval workflow"""
    __tablename__ = "creator_tiers"
    __table_args__ = schema_table_args(
        Index('idx_creator_user', 'user_id'),
        Index('idx_creator_tier', 'tier_level'),
        Index('idx_creator_auto_approve', 'auto_approve'),
    )

    tier_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey(fk('users.user_id')), nullable=False, unique=True)

    tier_level = Column(String, nullable=False, default='new')
    auto_approve = Column(Boolean, default=False)

    # Metrics
    total_apps_created = Column(Integer, default=0)
    total_subscribers = Column(Integer, default=0)
    avg_app_rating = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)

    # Tier assignment
    assigned_by = Column(String, ForeignKey(fk('users.user_id')))
    assigned_at = Column(DateTime(timezone=True))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MarketplaceApproval(Base):
    """Approval workflow tracking for marketplace submissions"""
    __tablename__ = "marketplace_approvals"
    __table_args__ = schema_table_args(
        Index('idx_approval_app', 'app_id'),
        Index('idx_approval_status', 'status'),
        Index('idx_approval_submitted_at', 'submitted_at'),
    )

    approval_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)

    # Approval status
    status = Column(String, nullable=False, default='pending')

    # Submission info
    submitted_by = Column(String, ForeignKey(fk('users.user_id')), nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Review info
    reviewed_by = Column(String, ForeignKey(fk('users.user_id')))
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    rejection_reason = Column(Text)

    # Version tracking
    version = Column(Integer, default=1)
    previous_approval_id = Column(String, ForeignKey(fk('marketplace_approvals.approval_id')))


class AppMetrics(Base):
    """Cached metrics for marketplace display"""
    __tablename__ = "app_metrics"
    __table_args__ = schema_table_args(
        Index('idx_metrics_app', 'app_id'),
        Index('idx_metrics_trending', 'trending_score'),
        Index('idx_metrics_featured', 'featured_rank'),
        Index('idx_metrics_rating', 'avg_rating'),
    )

    metric_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False, unique=True)

    # Subscriber metrics
    total_subscribers = Column(Integer, default=0)
    active_subscribers = Column(Integer, default=0)
    subscribers_last_7_days = Column(Integer, default=0)
    subscribers_last_30_days = Column(Integer, default=0)

    # Review metrics
    total_reviews = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    rating_distribution = Column(JSONB)

    # Execution metrics
    total_executions = Column(Integer, default=0)
    executions_last_7_days = Column(Integer, default=0)
    executions_last_30_days = Column(Integer, default=0)
    avg_execution_time = Column(Float)
    success_rate = Column(Float)

    # Revenue metrics
    total_revenue = Column(Float, default=0.0)
    revenue_last_30_days = Column(Float, default=0.0)

    # Trending score
    trending_score = Column(Float, default=0.0)

    # Featured status
    featured_rank = Column(Integer)
    featured_until = Column(DateTime(timezone=True))

    # Timestamps
    last_calculated = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MarketplaceSettings(Base):
    """Global marketplace settings"""
    __tablename__ = "marketplace_settings"
    __table_args__ = schema_table_args(
        Index('idx_setting_key', 'key'),
    )

    setting_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, nullable=False, unique=True)
    value = Column(JSONB)
    description = Column(Text)
    updated_by = Column(String, ForeignKey(fk('users.user_id')))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MicroSaasSubscriber(Base):
    """Subscriptions for micro SaaS apps"""
    __tablename__ = "micro_saas_subscribers"
    __table_args__ = schema_table_args(
        Index('idx_micro_saas_sub_app', 'frontend_app_id'),
        Index('idx_micro_saas_sub_tenant', 'tenant_id'),
        Index('idx_micro_saas_sub_user', 'user_id'),
        Index('idx_micro_saas_sub_status', 'subscription_status'),
        Index('idx_micro_saas_sub_unique', 'frontend_app_id', 'tenant_id', unique=True),
    )

    subscriber_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    frontend_app_id = Column(String, ForeignKey(fk('frontend_flow_applications.frontend_app_id')), nullable=False)
    user_id = Column(String, ForeignKey(fk('users.user_id')))
    tenant_id = Column(String, ForeignKey(fk('tenants.tenant_id')))

    subscription_status = Column(String(20), default='active')
    billing_cycle_start = Column(DateTime(timezone=True))
    billing_cycle_end = Column(DateTime(timezone=True))
    last_payment_date = Column(DateTime(timezone=True))
    last_payment_amount = Column(Float)
    total_paid = Column(Float, default=0)
    execution_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

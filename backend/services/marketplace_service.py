"""
Marketplace Service - Business logic for IOFlow marketplace
Handles app discovery, subscriptions, reviews, approvals, and analytics
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
import json


def _parse_json_field(value: Any) -> Any:
    """
    Parse a JSON field that might be a string or already a dict/list.
    SQLite JSON fields return dicts, PostgreSQL JSONB may return strings.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    return value

# Import unified models (work with both PostgreSQL and SQLite)
from db.application_models import (
    FrontendFlowApplication,
    ApplicationSubscription,
    PublishedApplication,
    Application
)
from db.marketplace_models import (
    AppCategory,
    AppTag,
    AppCategoryMapping,
    AppTagMapping,
    AppReview,
    ReviewHelpful,
    CreatorTier,
    MarketplaceApproval,
    AppMetrics,
    MicroSaasSubscriber
)
from db.models import User
from schemas.marketplace_schemas import (
    MarketplaceFilters,
    AppSortBy,
    ReviewCreate,
    ReviewUpdate,
    CreatorTierLevel
)


class MarketplaceService:
    """Service for marketplace operations"""

    def __init__(self, db: Session):
        self.db = db

    # ============================================================================
    # APP DISCOVERY & BROWSING
    # ============================================================================

    def get_marketplace_apps(
        self,
        filters: MarketplaceFilters,
        current_user_id: Optional[str] = None,
        current_user_tenant_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated list of marketplace apps with filters

        Shows:
        - Public apps (visibility='public' and approved) to everyone
        - Apps user has access to (if logged in) based on access_type and access_config

        Returns (apps, total_count)
        """

        # Base query - active apps only
        query = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.is_active == True
        )

        # Build visibility filter
        visibility_conditions = []

        # 1. Public apps (approved for marketplace)
        visibility_conditions.append(
            and_(
                FrontendFlowApplication.visibility == 'public',
                FrontendFlowApplication.marketplace_status.in_(['approved', 'auto_approved'])
            )
        )

        # 2. If user is logged in, also include apps they have access to
        if current_user_id and current_user_tenant_id:
            # Apps in user's organization
            visibility_conditions.append(
                and_(
                    FrontendFlowApplication.access_type == 'organization',
                    FrontendFlowApplication.tenant_id == current_user_tenant_id
                )
            )

            # Apps where user is specifically granted access
            # Note: access_config is JSON with allowed_users array
            # This is a simplified check - in production you'd parse the JSON properly
            visibility_conditions.append(
                and_(
                    FrontendFlowApplication.access_type == 'specific_users',
                    FrontendFlowApplication.access_config.like(f'%{current_user_id}%')
                )
            )

            # Apps where user's tenant is in allowed tenants
            visibility_conditions.append(
                and_(
                    FrontendFlowApplication.access_type == 'tenant_list',
                    FrontendFlowApplication.access_config.like(f'%{current_user_tenant_id}%')
                )
            )

        # Apply visibility filter
        query = query.filter(or_(*visibility_conditions))

        # Apply search filter
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    FrontendFlowApplication.frontend_app_name.ilike(search_term),
                    FrontendFlowApplication.description.ilike(search_term)
                )
            )

        # Apply category filter
        if filters.category_id or filters.category_slug:
            category_filter = filters.category_id if filters.category_id else filters.category_slug
            # Join with category mapping
            query = query.join(
                AppCategoryMapping,
                AppCategoryMapping.app_id == FrontendFlowApplication.frontend_app_id
            )
            if filters.category_id:
                query = query.filter(AppCategoryMapping.category_id == category_filter)
            else:
                query = query.join(AppCategory).filter(AppCategory.slug == category_filter)

        # Apply tag filters
        if filters.tags and len(filters.tags) > 0:
            query = query.join(
                AppTagMapping,
                AppTagMapping.app_id == FrontendFlowApplication.frontend_app_id
            ).join(
                AppTag,
                AppTag.tag_id == AppTagMapping.tag_id
            ).filter(AppTag.slug.in_(filters.tags))

        # Apply rating filter
        if filters.min_rating:
            query = query.filter(FrontendFlowApplication.avg_rating >= filters.min_rating)

        # Apply pricing filters
        if filters.billing_preference:
            query = query.filter(FrontendFlowApplication.billing_preference == filters.billing_preference)

        # Apply max price filter (for per_user_per_month or per_execution)
        if filters.max_price:
            # This requires checking pricing_config JSON
            # Skip for now, can be implemented if needed
            pass

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        if filters.sort_by == AppSortBy.RECENT:
            query = query.order_by(desc(FrontendFlowApplication.created_at))
        elif filters.sort_by == AppSortBy.POPULAR:
            query = query.order_by(desc(FrontendFlowApplication.total_subscribers))
        elif filters.sort_by == AppSortBy.TRENDING:
            query = query.order_by(desc(FrontendFlowApplication.trending_score))
        elif filters.sort_by == AppSortBy.RATING:
            query = query.order_by(desc(FrontendFlowApplication.avg_rating))
        elif filters.sort_by == AppSortBy.PRICE_LOW:
            # Complex sorting by price from JSON - simplified for now
            query = query.order_by(asc(FrontendFlowApplication.billing_preference))
        elif filters.sort_by == AppSortBy.PRICE_HIGH:
            query = query.order_by(desc(FrontendFlowApplication.billing_preference))

        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        # Execute query
        apps = query.all()

        # Enrich apps with creator and category/tag info
        enriched_apps = []
        for app in apps:
            app_dict = self._enrich_app_listing(app, current_user_id)
            enriched_apps.append(app_dict)

        return enriched_apps, total_count

    def get_app_detail(self, slug: str, current_user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get full app details by slug"""

        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.public_url_slug == slug
        ).first()

        if not app:
            return None

        # Build detailed response
        app_dict = self._enrich_app_detail(app, current_user_id)
        return app_dict

    def _enrich_app_listing(self, app: FrontendFlowApplication, current_user_id: Optional[str] = None) -> Dict[str, Any]:
        """Enrich app with creator and category/tag info for listing"""

        # Get creator info
        creator = self.db.query(User).filter(User.user_id == app.created_by).first()

        # Get categories
        categories = self.db.query(AppCategory).join(
            AppCategoryMapping,
            AppCategoryMapping.category_id == AppCategory.category_id
        ).filter(AppCategoryMapping.app_id == app.frontend_app_id).all()

        # Get tags
        tags = self.db.query(AppTag).join(
            AppTagMapping,
            AppTagMapping.tag_id == AppTag.tag_id
        ).filter(AppTagMapping.app_id == app.frontend_app_id).all()

        # Parse JSON fields
        pricing_config = _parse_json_field(app.pricing_config)
        categories_list = [cat.slug for cat in categories]
        tags_list = [tag.slug for tag in tags]

        return {
            "frontend_app_id": app.frontend_app_id,
            "public_url_slug": app.public_url_slug,
            "frontend_app_name": app.frontend_app_name,
            "description": app.description,
            "icon_url": app.icon_url,
            "creator_name": creator.user_name if creator else "Unknown",
            "creator_id": app.created_by,
            "billing_preference": app.billing_preference,
            "pricing_config": pricing_config,
            "avg_rating": app.avg_rating or 0.0,
            "total_reviews": app.total_reviews or 0,
            "total_subscribers": app.total_subscribers or 0,
            "trending_score": app.trending_score or 0.0,
            "categories": categories_list,
            "tags": tags_list,
            "featured_rank": app.featured_rank,
            "created_at": app.created_at,
            "updated_at": app.updated_at
        }

    def _enrich_app_detail(self, app: FrontendFlowApplication, current_user_id: Optional[str] = None) -> Dict[str, Any]:
        """Enrich app with full details including reviews"""

        # Get basic listing data
        app_dict = self._enrich_app_listing(app, current_user_id)

        # Add detailed fields
        screenshots = _parse_json_field(app.screenshots) or []
        usage_limits = _parse_json_field(app.usage_limits)

        # Get recent reviews (top 5)
        reviews = self.get_app_reviews(app.frontend_app_id, current_user_id, page=1, page_size=5)

        # Get review summary
        review_summary = self.get_review_summary(app.frontend_app_id)

        # Get creator tier
        creator_tier = self.db.query(CreatorTier).filter(
            CreatorTier.user_id == app.created_by
        ).first()

        app_dict.update({
            "screenshots": screenshots,
            "demo_url": app.demo_url,
            "usage_limits": usage_limits,
            "access_type": app.access_type,
            "visibility": app.visibility,
            "active_subscribers": app.active_subscribers or 0,
            "usage_count": app.usage_count or 0,
            "review_summary": review_summary,
            "recent_reviews": reviews,
            "creator_tier": creator_tier.tier_level if creator_tier else "new",
            "creator_total_apps": creator_tier.total_apps_created if creator_tier else 0
        })

        return app_dict

    # ============================================================================
    # CATEGORIES & TAGS
    # ============================================================================

    def get_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all categories with app counts"""

        query = self.db.query(AppCategory)
        if active_only:
            query = query.filter(AppCategory.is_active == True)

        categories = query.order_by(AppCategory.display_order, AppCategory.name).all()

        result = []
        for cat in categories:
            # Count apps in this category
            app_count = self.db.query(AppCategoryMapping).filter(
                AppCategoryMapping.category_id == cat.category_id
            ).count()

            result.append({
                "category_id": cat.category_id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "icon": cat.icon,
                "display_order": cat.display_order,
                "is_active": cat.is_active,
                "app_count": app_count,
                "created_at": cat.created_at
            })

        return result

    def get_tags(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all tags"""

        query = self.db.query(AppTag)
        if active_only:
            query = query.filter(AppTag.is_active == True)

        tags = query.order_by(desc(AppTag.usage_count), AppTag.name).all()

        return [{
            "tag_id": tag.tag_id,
            "name": tag.name,
            "slug": tag.slug,
            "color": tag.color,
            "is_active": tag.is_active,
            "usage_count": tag.usage_count,
            "created_at": tag.created_at
        } for tag in tags]

    # ============================================================================
    # REVIEWS & RATINGS
    # ============================================================================

    def get_app_reviews(
        self,
        app_id: str,
        current_user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "recent"
    ) -> List[Dict[str, Any]]:
        """Get reviews for an app"""

        query = self.db.query(AppReview).filter(
            and_(
                AppReview.app_id == app_id,
                AppReview.is_visible == True
            )
        )

        # Apply sorting
        if sort_by == "recent":
            query = query.order_by(desc(AppReview.created_at))
        elif sort_by == "helpful":
            query = query.order_by(desc(AppReview.helpful_count))
        elif sort_by == "rating_high":
            query = query.order_by(desc(AppReview.rating), desc(AppReview.created_at))
        elif sort_by == "rating_low":
            query = query.order_by(asc(AppReview.rating), desc(AppReview.created_at))

        # Pagination
        offset = (page - 1) * page_size
        reviews = query.offset(offset).limit(page_size).all()

        # Enrich with user info
        result = []
        for review in reviews:
            user = self.db.query(User).filter(User.user_id == review.user_id).first()

            # Check if current user found this helpful
            user_found_helpful = False
            if current_user_id:
                helpful = self.db.query(ReviewHelpful).filter(
                    and_(
                        ReviewHelpful.review_id == review.review_id,
                        ReviewHelpful.user_id == current_user_id
                    )
                ).first()
                user_found_helpful = helpful is not None

            result.append({
                "review_id": review.review_id,
                "app_id": review.app_id,
                "user_id": review.user_id,
                "user_name": user.user_name if user else "Anonymous",
                "user_email": user.email if user else None,
                "rating": review.rating,
                "title": review.title,
                "review_text": review.review_text,
                "helpful_count": review.helpful_count,
                "verified_subscriber": review.verified_subscriber,
                "is_edited": review.is_edited,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
                "user_found_helpful": user_found_helpful
            })

        return result

    def get_review_summary(self, app_id: str) -> Dict[str, Any]:
        """Get review summary statistics"""

        reviews = self.db.query(AppReview).filter(
            and_(
                AppReview.app_id == app_id,
                AppReview.is_visible == True
            )
        ).all()

        total_reviews = len(reviews)
        if total_reviews == 0:
            return {
                "total_reviews": 0,
                "avg_rating": 0.0,
                "rating_distribution": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
            }

        # Calculate average rating
        total_rating = sum(r.rating for r in reviews)
        avg_rating = round(total_rating / total_reviews, 2)

        # Calculate distribution
        distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        for review in reviews:
            distribution[str(review.rating)] += 1

        return {
            "total_reviews": total_reviews,
            "avg_rating": avg_rating,
            "rating_distribution": distribution
        }

    def create_review(
        self,
        app_id: str,
        user_id: str,
        tenant_id: str,
        review_data: ReviewCreate
    ) -> Dict[str, Any]:
        """Create a new review"""

        # Check if user already reviewed this app
        existing = self.db.query(AppReview).filter(
            and_(
                AppReview.app_id == app_id,
                AppReview.user_id == user_id
            )
        ).first()

        if existing:
            raise ValueError("You have already reviewed this app. Please update your existing review.")

        # Check if user is subscribed
        subscription = self.db.query(ApplicationSubscription).join(
            FrontendFlowApplication,
            FrontendFlowApplication.published_app_id == ApplicationSubscription.app_id
        ).filter(
            and_(
                FrontendFlowApplication.frontend_app_id == app_id,
                ApplicationSubscription.tenant_id == tenant_id,
                ApplicationSubscription.status == 'active'
            )
        ).first()

        verified_subscriber = subscription is not None

        # Create review
        review = AppReview(
            review_id=str(uuid.uuid4()),
            app_id=app_id,
            user_id=user_id,
            tenant_id=tenant_id,
            rating=review_data.rating,
            title=review_data.title,
            review_text=review_data.review_text,
            verified_subscriber=verified_subscriber
        )

        self.db.add(review)

        # Update app metrics
        self._update_app_review_metrics(app_id)

        self.db.commit()
        self.db.refresh(review)

        return self._review_to_dict(review)

    def update_review(
        self,
        review_id: str,
        user_id: str,
        review_data: ReviewUpdate
    ) -> Dict[str, Any]:
        """Update an existing review"""

        review = self.db.query(AppReview).filter(
            and_(
                AppReview.review_id == review_id,
                AppReview.user_id == user_id
            )
        ).first()

        if not review:
            raise ValueError("Review not found or you don't have permission to update it")

        # Update fields
        if review_data.rating is not None:
            review.rating = review_data.rating
        if review_data.title is not None:
            review.title = review_data.title
        if review_data.review_text is not None:
            review.review_text = review_data.review_text

        review.is_edited = True
        review.updated_at = datetime.utcnow()

        # Update app metrics
        self._update_app_review_metrics(review.app_id)

        self.db.commit()
        self.db.refresh(review)

        return self._review_to_dict(review)

    def mark_review_helpful(self, review_id: str, user_id: str) -> bool:
        """Mark a review as helpful"""

        # Check if already marked
        existing = self.db.query(ReviewHelpful).filter(
            and_(
                ReviewHelpful.review_id == review_id,
                ReviewHelpful.user_id == user_id
            )
        ).first()

        if existing:
            # Remove helpful mark
            self.db.delete(existing)
            # Decrement count
            review = self.db.query(AppReview).filter(AppReview.review_id == review_id).first()
            if review:
                review.helpful_count = max(0, review.helpful_count - 1)
            self.db.commit()
            return False
        else:
            # Add helpful mark
            helpful = ReviewHelpful(
                id=str(uuid.uuid4()),
                review_id=review_id,
                user_id=user_id
            )
            self.db.add(helpful)
            # Increment count
            review = self.db.query(AppReview).filter(AppReview.review_id == review_id).first()
            if review:
                review.helpful_count += 1
            self.db.commit()
            return True

    def _review_to_dict(self, review: AppReview) -> Dict[str, Any]:
        """Convert review to dict"""
        user = self.db.query(User).filter(User.user_id == review.user_id).first()
        return {
            "review_id": review.review_id,
            "app_id": review.app_id,
            "user_id": review.user_id,
            "user_name": user.user_name if user else "Anonymous",
            "rating": review.rating,
            "title": review.title,
            "review_text": review.review_text,
            "helpful_count": review.helpful_count,
            "verified_subscriber": review.verified_subscriber,
            "is_edited": review.is_edited,
            "created_at": review.created_at,
            "updated_at": review.updated_at
        }

    def _update_app_review_metrics(self, app_id: str):
        """Update cached review metrics on app"""
        summary = self.get_review_summary(app_id)

        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if app:
            app.avg_rating = summary["avg_rating"]
            app.total_reviews = summary["total_reviews"]

    # ============================================================================
    # SUBSCRIPTIONS
    # ============================================================================

    def check_subscription_requirements(
        self,
        app_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Check if user has all required applications for this marketplace app"""

        # Get the app
        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            raise ValueError("App not found")

        # Get the published application to find dependencies
        if not app.published_app_id:
            # App without published application - no dependencies
            return {
                "app_id": app_id,
                "app_name": app.frontend_app_name,
                "required_applications": [],
                "missing_applications": [],
                "ready_to_subscribe": True
            }

        # Get flow dependencies from published app
        published_app = self.db.query(PublishedApplication).filter(
            PublishedApplication.published_app_id == app.published_app_id
        ).first()

        if not published_app or not published_app.flow_analysis:
            return {
                "app_id": app_id,
                "app_name": app.frontend_app_name,
                "required_applications": [],
                "missing_applications": [],
                "ready_to_subscribe": True
            }

        # Parse flow analysis to find required applications
        flow_analysis = _parse_json_field(published_app.flow_analysis) or {}
        required_apps = flow_analysis.get("required_applications", [])

        # Check which apps are installed and connected for this tenant
        required_app_status = []
        missing_apps = []

        for req_app in required_apps:
            app_key = req_app.get("app_key") or req_app.get("application_key")

            # Find the application. A published flow can only rely on a
            # GLOBAL connector — never another tenant's own seed application
            # that happens to use the same key.
            from services.application_lookup import find_by_seed_key
            required_application = find_by_seed_key(self.db, app_key)

            if not required_application:
                missing_apps.append(app_key)
                required_app_status.append({
                    "app_key": app_key,
                    "app_name": req_app.get("app_name", app_key),
                    "status": "not_installed",
                    "subscribed": False,
                    "connected": False
                })
                continue

            # Check subscription
            subscription = self.db.query(ApplicationSubscription).filter(
                and_(
                    ApplicationSubscription.app_id == required_application.app_id,
                    ApplicationSubscription.tenant_id == tenant_id,
                    ApplicationSubscription.status == 'active'
                )
            ).first()

            if not subscription:
                missing_apps.append(app_key)
                required_app_status.append({
                    "app_key": app_key,
                    "app_id": required_application.app_id,
                    "app_name": required_application.app_name,
                    "status": "not_subscribed",
                    "subscribed": False,
                    "connected": False
                })
                continue

            # Check if connected (has credentials)
            has_credentials = subscription.auth_credentials is not None
            if not has_credentials:
                missing_apps.append(app_key)

            required_app_status.append({
                "app_key": app_key,
                "app_id": required_application.app_id,
                "app_name": required_application.app_name,
                "status": "ready" if has_credentials else "not_connected",
                "subscribed": True,
                "connected": has_credentials
            })

        return {
            "app_id": app_id,
            "app_name": app.frontend_app_name,
            "required_applications": required_app_status,
            "missing_applications": missing_apps,
            "ready_to_subscribe": len(missing_apps) == 0
        }

    def subscribe_to_app(
        self,
        app_id: str,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Subscribe a user/tenant to a marketplace app

        Returns subscription details including execution URL
        """
        import uuid
        from datetime import datetime

        # Get the app
        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            raise ValueError("App not found")

        subscription_id = None

        # Check if already subscribed
        if app.published_app_id:
            # App has published_app_id - use ApplicationSubscription
            published_app = self.db.query(PublishedApplication).filter(
                PublishedApplication.published_app_id == app.published_app_id
            ).first()

            if published_app:
                existing_sub = self.db.query(ApplicationSubscription).filter(
                    and_(
                        ApplicationSubscription.app_id == published_app.app_id,
                        ApplicationSubscription.tenant_id == tenant_id
                    )
                ).first()

                if existing_sub:
                    # Already subscribed, return existing subscription
                    return {
                        "subscription_id": existing_sub.subscription_id,
                        "app_id": app_id,
                        "app_name": app.frontend_app_name,
                        "public_url_slug": app.public_url_slug,
                        "already_subscribed": True,
                        "subscribed_at": existing_sub.subscribed_at
                    }

                # Create new subscription for the published app
                subscription_id = str(uuid.uuid4())
                new_sub = ApplicationSubscription(
                    subscription_id=subscription_id,
                    tenant_id=tenant_id,
                    app_id=published_app.app_id,
                    auth_credentials=None,  # Frontend apps don't need auth credentials
                    subscription_config=None,
                    status='active',
                    subscribed_at=datetime.utcnow()
                )

                self.db.add(new_sub)
        else:
            # App doesn't have published_app_id - use MicroSaasSubscriber
            existing_sub = self.db.query(MicroSaasSubscriber).filter(
                and_(
                    MicroSaasSubscriber.frontend_app_id == app_id,
                    MicroSaasSubscriber.tenant_id == tenant_id
                )
            ).first()

            if existing_sub:
                # Already subscribed, return existing subscription
                return {
                    "subscription_id": existing_sub.subscriber_id,
                    "app_id": app_id,
                    "app_name": app.frontend_app_name,
                    "public_url_slug": app.public_url_slug,
                    "already_subscribed": True,
                    "subscribed_at": existing_sub.created_at
                }

            # Create new micro SaaS subscription
            subscription_id = str(uuid.uuid4())
            new_sub = MicroSaasSubscriber(
                subscriber_id=subscription_id,
                frontend_app_id=app_id,
                user_id=user_id,
                tenant_id=tenant_id,
                subscription_status='active',
                created_at=datetime.utcnow()
            )

            self.db.add(new_sub)

        # Update subscriber count
        app.total_subscribers = (app.total_subscribers or 0) + 1
        app.active_subscribers = (app.active_subscribers or 0) + 1

        self.db.commit()

        return {
            "subscription_id": subscription_id,
            "app_id": app_id,
            "app_name": app.frontend_app_name,
            "public_url_slug": app.public_url_slug,
            "already_subscribed": False,
            "subscribed_at": datetime.utcnow().isoformat()
        }

    def get_user_subscriptions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all marketplace app subscriptions for a user/tenant"""

        result = []

        # Query subscriptions from ApplicationSubscription (for apps with published_app_id)
        app_sub_results = self.db.query(
            ApplicationSubscription,
            FrontendFlowApplication
        ).join(
            PublishedApplication,
            PublishedApplication.app_id == ApplicationSubscription.app_id
        ).join(
            FrontendFlowApplication,
            FrontendFlowApplication.published_app_id == PublishedApplication.published_app_id
        ).filter(
            and_(
                ApplicationSubscription.tenant_id == tenant_id,
                ApplicationSubscription.status == 'active',
                FrontendFlowApplication.is_active == True,
                FrontendFlowApplication.visibility == 'public'
            )
        ).all()

        for sub, frontend_app in app_sub_results:
            pricing_config = _parse_json_field(frontend_app.pricing_config)
            usage_limits = _parse_json_field(frontend_app.usage_limits)

            result.append({
                "subscription_id": sub.subscription_id,
                "app_id": frontend_app.frontend_app_id,
                "app_name": frontend_app.frontend_app_name,
                "description": frontend_app.description,
                "public_url_slug": frontend_app.public_url_slug,
                "icon_url": frontend_app.icon_url,
                "avg_rating": frontend_app.avg_rating or 0,
                "total_reviews": frontend_app.total_reviews or 0,
                "subscription_status": sub.status,
                "subscribed_at": sub.subscribed_at,
                "expires_at": sub.expires_at,
                "usage_count": frontend_app.usage_count or 0,
                "usage_limits": usage_limits,
                "billing_preference": frontend_app.billing_preference,
                "pricing_config": pricing_config
            })

        # Query subscriptions from MicroSaasSubscriber (for micro SaaS apps without published_app_id)
        micro_saas_results = self.db.query(
            MicroSaasSubscriber,
            FrontendFlowApplication
        ).join(
            FrontendFlowApplication,
            FrontendFlowApplication.frontend_app_id == MicroSaasSubscriber.frontend_app_id
        ).filter(
            and_(
                MicroSaasSubscriber.tenant_id == tenant_id,
                MicroSaasSubscriber.subscription_status == 'active',
                FrontendFlowApplication.is_active == True,
                FrontendFlowApplication.marketplace_enabled == True
            )
        ).all()

        for sub, frontend_app in micro_saas_results:
            pricing_config = _parse_json_field(frontend_app.pricing_config)
            usage_limits = _parse_json_field(frontend_app.usage_limits)

            result.append({
                "subscription_id": sub.subscriber_id,
                "app_id": frontend_app.frontend_app_id,
                "app_name": frontend_app.frontend_app_name,
                "description": frontend_app.description,
                "public_url_slug": frontend_app.public_url_slug,
                "icon_url": frontend_app.icon_url,
                "avg_rating": frontend_app.avg_rating or 0,
                "total_reviews": frontend_app.total_reviews or 0,
                "subscription_status": sub.subscription_status,
                "subscribed_at": sub.created_at,
                "expires_at": sub.billing_cycle_end,
                "usage_count": sub.execution_count or 0,
                "usage_limits": usage_limits,
                "billing_preference": frontend_app.billing_preference,
                "pricing_config": pricing_config
            })

        return result

    # ============================================================================
    # CREATOR TIERS & APPROVAL
    # ============================================================================

    def get_or_create_creator_tier(self, user_id: str) -> CreatorTier:
        """Get or create creator tier for user"""

        tier = self.db.query(CreatorTier).filter(CreatorTier.user_id == user_id).first()

        if not tier:
            tier = CreatorTier(
                tier_id=str(uuid.uuid4()),
                user_id=user_id,
                tier_level='new',
                auto_approve=False
            )
            self.db.add(tier)
            self.db.commit()
            self.db.refresh(tier)

        return tier

    def submit_for_approval(
        self,
        app_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Submit marketplace app for approval"""

        # Get or create creator tier
        tier = self.get_or_create_creator_tier(user_id)

        # Get the app
        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            raise ValueError("App not found")

        if app.created_by != user_id:
            raise ValueError("You don't have permission to submit this app")

        # Check if auto-approve
        if tier.auto_approve:
            app.marketplace_status = 'auto_approved'
            app.approved_at = datetime.utcnow()

            approval = MarketplaceApproval(
                approval_id=str(uuid.uuid4()),
                app_id=app_id,
                status='auto_approved',
                submitted_by=user_id,
                reviewed_by=None,
                reviewed_at=datetime.utcnow(),
                review_notes="Auto-approved based on creator tier"
            )
        else:
            app.marketplace_status = 'pending'

            approval = MarketplaceApproval(
                approval_id=str(uuid.uuid4()),
                app_id=app_id,
                status='pending',
                submitted_by=user_id
            )

        self.db.add(approval)
        self.db.commit()
        self.db.refresh(app)

        return {
            "app_id": app_id,
            "marketplace_status": app.marketplace_status,
            "auto_approved": tier.auto_approve
        }

    def approve_app(
        self,
        app_id: str,
        admin_user_id: str,
        review_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Admin approve marketplace app"""

        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            raise ValueError("App not found")

        app.marketplace_status = 'approved'
        app.approved_by = admin_user_id
        app.approved_at = datetime.utcnow()

        # Update approval record
        approval = self.db.query(MarketplaceApproval).filter(
            and_(
                MarketplaceApproval.app_id == app_id,
                MarketplaceApproval.status == 'pending'
            )
        ).first()

        if approval:
            approval.status = 'approved'
            approval.reviewed_by = admin_user_id
            approval.reviewed_at = datetime.utcnow()
            approval.review_notes = review_notes

        self.db.commit()

        return {"app_id": app_id, "status": "approved"}

    def reject_app(
        self,
        app_id: str,
        admin_user_id: str,
        rejection_reason: str
    ) -> Dict[str, Any]:
        """Admin reject marketplace app"""

        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            raise ValueError("App not found")

        app.marketplace_status = 'rejected'
        app.approval_notes = rejection_reason

        # Update approval record
        approval = self.db.query(MarketplaceApproval).filter(
            and_(
                MarketplaceApproval.app_id == app_id,
                MarketplaceApproval.status == 'pending'
            )
        ).first()

        if approval:
            approval.status = 'rejected'
            approval.reviewed_by = admin_user_id
            approval.reviewed_at = datetime.utcnow()
            approval.rejection_reason = rejection_reason

        self.db.commit()

        return {"app_id": app_id, "status": "rejected"}

    # ============================================================================
    # FEATURED & TRENDING
    # ============================================================================

    def get_featured_apps(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get featured marketplace apps (public apps only)"""

        apps = self.db.query(FrontendFlowApplication).filter(
            and_(
                FrontendFlowApplication.visibility == 'public',
                FrontendFlowApplication.marketplace_status.in_(['approved', 'auto_approved']),
                FrontendFlowApplication.featured_rank.isnot(None),
                FrontendFlowApplication.is_active == True
            )
        ).order_by(asc(FrontendFlowApplication.featured_rank)).limit(limit).all()

        return [self._enrich_app_listing(app) for app in apps]

    def get_trending_apps(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending marketplace apps (public apps only)"""

        apps = self.db.query(FrontendFlowApplication).filter(
            and_(
                FrontendFlowApplication.visibility == 'public',
                FrontendFlowApplication.marketplace_status.in_(['approved', 'auto_approved']),
                FrontendFlowApplication.is_active == True
            )
        ).order_by(desc(FrontendFlowApplication.trending_score)).limit(limit).all()

        return [self._enrich_app_listing(app) for app in apps]

    def calculate_trending_score(self, app_id: str) -> float:
        """Calculate trending score for an app"""

        # Get recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        app = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == app_id
        ).first()

        if not app:
            return 0.0

        # Factors:
        # 1. Recent subscribers (weight: 3)
        # 2. Recent reviews (weight: 2)
        # 3. Average rating (weight: 1)
        # 4. Total subscribers (weight: 0.5)

        # Simplified calculation (would need access to time-based data)
        score = 0.0
        score += (app.total_subscribers or 0) * 0.5
        score += (app.total_reviews or 0) * 2
        score += (app.avg_rating or 0) * 10

        return round(score, 2)

    def update_trending_scores(self):
        """Update trending scores for all marketplace apps (background job)"""

        apps = self.db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.marketplace_enabled == True
        ).all()

        for app in apps:
            score = self.calculate_trending_score(app.frontend_app_id)
            app.trending_score = score

        self.db.commit()

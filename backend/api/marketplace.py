"""
Marketplace API Endpoints
Handles public browsing, subscriptions, reviews, and admin approval workflows
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import List, Optional
import logging

from db.database import get_db
from api.auth import get_current_user
from core.auth_utils import get_current_user_optional
from db.models import User, UserRole
from services.marketplace_service import MarketplaceService
from schemas.marketplace_schemas import (
    # Responses
    MarketplaceAppList,
    MarketplaceAppListItem,
    MarketplaceAppDetail,
    CategoryResponse,
    TagResponse,
    ReviewResponse,
    ReviewSummary,
    SubscriptionRequirements,
    UserSubscriptionInfo,
    ApprovalResponse,
    MessageResponse,
    # Requests
    MarketplaceFilters,
    AppSortBy,
    ReviewCreate,
    ReviewUpdate,
    ApprovalReview,
    MarketplaceAppUpdate
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


# ============================================================================
# PUBLIC ENDPOINTS (No authentication required)
# ============================================================================

@router.get("/apps", response_model=MarketplaceAppList)
def browse_marketplace_apps(
    search: Optional[str] = Query(None, description="Search term"),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    category_slug: Optional[str] = Query(None, description="Filter by category slug"),
    tags: Optional[List[str]] = Query([], description="Filter by tag slugs"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    billing_preference: Optional[str] = Query(None, description="Billing preference: free, per_user_per_month, per_execution"),
    sort_by: AppSortBy = Query(AppSortBy.POPULAR, description="Sort by field"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Browse marketplace apps

    Shows:
    - Public apps (approved) to everyone
    - Apps user has access to (if logged in)

    Returns paginated list with filters and search
    """

    try:
        # Build filters
        filters = MarketplaceFilters(
            search=search,
            category_id=category_id,
            category_slug=category_slug,
            tags=tags if tags else [],
            min_rating=min_rating,
            max_price=max_price,
            billing_preference=billing_preference,
            sort_by=sort_by,
            page=page,
            page_size=page_size
        )

        # Get user info if logged in
        current_user_id = current_user.user_id if current_user else None
        current_user_tenant_id = current_user.tenant_id if current_user else None

        service = MarketplaceService(db)
        apps, total = service.get_marketplace_apps(
            filters,
            current_user_id=current_user_id,
            current_user_tenant_id=current_user_tenant_id
        )

        total_pages = (total + page_size - 1) // page_size

        return {
            "apps": apps,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    except Exception as e:
        logger.error(f"Error browsing marketplace apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to browse marketplace apps: {str(e)}"
        )


@router.get("/apps/{slug}", response_model=MarketplaceAppDetail)
def get_app_details(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Get detailed app information by slug

    Shows public apps to everyone, and private apps to users with access.
    """

    try:
        service = MarketplaceService(db)
        user_id = current_user.user_id if current_user else None

        app_detail = service.get_app_detail(slug, user_id)

        if not app_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="App not found"
            )

        return app_detail

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting app details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get app details: {str(e)}"
        )


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    active_only: bool = Query(True, description="Return only active categories"),
    db: Session = Depends(get_db)
):
    """Get all marketplace categories (public access)"""

    try:
        service = MarketplaceService(db)
        categories = service.get_categories(active_only)
        return categories

    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get categories: {str(e)}"
        )


@router.get("/tags", response_model=List[TagResponse])
def get_tags(
    active_only: bool = Query(True, description="Return only active tags"),
    db: Session = Depends(get_db)
):
    """Get all marketplace tags (public access)"""

    try:
        service = MarketplaceService(db)
        tags = service.get_tags(active_only)
        return tags

    except Exception as e:
        logger.error(f"Error getting tags: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tags: {str(e)}"
        )


@router.get("/featured", response_model=List[MarketplaceAppListItem])
def get_featured_apps(
    limit: int = Query(10, ge=1, le=50, description="Number of featured apps"),
    db: Session = Depends(get_db)
):
    """Get featured marketplace apps (public access)"""

    try:
        service = MarketplaceService(db)
        apps = service.get_featured_apps(limit)
        return apps

    except Exception as e:
        logger.error(f"Error getting featured apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get featured apps: {str(e)}"
        )


@router.get("/trending", response_model=List[MarketplaceAppListItem])
def get_trending_apps(
    limit: int = Query(10, ge=1, le=50, description="Number of trending apps"),
    db: Session = Depends(get_db)
):
    """Get trending marketplace apps (public access)"""

    try:
        service = MarketplaceService(db)
        apps = service.get_trending_apps(limit)
        return apps

    except Exception as e:
        logger.error(f"Error getting trending apps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trending apps: {str(e)}"
        )


@router.get("/apps/{app_id}/reviews", response_model=List[ReviewResponse])
def get_app_reviews(
    app_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort_by: str = Query("recent", description="Sort by: recent, helpful, rating_high, rating_low"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get reviews for an app (public access)"""

    try:
        service = MarketplaceService(db)
        user_id = current_user.user_id if current_user else None

        reviews = service.get_app_reviews(
            app_id=app_id,
            current_user_id=user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by
        )

        return reviews

    except Exception as e:
        logger.error(f"Error getting app reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get app reviews: {str(e)}"
        )


# ============================================================================
# PROTECTED ENDPOINTS (Authentication required)
# ============================================================================

@router.get("/my-subscriptions", response_model=List[UserSubscriptionInfo])
def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's marketplace app subscriptions"""

    try:
        service = MarketplaceService(db)
        subscriptions = service.get_user_subscriptions(current_user.tenant_id)
        return subscriptions

    except Exception as e:
        logger.error(f"Error getting user subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscriptions: {str(e)}"
        )


@router.get("/apps/{app_id}/subscription-requirements", response_model=SubscriptionRequirements)
def check_subscription_requirements(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has all required applications installed and connected
    Used before subscribing to an app
    """

    try:
        service = MarketplaceService(db)
        requirements = service.check_subscription_requirements(
            app_id=app_id,
            tenant_id=current_user.tenant_id
        )
        return requirements

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error checking subscription requirements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check requirements: {str(e)}"
        )


@router.post("/apps/{app_id}/subscribe", response_model=MessageResponse)
def subscribe_to_marketplace_app(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Subscribe to a marketplace app

    Creates subscription and returns execution URL
    """

    try:
        service = MarketplaceService(db)
        result = service.subscribe_to_app(
            app_id=app_id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id
        )

        return {
            "success": True,
            "message": f"Successfully subscribed to {result['app_name']}",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error subscribing to app: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@router.post("/reviews", response_model=ReviewResponse)
def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a review for a marketplace app"""

    try:
        service = MarketplaceService(db)

        review = service.create_review(
            app_id=review_data.app_id,
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
            review_data=review_data
        )

        return review

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review: {str(e)}"
        )


@router.put("/reviews/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: str,
    review_data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing review"""

    try:
        service = MarketplaceService(db)

        review = service.update_review(
            review_id=review_id,
            user_id=current_user.user_id,
            review_data=review_data
        )

        return review

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update review: {str(e)}"
        )


@router.post("/reviews/{review_id}/helpful", response_model=MessageResponse)
def mark_review_helpful(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark/unmark a review as helpful"""

    try:
        service = MarketplaceService(db)

        is_helpful = service.mark_review_helpful(
            review_id=review_id,
            user_id=current_user.user_id
        )

        return {
            "success": True,
            "message": "Review marked as helpful" if is_helpful else "Review unmarked as helpful",
            "data": {"is_helpful": is_helpful}
        }

    except Exception as e:
        logger.error(f"Error marking review helpful: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark review: {str(e)}"
        )


@router.post("/apps/{app_id}/submit-for-approval", response_model=MessageResponse)
def submit_app_for_approval(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a micro SaaS app for marketplace approval"""

    try:
        service = MarketplaceService(db)

        result = service.submit_for_approval(
            app_id=app_id,
            user_id=current_user.user_id
        )

        return {
            "success": True,
            "message": "App submitted for approval" if not result["auto_approved"] else "App auto-approved",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting app for approval: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit app: {str(e)}"
        )


# ============================================================================
# ADMIN ENDPOINTS (Admin access required)
# ============================================================================

@router.get("/admin/apps")
def get_all_apps_admin(
    app_status: Optional[str] = Query(None, description="Filter by marketplace_status", alias="status"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    visibility: Optional[str] = Query(None, description="Filter by visibility"),
    sort_by: str = Query("created_at", description="Sort by field (created_at, frontend_app_name, marketplace_status, tenant_id)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all marketplace apps with filters and sorting (admin only)"""

    # Check if user is admin (compare enum to enum)
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this endpoint"
        )

    try:
        from db.application_models import FrontendFlowApplication
        from db.models import User

        # Base query
        query = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.marketplace_enabled == True
        )

        # Apply filters
        if app_status:
            query = query.filter(FrontendFlowApplication.marketplace_status == app_status)

        if tenant_id:
            query = query.filter(FrontendFlowApplication.tenant_id == tenant_id)

        if visibility:
            query = query.filter(FrontendFlowApplication.visibility == visibility)

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        sort_field = getattr(FrontendFlowApplication, sort_by, FrontendFlowApplication.created_at)
        if sort_order == "asc":
            query = query.order_by(asc(sort_field))
        else:
            query = query.order_by(desc(sort_field))

        # Apply pagination
        offset = (page - 1) * page_size
        apps = query.offset(offset).limit(page_size).all()

        # Format results
        result = []
        for app in apps:
            # Get creator info
            creator = db.query(User).filter(User.user_id == app.created_by).first()

            result.append({
                "frontend_app_id": app.frontend_app_id,
                "frontend_app_name": app.frontend_app_name,
                "description": app.description,
                "visibility": app.visibility,
                "marketplace_enabled": app.marketplace_enabled,
                "marketplace_status": app.marketplace_status,
                "tenant_id": app.tenant_id,
                "created_by": app.created_by,
                "creator_name": creator.user_name if creator else None,
                "creator_email": creator.email if creator else None,
                "created_at": app.created_at,
                "approved_at": app.approved_at,
                "approved_by": app.approved_by,
                "public_url_slug": app.public_url_slug,
                "total_subscribers": app.total_subscribers or 0,
                "avg_rating": app.avg_rating or 0.0,
                "total_reviews": app.total_reviews or 0
            })

        return {
            "apps": result,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }

    except Exception as e:
        logger.error(f"Error getting admin apps list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get apps: {str(e)}"
        )


@router.get("/admin/pending-approvals", response_model=List[ApprovalResponse])
def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all pending marketplace app approvals (admin only)"""

    # Check if user is admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this endpoint"
        )

    try:
        from db.marketplace_models import MarketplaceApproval
        from db.application_models import FrontendFlowApplication

        approvals = db.query(MarketplaceApproval).filter(
            MarketplaceApproval.status == 'pending'
        ).order_by(MarketplaceApproval.submitted_at.desc()).all()

        result = []
        for approval in approvals:
            # Get app info
            app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == approval.app_id
            ).first()

            # Get user info
            from db.models import User
            submitter = db.query(User).filter(User.user_id == approval.submitted_by).first()

            result.append({
                "approval_id": approval.approval_id,
                "app_id": approval.app_id,
                "app_name": app.frontend_app_name if app else None,
                "status": approval.status,
                "submitted_by": approval.submitted_by,
                "submitted_by_name": submitter.user_name if submitter else None,
                "submitted_at": approval.submitted_at,
                "reviewed_by": approval.reviewed_by,
                "reviewed_by_name": None,
                "reviewed_at": approval.reviewed_at,
                "review_notes": approval.review_notes,
                "rejection_reason": approval.rejection_reason,
                "version": approval.version
            })

        return result

    except Exception as e:
        logger.error(f"Error getting pending approvals: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending approvals: {str(e)}"
        )


@router.post("/admin/apps/{app_id}/approve", response_model=MessageResponse)
def approve_marketplace_app(
    app_id: str,
    review: ApprovalReview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve a marketplace app (admin only)"""

    # Check if user is admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this endpoint"
        )

    try:
        service = MarketplaceService(db)

        if review.status.value == "approved":
            result = service.approve_app(
                app_id=app_id,
                admin_user_id=current_user.user_id,
                review_notes=review.review_notes
            )
            return {
                "success": True,
                "message": "App approved successfully",
                "data": result
            }
        else:
            result = service.reject_app(
                app_id=app_id,
                admin_user_id=current_user.user_id,
                rejection_reason=review.rejection_reason or review.review_notes or "No reason provided"
            )
            return {
                "success": True,
                "message": "App rejected",
                "data": result
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error approving/rejecting app: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review app: {str(e)}"
        )


@router.post("/admin/update-trending-scores", response_model=MessageResponse)
def update_trending_scores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recalculate trending scores for all apps (admin only, background job)"""

    # Check if user is admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this endpoint"
        )

    try:
        service = MarketplaceService(db)
        service.update_trending_scores()

        return {
            "success": True,
            "message": "Trending scores updated successfully"
        }

    except Exception as e:
        logger.error(f"Error updating trending scores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update trending scores: {str(e)}"
        )

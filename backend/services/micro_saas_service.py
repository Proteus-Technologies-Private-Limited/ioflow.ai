"""
Micro SaaS Service

Core business logic for managing Micro SaaS applications, including creation, settings management,
billing, analytics, subscriber management, and usage tracking.
"""

import json
import uuid
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from collections import defaultdict, Counter

from core.config import settings

# Import models - PostgreSQL Only
from db.models import User, Tenant
from db.application_models import (
    PublishedApplication, FrontendFlowApplication, FrontendAppAccessLog,
)

from services.frontend_app_service import FrontendAppService, FrontendAppError
from services.flow_publisher import FlowPublisher

logger = logging.getLogger(__name__)


class MicroSaasError(Exception):
    """Custom exception for Micro SaaS application errors"""
    pass


class BillingError(MicroSaasError):
    """Exception raised for billing-related errors"""
    pass


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


class UsageLimitExceededError(MicroSaasError):
    """Exception raised when usage limits are exceeded"""
    pass


class MicroSaasService:
    """Main service for managing Micro SaaS applications"""

    def __init__(self):
        self.frontend_service = FrontendAppService()
        self.flow_publisher = FlowPublisher()

    def check_existing_micro_saas_app(self,
                                      db: Session,
                                      flow_id: str,
                                      user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if a flow is already published as a Micro SaaS app by this tenant

        Args:
            db: Database session
            flow_id: Flow ID to check
            user_id: User ID (to get tenant_id)

        Returns:
            Dictionary with app info if exists, None otherwise
        """
        # Get user's tenant_id
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return None

        # Check if this flow is already published as a Micro SaaS app by this tenant
        existing_app = db.query(FrontendFlowApplication).filter(
            and_(
                FrontendFlowApplication.flow_id == flow_id,
                FrontendFlowApplication.visibility.isnot(None),  # Micro SaaS apps have visibility set
                FrontendFlowApplication.is_active == True
            )
        ).join(
            User, FrontendFlowApplication.created_by == User.user_id
        ).filter(
            User.tenant_id == user.tenant_id
        ).first()

        if existing_app:
            return {
                "frontend_app_id": existing_app.frontend_app_id,
                "app_name": existing_app.frontend_app_name,
                "public_url_slug": existing_app.public_url_slug
            }

        return None

    def create_micro_saas_app(self,
                             db: Session,
                             flow_id: str,
                             user_id: str,
                             app_key: str,
                             app_name: Optional[str] = None,
                             description: Optional[str] = None,
                             category: str = "Micro SaaS Apps",
                             icon_url: Optional[str] = None,
                             visibility: str = "private",
                             billing_preference: str = "free",
                             pricing_config: Optional[Dict[str, Any]] = None,
                             usage_limits: Optional[Dict[str, Any]] = None,
                             access_type: str = "public_url",
                             access_config: Optional[Dict[str, Any]] = None,
                             public_url_slug: Optional[str] = None,
                             rate_limit_per_hour: int = 100,
                             custom_styling: Optional[Dict[str, Any]] = None,
                             auto_update: bool = False,
                             embed_enabled: bool = True,
                             marketplace_enabled: bool = False,
                             base_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new Micro SaaS application from a flow

        This method:
        1. Creates a frontend application directly from the flow (no reusable app needed)
        2. Sets up Micro SaaS specific settings (visibility, billing, marketplace)
        3. Sets up billing configuration
        4. Initializes usage tracking

        Args:
            db: Database session
            flow_id: ID of the flow to publish
            user_id: ID of the user creating the app
            app_key: Unique key for the application
            app_name: Display name
            description: Description
            category: Category
            icon_url: Icon URL
            visibility: Marketplace visibility (public, private, granted_access)
            billing_preference: Billing model (per_user_per_month, per_execution, free)
            pricing_config: Pricing configuration dict
            usage_limits: Usage limits configuration dict
            access_type: Access control type
            access_config: Access configuration
            public_url_slug: Custom URL slug
            rate_limit_per_hour: Rate limit
            custom_styling: Custom CSS/styling
            auto_update: Auto-update when flow changes
            embed_enabled: Enable embed functionality
            marketplace_enabled: Enable in marketplace

        Returns:
            Dictionary with creation result
        """
        logger.info(f"Creating Micro SaaS app from flow: {flow_id}")

        try:
            # Get user's tenant_id for validation
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                raise MicroSaasError("User not found")

            # Check if this flow is already published as a Micro SaaS app by this tenant
            existing_app = db.query(FrontendFlowApplication).filter(
                and_(
                    FrontendFlowApplication.flow_id == flow_id,
                    FrontendFlowApplication.visibility.isnot(None),  # Micro SaaS apps have visibility set
                    FrontendFlowApplication.is_active == True
                )
            ).join(
                User, FrontendFlowApplication.created_by == User.user_id
            ).filter(
                User.tenant_id == user.tenant_id
            ).first()

            if existing_app:
                raise MicroSaasError(
                    f"This flow is already published as a Micro SaaS app: '{existing_app.frontend_app_name}'. "
                    f"Please unpublish or delete the existing app before creating a new one."
                )

            # Validate the flow exists
            from db.models import Flow
            flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
            if not flow:
                raise MicroSaasError(f"Flow {flow_id} not found")

            # Create frontend application directly from the flow (no reusable app needed)
            logger.info(f"Creating Micro SaaS frontend app directly from flow {flow_id}")
            frontend_result = self.frontend_service.create_frontend_application(
                db=db,
                user_id=user_id,
                frontend_app_name=app_name or app_key,
                access_type=access_type,
                flow_id=flow_id,  # Direct flow reference, no published_app_id needed
                access_config=access_config,
                public_url_slug=public_url_slug,
                description=description,
                rate_limit_per_hour=rate_limit_per_hour,
                custom_styling=custom_styling
            )

            if not frontend_result.get("success"):
                raise MicroSaasError(f"Failed to create frontend app: {frontend_result.get('error')}")

            frontend_app_id = frontend_result.get("frontend_app_id")

            # Update frontend application with Micro SaaS specific fields
            frontend_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == frontend_app_id
            ).first()

            if frontend_app:
                # Set Micro SaaS specific fields
                frontend_app.visibility = visibility
                frontend_app.billing_preference = billing_preference
                frontend_app.pricing_config = json.dumps(pricing_config) if pricing_config else None
                frontend_app.usage_limits = json.dumps(usage_limits) if usage_limits else None
                frontend_app.embed_enabled = embed_enabled
                frontend_app.marketplace_enabled = marketplace_enabled
                frontend_app.flow_id = flow_id  # Store flow_id for reference

                # Create marketplace approval record if marketplace is enabled
                if marketplace_enabled:
                    from db.marketplace_models import MarketplaceApproval

                    # Set initial marketplace status to pending (requires admin approval)
                    frontend_app.marketplace_status = 'pending'

                    # Create approval record for admin review
                    approval = MarketplaceApproval(
                        approval_id=str(uuid.uuid4()),
                        app_id=frontend_app_id,
                        status='pending',
                        submitted_by=user_id,
                        submitted_at=datetime.utcnow(),
                        version=1
                    )
                    db.add(approval)
                    logger.info(f"Created marketplace approval request for app {frontend_app_id}")
                else:
                    # If marketplace not enabled, set status to draft
                    frontend_app.marketplace_status = 'draft'

                db.commit()

            # Step 4: Initialize billing configuration (if not free)
            if billing_preference != "free" and pricing_config:
                self._initialize_billing_config(
                    db=db,
                    frontend_app_id=frontend_app_id,
                    billing_preference=billing_preference,
                    pricing_config=pricing_config,
                    usage_limits=usage_limits
                )

            logger.info(f"Successfully created Micro SaaS app {frontend_app_id}")

            # Use provided base_url or fall back to settings
            url_base = base_url or settings.base_url

            return {
                "success": True,
                "message": f"Micro SaaS app '{app_name or app_key}' created successfully",
                "frontend_app_id": frontend_app_id,
                "flow_id": flow_id,
                "app_key": app_key,
                "public_url": f"{url_base}/public-app/{public_url_slug or frontend_app_id}",
                "admin_url": f"{url_base}/micro-saas/{frontend_app_id}",
                "warnings": []
            }

        except FrontendAppError as e:
            # Specific frontend app errors (like duplicate slug)
            error_msg = str(e)
            logger.error(f"Frontend app creation error: {error_msg}")
            db.rollback()

            if "already in use" in error_msg or "duplicate" in error_msg.lower():
                raise MicroSaasError(error_msg)
            else:
                raise MicroSaasError(f"Frontend app creation failed: {error_msg}")

        except MicroSaasError:
            # Re-raise MicroSaasError without wrapping
            db.rollback()
            raise

        except Exception as e:
            logger.error(f"Unexpected error creating Micro SaaS app: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            db.rollback()

            # Check for common database errors
            error_str = str(e).lower()
            if "unique constraint" in error_str or "duplicate" in error_str:
                if "app_key" in error_str:
                    raise MicroSaasError(f"Application key '{app_key}' is already in use. Please choose a different key.")
                elif "public_url_slug" in error_str:
                    raise MicroSaasError(f"URL slug '{public_url_slug}' is already in use. Please try a different name.")
                else:
                    raise MicroSaasError(f"A unique constraint was violated. Please check your input values.")
            else:
                raise MicroSaasError(f"Failed to create Micro SaaS app: {str(e)}")

    def get_user_micro_saas_apps(self,
                                 db: Session,
                                 user_id: str,
                                 include_inactive: bool = False,
                                 visibility_filter: Optional[str] = None,
                                 base_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all Micro SaaS apps for a user

        Args:
            db: Database session
            user_id: User ID
            include_inactive: Include inactive apps
            visibility_filter: Filter by visibility (public, private, granted_access)
            base_url: Base URL for generating public URLs

        Returns:
            List of Micro SaaS apps
        """
        logger.info(f"Getting Micro SaaS apps for user: {user_id}")

        try:
            # Join with User and Tenant tables to get creator and tenant information
            query = db.query(
                FrontendFlowApplication,
                User.user_name.label('creator_username'),
                User.email.label('creator_email'),
                Tenant.tenant_name.label('tenant_name')
            ).outerjoin(
                User, FrontendFlowApplication.created_by == User.user_id
            ).outerjoin(
                Tenant, User.tenant_id == Tenant.tenant_id
            ).filter(
                FrontendFlowApplication.created_by == user_id
            )

            # Filter by active status
            if not include_inactive:
                query = query.filter(FrontendFlowApplication.is_active == True)

            # Filter by visibility
            if visibility_filter:
                query = query.filter(FrontendFlowApplication.visibility == visibility_filter)

            # Only get apps that have visibility field set (Micro SaaS apps)
            # Regular frontend apps won't have this field populated
            query = query.filter(FrontendFlowApplication.visibility.isnot(None))

            results = query.order_by(desc(FrontendFlowApplication.created_at)).all()

            formatted_results = []
            for app, creator_username, creator_email, tenant_name in results:
                app_data = self._format_micro_saas_app(
                    app,
                    base_url,
                    creator_username=creator_username,
                    creator_email=creator_email,
                    tenant_name=tenant_name
                )
                formatted_results.append(app_data)

            logger.info(f"Found {len(formatted_results)} Micro SaaS apps")
            return formatted_results

        except Exception as e:
            logger.error(f"Error in get_user_micro_saas_apps: {str(e)}")
            logger.exception("Full traceback:")
            raise

    def get_micro_saas_app(self,
                          db: Session,
                          frontend_app_id: str,
                          user_id: str,
                          base_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a specific Micro SaaS app with full details

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID (for permission check)
            base_url: Base URL for generating public URLs

        Returns:
            Micro SaaS app details
        """
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found")

        # Check permission
        if app.created_by != user_id:
            raise MicroSaasError("You don't have permission to access this app")

        return self._format_micro_saas_app(app, base_url=base_url, include_details=True)

    def update_app_settings(self,
                           db: Session,
                           frontend_app_id: str,
                           user_id: str,
                           updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update all settings for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID (for permission check)
            updates: Dictionary of fields to update

        Returns:
            Updated app details
        """
        logger.info(f"Updating settings for Micro SaaS app: {frontend_app_id}")

        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found")

        # Check permission
        if app.created_by != user_id:
            raise MicroSaasError("You don't have permission to update this app")

        # Update allowed fields
        allowed_fields = [
            'frontend_app_name', 'description', 'icon_url', 'visibility',
            'billing_preference', 'pricing_config', 'usage_limits',
            'access_type', 'access_config', 'rate_limit_per_hour',
            'custom_styling', 'is_active', 'embed_enabled', 'marketplace_enabled',
            'page_definition'
        ]

        # Track if marketplace_enabled is being changed
        was_marketplace_enabled = app.marketplace_enabled
        marketplace_enabled_changed = 'marketplace_enabled' in updates and updates['marketplace_enabled'] != was_marketplace_enabled

        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                if field in ['pricing_config', 'usage_limits', 'access_config', 'custom_styling']:
                    # JSON fields
                    setattr(app, field, json.dumps(value) if value else None)
                else:
                    setattr(app, field, value)

        # Handle marketplace approval workflow
        if app.marketplace_enabled and marketplace_enabled_changed:
            from db.marketplace_models import MarketplaceApproval

            # Check if there's already a pending approval
            existing_approval = db.query(MarketplaceApproval).filter(
                MarketplaceApproval.app_id == frontend_app_id,
                MarketplaceApproval.status == 'pending'
            ).first()

            if not existing_approval:
                # Create new approval request
                app.marketplace_status = 'pending'

                # Get the latest version number
                latest_approval = db.query(MarketplaceApproval).filter(
                    MarketplaceApproval.app_id == frontend_app_id
                ).order_by(MarketplaceApproval.version.desc()).first()

                version = (latest_approval.version + 1) if latest_approval else 1

                approval = MarketplaceApproval(
                    approval_id=str(uuid.uuid4()),
                    app_id=frontend_app_id,
                    status='pending',
                    submitted_by=user_id,
                    submitted_at=datetime.utcnow(),
                    version=version,
                    previous_approval_id=latest_approval.approval_id if latest_approval else None
                )
                db.add(approval)
                logger.info(f"Created marketplace approval request (version {version}) for app {frontend_app_id}")
            else:
                logger.info(f"App {frontend_app_id} already has a pending approval request")

        elif not app.marketplace_enabled and marketplace_enabled_changed:
            # Marketplace disabled - set status to draft
            app.marketplace_status = 'draft'
            logger.info(f"Marketplace disabled for app {frontend_app_id}, status set to draft")

        app.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Successfully updated Micro SaaS app {frontend_app_id}")

        return self._format_micro_saas_app(app, include_details=True)

    def update_visibility(self,
                         db: Session,
                         frontend_app_id: str,
                         user_id: str,
                         visibility: str) -> Dict[str, Any]:
        """
        Update visibility setting for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID
            visibility: New visibility (public, private, granted_access)

        Returns:
            Updated app details
        """
        return self.update_app_settings(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=user_id,
            updates={"visibility": visibility}
        )

    def update_billing_config(self,
                             db: Session,
                             frontend_app_id: str,
                             user_id: str,
                             billing_preference: str,
                             pricing_config: Optional[Dict[str, Any]] = None,
                             usage_limits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update billing configuration for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID
            billing_preference: New billing preference
            pricing_config: New pricing configuration
            usage_limits: New usage limits

        Returns:
            Updated app details
        """
        updates = {
            "billing_preference": billing_preference,
            "pricing_config": pricing_config,
            "usage_limits": usage_limits
        }

        result = self.update_app_settings(
            db=db,
            frontend_app_id=frontend_app_id,
            user_id=user_id,
            updates=updates
        )

        # Update or create billing config record
        if billing_preference != "free" and pricing_config:
            self._update_or_create_billing_config(
                db=db,
                frontend_app_id=frontend_app_id,
                billing_preference=billing_preference,
                pricing_config=pricing_config,
                usage_limits=usage_limits
            )

        return result

    def get_app_analytics(self,
                         db: Session,
                         frontend_app_id: str,
                         user_id: str,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID
            start_date: Start date for analytics (default: 30 days ago)
            end_date: End date for analytics (default: now)

        Returns:
            Analytics data
        """
        logger.info(f"Generating analytics for Micro SaaS app: {frontend_app_id}")

        # Check permission
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found")

        if app.created_by != user_id:
            raise MicroSaasError("You don't have permission to view analytics for this app")

        # Set default date range
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get access logs for the period - only executions, not views
        access_logs = db.query(FrontendAppAccessLog).filter(
            and_(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                FrontendAppAccessLog.access_type == 'execute',  # Only count executions
                FrontendAppAccessLog.accessed_at >= start_date,
                FrontendAppAccessLog.accessed_at <= end_date
            )
        ).all()

        # Calculate execution metrics
        total_executions = len(access_logs)
        successful_executions = len([log for log in access_logs if log.execution_success == True])
        failed_executions = len([log for log in access_logs if log.execution_success == False])

        # Log for debugging
        logger.info(f"Analytics for {frontend_app_id}: {total_executions} total, {successful_executions} success, {failed_executions} failed")

        execution_times = [log.execution_time_ms for log in access_logs if log.execution_time_ms]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

        # Calculate cost (if applicable)
        total_cost = 0.0
        if app.billing_preference == "per_execution" and app.pricing_config:
            pricing = _parse_json_field(app.pricing_config)
            if pricing and 'per_execution_config' in pricing:
                price_per_exec = pricing['per_execution_config'].get('price_per_execution', 0)
                total_cost = successful_executions * price_per_exec

        execution_metrics = {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "average_execution_time_ms": avg_execution_time,
            "total_cost_incurred": total_cost
        }

        # Group executions by day
        executions_by_day = defaultdict(lambda: {"count": 0, "cost": 0})
        for log in access_logs:
            day = log.accessed_at.date().isoformat()
            executions_by_day[day]["count"] += 1
            if app.billing_preference == "per_execution" and log.execution_success:
                executions_by_day[day]["cost"] += total_cost / successful_executions if successful_executions > 0 else 0

        executions_by_day_list = [
            {"date": day, "count": data["count"], "cost": data["cost"]}
            for day, data in sorted(executions_by_day.items())
        ]

        # Calculate revenue metrics (placeholder - would integrate with actual payment data)
        revenue_metrics = None
        if app.billing_preference != "free":
            revenue_metrics = {
                "total_revenue": total_cost,  # Simplified
                "revenue_this_month": total_cost,  # Would need actual payment data
                "revenue_last_month": 0.0,
                "currency": "USD"
            }

        # Subscriber metrics (placeholder)
        subscriber_metrics = {
            "total_subscribers": 0,  # Would query subscribers table
            "active_subscribers": 0,
            "new_subscribers_this_month": 0,
            "cancelled_this_month": 0
        }

        # Top subscribers (placeholder)
        top_subscribers = []

        # Usage by hour
        hour_counts = Counter(log.accessed_at.hour for log in access_logs)
        popular_execution_hours = [
            {"hour": hour, "count": count}
            for hour, count in sorted(hour_counts.items())
        ]

        return {
            "frontend_app_id": frontend_app_id,
            "app_name": app.frontend_app_name,
            "execution_metrics": execution_metrics,
            "executions_by_day": executions_by_day_list,
            "revenue_metrics": revenue_metrics,
            "subscriber_metrics": subscriber_metrics,
            "top_subscribers": top_subscribers,
            "usage_by_country": None,  # Would require IP geolocation
            "popular_execution_hours": popular_execution_hours
        }

    def get_subscribers(self,
                       db: Session,
                       frontend_app_id: str,
                       user_id: str,
                       status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of subscribers for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID
            status_filter: Filter by status (active, paused, expired, cancelled)

        Returns:
            List of subscribers
        """
        logger.info(f"Getting subscribers for Micro SaaS app: {frontend_app_id}")

        # Check permission
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found")

        if app.created_by != user_id:
            raise MicroSaasError("You don't have permission to view subscribers")

        # Placeholder - would query MicroSaasSubscriber table
        # For now, return empty list as table doesn't exist yet
        return []

    def get_billing_history(self,
                           db: Session,
                           frontend_app_id: str,
                           user_id: str,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get billing history for a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID
            start_date: Start date
            end_date: End date

        Returns:
            Billing history
        """
        logger.info(f"Getting billing history for Micro SaaS app: {frontend_app_id}")

        # Check permission
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found")

        if app.created_by != user_id:
            raise MicroSaasError("You don't have permission to view billing history")

        # Placeholder - would query MicroSaasBillingTransaction table
        return {
            "frontend_app_id": frontend_app_id,
            "app_name": app.frontend_app_name,
            "total_transactions": 0,
            "total_revenue": 0.0,
            "total_costs": 0.0,
            "net_revenue": 0.0,
            "currency": "USD",
            "transactions": [],
            "execution_costs": [],
            "prepaid_balance": None,
            "prepaid_transactions": None
        }

    def calculate_usage_cost(self,
                            db: Session,
                            frontend_app_id: str,
                            executions: int) -> float:
        """
        Calculate cost for a given number of executions

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            executions: Number of executions

        Returns:
            Cost in configured currency
        """
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app or app.billing_preference != "per_execution":
            return 0.0

        if not app.pricing_config:
            return 0.0

        pricing = _parse_json_field(app.pricing_config)
        if not pricing or 'per_execution_config' not in pricing:
            return 0.0

        per_exec_config = pricing['per_execution_config']
        price_per_execution = per_exec_config.get('price_per_execution', 0)
        free_executions = per_exec_config.get('free_executions_per_month', 0)

        # Apply free executions
        billable_executions = max(0, executions - free_executions)

        # Apply bulk discounts if configured
        bulk_discounts = per_exec_config.get('bulk_discounts', [])
        if bulk_discounts:
            bulk_discounts = sorted(bulk_discounts, key=lambda x: x.get('execution_threshold', 0), reverse=True)
            for discount in bulk_discounts:
                threshold = discount.get('execution_threshold', 0)
                discount_percent = discount.get('discount_percent', 0)
                if billable_executions >= threshold:
                    price_per_execution *= (1 - discount_percent / 100)
                    break

        total_cost = billable_executions * price_per_execution

        # Apply minimum charge if configured
        minimum_charge = per_exec_config.get('minimum_charge')
        if minimum_charge and total_cost < minimum_charge:
            total_cost = minimum_charge

        return round(total_cost, 2)

    def check_usage_limits(self,
                          db: Session,
                          frontend_app_id: str,
                          subscriber_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if usage limits are exceeded

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            subscriber_id: Subscriber ID (if applicable)

        Returns:
            Tuple of (within_limits: bool, error_message: Optional[str])
        """
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id
        ).first()

        if not app or not app.usage_limits:
            return True, None

        limits = _parse_json_field(app.usage_limits)
        if not limits:
            return True, None

        # Check daily limit
        max_daily = limits.get('max_executions_per_day')
        if max_daily:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = db.query(func.count(FrontendAppAccessLog.log_id)).filter(
                and_(
                    FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                    FrontendAppAccessLog.accessed_at >= today_start
                )
            ).scalar()

            if today_count >= max_daily:
                return False, f"Daily execution limit of {max_daily} reached"

        # Check monthly limit
        max_monthly = limits.get('max_executions_per_month')
        if max_monthly:
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_count = db.query(func.count(FrontendAppAccessLog.log_id)).filter(
                and_(
                    FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                    FrontendAppAccessLog.accessed_at >= month_start
                )
            ).scalar()

            if month_count >= max_monthly:
                return False, f"Monthly execution limit of {max_monthly} reached"

        return True, None

    def delete_micro_saas_app(self,
                             db: Session,
                             frontend_app_id: str,
                             user_id: str,
                             hard_delete: bool = False) -> Dict[str, Any]:
        """
        Delete (or deactivate) a Micro SaaS app

        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            user_id: User ID (for permission check)
            hard_delete: If True, permanently delete. If False, just deactivate (default)

        Returns:
            Result dictionary with success status and message
        """
        # Get the app
        app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app_id,
            FrontendFlowApplication.created_by == user_id
        ).first()

        if not app:
            raise MicroSaasError(f"Micro SaaS app {frontend_app_id} not found or access denied")

        try:
            if hard_delete:
                # Permanently delete the app and all related data
                # Delete access logs
                db.query(FrontendAppAccessLog).filter(
                    FrontendAppAccessLog.frontend_app_id == frontend_app_id
                ).delete()

                # TODO: Delete Micro SaaS specific data when model classes are created
                # - MicroSaasBillingTransaction
                # - MicroSaasSubscriber
                # - MicroSaasUsageLog
                # - MicroSaasBillingConfig

                # Delete the app itself
                db.delete(app)

                db.commit()
                logger.info(f"Permanently deleted Micro SaaS app {frontend_app_id}")

                return {
                    "success": True,
                    "message": "Micro SaaS app permanently deleted"
                }
            else:
                # Soft delete - just deactivate to preserve billing history
                app.is_active = False
                db.commit()

                logger.info(f"Deactivated Micro SaaS app {frontend_app_id}")

                return {
                    "success": True,
                    "message": "Micro SaaS app deactivated successfully"
                }

        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting Micro SaaS app {frontend_app_id}: {str(e)}")
            raise MicroSaasError(f"Failed to delete Micro SaaS app: {str(e)}")

    # Private helper methods

    def _format_micro_saas_app(self,
                              app: FrontendFlowApplication,
                              base_url: Optional[str] = None,
                              include_details: bool = False,
                              creator_username: Optional[str] = None,
                              creator_email: Optional[str] = None,
                              tenant_name: Optional[str] = None) -> Dict[str, Any]:
        """Format a Micro SaaS app for API response"""
        # Use provided base_url or fall back to settings
        url_base = base_url or settings.base_url

        base_data = {
            "frontend_app_id": app.frontend_app_id,
            "published_app_id": app.published_app_id,
            "flow_id": getattr(app, 'flow_id', None),
            "frontend_app_name": app.frontend_app_name,
            "description": app.description,
            "public_url_slug": app.public_url_slug,
            "public_url": f"{url_base}/public-app/{app.public_url_slug}",
            "visibility": app.visibility,
            "billing_preference": app.billing_preference,
            "access_type": app.access_type,
            "is_active": app.is_active,
            "usage_count": app.usage_count or 0,
            "rate_limit_per_hour": app.rate_limit_per_hour,
            "embed_enabled": app.embed_enabled,
            "marketplace_enabled": app.marketplace_enabled,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None,
            "last_accessed_at": app.last_accessed_at.isoformat() if app.last_accessed_at else None,
            "creator_username": creator_username,
            "creator_email": creator_email,
            "tenant_name": tenant_name
        }

        # Always include page_definition
        base_data["page_definition"] = _parse_json_field(app.page_definition)

        if include_details:
            base_data["pricing_config"] = _parse_json_field(app.pricing_config)
            base_data["usage_limits"] = _parse_json_field(app.usage_limits)
            base_data["access_config"] = _parse_json_field(app.access_config)
            base_data["custom_styling"] = _parse_json_field(app.custom_styling)
        else:
            base_data["pricing_config"] = None
            base_data["usage_limits"] = None
            base_data["access_config"] = None

        return base_data

    def _initialize_billing_config(self,
                                   db: Session,
                                   frontend_app_id: str,
                                   billing_preference: str,
                                   pricing_config: Dict[str, Any],
                                   usage_limits: Optional[Dict[str, Any]] = None):
        """Initialize billing configuration (placeholder for future billing table)"""
        # This would create a record in MicroSaasBillingConfig table
        # For now, just log
        logger.info(f"Initialized billing config for {frontend_app_id} with preference: {billing_preference}")

    def _update_or_create_billing_config(self,
                                        db: Session,
                                        frontend_app_id: str,
                                        billing_preference: str,
                                        pricing_config: Dict[str, Any],
                                        usage_limits: Optional[Dict[str, Any]] = None):
        """Update or create billing configuration (placeholder)"""
        # This would update/create a record in MicroSaasBillingConfig table
        logger.info(f"Updated billing config for {frontend_app_id}")

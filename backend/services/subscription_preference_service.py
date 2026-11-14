"""
Service for managing tenant subscription preferences
"""
import logging
from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.database import get_db
from db.models import User, Tenant
from db.subscription_preferences import (
    TenantSubscriptionPreferences,
    BillingPreference,
    PaymentMethod,
    InvoiceFrequency,
    NotificationPreference
)

logger = logging.getLogger(__name__)


class SubscriptionPreferenceService:
    """Service for handling tenant subscription preferences"""
    
    def get_preferences(self, tenant_id: str, db: Session = None) -> Optional[TenantSubscriptionPreferences]:
        """Get subscription preferences for a tenant"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = db.query(TenantSubscriptionPreferences).filter(
                TenantSubscriptionPreferences.tenant_id == tenant_id
            ).first()
            
            if not preferences:
                # Create default preferences if not exist
                preferences = self.create_default_preferences(tenant_id, db)
            
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting preferences for tenant {tenant_id}: {str(e)}")
            return None
    
    def create_default_preferences(
        self,
        tenant_id: str,
        db: Session = None
    ) -> TenantSubscriptionPreferences:
        """Create default subscription preferences for a tenant"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = TenantSubscriptionPreferences(
                tenant_id=tenant_id,
                billing_preference=BillingPreference.PREPAID.value,
                default_payment_method=PaymentMethod.RAZORPAY.value,
                auto_renewal_enabled=True,
                auto_topup_enabled=False,
                invoice_frequency=InvoiceFrequency.MONTHLY.value,
                notification_preference=NotificationPreference.EMAIL.value,
                low_balance_alert_enabled=True,
                usage_alert_enabled=True,
                alert_threshold_percentage=20,
                prefer_cached_results=False,
                max_retry_on_failure=3,
                enable_cost_optimization=True,
                auto_subscribe_new_apps=False,
                send_detailed_invoice=True
            )
            
            db.add(preferences)
            db.commit()
            db.refresh(preferences)
            
            logger.info(f"Created default preferences for tenant {tenant_id}")
            return preferences
            
        except IntegrityError:
            # Preferences already exist
            db.rollback()
            return db.query(TenantSubscriptionPreferences).filter(
                TenantSubscriptionPreferences.tenant_id == tenant_id
            ).first()
        except Exception as e:
            logger.error(f"Error creating default preferences: {str(e)}")
            db.rollback()
            raise
    
    def update_preferences(
        self,
        tenant_id: str,
        preferences_data: Dict,
        user_id: str,
        db: Session = None
    ) -> Dict:
        """Update subscription preferences for a tenant"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = self.get_preferences(tenant_id, db)
            
            if not preferences:
                return {
                    "success": False,
                    "error": "Preferences not found"
                }
            
            # Update fields
            updateable_fields = [
                'billing_preference', 'default_payment_method',
                'auto_renewal_enabled', 'auto_topup_enabled',
                'auto_topup_amount', 'auto_topup_trigger_amount',
                'monthly_spending_limit', 'daily_spending_limit',
                'per_execution_limit', 'invoice_frequency',
                'invoice_email', 'send_detailed_invoice',
                'notification_preference', 'low_balance_alert_enabled',
                'usage_alert_enabled', 'alert_threshold_percentage',
                'prefer_cached_results', 'max_retry_on_failure',
                'enable_cost_optimization', 'default_subscription_tier',
                'auto_subscribe_new_apps', 'budget_alert_contacts',
                'additional_preferences'
            ]
            
            for field in updateable_fields:
                if field in preferences_data:
                    # Convert decimal fields
                    if field in ['auto_topup_amount', 'auto_topup_trigger_amount', 
                               'monthly_spending_limit', 'daily_spending_limit', 
                               'per_execution_limit']:
                        if preferences_data[field] is not None:
                            setattr(preferences, field, Decimal(str(preferences_data[field])))
                        else:
                            setattr(preferences, field, None)
                    else:
                        setattr(preferences, field, preferences_data[field])
            
            # Update metadata
            preferences.updated_by = user_id
            preferences.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(preferences)
            
            logger.info(f"Updated preferences for tenant {tenant_id}")
            
            return {
                "success": True,
                "preferences": self._serialize_preferences(preferences)
            }
            
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_spending_limits(
        self,
        tenant_id: str,
        amount: Decimal,
        limit_type: str = 'execution',
        db: Session = None
    ) -> bool:
        """Check if a spending amount is within configured limits"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = self.get_preferences(tenant_id, db)
            
            if not preferences:
                return True  # No limits configured
            
            if limit_type == 'execution' and preferences.per_execution_limit:
                if amount > preferences.per_execution_limit:
                    logger.warning(f"Execution cost {amount} exceeds limit {preferences.per_execution_limit} for tenant {tenant_id}")
                    return False
            
            # Check daily limit
            if preferences.daily_spending_limit:
                from db.pricing_models import BalanceTransaction, TransactionType
                from sqlalchemy import func, and_
                from datetime import datetime, timedelta
                
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                
                daily_spent = db.query(
                    func.sum(BalanceTransaction.amount)
                ).filter(
                    and_(
                        BalanceTransaction.tenant_id == tenant_id,
                        BalanceTransaction.transaction_type == TransactionType.DEBIT.value,
                        BalanceTransaction.created_at >= today_start
                    )
                ).scalar() or Decimal(0)
                
                if daily_spent + amount > preferences.daily_spending_limit:
                    logger.warning(f"Daily spending {daily_spent + amount} would exceed limit {preferences.daily_spending_limit} for tenant {tenant_id}")
                    return False
            
            # Check monthly limit
            if preferences.monthly_spending_limit:
                from db.pricing_models import BalanceTransaction, TransactionType
                from sqlalchemy import func, and_
                
                month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                monthly_spent = db.query(
                    func.sum(BalanceTransaction.amount)
                ).filter(
                    and_(
                        BalanceTransaction.tenant_id == tenant_id,
                        BalanceTransaction.transaction_type == TransactionType.DEBIT.value,
                        BalanceTransaction.created_at >= month_start
                    )
                ).scalar() or Decimal(0)
                
                if monthly_spent + amount > preferences.monthly_spending_limit:
                    logger.warning(f"Monthly spending {monthly_spent + amount} would exceed limit {preferences.monthly_spending_limit} for tenant {tenant_id}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating spending limits: {str(e)}")
            return True  # Allow on error to not block operations
    
    def should_send_alert(
        self,
        tenant_id: str,
        alert_type: str,
        db: Session = None
    ) -> Dict:
        """Check if an alert should be sent based on preferences"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = self.get_preferences(tenant_id, db)
            
            if not preferences:
                return {"send": False}
            
            response = {
                "send": False,
                "method": preferences.notification_preference,
                "contacts": []
            }
            
            if alert_type == 'low_balance' and preferences.low_balance_alert_enabled:
                response["send"] = True
            elif alert_type == 'usage' and preferences.usage_alert_enabled:
                response["send"] = True
            elif alert_type == 'budget':
                response["send"] = True
                if preferences.budget_alert_contacts:
                    response["contacts"] = preferences.budget_alert_contacts
            
            # Get tenant email if needed
            if response["send"] and preferences.notification_preference in ['email', 'both']:
                if preferences.invoice_email:
                    response["email"] = preferences.invoice_email
                else:
                    # Get tenant admin email
                    from db.models import User, UserRole
                    admin = db.query(User).filter(
                        and_(
                            User.tenant_id == tenant_id,
                            User.role == UserRole.TENANT_ADMIN
                        )
                    ).first()
                    if admin:
                        response["email"] = admin.email
            
            return response
            
        except Exception as e:
            logger.error(f"Error checking alert preferences: {str(e)}")
            return {"send": False}
    
    def get_cost_optimization_settings(
        self,
        tenant_id: str,
        db: Session = None
    ) -> Dict:
        """Get cost optimization settings for a tenant"""
        if not db:
            db = next(get_db())
        
        try:
            preferences = self.get_preferences(tenant_id, db)
            
            if not preferences:
                return {
                    "prefer_cached_results": False,
                    "max_retry_on_failure": 3,
                    "enable_cost_optimization": True
                }
            
            return {
                "prefer_cached_results": preferences.prefer_cached_results,
                "max_retry_on_failure": preferences.max_retry_on_failure,
                "enable_cost_optimization": preferences.enable_cost_optimization
            }
            
        except Exception as e:
            logger.error(f"Error getting cost optimization settings: {str(e)}")
            return {
                "prefer_cached_results": False,
                "max_retry_on_failure": 3,
                "enable_cost_optimization": True
            }
    
    def _serialize_preferences(self, preferences: TenantSubscriptionPreferences) -> Dict:
        """Serialize preferences object to dictionary"""
        return {
            "preference_id": str(preferences.preference_id),
            "tenant_id": str(preferences.tenant_id),
            "billing_preference": preferences.billing_preference,
            "default_payment_method": preferences.default_payment_method,
            "auto_renewal_enabled": preferences.auto_renewal_enabled,
            "auto_topup_enabled": preferences.auto_topup_enabled,
            "auto_topup_amount": float(preferences.auto_topup_amount) if preferences.auto_topup_amount else None,
            "auto_topup_trigger_amount": float(preferences.auto_topup_trigger_amount) if preferences.auto_topup_trigger_amount else None,
            "monthly_spending_limit": float(preferences.monthly_spending_limit) if preferences.monthly_spending_limit else None,
            "daily_spending_limit": float(preferences.daily_spending_limit) if preferences.daily_spending_limit else None,
            "per_execution_limit": float(preferences.per_execution_limit) if preferences.per_execution_limit else None,
            "invoice_frequency": preferences.invoice_frequency,
            "invoice_email": preferences.invoice_email,
            "send_detailed_invoice": preferences.send_detailed_invoice,
            "notification_preference": preferences.notification_preference,
            "low_balance_alert_enabled": preferences.low_balance_alert_enabled,
            "usage_alert_enabled": preferences.usage_alert_enabled,
            "alert_threshold_percentage": preferences.alert_threshold_percentage,
            "prefer_cached_results": preferences.prefer_cached_results,
            "max_retry_on_failure": preferences.max_retry_on_failure,
            "enable_cost_optimization": preferences.enable_cost_optimization,
            "default_subscription_tier": preferences.default_subscription_tier,
            "auto_subscribe_new_apps": preferences.auto_subscribe_new_apps,
            "budget_alert_contacts": preferences.budget_alert_contacts,
            "additional_preferences": preferences.additional_preferences,
            "created_at": preferences.created_at.isoformat() if preferences.created_at else None,
            "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None
        }


# Singleton instance
subscription_preference_service = SubscriptionPreferenceService()
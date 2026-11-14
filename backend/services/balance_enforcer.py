"""
Balance Enforcer Service for managing balance checks and reservations
"""
import logging
from typing import Optional, Dict, Tuple, Any
from decimal import Decimal
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from db.database import get_db
from db.pricing_models import (
    ApplicationPricing, ServicePricing, TenantBalance,
    BalanceTransaction, ExecutionCostLog, UsageLimit,
    TransactionType, BillingMode
)
from db.application_models import Application, ApplicationService
from exceptions.billing_exceptions import (
    InsufficientBalanceError, ServiceAccessDeniedError,
    UsageLimitExceededError, PricingNotConfiguredError,
    BalanceReservationError
)
from services.topup_service import topup_service

logger = logging.getLogger(__name__)


class BalanceEnforcer:
    """Service for enforcing balance requirements and managing reservations"""

    def __init__(self):
        self.reserved_executions = {}  # Track reserved amounts by execution_id

    def check_balance_for_service(
        self,
        tenant_id: str,
        app_id: str,
        service_id: Optional[str] = None,
        estimated_data_kb: int = 0,
        estimated_tokens: int = 0,
        db: Session = None
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Check if tenant has sufficient balance for a service execution

        Returns:
            Tuple of (can_execute, estimated_cost, billing_mode)
        """
        if not db:
            db = next(get_db())

        try:
            # Get application and pricing information
            app = db.query(Application).filter(Application.app_id == app_id).first()
            if not app:
                logger.error(f"Application {app_id} not found")
                return False, None, None

            # Get application pricing
            app_pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()

            if not app_pricing:
                logger.info(f"No pricing configured for application {app_id}, treating as free")
                return True, 0.0, BillingMode.FREE.value

            # Check if application is free
            if app_pricing.is_free or app_pricing.billing_mode == BillingMode.FREE.value:
                logger.info(f"Application {app.app_name} is free to use")
                return True, 0.0, BillingMode.FREE.value

            # Calculate estimated cost
            estimated_cost = self._calculate_estimated_cost(
                app_pricing=app_pricing,
                service_id=service_id,
                estimated_data_kb=estimated_data_kb,
                estimated_tokens=estimated_tokens,
                db=db
            )

            # Check billing mode
            billing_mode = app_pricing.billing_mode

            if billing_mode == BillingMode.SUBSCRIPTION.value:
                # Check if tenant has active subscription
                return self._check_subscription_access(tenant_id, app_id, db), estimated_cost, billing_mode

            elif billing_mode == BillingMode.POSTPAID.value:
                # Postpaid - always allow but track usage
                return True, estimated_cost, billing_mode

            else:  # PREPAID (default)
                # Check balance for prepaid
                balance = topup_service.get_or_create_balance(tenant_id, db)

                if balance.available_balance >= estimated_cost:
                    return True, estimated_cost, billing_mode
                else:
                    # Insufficient balance
                    logger.warning(
                        f"Insufficient balance for tenant {tenant_id}: "
                        f"Required ${estimated_cost:.2f}, Available ${balance.available_balance:.2f}"
                    )
                    raise InsufficientBalanceError(
                        required_amount=float(estimated_cost),
                        available_amount=float(balance.available_balance),
                        service_name=self._get_service_name(service_id, db) if service_id else None,
                        app_name=app.app_name,
                        suggested_topup=float(estimated_cost - balance.available_balance + 10)  # Add buffer
                    )

        except Exception as e:
            if isinstance(e, (InsufficientBalanceError, PricingNotConfiguredError)):
                raise
            logger.error(f"Error checking balance: {str(e)}")
            return False, None, None

    def reserve_funds(
        self,
        tenant_id: str,
        amount: Decimal,
        execution_id: str,
        app_id: str,
        service_name: Optional[str] = None,
        db: Session = None
    ) -> bool:
        """
        Reserve funds for an execution

        Returns:
            True if reservation successful, False otherwise
        """
        if not db:
            db = next(get_db())

        try:
            # Get or create balance
            balance = topup_service.get_or_create_balance(tenant_id, db)

            # Check if sufficient funds available
            if balance.available_balance < amount:
                raise InsufficientBalanceError(
                    required_amount=float(amount),
                    available_amount=float(balance.available_balance),
                    service_name=service_name
                )

            # Reserve the amount
            balance.reserved_balance += amount
            balance.available_balance = balance.current_balance - balance.reserved_balance

            # Track reservation
            self.reserved_executions[execution_id] = {
                'tenant_id': tenant_id,
                'amount': amount,
                'app_id': app_id,
                'service_name': service_name,
                'reserved_at': datetime.utcnow()
            }

            db.commit()
            logger.info(f"Reserved ${amount} for execution {execution_id}")
            return True

        except Exception as e:
            db.rollback()
            if isinstance(e, InsufficientBalanceError):
                raise
            raise BalanceReservationError(
                operation="reserve",
                amount=float(amount),
                reason=str(e),
                execution_id=execution_id
            )

    def commit_reserved_funds(
        self,
        execution_id: str,
        actual_cost: Decimal,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> bool:
        """
        Commit reserved funds after successful execution

        Returns:
            True if successful, False otherwise
        """
        if not db:
            db = next(get_db())

        try:
            # Get reservation details
            reservation = self.reserved_executions.get(execution_id)
            if not reservation:
                logger.warning(f"No reservation found for execution {execution_id}")
                return False

            tenant_id = reservation['tenant_id']
            reserved_amount = reservation['amount']

            # Get balance
            balance = db.query(TenantBalance).filter(
                TenantBalance.tenant_id == tenant_id
            ).first()

            if not balance:
                logger.error(f"Balance not found for tenant {tenant_id}")
                return False

            # Calculate adjustment if actual cost differs from reserved
            adjustment = reserved_amount - actual_cost

            # Update balance
            balance_before = balance.current_balance
            balance.current_balance -= actual_cost
            balance.reserved_balance -= reserved_amount
            balance.available_balance = balance.current_balance - balance.reserved_balance
            balance.total_spent += actual_cost

            # Create transaction record
            transaction = BalanceTransaction(
                tenant_id=tenant_id,
                transaction_type=TransactionType.DEBIT.value,
                amount=actual_cost,
                currency=balance.currency,
                balance_before=balance_before,
                balance_after=balance.current_balance,
                reference_id=execution_id,
                reference_type='execution',
                description=description or f"Service execution: {reservation.get('service_name', 'Unknown')}",
                transaction_metadata=metadata
            )

            db.add(transaction)
            db.commit()

            # Remove reservation
            del self.reserved_executions[execution_id]

            logger.info(f"Committed ${actual_cost} for execution {execution_id} (reserved ${reserved_amount})")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error committing reserved funds: {str(e)}")
            raise BalanceReservationError(
                operation="commit",
                amount=float(actual_cost),
                reason=str(e),
                execution_id=execution_id
            )

    def release_reserved_funds(
        self,
        execution_id: str,
        db: Session = None
    ) -> bool:
        """
        Release reserved funds if execution failed or was cancelled

        Returns:
            True if successful, False otherwise
        """
        if not db:
            db = next(get_db())

        try:
            # Get reservation details
            reservation = self.reserved_executions.get(execution_id)
            if not reservation:
                logger.warning(f"No reservation found for execution {execution_id}")
                return True  # Nothing to release

            tenant_id = reservation['tenant_id']
            reserved_amount = reservation['amount']

            # Get balance
            balance = db.query(TenantBalance).filter(
                TenantBalance.tenant_id == tenant_id
            ).first()

            if not balance:
                logger.error(f"Balance not found for tenant {tenant_id}")
                return False

            # Release reserved amount
            balance.reserved_balance -= reserved_amount
            balance.available_balance = balance.current_balance - balance.reserved_balance

            db.commit()

            # Remove reservation
            del self.reserved_executions[execution_id]

            logger.info(f"Released ${reserved_amount} for execution {execution_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error releasing reserved funds: {str(e)}")
            return False

    def get_required_balance(
        self,
        app_id: str,
        service_id: Optional[str] = None,
        estimated_data_kb: int = 0,
        estimated_tokens: int = 0,
        db: Session = None
    ) -> float:
        """
        Get the required balance for a service execution

        Returns:
            Estimated cost as float
        """
        if not db:
            db = next(get_db())

        try:
            # Get application pricing
            app_pricing = db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id == app_id,
                ApplicationPricing.is_active == True
            ).first()

            if not app_pricing:
                return 0.0

            # If free, return 0
            if app_pricing.is_free:
                return 0.0

            return float(self._calculate_estimated_cost(
                app_pricing=app_pricing,
                service_id=service_id,
                estimated_data_kb=estimated_data_kb,
                estimated_tokens=estimated_tokens,
                db=db
            ))

        except Exception as e:
            logger.error(f"Error calculating required balance: {str(e)}")
            return 0.0

    def check_usage_limits(
        self,
        tenant_id: str,
        app_id: Optional[str] = None,
        amount: Decimal = Decimal(0),
        db: Session = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if tenant has exceeded any usage limits

        Returns:
            Tuple of (within_limits, error_message)
        """
        if not db:
            db = next(get_db())

        try:
            # Get active usage limits for tenant
            query = db.query(UsageLimit).filter(
                UsageLimit.tenant_id == tenant_id,
                UsageLimit.is_active == True
            )

            if app_id:
                query = query.filter(UsageLimit.app_id == app_id)

            limits = query.all()

            for limit in limits:
                # Check if limit exceeded
                if limit.current_usage + amount > limit.limit_value:
                    # Check action on exceed
                    if limit.action_on_exceed == 'block':
                        raise UsageLimitExceededError(
                            limit_type=limit.limit_type,
                            current_usage=float(limit.current_usage),
                            limit_value=float(limit.limit_value),
                            period=limit.reset_period,
                            reset_time=limit.next_reset.isoformat() if limit.next_reset else None
                        )
                    elif limit.action_on_exceed == 'alert':
                        logger.warning(
                            f"Usage limit warning for tenant {tenant_id}: "
                            f"{limit.limit_type} at {limit.current_usage}/{limit.limit_value}"
                        )

            return True, None

        except UsageLimitExceededError:
            raise
        except Exception as e:
            logger.error(f"Error checking usage limits: {str(e)}")
            return True, None  # Allow execution on error

    def _calculate_estimated_cost(
        self,
        app_pricing: ApplicationPricing,
        service_id: Optional[str],
        estimated_data_kb: int,
        estimated_tokens: int,
        db: Session
    ) -> Decimal:
        """Calculate estimated cost for service execution"""

        total_cost = Decimal(0)

        # Check for service-specific pricing
        if service_id and app_pricing.service_pricing_enabled:
            service_pricing = db.query(ServicePricing).filter(
                ServicePricing.service_id == service_id,
                ServicePricing.is_active == True
            ).first()

            if service_pricing:
                if service_pricing.is_free:
                    return Decimal(0)

                if service_pricing.override_app_pricing:
                    # Use service pricing exclusively
                    total_cost = service_pricing.cost_per_request

                    if service_pricing.cost_per_kb and estimated_data_kb:
                        total_cost += service_pricing.cost_per_kb * Decimal(estimated_data_kb)

                    if service_pricing.cost_per_token and estimated_tokens:
                        total_cost += service_pricing.cost_per_token * Decimal(estimated_tokens)

                    return total_cost

        # Use application-level pricing
        total_cost = app_pricing.incoming_event_cost + app_pricing.outgoing_service_cost

        if app_pricing.cost_per_kb and estimated_data_kb:
            total_cost += app_pricing.cost_per_kb * Decimal(estimated_data_kb)

        if app_pricing.cost_per_token and estimated_tokens:
            total_cost += app_pricing.cost_per_token * Decimal(estimated_tokens)

        return total_cost

    def _check_subscription_access(
        self,
        tenant_id: str,
        app_id: str,
        db: Session
    ) -> bool:
        """Check if tenant has active subscription for the application"""
        from db.pricing_models import TenantApplicationSubscription

        subscription = db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.tenant_id == tenant_id,
            TenantApplicationSubscription.app_id == app_id,
            TenantApplicationSubscription.status == 'active'
        ).first()

        if subscription:
            # Check if subscription is still valid
            if subscription.subscription_end_date:
                return subscription.subscription_end_date >= datetime.utcnow()
            return True

        return False

    def _get_service_name(self, service_id: str, db: Session) -> Optional[str]:
        """Get service name by ID"""
        service = db.query(ApplicationService).filter(
            ApplicationService.service_id == service_id
        ).first()
        return service.service_name if service else None


# Singleton instance
balance_enforcer = BalanceEnforcer()
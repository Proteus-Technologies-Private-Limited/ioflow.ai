"""
Top-up Service for managing tenant balance and payments
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from db.database import get_db
from db.models import User, Tenant
from db.pricing_models import (
    TenantBalance, BalanceTransaction, TransactionType,
    ExecutionCostLog, UsageLimit
)
from services.razorpay_service import razorpay_service

logger = logging.getLogger(__name__)


class TopupService:
    """Service for handling balance top-ups and management"""
    
    def get_or_create_balance(self, tenant_id: str, db: Session) -> TenantBalance:
        """Get existing balance or create new one for tenant"""
        balance = db.query(TenantBalance).filter(
            TenantBalance.tenant_id == tenant_id
        ).first()
        
        if not balance:
            balance = TenantBalance(
                tenant_id=tenant_id,
                current_balance=Decimal(0),
                reserved_balance=Decimal(0),
                available_balance=Decimal(0),
                currency='USD',
                total_topped_up=Decimal(0),
                total_spent=Decimal(0)
            )
            db.add(balance)
            db.commit()
            db.refresh(balance)
            logger.info(f"Created new balance for tenant {tenant_id}")
        
        return balance
    
    def process_topup(
        self,
        tenant_id: str,
        amount: Decimal,
        payment_method: str,
        payment_reference: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Session = None
    ) -> Dict:
        """Process a balance top-up"""
        if not db:
            db = next(get_db())
        
        try:
            # Get or create balance
            balance = self.get_or_create_balance(tenant_id, db)
            
            # Record balance before
            balance_before = balance.current_balance
            
            # Update balance
            balance.current_balance += amount
            balance.available_balance = balance.current_balance - balance.reserved_balance
            balance.total_topped_up += amount
            balance.last_topup_date = datetime.utcnow()
            
            # Create transaction record
            transaction = BalanceTransaction(
                tenant_id=tenant_id,
                transaction_type=TransactionType.TOPUP.value,
                amount=amount,
                currency=balance.currency,
                balance_before=balance_before,
                balance_after=balance.current_balance,
                reference_type='payment',
                description=description or f"Balance top-up via {payment_method}",
                payment_method=payment_method,
                payment_reference=payment_reference,
                payment_status='completed',
                created_by=user_id
            )
            
            db.add(transaction)
            db.commit()
            db.refresh(balance)
            db.refresh(transaction)
            
            logger.info(f"Processed top-up of {amount} for tenant {tenant_id}")
            
            # Check if auto-topup was triggered
            self._check_and_clear_alerts(balance, db)
            
            return {
                "success": True,
                "transaction_id": str(transaction.transaction_id),
                "new_balance": float(balance.current_balance),
                "available_balance": float(balance.available_balance),
                "currency": balance.currency
            }
            
        except Exception as e:
            logger.error(f"Error processing top-up: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_razorpay_topup(
        self,
        tenant_id: str,
        amount: Decimal,
        currency: str = 'USD',
        user_id: Optional[str] = None,
        db: Session = None
    ) -> Dict:
        """Process top-up via Razorpay"""
        if not db:
            db = next(get_db())
        
        try:
            # Get tenant
            tenant = db.query(Tenant).filter(
                Tenant.tenant_id == tenant_id
            ).first()
            
            if not tenant:
                return {
                    "success": False,
                    "error": "Tenant not found"
                }
            
            # Create Razorpay order
            razorpay_order = razorpay_service.create_order(
                amount=int(amount * 100),  # Convert to smallest currency unit
                currency=currency,
                notes={
                    "tenant_id": str(tenant_id),
                    "type": "balance_topup"
                }
            )
            
            if not razorpay_order:
                return {
                    "success": False,
                    "error": "Failed to create payment order"
                }
            
            # Create pending transaction
            transaction = BalanceTransaction(
                tenant_id=tenant_id,
                transaction_type=TransactionType.TOPUP.value,
                amount=amount,
                currency=currency,
                balance_before=Decimal(0),  # Will be updated on completion
                balance_after=Decimal(0),  # Will be updated on completion
                reference_id=razorpay_order['id'],
                reference_type='payment',
                description=f"Pending top-up via Razorpay",
                payment_method='razorpay',
                payment_reference=razorpay_order['id'],
                payment_status='pending',
                created_by=user_id
            )
            
            db.add(transaction)
            db.commit()
            
            return {
                "success": True,
                "order_id": razorpay_order['id'],
                "amount": float(amount),
                "currency": currency,
                "transaction_id": str(transaction.transaction_id)
            }
            
        except Exception as e:
            logger.error(f"Error creating Razorpay top-up: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def confirm_razorpay_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
        db: Session = None
    ) -> bool:
        """Confirm Razorpay payment and update balance"""
        if not db:
            db = next(get_db())
        
        try:
            # Verify payment signature
            if not razorpay_service.verify_payment_signature(
                order_id=order_id,
                payment_id=payment_id,
                signature=signature
            ):
                logger.error("Invalid payment signature")
                return False
            
            # Find pending transaction
            transaction = db.query(BalanceTransaction).filter(
                and_(
                    BalanceTransaction.reference_id == order_id,
                    BalanceTransaction.payment_status == 'pending'
                )
            ).first()
            
            if not transaction:
                logger.error(f"Pending transaction not found for order {order_id}")
                return False
            
            # Get or create balance
            balance = self.get_or_create_balance(transaction.tenant_id, db)
            
            # Update balance
            balance_before = balance.current_balance
            balance.current_balance += transaction.amount
            balance.available_balance = balance.current_balance - balance.reserved_balance
            balance.total_topped_up += transaction.amount
            balance.last_topup_date = datetime.utcnow()
            
            # Update transaction
            transaction.balance_before = balance_before
            transaction.balance_after = balance.current_balance
            transaction.payment_status = 'completed'
            transaction.payment_reference = payment_id
            transaction.description = f"Balance top-up via Razorpay"
            
            db.commit()
            
            logger.info(f"Confirmed Razorpay payment {payment_id} for tenant {transaction.tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error confirming Razorpay payment: {str(e)}")
            db.rollback()
            return False
    
    def deduct_from_balance(
        self,
        tenant_id: str,
        amount: Decimal,
        execution_id: str,
        description: str,
        transaction_metadata: Optional[Dict] = None,
        db: Session = None
    ) -> bool:
        """Deduct amount from tenant balance"""
        if not db:
            db = next(get_db())
        
        try:
            balance = self.get_or_create_balance(tenant_id, db)
            
            # Check if sufficient balance
            if balance.available_balance < amount:
                logger.warning(f"Insufficient balance for tenant {tenant_id}: {balance.available_balance} < {amount}")
                
                # Check auto-topup
                if balance.auto_topup_enabled and balance.auto_topup_amount:
                    self._trigger_auto_topup(balance, db)
                    # Refresh balance
                    db.refresh(balance)
                    
                    # Check again
                    if balance.available_balance < amount:
                        return False
                else:
                    return False
            
            # Record balance before
            balance_before = balance.current_balance
            
            # Deduct from balance
            balance.current_balance -= amount
            balance.available_balance = balance.current_balance - balance.reserved_balance
            balance.total_spent += amount
            
            # Create transaction record
            transaction = BalanceTransaction(
                tenant_id=tenant_id,
                transaction_type=TransactionType.DEBIT.value,
                amount=amount,
                currency=balance.currency,
                balance_before=balance_before,
                balance_after=balance.current_balance,
                reference_id=execution_id,
                reference_type='execution',
                description=description,
                transaction_metadata=transaction_metadata
            )
            
            db.add(transaction)
            
            # Check for low balance alerts
            self._check_low_balance_alerts(balance, db)
            
            db.commit()
            
            logger.info(f"Deducted {amount} from tenant {tenant_id} balance for execution {execution_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deducting from balance: {str(e)}")
            db.rollback()
            return False
    
    def reserve_balance(
        self,
        tenant_id: str,
        amount: Decimal,
        db: Session = None
    ) -> bool:
        """Reserve amount from available balance (for pending executions)"""
        if not db:
            db = next(get_db())
        
        try:
            balance = self.get_or_create_balance(tenant_id, db)
            
            if balance.available_balance < amount:
                return False
            
            balance.reserved_balance += amount
            balance.available_balance = balance.current_balance - balance.reserved_balance
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error reserving balance: {str(e)}")
            db.rollback()
            return False
    
    def release_reserved_balance(
        self,
        tenant_id: str,
        amount: Decimal,
        db: Session = None
    ) -> bool:
        """Release reserved balance"""
        if not db:
            db = next(get_db())
        
        try:
            balance = db.query(TenantBalance).filter(
                TenantBalance.tenant_id == tenant_id
            ).first()
            
            if not balance:
                return False
            
            balance.reserved_balance = max(Decimal(0), balance.reserved_balance - amount)
            balance.available_balance = balance.current_balance - balance.reserved_balance
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error releasing reserved balance: {str(e)}")
            db.rollback()
            return False
    
    def get_balance_summary(
        self,
        tenant_id: str,
        db: Session = None
    ) -> Dict:
        """Get balance summary for tenant"""
        if not db:
            db = next(get_db())
        
        balance = self.get_or_create_balance(tenant_id, db)
        
        # Get recent transactions
        recent_transactions = db.query(BalanceTransaction).filter(
            BalanceTransaction.tenant_id == tenant_id
        ).order_by(BalanceTransaction.created_at.desc()).limit(10).all()
        
        # Get spending this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        monthly_spending = db.query(
            func.sum(BalanceTransaction.amount)
        ).filter(
            and_(
                BalanceTransaction.tenant_id == tenant_id,
                BalanceTransaction.transaction_type == TransactionType.DEBIT.value,
                BalanceTransaction.created_at >= month_start
            )
        ).scalar() or Decimal(0)
        
        return {
            "current_balance": float(balance.current_balance),
            "reserved_balance": float(balance.reserved_balance),
            "available_balance": float(balance.available_balance),
            "currency": balance.currency,
            "total_topped_up": float(balance.total_topped_up),
            "total_spent": float(balance.total_spent),
            "monthly_spending": float(monthly_spending),
            "low_balance_threshold": float(balance.low_balance_threshold) if balance.low_balance_threshold else None,
            "auto_topup_enabled": balance.auto_topup_enabled,
            "auto_topup_amount": float(balance.auto_topup_amount) if balance.auto_topup_amount else None,
            "last_topup_date": balance.last_topup_date.isoformat() if balance.last_topup_date else None,
            "recent_transactions": [
                {
                    "transaction_id": str(t.transaction_id),
                    "type": t.transaction_type,
                    "amount": float(t.amount),
                    "balance_after": float(t.balance_after),
                    "description": t.description,
                    "created_at": t.created_at.isoformat()
                }
                for t in recent_transactions
            ]
        }
    
    def _check_low_balance_alerts(self, balance: TenantBalance, db: Session):
        """Check and send low balance alerts"""
        now = datetime.utcnow()
        
        # Skip if alert was sent recently (within last hour)
        if balance.last_alert_sent and (now - balance.last_alert_sent).seconds < 3600:
            return
        
        if balance.critical_balance_threshold and balance.available_balance <= balance.critical_balance_threshold:
            # Send critical alert
            logger.warning(f"Critical balance alert for tenant {balance.tenant_id}: {balance.available_balance}")
            balance.last_alert_sent = now
            # TODO: Send email/notification
        elif balance.low_balance_threshold and balance.available_balance <= balance.low_balance_threshold:
            # Send low balance alert
            logger.warning(f"Low balance alert for tenant {balance.tenant_id}: {balance.available_balance}")
            balance.last_alert_sent = now
            # TODO: Send email/notification
    
    def _trigger_auto_topup(self, balance: TenantBalance, db: Session):
        """Trigger automatic top-up"""
        if not balance.auto_topup_enabled or not balance.auto_topup_amount:
            return
        
        logger.info(f"Triggering auto top-up of {balance.auto_topup_amount} for tenant {balance.tenant_id}")
        
        # Process auto top-up
        self.process_topup(
            tenant_id=balance.tenant_id,
            amount=balance.auto_topup_amount,
            payment_method='auto_topup',
            description="Automatic balance top-up",
            db=db
        )
    
    def _check_and_clear_alerts(self, balance: TenantBalance, db: Session):
        """Clear alert status if balance is healthy"""
        if balance.low_balance_threshold and balance.available_balance > balance.low_balance_threshold:
            balance.last_alert_sent = None


# Singleton instance
topup_service = TopupService()
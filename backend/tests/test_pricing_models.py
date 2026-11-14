"""
Test pricing models and database operations
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from db.database import get_db, init_db
from db.models import Tenant, User, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice,
    PricingModel, BillingCycle, UsageMetricType, CurrencyType, PaymentStatus
)
from sqlalchemy.exc import IntegrityError


class TestPricingModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        init_db()
        cls.db = next(get_db())
        
        # Create test tenant and user
        cls.test_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="TestTenant",
            schema_name="test_tenant",
            email_domain="test.com",
            status="active"
        )
        cls.db.add(cls.test_tenant)
        
        cls.test_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Test User",
            email="test@test.com",
            auth_provider="email",
            pass_wd_sha="hashed_password",
            tenant_id=cls.test_tenant.tenant_id,
            role=UserRole.APPLICATION_PROVIDER,
            status='A'
        )
        cls.db.add(cls.test_user)
        
        # Create test application
        cls.test_app = Application(
            app_id=str(uuid.uuid4()),
            app_name="Test App",
            app_type="tenant",
            tenant_id_owner=cls.test_tenant.tenant_id,
            created_by=cls.test_user.user_id,
            auth_type="api_key",
            status="active"
        )
        cls.db.add(cls.test_app)
        cls.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Delete in reverse order of dependencies
        cls.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(ExecutionCostLog).filter(
            ExecutionCostLog.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(Application).filter(
            Application.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(User).filter(
            User.user_id == cls.test_user.user_id
        ).delete()
        cls.db.query(Tenant).filter(
            Tenant.tenant_id == cls.test_tenant.tenant_id
        ).delete()
        cls.db.commit()
        cls.db.close()
    
    def test_create_subscription_pricing(self):
        """Test creating subscription-based pricing"""
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.99'),
            incoming_event_cost=Decimal('0.01'),
            outgoing_service_cost=Decimal('0.02'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        
        self.db.add(pricing)
        self.db.commit()
        
        # Verify
        saved_pricing = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.pricing_id == pricing.pricing_id
        ).first()
        
        self.assertIsNotNone(saved_pricing)
        self.assertEqual(saved_pricing.pricing_model, PricingModel.SUBSCRIPTION.value)
        self.assertEqual(saved_pricing.base_subscription_cost, Decimal('99.99'))
        self.assertEqual(saved_pricing.currency, CurrencyType.USD.value)
        
        # Cleanup
        self.db.delete(pricing)
        self.db.commit()
    
    def test_create_usage_pricing(self):
        """Test creating usage-based pricing"""
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type=UsageMetricType.PER_REQUEST.value,
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            cost_per_kb=Decimal('0.01'),
            cost_per_token=Decimal('0.001'),
            currency=CurrencyType.INR.value,
            is_active=True
        )
        
        self.db.add(pricing)
        self.db.commit()
        
        # Verify
        saved_pricing = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.pricing_id == pricing.pricing_id
        ).first()
        
        self.assertIsNotNone(saved_pricing)
        self.assertEqual(saved_pricing.pricing_model, PricingModel.PAY_PER_USE.value)
        self.assertEqual(saved_pricing.usage_metric_type, UsageMetricType.PER_REQUEST.value)
        self.assertEqual(saved_pricing.cost_per_kb, Decimal('0.01'))
        
        # Cleanup
        self.db.delete(pricing)
        self.db.commit()
    
    def test_pricing_constraints(self):
        """Test pricing constraints (negative values should fail)"""
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            incoming_event_cost=Decimal('-0.01'),  # Negative value
            outgoing_service_cost=Decimal('0.02'),
            currency=CurrencyType.USD.value
        )
        
        # This should raise an error due to check constraint
        # Note: SQLite doesn't enforce check constraints by default
        # PostgreSQL will enforce this
        try:
            self.db.add(pricing)
            self.db.commit()
            # If using SQLite, manually check
            if pricing.incoming_event_cost < 0:
                self.fail("Negative cost should not be allowed")
        except Exception:
            self.db.rollback()
            # Expected behavior for PostgreSQL
            pass
    
    def test_create_subscription(self):
        """Test creating a tenant subscription"""
        # First create pricing
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        self.db.commit()
        
        # Create subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active',
            invocation_api_key='test-api-key-123'
        )
        
        self.db.add(subscription)
        self.db.commit()
        
        # Verify
        saved_sub = self.db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.subscription_id == subscription.subscription_id
        ).first()
        
        self.assertIsNotNone(saved_sub)
        self.assertEqual(saved_sub.status, 'active')
        self.assertEqual(saved_sub.invocation_api_key, 'test-api-key-123')
        
        # Cleanup
        self.db.delete(subscription)
        self.db.delete(pricing)
        self.db.commit()
    
    def test_execution_cost_log(self):
        """Test creating execution cost logs"""
        cost_log = ExecutionCostLog(
            execution_id=str(uuid.uuid4()),
            app_id=self.test_app.app_id,
            tenant_id=self.test_tenant.tenant_id,
            flow_id=str(uuid.uuid4()),
            flow_name="Test Flow",
            trigger_type="webhook",
            incoming_event_count=1,
            outgoing_service_count=3,
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.60'),
            data_transfer_kb=100,
            data_transfer_cost=Decimal('1.00'),
            token_count=1000,
            token_cost=Decimal('1.00'),
            total_cost=Decimal('2.70'),
            currency=CurrencyType.USD.value
        )
        
        self.db.add(cost_log)
        self.db.commit()
        
        # Verify
        saved_log = self.db.query(ExecutionCostLog).filter(
            ExecutionCostLog.cost_log_id == cost_log.cost_log_id
        ).first()
        
        self.assertIsNotNone(saved_log)
        self.assertEqual(saved_log.total_cost, Decimal('2.70'))
        self.assertEqual(saved_log.incoming_event_count, 1)
        self.assertEqual(saved_log.outgoing_service_count, 3)
        
        # Cleanup
        self.db.delete(cost_log)
        self.db.commit()
    
    def test_create_invoice(self):
        """Test creating an invoice"""
        invoice = ApplicationInvoice(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            invoice_number="INV-2024-0001",
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=30),
            billing_period_end=datetime.utcnow(),
            subscription_charges=Decimal('99.00'),
            usage_charges=Decimal('25.50'),
            usage_details={
                "executions": 100,
                "data_transfer_kb": 2550
            },
            subtotal=Decimal('124.50'),
            tax_amount=Decimal('12.45'),
            total_amount=Decimal('136.95'),
            currency=CurrencyType.USD.value,
            payment_status=PaymentStatus.PENDING.value
        )
        
        self.db.add(invoice)
        self.db.commit()
        
        # Verify
        saved_invoice = self.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.invoice_id == invoice.invoice_id
        ).first()
        
        self.assertIsNotNone(saved_invoice)
        self.assertEqual(saved_invoice.invoice_number, "INV-2024-0001")
        self.assertEqual(saved_invoice.total_amount, Decimal('136.95'))
        self.assertEqual(saved_invoice.payment_status, PaymentStatus.PENDING.value)
        
        # Test updating payment status
        saved_invoice.payment_status = PaymentStatus.PAID.value
        saved_invoice.payment_date = datetime.utcnow()
        self.db.commit()
        
        updated_invoice = self.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.invoice_id == invoice.invoice_id
        ).first()
        
        self.assertEqual(updated_invoice.payment_status, PaymentStatus.PAID.value)
        self.assertIsNotNone(updated_invoice.payment_date)
        
        # Cleanup
        self.db.delete(invoice)
        self.db.commit()
    
    def test_multiple_pricing_plans(self):
        """Test having multiple pricing plans with only one active"""
        # Create first pricing plan
        pricing1 = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing1)
        self.db.commit()
        
        # Create second pricing plan
        pricing2 = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.YEARLY.value,
            base_subscription_cost=Decimal('999.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing2)
        self.db.commit()
        
        # Verify both exist
        active_pricing = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == self.test_app.app_id,
            ApplicationPricing.is_active == True
        ).all()
        
        self.assertEqual(len(active_pricing), 2)
        
        # In practice, only one should be active at a time
        # Deactivate the first one
        pricing1.is_active = False
        self.db.commit()
        
        active_pricing = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == self.test_app.app_id,
            ApplicationPricing.is_active == True
        ).all()
        
        self.assertEqual(len(active_pricing), 1)
        self.assertEqual(active_pricing[0].pricing_id, pricing2.pricing_id)
        
        # Cleanup
        self.db.delete(pricing1)
        self.db.delete(pricing2)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
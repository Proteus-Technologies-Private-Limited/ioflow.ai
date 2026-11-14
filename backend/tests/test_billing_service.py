"""
Test billing service
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from db.database import get_db, init_db
from db.models import User, Tenant, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice,
    PricingModel, BillingCycle, CurrencyType
)
from services.billing_service import BillingService


class TestBillingService(unittest.TestCase):
    """Test billing service functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and service"""
        init_db()
        cls.db = next(get_db())
        cls.billing_service = BillingService()
        
        # Create test data
        cls.test_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="BillingTestTenant",
            schema_name="billing_test",
            email_domain="billing.test",
            status="active"
        )
        cls.db.add(cls.test_tenant)
        
        cls.test_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Billing Test User",
            email="billing@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.test_tenant.tenant_id,
            role=UserRole.APPLICATION_PROVIDER,
            status='A'
        )
        cls.db.add(cls.test_user)
        
        cls.test_app = Application(
            app_id=str(uuid.uuid4()),
            app_name="Billing Test App",
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
        # Clean up in reverse order
        cls.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.tenant_id == cls.test_tenant.tenant_id
        ).delete()
        cls.db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == cls.test_tenant.tenant_id
        ).delete()
        cls.db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.tenant_id == cls.test_tenant.tenant_id
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
    
    def setUp(self):
        """Set up for each test"""
        # Clean up any existing test invoices
        self.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.tenant_id == self.test_tenant.tenant_id
        ).delete()
        self.db.commit()
    
    def test_generate_invoice_subscription_model(self):
        """Test generating invoice for subscription model"""
        # Create subscription pricing
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        
        # Create subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=pricing.pricing_id,
            subscription_start_date=datetime.utcnow() - timedelta(days=45),
            status='active'
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Generate invoice
        billing_start = datetime.utcnow() - timedelta(days=30)
        billing_end = datetime.utcnow()
        
        invoice = self.billing_service._generate_invoice_for_subscription(
            subscription=subscription,
            billing_start=billing_start,
            billing_end=billing_end,
            db=self.db
        )
        
        # Verify
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subscription_charges, Decimal('99.00'))
        self.assertEqual(invoice.usage_charges, Decimal('0'))
        self.assertEqual(invoice.total_amount, Decimal('99.00'))
        self.assertIn("INV-", invoice.invoice_number)
        
        # Clean up
        self.db.delete(invoice)
        self.db.delete(subscription)
        self.db.delete(pricing)
        self.db.commit()
    
    def test_generate_invoice_usage_model(self):
        """Test generating invoice for usage-based model"""
        # Create usage pricing
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type="per_request",
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        
        # Create subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=pricing.pricing_id,
            subscription_start_date=datetime.utcnow() - timedelta(days=45),
            status='active'
        )
        self.db.add(subscription)
        
        # Create usage logs
        total_usage_cost = Decimal('0')
        for i in range(10):
            cost = Decimal('5.50')
            log = ExecutionCostLog(
                execution_id=str(uuid.uuid4()),
                app_id=self.test_app.app_id,
                tenant_id=self.test_tenant.tenant_id,
                flow_id=str(uuid.uuid4()),
                flow_name=f"Test Flow {i}",
                trigger_type="webhook",
                incoming_event_count=1,
                outgoing_service_count=2,
                incoming_event_cost=Decimal('0.10'),
                outgoing_service_cost=Decimal('0.40'),
                total_cost=cost,
                currency=CurrencyType.USD.value,
                timestamp=datetime.utcnow() - timedelta(days=15)
            )
            self.db.add(log)
            total_usage_cost += cost
        
        self.db.commit()
        
        # Generate invoice
        billing_start = datetime.utcnow() - timedelta(days=30)
        billing_end = datetime.utcnow()
        
        invoice = self.billing_service._generate_invoice_for_subscription(
            subscription=subscription,
            billing_start=billing_start,
            billing_end=billing_end,
            db=self.db
        )
        
        # Verify
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subscription_charges, Decimal('0'))
        self.assertEqual(invoice.usage_charges, total_usage_cost)
        self.assertEqual(invoice.total_amount, total_usage_cost)
        self.assertEqual(invoice.usage_details['executions'], 10)
        
        # Clean up
        self.db.delete(invoice)
        self.db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == self.test_tenant.tenant_id
        ).delete()
        self.db.delete(subscription)
        self.db.delete(pricing)
        self.db.commit()
    
    def test_generate_invoice_prorated(self):
        """Test generating prorated invoice for partial month"""
        # Create subscription pricing
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('100.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        
        # Create subscription that started mid-month
        billing_start = datetime.utcnow() - timedelta(days=30)
        subscription_start = billing_start + timedelta(days=15)  # Started halfway through
        
        subscription = TenantApplicationSubscription(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=pricing.pricing_id,
            subscription_start_date=subscription_start,
            status='active'
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Generate invoice
        billing_end = datetime.utcnow()
        
        invoice = self.billing_service._generate_invoice_for_subscription(
            subscription=subscription,
            billing_start=billing_start,
            billing_end=billing_end,
            db=self.db
        )
        
        # Verify prorated amount (approximately half)
        self.assertIsNotNone(invoice)
        self.assertLess(invoice.subscription_charges, Decimal('100.00'))
        self.assertGreater(invoice.subscription_charges, Decimal('40.00'))  # Should be around 50
        
        # Clean up
        self.db.delete(invoice)
        self.db.delete(subscription)
        self.db.delete(pricing)
        self.db.commit()
    
    def test_generate_monthly_invoices(self):
        """Test batch generation of monthly invoices"""
        # Create multiple subscriptions
        subscriptions = []
        pricings = []
        
        for i in range(3):
            pricing = ApplicationPricing(
                app_id=self.test_app.app_id,
                pricing_model=PricingModel.SUBSCRIPTION.value if i < 2 else PricingModel.PAY_PER_USE.value,
                billing_cycle=BillingCycle.MONTHLY.value if i < 2 else None,
                usage_metric_type=None if i < 2 else "per_request",
                base_subscription_cost=Decimal('50.00') * (i + 1) if i < 2 else None,
                incoming_event_cost=Decimal('0') if i < 2 else Decimal('0.10'),
                outgoing_service_cost=Decimal('0') if i < 2 else Decimal('0.20'),
                currency=CurrencyType.USD.value,
                is_active=True
            )
            self.db.add(pricing)
            pricings.append(pricing)
            
            subscription = TenantApplicationSubscription(
                tenant_id=self.test_tenant.tenant_id,
                app_id=self.test_app.app_id,
                pricing_id=pricing.pricing_id,
                subscription_start_date=datetime.utcnow() - timedelta(days=60),
                status='active'
            )
            self.db.add(subscription)
            subscriptions.append(subscription)
        
        self.db.commit()
        
        # Generate monthly invoices
        invoices = self.billing_service.generate_monthly_invoices(db=self.db)
        
        # Should generate invoices for subscription-based plans
        # Usage-based plan without usage won't generate invoice
        self.assertGreaterEqual(len(invoices), 2)
        
        # Clean up
        for invoice in invoices:
            self.db.delete(invoice)
        for subscription in subscriptions:
            self.db.delete(subscription)
        for pricing in pricings:
            self.db.delete(pricing)
        self.db.commit()
    
    def test_invoice_number_generation(self):
        """Test unique invoice number generation"""
        # Generate multiple invoice numbers
        numbers = []
        for i in range(5):
            number = self.billing_service._generate_invoice_number(self.db)
            numbers.append(number)
            
            # Create dummy invoice to increment counter
            invoice = ApplicationInvoice(
                tenant_id=self.test_tenant.tenant_id,
                app_id=self.test_app.app_id,
                invoice_number=number,
                invoice_date=datetime.utcnow(),
                billing_period_start=datetime.utcnow() - timedelta(days=30),
                billing_period_end=datetime.utcnow(),
                subtotal=Decimal('100.00'),
                total_amount=Decimal('100.00'),
                currency='USD'
            )
            self.db.add(invoice)
        
        self.db.commit()
        
        # Verify all numbers are unique
        self.assertEqual(len(numbers), len(set(numbers)))
        
        # Verify format
        for number in numbers:
            self.assertTrue(number.startswith("INV-"))
            parts = number.split("-")
            self.assertEqual(len(parts), 3)
            self.assertEqual(len(parts[1]), 6)  # YYYYMM
            self.assertTrue(parts[2].isdigit())
    
    def test_process_payment(self):
        """Test processing payment for invoice"""
        # Create invoice
        invoice = ApplicationInvoice(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            invoice_number="INV-TEST-PAYMENT",
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=30),
            billing_period_end=datetime.utcnow(),
            subtotal=Decimal('100.00'),
            total_amount=Decimal('100.00'),
            currency='USD',
            payment_status='pending'
        )
        self.db.add(invoice)
        self.db.commit()
        
        # Process payment
        result = self.billing_service.process_payment(
            invoice_id=str(invoice.invoice_id),
            payment_id='pay_TestPayment123',
            payment_method='razorpay',
            db=self.db
        )
        
        # Verify
        self.assertTrue(result)
        self.db.refresh(invoice)
        self.assertEqual(invoice.payment_status, 'paid')
        self.assertEqual(invoice.razorpay_payment_id, 'pay_TestPayment123')
        self.assertIsNotNone(invoice.payment_date)
        
        # Clean up
        self.db.delete(invoice)
        self.db.commit()
    
    def test_get_pending_invoices(self):
        """Test getting pending invoices for a tenant"""
        # Create mixed invoices
        paid_invoice = ApplicationInvoice(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            invoice_number="INV-PAID-001",
            invoice_date=datetime.utcnow() - timedelta(days=10),
            billing_period_start=datetime.utcnow() - timedelta(days=40),
            billing_period_end=datetime.utcnow() - timedelta(days=10),
            subtotal=Decimal('50.00'),
            total_amount=Decimal('50.00'),
            currency='USD',
            payment_status='paid'
        )
        self.db.add(paid_invoice)
        
        pending_invoices = []
        for i in range(2):
            invoice = ApplicationInvoice(
                tenant_id=self.test_tenant.tenant_id,
                app_id=self.test_app.app_id,
                invoice_number=f"INV-PENDING-{i:03d}",
                invoice_date=datetime.utcnow() - timedelta(days=i),
                billing_period_start=datetime.utcnow() - timedelta(days=30+i),
                billing_period_end=datetime.utcnow() - timedelta(days=i),
                subtotal=Decimal('100.00'),
                total_amount=Decimal('100.00'),
                currency='USD',
                payment_status='pending'
            )
            self.db.add(invoice)
            pending_invoices.append(invoice)
        
        self.db.commit()
        
        # Get pending invoices
        result = self.billing_service.get_pending_invoices(
            tenant_id=self.test_tenant.tenant_id,
            db=self.db
        )
        
        # Verify
        self.assertEqual(len(result), 2)
        for invoice in result:
            self.assertEqual(invoice.payment_status, 'pending')
    
    def test_get_invoice_summary(self):
        """Test getting invoice summary"""
        # Create test invoices
        invoices_data = [
            ('paid', Decimal('100.00')),
            ('paid', Decimal('150.00')),
            ('pending', Decimal('200.00')),
            ('pending', Decimal('75.00')),
        ]
        
        for i, (status, amount) in enumerate(invoices_data):
            invoice = ApplicationInvoice(
                tenant_id=self.test_tenant.tenant_id,
                app_id=self.test_app.app_id,
                invoice_number=f"INV-SUMMARY-{i:03d}",
                invoice_date=datetime.utcnow() - timedelta(days=i*10),
                billing_period_start=datetime.utcnow() - timedelta(days=(i+1)*30),
                billing_period_end=datetime.utcnow() - timedelta(days=i*30),
                subtotal=amount,
                total_amount=amount,
                currency='USD',
                payment_status=status
            )
            self.db.add(invoice)
        
        self.db.commit()
        
        # Get summary
        summary = self.billing_service.get_invoice_summary(
            tenant_id=self.test_tenant.tenant_id,
            db=self.db
        )
        
        # Verify
        self.assertEqual(summary['total_invoices'], 4)
        self.assertEqual(summary['paid_invoices'], 2)
        self.assertEqual(summary['pending_invoices'], 2)
        self.assertEqual(summary['total_amount'], Decimal('525.00'))
        self.assertEqual(summary['paid_amount'], Decimal('250.00'))
        self.assertEqual(summary['pending_amount'], Decimal('275.00'))
        self.assertEqual(summary['currency'], 'USD')


if __name__ == "__main__":
    unittest.main()
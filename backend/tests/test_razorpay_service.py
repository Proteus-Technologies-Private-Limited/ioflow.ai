"""
Test Razorpay service (using mocks since we can't test actual API)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from db.database import get_db, init_db
from db.models import Tenant
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ApplicationInvoice, BillingCycle, CurrencyType
)
from services.razorpay_service import RazorpayService


class TestRazorpayService(unittest.TestCase):
    """Test Razorpay service with mocked API calls"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        init_db()
        cls.db = next(get_db())
        
        # Create test tenant
        cls.test_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="RazorpayTestTenant",
            schema_name="razorpay_test",
            email_domain="razorpay.test",
            status="active"
        )
        cls.db.add(cls.test_tenant)
        cls.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        cls.db.query(Tenant).filter(
            Tenant.tenant_id == cls.test_tenant.tenant_id
        ).delete()
        cls.db.commit()
        cls.db.close()
    
    def setUp(self):
        """Set up mocked Razorpay service"""
        # Mock the Razorpay client
        self.mock_client = Mock()
        
        # Create service with mocked client
        self.service = RazorpayService()
        self.service.client = self.mock_client
        self.service.webhook_secret = "test_webhook_secret"
    
    def test_create_subscription_plan(self):
        """Test creating a Razorpay subscription plan"""
        # Set up test data
        pricing = ApplicationPricing(
            pricing_id=str(uuid.uuid4()),
            app_id=str(uuid.uuid4()),
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.99'),
            currency=CurrencyType.USD.value
        )
        
        # Mock the API response
        self.mock_client.plan.create.return_value = {
            'id': 'plan_TestPlanId123',
            'entity': 'plan',
            'interval': 1,
            'period': 'monthly',
            'item': {
                'name': 'Test App - monthly Plan',
                'amount': 9999,
                'currency': 'USD'
            }
        }
        
        # Call the method
        plan_id = self.service.create_subscription_plan(pricing, "Test App")
        
        # Verify
        self.assertEqual(plan_id, 'plan_TestPlanId123')
        self.mock_client.plan.create.assert_called_once()
        
        # Check the call arguments
        call_args = self.mock_client.plan.create.call_args[1]['data']
        self.assertEqual(call_args['period'], 'monthly')
        self.assertEqual(call_args['item']['amount'], 9999)  # 99.99 * 100
        self.assertEqual(call_args['item']['currency'], 'USD')
    
    def test_create_customer(self):
        """Test creating a Razorpay customer"""
        # Mock the API response
        self.mock_client.customer.create.return_value = {
            'id': 'cust_TestCustomer123',
            'entity': 'customer',
            'name': 'RazorpayTestTenant',
            'email': 'test@razorpay.test'
        }
        
        # Call the method
        customer_id = self.service.create_customer(
            self.test_tenant,
            'test@razorpay.test'
        )
        
        # Verify
        self.assertEqual(customer_id, 'cust_TestCustomer123')
        self.mock_client.customer.create.assert_called_once()
        
        # Check the call arguments
        call_args = self.mock_client.customer.create.call_args[1]['data']
        self.assertEqual(call_args['name'], 'RazorpayTestTenant')
        self.assertEqual(call_args['email'], 'test@razorpay.test')
    
    def test_create_subscription(self):
        """Test creating a Razorpay subscription"""
        # Mock the API response
        self.mock_client.subscription.create.return_value = {
            'id': 'sub_TestSubscription123',
            'entity': 'subscription',
            'plan_id': 'plan_TestPlanId123',
            'customer_id': 'cust_TestCustomer123',
            'status': 'created',
            'charge_at': 1234567890
        }
        
        # Call the method
        subscription = self.service.create_subscription(
            plan_id='plan_TestPlanId123',
            customer_id='cust_TestCustomer123',
            notes={'test': 'data'}
        )
        
        # Verify
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription['id'], 'sub_TestSubscription123')
        self.mock_client.subscription.create.assert_called_once()
    
    def test_cancel_subscription(self):
        """Test cancelling a Razorpay subscription"""
        # Mock the API response
        self.mock_client.subscription.cancel.return_value = {
            'id': 'sub_TestSubscription123',
            'status': 'cancelled'
        }
        
        # Call the method
        result = self.service.cancel_subscription(
            'sub_TestSubscription123',
            cancel_at_cycle_end=True
        )
        
        # Verify
        self.assertTrue(result)
        self.mock_client.subscription.cancel.assert_called_once_with(
            'sub_TestSubscription123',
            data={'cancel_at_cycle_end': 1}
        )
    
    def test_create_addon(self):
        """Test creating an addon charge"""
        # Mock the API response
        self.mock_client.subscription.createAddon.return_value = {
            'id': 'ao_TestAddon123',
            'entity': 'addon',
            'subscription_id': 'sub_TestSubscription123',
            'invoice_id': None,
            'quantity': 1,
            'created_at': 1234567890
        }
        
        # Call the method
        addon = self.service.create_addon(
            subscription_id='sub_TestSubscription123',
            amount=1000,  # 10.00 in paise
            currency='USD',
            description='Additional usage charges'
        )
        
        # Verify
        self.assertIsNotNone(addon)
        self.assertEqual(addon['id'], 'ao_TestAddon123')
        self.mock_client.subscription.createAddon.assert_called_once()
    
    def test_verify_webhook_signature(self):
        """Test webhook signature verification"""
        # Mock successful verification
        self.mock_client.utility.verify_webhook_signature.return_value = True
        
        # Test valid signature
        result = self.service.verify_webhook_signature(
            webhook_body='{"event":"subscription.charged"}',
            webhook_signature='valid_signature'
        )
        self.assertTrue(result)
        
        # Mock failed verification
        self.mock_client.utility.verify_webhook_signature.side_effect = Exception("Invalid signature")
        
        # Test invalid signature
        result = self.service.verify_webhook_signature(
            webhook_body='{"event":"subscription.charged"}',
            webhook_signature='invalid_signature'
        )
        self.assertFalse(result)
    
    def test_process_subscription_webhook(self):
        """Test processing subscription webhooks"""
        # Create test subscription
        subscription = TenantApplicationSubscription(
            subscription_id=str(uuid.uuid4()),
            tenant_id=self.test_tenant.tenant_id,
            app_id=str(uuid.uuid4()),
            pricing_id=str(uuid.uuid4()),
            razorpay_subscription_id='sub_TestSubscription123',
            subscription_start_date=datetime.utcnow(),
            status='pending'
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Test activation webhook
        payload = {
            'subscription': {
                'id': 'sub_TestSubscription123',
                'status': 'active'
            }
        }
        
        result = self.service.process_subscription_webhook(
            event_type='subscription.activated',
            payload=payload,
            db=self.db
        )
        
        self.assertTrue(result)
        self.db.refresh(subscription)
        self.assertEqual(subscription.status, 'active')
        
        # Test charged webhook
        payload['subscription']['charge_at'] = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        
        result = self.service.process_subscription_webhook(
            event_type='subscription.charged',
            payload=payload,
            db=self.db
        )
        
        self.assertTrue(result)
        self.db.refresh(subscription)
        self.assertIsNotNone(subscription.next_billing_date)
        
        # Test cancellation webhook
        result = self.service.process_subscription_webhook(
            event_type='subscription.cancelled',
            payload=payload,
            db=self.db
        )
        
        self.assertTrue(result)
        self.db.refresh(subscription)
        self.assertEqual(subscription.status, 'cancelled')
        
        # Clean up
        self.db.delete(subscription)
        self.db.commit()
    
    def test_process_payment_webhook(self):
        """Test processing payment webhooks"""
        # Create test invoice
        invoice = ApplicationInvoice(
            invoice_id=str(uuid.uuid4()),
            tenant_id=self.test_tenant.tenant_id,
            app_id=str(uuid.uuid4()),
            invoice_number='INV-TEST-0001',
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=30),
            billing_period_end=datetime.utcnow(),
            subtotal=Decimal('100.00'),
            total_amount=Decimal('100.00'),
            currency='USD',
            razorpay_invoice_id='inv_TestInvoice123',
            payment_status='pending'
        )
        self.db.add(invoice)
        self.db.commit()
        
        # Test payment captured webhook
        payload = {
            'payment': {
                'id': 'pay_TestPayment123',
                'invoice_id': 'inv_TestInvoice123',
                'status': 'captured',
                'amount': 10000
            }
        }
        
        result = self.service.process_payment_webhook(
            event_type='payment.captured',
            payload=payload,
            db=self.db
        )
        
        self.assertTrue(result)
        self.db.refresh(invoice)
        self.assertEqual(invoice.payment_status, 'paid')
        self.assertEqual(invoice.razorpay_payment_id, 'pay_TestPayment123')
        self.assertIsNotNone(invoice.payment_date)
        
        # Clean up
        self.db.delete(invoice)
        self.db.commit()
    
    def test_create_invoice_for_charges(self):
        """Test creating a one-time invoice"""
        # Mock the API response
        self.mock_client.invoice.create.return_value = {
            'id': 'inv_TestInvoice123',
            'entity': 'invoice',
            'customer_id': 'cust_TestCustomer123',
            'status': 'issued',
            'amount': 5000
        }
        
        # Call the method
        line_items = [{
            'name': 'Usage Charges',
            'description': 'API usage for January',
            'amount': 5000,
            'currency': 'USD',
            'quantity': 1
        }]
        
        invoice = self.service.create_invoice_for_charges(
            customer_id='cust_TestCustomer123',
            amount=5000,
            currency='USD',
            description='Monthly usage charges',
            line_items=line_items
        )
        
        # Verify
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice['id'], 'inv_TestInvoice123')
        self.mock_client.invoice.create.assert_called_once()
    
    def test_fetch_subscription(self):
        """Test fetching subscription details"""
        # Mock the API response
        self.mock_client.subscription.fetch.return_value = {
            'id': 'sub_TestSubscription123',
            'status': 'active',
            'current_start': 1234567890,
            'current_end': 1234567890,
            'charge_at': 1234567890
        }
        
        # Call the method
        subscription = self.service.fetch_subscription('sub_TestSubscription123')
        
        # Verify
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription['id'], 'sub_TestSubscription123')
        self.assertEqual(subscription['status'], 'active')
        self.mock_client.subscription.fetch.assert_called_once_with('sub_TestSubscription123')


if __name__ == "__main__":
    unittest.main()
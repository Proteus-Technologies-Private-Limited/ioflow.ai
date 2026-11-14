"""
Test billing API endpoints
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import json
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from fastapi.testclient import TestClient

from main import app
from db.database import get_db, init_db
from db.models import User, Tenant, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice,
    PricingModel, BillingCycle, CurrencyType
)
from core.security import create_access_token
from utils.crypto_utils import generate_api_key


class TestBillingAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test client and data"""
        init_db()
        cls.client = TestClient(app)
        cls.db = next(get_db())
        
        # Create test tenants
        cls.app_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="AppProviderTenant",
            schema_name="app_provider",
            email_domain="appprovider.test",
            status="active"
        )
        cls.db.add(cls.app_tenant)
        
        cls.consumer_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="ConsumerTenant",
            schema_name="consumer",
            email_domain="consumer.test",
            status="active"
        )
        cls.db.add(cls.consumer_tenant)
        
        # Create test users
        cls.consumer_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Consumer User",
            email="consumer@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.consumer_tenant.tenant_id,
            role=UserRole.PROJECT_OWNER,
            status='A'
        )
        cls.db.add(cls.consumer_user)
        
        cls.admin_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Admin User",
            email="admin@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.app_tenant.tenant_id,
            role=UserRole.ADMIN,
            status='A'
        )
        cls.db.add(cls.admin_user)
        
        # Create test application
        cls.test_app = Application(
            app_id=str(uuid.uuid4()),
            app_name="Billing Test App",
            app_type="tenant",
            tenant_id_owner=cls.app_tenant.tenant_id,
            created_by=cls.admin_user.user_id,
            auth_type="api_key",
            status="active"
        )
        cls.db.add(cls.test_app)
        
        # Create pricing
        cls.test_pricing = ApplicationPricing(
            pricing_id=str(uuid.uuid4()),
            app_id=cls.test_app.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type="per_request",
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            cost_per_kb=Decimal('0.01'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        cls.db.add(cls.test_pricing)
        
        cls.db.commit()
        
        # Create access tokens
        cls.consumer_token = create_access_token(
            data={"sub": cls.consumer_user.email}
        )
        cls.admin_token = create_access_token(
            data={"sub": cls.admin_user.email}
        )
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Delete in order of dependencies
        cls.db.query(ApplicationInvoice).filter(
            ApplicationInvoice.tenant_id == cls.consumer_tenant.tenant_id
        ).delete()
        cls.db.query(ExecutionCostLog).filter(
            ExecutionCostLog.tenant_id == cls.consumer_tenant.tenant_id
        ).delete()
        cls.db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.tenant_id == cls.consumer_tenant.tenant_id
        ).delete()
        cls.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(Application).filter(
            Application.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(User).filter(
            User.user_id.in_([cls.consumer_user.user_id, cls.admin_user.user_id])
        ).delete()
        cls.db.query(Tenant).filter(
            Tenant.tenant_id.in_([cls.app_tenant.tenant_id, cls.consumer_tenant.tenant_id])
        ).delete()
        cls.db.commit()
        cls.db.close()
    
    def test_subscribe_to_application(self):
        """Test subscribing to an application"""
        subscription_data = {
            "pricing_id": str(self.test_pricing.pricing_id),
            "webhook_url": "https://consumer.test/webhook",
            "auth_credentials": {"api_key": "test-key-123"}
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/subscribe",
            json=subscription_data,
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("subscription_id", data)
        self.assertEqual(data["status"], "active")  # Pay-per-use activates immediately
        self.assertIn("invocation_api_key", data)
        
        # Store for other tests
        self.subscription_id = data["subscription_id"]
        
        # Clean up
        self.db.query(TenantApplicationSubscription).filter(
            TenantApplicationSubscription.subscription_id == self.subscription_id
        ).delete()
        self.db.commit()
    
    def test_subscribe_duplicate_fails(self):
        """Test that duplicate subscription fails"""
        # Create first subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=self.test_pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active',
            invocation_api_key=generate_api_key()
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Try to subscribe again
        subscription_data = {
            "pricing_id": str(self.test_pricing.pricing_id),
            "webhook_url": "https://consumer.test/webhook"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/subscribe",
            json=subscription_data,
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("already subscribed", response.json()["detail"].lower())
        
        # Clean up
        self.db.delete(subscription)
        self.db.commit()
    
    def test_unsubscribe_from_application(self):
        """Test unsubscribing from an application"""
        # Create subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=self.test_pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active',
            invocation_api_key=generate_api_key()
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Unsubscribe
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/unsubscribe",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify subscription is cancelled
        self.db.refresh(subscription)
        self.assertEqual(subscription.status, 'cancelled')
        
        # Clean up
        self.db.delete(subscription)
        self.db.commit()
    
    def test_get_tenant_subscriptions(self):
        """Test getting tenant subscriptions"""
        # Create subscriptions
        sub1 = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=self.test_pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active',
            invocation_api_key=generate_api_key()
        )
        self.db.add(sub1)
        
        # Create another app and subscription
        app2 = Application(
            app_id=str(uuid.uuid4()),
            app_name="Another App",
            app_type="tenant",
            tenant_id_owner=self.app_tenant.tenant_id,
            created_by=self.admin_user.user_id,
            auth_type="api_key",
            status="active"
        )
        self.db.add(app2)
        
        pricing2 = ApplicationPricing(
            app_id=app2.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing2)
        
        sub2 = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app2.app_id,
            pricing_id=pricing2.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='pending',
            invocation_api_key=generate_api_key()
        )
        self.db.add(sub2)
        self.db.commit()
        
        # Get all subscriptions
        response = self.client.get(
            "/api/v1/tenant/subscriptions",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        
        # Get only active subscriptions
        response = self.client.get(
            "/api/v1/tenant/subscriptions?status=active",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "active")
        
        # Clean up
        self.db.delete(sub2)
        self.db.delete(sub1)
        self.db.delete(pricing2)
        self.db.delete(app2)
        self.db.commit()
    
    def test_get_usage_costs(self):
        """Test getting usage cost summary"""
        # Create some execution cost logs
        for i in range(5):
            log = ExecutionCostLog(
                execution_id=str(uuid.uuid4()),
                app_id=self.test_app.app_id,
                tenant_id=self.consumer_tenant.tenant_id,
                flow_id=str(uuid.uuid4()),
                flow_name=f"Test Flow {i}",
                trigger_type="webhook",
                incoming_event_count=1,
                outgoing_service_count=2,
                incoming_event_cost=Decimal('0.10'),
                outgoing_service_cost=Decimal('0.40'),
                data_transfer_kb=10 * (i + 1),
                data_transfer_cost=Decimal(str(0.1 * (i + 1))),
                total_cost=Decimal('0.50') + Decimal(str(0.1 * (i + 1))),
                currency=CurrencyType.USD.value,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            self.db.add(log)
        self.db.commit()
        
        # Get usage costs
        response = self.client.get(
            "/api/v1/tenant/usage-costs",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_executions"], 5)
        self.assertEqual(data["incoming_events"], 5)
        self.assertEqual(data["outgoing_services"], 10)
        self.assertIn("cost_breakdown", data)
        
        # Test with date filter
        start_date = (datetime.utcnow() - timedelta(days=2)).isoformat()
        response = self.client.get(
            f"/api/v1/tenant/usage-costs?start_date={start_date}",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_executions"], 3)  # Only last 3 days
    
    def test_get_execution_cost(self):
        """Test getting cost for specific execution"""
        # Create cost log
        execution_id = str(uuid.uuid4())
        log = ExecutionCostLog(
            execution_id=execution_id,
            app_id=self.test_app.app_id,
            tenant_id=self.consumer_tenant.tenant_id,
            flow_id=str(uuid.uuid4()),
            flow_name="Test Flow",
            trigger_type="api_call",
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
        self.db.add(log)
        self.db.commit()
        
        # Get execution cost
        response = self.client.get(
            f"/api/v1/executions/{execution_id}/cost",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["execution_id"], execution_id)
        self.assertEqual(float(data["total_cost"]), 2.70)
        self.assertIn("cost_breakdown", data)
        self.assertEqual(float(data["cost_breakdown"]["incoming_events"]), 0.10)
    
    def test_get_invoices(self):
        """Test getting tenant invoices"""
        # Create subscription for invoice
        subscription = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=self.test_pricing.pricing_id,
            subscription_start_date=datetime.utcnow() - timedelta(days=30),
            status='active'
        )
        self.db.add(subscription)
        
        # Create invoices
        invoice1 = ApplicationInvoice(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            subscription_id=subscription.subscription_id,
            invoice_number="INV-2024-0001",
            invoice_date=datetime.utcnow() - timedelta(days=5),
            billing_period_start=datetime.utcnow() - timedelta(days=35),
            billing_period_end=datetime.utcnow() - timedelta(days=5),
            subscription_charges=Decimal('0.00'),
            usage_charges=Decimal('50.00'),
            subtotal=Decimal('50.00'),
            tax_amount=Decimal('0.00'),
            total_amount=Decimal('50.00'),
            currency=CurrencyType.USD.value,
            payment_status='paid',
            payment_date=datetime.utcnow() - timedelta(days=3)
        )
        self.db.add(invoice1)
        
        invoice2 = ApplicationInvoice(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            subscription_id=subscription.subscription_id,
            invoice_number="INV-2024-0002",
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=5),
            billing_period_end=datetime.utcnow(),
            usage_charges=Decimal('25.00'),
            subtotal=Decimal('25.00'),
            tax_amount=Decimal('0.00'),
            total_amount=Decimal('25.00'),
            currency=CurrencyType.USD.value,
            payment_status='pending'
        )
        self.db.add(invoice2)
        self.db.commit()
        
        # Get all invoices
        response = self.client.get(
            "/api/v1/tenant/invoices",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(float(data["total_amount"]), 75.00)
        
        # Get only pending invoices
        response = self.client.get(
            "/api/v1/tenant/invoices?payment_status=pending",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["invoices"][0]["payment_status"], "pending")
        
        # Clean up
        self.db.delete(invoice2)
        self.db.delete(invoice1)
        self.db.delete(subscription)
        self.db.commit()
    
    def test_get_specific_invoice(self):
        """Test getting a specific invoice"""
        # Create invoice
        invoice = ApplicationInvoice(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=self.test_app.app_id,
            invoice_number="INV-TEST-0001",
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=30),
            billing_period_end=datetime.utcnow(),
            usage_charges=Decimal('100.00'),
            usage_details={
                "executions": 50,
                "data_transfer_kb": 1000
            },
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            total_amount=Decimal('110.00'),
            currency=CurrencyType.USD.value,
            payment_status='pending'
        )
        self.db.add(invoice)
        self.db.commit()
        
        # Get invoice
        response = self.client.get(
            f"/api/v1/invoices/{invoice.invoice_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["invoice_number"], "INV-TEST-0001")
        self.assertEqual(float(data["total_amount"]), 110.00)
        self.assertIn("usage_details", data)
        
        # Test access to other tenant's invoice (should fail)
        other_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="OtherTenant",
            schema_name="other",
            email_domain="other.test",
            status="active"
        )
        self.db.add(other_tenant)
        
        other_invoice = ApplicationInvoice(
            tenant_id=other_tenant.tenant_id,
            app_id=self.test_app.app_id,
            invoice_number="INV-OTHER-0001",
            invoice_date=datetime.utcnow(),
            billing_period_start=datetime.utcnow() - timedelta(days=30),
            billing_period_end=datetime.utcnow(),
            subtotal=Decimal('50.00'),
            total_amount=Decimal('50.00'),
            currency=CurrencyType.USD.value
        )
        self.db.add(other_invoice)
        self.db.commit()
        
        response = self.client.get(
            f"/api/v1/invoices/{other_invoice.invoice_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 404)
        
        # Clean up
        self.db.delete(other_invoice)
        self.db.delete(other_tenant)
        self.db.delete(invoice)
        self.db.commit()
    
    def test_subscription_with_missing_pricing(self):
        """Test subscribing with invalid pricing ID"""
        subscription_data = {
            "pricing_id": str(uuid.uuid4()),  # Non-existent pricing
            "webhook_url": "https://consumer.test/webhook"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/subscribe",
            json=subscription_data,
            headers={"Authorization": f"Bearer {self.consumer_token}"}
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("pricing not found", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
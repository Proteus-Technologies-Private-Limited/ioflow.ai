"""
Test pricing API endpoints
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import json
from datetime import datetime
from decimal import Decimal
import uuid
from fastapi.testclient import TestClient

from main import app
from db.database import get_db, init_db
from db.models import User, Tenant, UserRole
from db.application_models import Application
from db.pricing_models import ApplicationPricing, PricingModel, BillingCycle, CurrencyType
from core.security import create_access_token


class TestPricingAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test client and data"""
        init_db()
        cls.client = TestClient(app)
        cls.db = next(get_db())
        
        # Create test tenants
        cls.provider_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="ProviderTenant",
            schema_name="provider_tenant",
            email_domain="provider.test",
            status="active"
        )
        cls.db.add(cls.provider_tenant)
        
        cls.other_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="OtherTenant", 
            schema_name="other_tenant",
            email_domain="other.test",
            status="active"
        )
        cls.db.add(cls.other_tenant)
        
        # Create test users
        cls.provider_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Provider User",
            email="provider@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.provider_tenant.tenant_id,
            role=UserRole.APPLICATION_PROVIDER,
            status='A'
        )
        cls.db.add(cls.provider_user)
        
        cls.admin_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Admin User",
            email="admin@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.provider_tenant.tenant_id,
            role=UserRole.ADMIN,
            status='A'
        )
        cls.db.add(cls.admin_user)
        
        cls.regular_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Regular User",
            email="regular@test.com",
            auth_provider="email",
            pass_wd_sha="hashed",
            tenant_id=cls.other_tenant.tenant_id,
            role=UserRole.PROJECT_OWNER,
            status='A'
        )
        cls.db.add(cls.regular_user)
        
        # Create test application
        cls.test_app = Application(
            app_id=str(uuid.uuid4()),
            app_name="Test Pricing App",
            app_type="tenant",
            tenant_id_owner=cls.provider_tenant.tenant_id,
            created_by=cls.provider_user.user_id,
            auth_type="api_key",
            status="active"
        )
        cls.db.add(cls.test_app)
        
        cls.db.commit()
        
        # Create access tokens
        cls.provider_token = create_access_token(
            data={"sub": cls.provider_user.email}
        )
        cls.admin_token = create_access_token(
            data={"sub": cls.admin_user.email}
        )
        cls.regular_token = create_access_token(
            data={"sub": cls.regular_user.email}
        )
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Delete pricing first
        cls.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == cls.test_app.app_id
        ).delete()
        
        cls.db.query(Application).filter(
            Application.app_id == cls.test_app.app_id
        ).delete()
        cls.db.query(User).filter(
            User.user_id.in_([
                cls.provider_user.user_id,
                cls.admin_user.user_id,
                cls.regular_user.user_id
            ])
        ).delete()
        cls.db.query(Tenant).filter(
            Tenant.tenant_id.in_([
                cls.provider_tenant.tenant_id,
                cls.other_tenant.tenant_id
            ])
        ).delete()
        cls.db.commit()
        cls.db.close()
    
    def test_create_pricing_as_provider(self):
        """Test creating pricing as application provider"""
        pricing_data = {
            "pricing_model": "subscription",
            "billing_cycle": "monthly",
            "base_subscription_cost": 99.99,
            "incoming_event_cost": 0.01,
            "outgoing_service_cost": 0.02,
            "currency": "USD"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            json=pricing_data,
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pricing_id", data)
        self.assertEqual(data["pricing_model"], "subscription")
        self.assertEqual(float(data["base_subscription_cost"]), 99.99)
        
        # Store pricing_id for cleanup
        self.created_pricing_id = data["pricing_id"]
    
    def test_create_pricing_as_admin(self):
        """Test creating pricing as admin"""
        pricing_data = {
            "pricing_model": "pay_per_use",
            "usage_metric_type": "per_request",
            "incoming_event_cost": 0.10,
            "outgoing_service_cost": 0.20,
            "cost_per_kb": 0.01,
            "currency": "INR"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            json=pricing_data,
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["pricing_model"], "pay_per_use")
        self.assertEqual(data["currency"], "INR")
    
    def test_create_pricing_unauthorized(self):
        """Test creating pricing without permission"""
        pricing_data = {
            "pricing_model": "subscription",
            "billing_cycle": "monthly",
            "base_subscription_cost": 99.99,
            "currency": "USD"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            json=pricing_data,
            headers={"Authorization": f"Bearer {self.regular_token}"}
        )
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("permission", response.json()["detail"].lower())
    
    def test_create_pricing_validation_errors(self):
        """Test pricing validation"""
        # Missing required fields for subscription
        pricing_data = {
            "pricing_model": "subscription",
            # Missing billing_cycle and base_subscription_cost
            "currency": "USD"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            json=pricing_data,
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("billing_cycle", response.json()["detail"])
    
    def test_get_pricing(self):
        """Test getting pricing plans"""
        # First create a pricing plan
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('49.99'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        self.db.commit()
        
        # Get pricing
        response = self.client.get(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pricing_plans", data)
        self.assertGreater(len(data["pricing_plans"]), 0)
        
        # Test include_inactive parameter
        pricing.is_active = False
        self.db.commit()
        
        response = self.client.get(
            f"/api/v1/applications/{self.test_app.app_id}/pricing?include_inactive=true",
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        inactive_plans = [p for p in data["pricing_plans"] if not p["is_active"]]
        self.assertGreater(len(inactive_plans), 0)
    
    def test_update_pricing(self):
        """Test updating pricing"""
        # Create pricing
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
        
        # Update pricing
        update_data = {
            "base_subscription_cost": 149.99,
            "incoming_event_cost": 0.05
        }
        
        response = self.client.put(
            f"/api/v1/applications/{self.test_app.app_id}/pricing/{pricing.pricing_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(float(data["base_subscription_cost"]), 149.99)
        self.assertEqual(float(data["incoming_event_cost"]), 0.05)
        
        # Verify in database
        updated_pricing = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.pricing_id == pricing.pricing_id
        ).first()
        self.assertEqual(updated_pricing.base_subscription_cost, Decimal('149.99'))
    
    def test_deactivate_pricing(self):
        """Test deactivating pricing"""
        # Create pricing
        pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.YEARLY.value,
            base_subscription_cost=Decimal('999.00'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        self.db.commit()
        
        # Deactivate
        response = self.client.delete(
            f"/api/v1/applications/{self.test_app.app_id}/pricing/{pricing.pricing_id}",
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify deactivated
        deactivated = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.pricing_id == pricing.pricing_id
        ).first()
        self.assertFalse(deactivated.is_active)
    
    def test_application_not_found(self):
        """Test pricing endpoints with non-existent application"""
        fake_app_id = str(uuid.uuid4())
        
        response = self.client.get(
            f"/api/v1/applications/{fake_app_id}/pricing",
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())
    
    def test_multiple_active_pricing_deactivation(self):
        """Test that creating new active pricing deactivates the old one"""
        # Create first pricing
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
        
        # Create second pricing via API
        pricing_data = {
            "pricing_model": "subscription",
            "billing_cycle": "yearly",
            "base_subscription_cost": 999.00,
            "currency": "USD"
        }
        
        response = self.client.post(
            f"/api/v1/applications/{self.test_app.app_id}/pricing",
            json=pricing_data,
            headers={"Authorization": f"Bearer {self.provider_token}"}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that first pricing is deactivated
        self.db.refresh(pricing1)
        self.assertFalse(pricing1.is_active)
        
        # Check that only one pricing is active
        active_pricings = self.db.query(ApplicationPricing).filter(
            ApplicationPricing.app_id == self.test_app.app_id,
            ApplicationPricing.is_active == True
        ).all()
        self.assertEqual(len(active_pricings), 1)


if __name__ == "__main__":
    unittest.main()
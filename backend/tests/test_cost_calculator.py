"""
Test cost calculator service
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import json

from db.database import get_db, init_db
from db.models import Tenant, User, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, PricingModel, BillingCycle, 
    UsageMetricType, CurrencyType
)
from services.cost_calculator import CostCalculator


class TestCostCalculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database and calculator"""
        init_db()
        cls.db = next(get_db())
        cls.calculator = CostCalculator()
        
        # Create test data
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
        
        # Create pricing
        cls.test_pricing = ApplicationPricing(
            app_id=cls.test_app.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type=UsageMetricType.PER_REQUEST.value,
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            cost_per_kb=Decimal('0.01'),
            cost_per_token=Decimal('0.001'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        cls.db.add(cls.test_pricing)
        
        cls.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Delete cost logs first
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
    
    def test_calculate_execution_cost_basic(self):
        """Test basic cost calculation"""
        total_cost, breakdown = self.calculator.calculate_execution_cost(
            app_id=self.test_app.app_id,
            tenant_id=self.test_tenant.tenant_id,
            incoming_events=2,
            outgoing_services=5,
            data_transfer_kb=100,
            token_count=1000,
            db=self.db
        )
        
        # Verify calculations
        expected_incoming = Decimal('2') * Decimal('0.10')  # 0.20
        expected_outgoing = Decimal('5') * Decimal('0.20')  # 1.00
        expected_data = Decimal('100') * Decimal('0.01')    # 1.00
        expected_tokens = Decimal('1000') * Decimal('0.001') # 1.00
        expected_total = expected_incoming + expected_outgoing + expected_data + expected_tokens  # 3.20
        
        self.assertEqual(total_cost, expected_total)
        self.assertEqual(breakdown['incoming_events'], expected_incoming)
        self.assertEqual(breakdown['outgoing_services'], expected_outgoing)
        self.assertEqual(breakdown['data_transfer'], expected_data)
        self.assertEqual(breakdown['tokens'], expected_tokens)
    
    def test_calculate_cost_no_pricing(self):
        """Test calculation when no pricing is defined"""
        # Create app without pricing
        app_no_pricing = Application(
            app_id=str(uuid.uuid4()),
            app_name="No Pricing App",
            app_type="tenant",
            tenant_id_owner=self.test_tenant.tenant_id,
            created_by=self.test_user.user_id,
            auth_type="api_key",
            status="active"
        )
        self.db.add(app_no_pricing)
        self.db.commit()
        
        total_cost, breakdown = self.calculator.calculate_execution_cost(
            app_id=app_no_pricing.app_id,
            tenant_id=self.test_tenant.tenant_id,
            incoming_events=10,
            outgoing_services=20,
            db=self.db
        )
        
        self.assertEqual(total_cost, Decimal('0'))
        self.assertEqual(breakdown, {})
        
        # Cleanup
        self.db.delete(app_no_pricing)
        self.db.commit()
    
    def test_subscription_no_usage_cost(self):
        """Test that subscription model with active subscription has no usage cost"""
        # Create subscription pricing
        sub_pricing = ApplicationPricing(
            app_id=self.test_app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            currency=CurrencyType.USD.value,
            is_active=False  # Deactivate the pay-per-use pricing
        )
        self.db.add(sub_pricing)
        
        # Deactivate pay-per-use pricing and activate subscription
        self.test_pricing.is_active = False
        sub_pricing.is_active = True
        
        # Create active subscription
        subscription = TenantApplicationSubscription(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            pricing_id=sub_pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active'
        )
        self.db.add(subscription)
        self.db.commit()
        
        # Calculate cost - should be 0 for subscription
        total_cost, breakdown = self.calculator.calculate_execution_cost(
            app_id=self.test_app.app_id,
            tenant_id=self.test_tenant.tenant_id,
            incoming_events=10,
            outgoing_services=20,
            db=self.db
        )
        
        self.assertEqual(total_cost, Decimal('0'))
        self.assertIn('subscription_covered', breakdown)
        
        # Cleanup
        self.db.delete(subscription)
        self.db.delete(sub_pricing)
        self.test_pricing.is_active = True
        self.db.commit()
    
    def test_create_cost_log(self):
        """Test creating a cost log entry"""
        execution_id = str(uuid.uuid4())
        flow_id = str(uuid.uuid4())
        
        cost_log = self.calculator.create_cost_log(
            execution_id=execution_id,
            app_id=self.test_app.app_id,
            tenant_id=self.test_tenant.tenant_id,
            flow_id=flow_id,
            flow_name="Test Flow",
            trigger_type="webhook",
            incoming_events=1,
            outgoing_services=3,
            data_transfer_kb=50,
            token_count=500,
            db=self.db
        )
        
        self.assertIsNotNone(cost_log)
        self.assertEqual(cost_log.execution_id, execution_id)
        self.assertEqual(cost_log.incoming_event_count, 1)
        self.assertEqual(cost_log.outgoing_service_count, 3)
        
        # Verify cost calculation
        expected_total = (
            Decimal('1') * Decimal('0.10') +    # incoming
            Decimal('3') * Decimal('0.20') +    # outgoing
            Decimal('50') * Decimal('0.01') +   # data
            Decimal('500') * Decimal('0.001')   # tokens
        )  # 0.10 + 0.60 + 0.50 + 0.50 = 1.70
        
        self.assertEqual(cost_log.total_cost, expected_total)
        
        # Cleanup is handled by tearDownClass
    
    def test_estimate_data_transfer(self):
        """Test data transfer estimation"""
        # Small object
        small_data = {"key": "value", "number": 123}
        small_kb = self.calculator.estimate_data_transfer_kb(small_data)
        self.assertEqual(small_kb, 1)  # Should round up to 1 KB
        
        # Larger object
        large_data = {
            "items": [{"id": i, "data": "x" * 100} for i in range(100)]
        }
        large_kb = self.calculator.estimate_data_transfer_kb(large_data)
        self.assertGreater(large_kb, 10)  # Should be more than 10 KB
        
        # Empty data
        empty_kb = self.calculator.estimate_data_transfer_kb({})
        self.assertEqual(empty_kb, 1)  # Minimum 1 KB
    
    def test_count_llm_tokens(self):
        """Test LLM token counting estimation"""
        # Short text
        short_text = "Hello, world!"
        short_tokens = self.calculator.count_llm_tokens(short_text)
        self.assertGreater(short_tokens, 0)
        self.assertLess(short_tokens, 10)
        
        # Longer text
        long_text = "This is a much longer text that should result in more tokens. " * 10
        long_tokens = self.calculator.count_llm_tokens(long_text)
        self.assertGreater(long_tokens, short_tokens)
        
        # Empty text
        empty_tokens = self.calculator.count_llm_tokens("")
        self.assertEqual(empty_tokens, 0)
    
    def test_get_tenant_usage_summary(self):
        """Test getting usage summary for a tenant"""
        # Create some cost logs
        for i in range(3):
            cost_log = ExecutionCostLog(
                execution_id=str(uuid.uuid4()),
                app_id=self.test_app.app_id,
                tenant_id=self.test_tenant.tenant_id,
                flow_id=str(uuid.uuid4()),
                flow_name=f"Flow {i}",
                trigger_type="api_call",
                incoming_event_count=1,
                outgoing_service_count=2,
                incoming_event_cost=Decimal('0.10'),
                outgoing_service_cost=Decimal('0.40'),
                data_transfer_kb=10,
                data_transfer_cost=Decimal('0.10'),
                token_count=100,
                token_cost=Decimal('0.10'),
                total_cost=Decimal('0.70'),
                currency=CurrencyType.USD.value,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            self.db.add(cost_log)
        self.db.commit()
        
        # Get summary
        summary = self.calculator.get_tenant_usage_summary(
            tenant_id=self.test_tenant.tenant_id,
            app_id=self.test_app.app_id,
            db=self.db
        )
        
        self.assertEqual(summary['total_executions'], 3)
        self.assertEqual(summary['total_cost'], Decimal('2.10'))  # 3 * 0.70
        self.assertEqual(summary['incoming_events'], 3)
        self.assertEqual(summary['outgoing_services'], 6)
        self.assertEqual(summary['data_transfer_kb'], 30)
        self.assertEqual(summary['tokens_used'], 300)
        self.assertEqual(summary['currency'], 'USD')
        
        # Test with date filter
        start_date = datetime.utcnow() - timedelta(days=1)
        filtered_summary = self.calculator.get_tenant_usage_summary(
            tenant_id=self.test_tenant.tenant_id,
            start_date=start_date,
            db=self.db
        )
        
        self.assertEqual(filtered_summary['total_executions'], 2)  # Only last 2 days
    
    def test_should_track_cost(self):
        """Test checking if cost tracking is enabled"""
        # App with pricing should track
        should_track = self.calculator.should_track_cost(
            app_id=self.test_app.app_id,
            db=self.db
        )
        self.assertTrue(should_track)
        
        # Non-existent app should not track
        should_not_track = self.calculator.should_track_cost(
            app_id=str(uuid.uuid4()),
            db=self.db
        )
        self.assertFalse(should_not_track)
        
        # App with inactive pricing should not track
        self.test_pricing.is_active = False
        self.db.commit()
        
        should_not_track_inactive = self.calculator.should_track_cost(
            app_id=self.test_app.app_id,
            db=self.db
        )
        self.assertFalse(should_not_track_inactive)
        
        # Restore
        self.test_pricing.is_active = True
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
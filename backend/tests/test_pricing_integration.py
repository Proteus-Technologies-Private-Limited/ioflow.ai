"""
Integration test for end-to-end pricing and billing flow
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import json

from db.database import get_db, init_db, get_tenant_db
from db.models import User, Tenant, UserRole, Flow, FlowExecution
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice,
    PricingModel, BillingCycle, CurrencyType
)
from services.cost_calculator import cost_calculator
from services.billing_service import billing_service
from services.execution_engine import ExecutionEngine
from core.security import get_password_hash


class TestPricingIntegration(unittest.TestCase):
    """Test complete pricing flow from setup to invoice generation"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        init_db()
        cls.db = next(get_db())
        
        # Create provider tenant and user
        cls.provider_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="IntegrationProvider",
            schema_name="integration_provider",
            email_domain="provider.integration",
            status="active"
        )
        cls.db.add(cls.provider_tenant)
        
        cls.provider_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Integration Provider",
            email="provider@integration.test",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password"),
            tenant_id=cls.provider_tenant.tenant_id,
            role=UserRole.APPLICATION_PROVIDER,
            status='A'
        )
        cls.db.add(cls.provider_user)
        
        # Create consumer tenant and user
        cls.consumer_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="IntegrationConsumer",
            schema_name="integration_consumer",
            email_domain="consumer.integration",
            status="active"
        )
        cls.db.add(cls.consumer_tenant)
        
        cls.consumer_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Integration Consumer",
            email="consumer@integration.test",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password"),
            tenant_id=cls.consumer_tenant.tenant_id,
            role=UserRole.PROJECT_OWNER,
            status='A'
        )
        cls.db.add(cls.consumer_user)
        
        cls.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Clean up in reverse order of dependencies
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
            ApplicationPricing.app_id.in_([
                app.app_id for app in cls.db.query(Application).filter(
                    Application.tenant_id_owner == cls.provider_tenant.tenant_id
                ).all()
            ])
        ).delete()
        cls.db.query(Application).filter(
            Application.tenant_id_owner == cls.provider_tenant.tenant_id
        ).delete()
        cls.db.query(User).filter(
            User.user_id.in_([cls.provider_user.user_id, cls.consumer_user.user_id])
        ).delete()
        cls.db.query(Tenant).filter(
            Tenant.tenant_id.in_([cls.provider_tenant.tenant_id, cls.consumer_tenant.tenant_id])
        ).delete()
        cls.db.commit()
        cls.db.close()
    
    def test_complete_pricing_flow(self):
        """Test the complete flow from app creation to billing"""
        
        # Step 1: Provider creates an application
        app = Application(
            app_id=str(uuid.uuid4()),
            app_name="Integration Test App",
            app_type="tenant",
            description="App for integration testing",
            tenant_id_owner=self.provider_tenant.tenant_id,
            created_by=self.provider_user.user_id,
            auth_type="api_key",
            status="active",
            category="analytics"
        )
        self.db.add(app)
        self.db.commit()
        
        print(f"✓ Step 1: Created application '{app.app_name}'")
        
        # Step 2: Provider sets up pricing
        pricing = ApplicationPricing(
            app_id=app.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type="per_request",
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            cost_per_kb=Decimal('0.01'),
            cost_per_token=Decimal('0.001'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing)
        self.db.commit()
        
        print(f"✓ Step 2: Set up pay-per-use pricing")
        
        # Step 3: Consumer subscribes to the application
        subscription = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app.app_id,
            pricing_id=pricing.pricing_id,
            subscription_start_date=datetime.utcnow(),
            status='active',
            invocation_api_key='test-integration-key-123',
            webhook_url='https://consumer.test/webhook',
            auth_credentials={'api_key': 'consumer-secret-key'}
        )
        self.db.add(subscription)
        self.db.commit()
        
        print(f"✓ Step 3: Consumer subscribed to application")
        
        # Step 4: Simulate flow executions that use the application
        total_executions = 5
        total_cost = Decimal('0')
        
        for i in range(total_executions):
            # Create execution cost log
            execution_id = str(uuid.uuid4())
            flow_id = str(uuid.uuid4())
            
            # Simulate varying usage
            incoming_events = 1
            outgoing_services = 2 + i  # Increasing service calls
            data_kb = 50 * (i + 1)  # Increasing data
            tokens = 1000 * (i + 1)  # Increasing token usage
            
            # Calculate costs
            exec_total, breakdown = cost_calculator.calculate_execution_cost(
                app_id=app.app_id,
                tenant_id=self.consumer_tenant.tenant_id,
                incoming_events=incoming_events,
                outgoing_services=outgoing_services,
                data_transfer_kb=data_kb,
                token_count=tokens,
                db=self.db
            )
            
            # Create cost log
            cost_log = cost_calculator.create_cost_log(
                execution_id=execution_id,
                app_id=app.app_id,
                tenant_id=self.consumer_tenant.tenant_id,
                flow_id=flow_id,
                flow_name=f"Test Flow {i+1}",
                trigger_type="webhook",
                incoming_events=incoming_events,
                outgoing_services=outgoing_services,
                data_transfer_kb=data_kb,
                token_count=tokens,
                db=self.db
            )
            
            total_cost += exec_total
            print(f"  - Execution {i+1}: ${exec_total:.2f} "
                  f"(events: {incoming_events}, services: {outgoing_services}, "
                  f"data: {data_kb}KB, tokens: {tokens})")
        
        print(f"✓ Step 4: Simulated {total_executions} executions, total cost: ${total_cost:.2f}")
        
        # Step 5: Get usage summary
        usage_summary = cost_calculator.get_tenant_usage_summary(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app.app_id,
            db=self.db
        )
        
        self.assertEqual(usage_summary['total_executions'], total_executions)
        self.assertEqual(usage_summary['total_cost'], total_cost)
        
        print(f"✓ Step 5: Usage summary retrieved")
        print(f"  - Total executions: {usage_summary['total_executions']}")
        print(f"  - Total cost: ${usage_summary['total_cost']:.2f}")
        print(f"  - Incoming events: {usage_summary['incoming_events']}")
        print(f"  - Outgoing services: {usage_summary['outgoing_services']}")
        print(f"  - Data transfer: {usage_summary['data_transfer_kb']}KB")
        print(f"  - Tokens used: {usage_summary['tokens_used']}")
        
        # Step 6: Generate invoice
        billing_start = datetime.utcnow() - timedelta(days=30)
        billing_end = datetime.utcnow()
        
        invoice = billing_service._generate_invoice_for_subscription(
            subscription=subscription,
            billing_start=billing_start,
            billing_end=billing_end,
            db=self.db
        )
        
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.usage_charges, total_cost)
        self.assertEqual(invoice.total_amount, total_cost)  # No subscription fee
        
        print(f"✓ Step 6: Invoice generated")
        print(f"  - Invoice #: {invoice.invoice_number}")
        print(f"  - Usage charges: ${invoice.usage_charges:.2f}")
        print(f"  - Total amount: ${invoice.total_amount:.2f}")
        print(f"  - Status: {invoice.payment_status}")
        
        # Step 7: Verify cost tracking disabled after pricing deactivation
        pricing.is_active = False
        self.db.commit()
        
        should_track = cost_calculator.should_track_cost(app.app_id, self.db)
        self.assertFalse(should_track)
        
        print(f"✓ Step 7: Cost tracking disabled after pricing deactivation")
        
        # Step 8: Test subscription-based pricing
        sub_pricing = ApplicationPricing(
            app_id=app.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            incoming_event_cost=Decimal('0'),  # No usage charges
            outgoing_service_cost=Decimal('0'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(sub_pricing)
        self.db.commit()
        
        # Update subscription to use new pricing
        subscription.pricing_id = sub_pricing.pricing_id
        self.db.commit()
        
        # Calculate cost with subscription - should be 0 (covered by subscription)
        sub_cost, sub_breakdown = cost_calculator.calculate_execution_cost(
            app_id=app.app_id,
            tenant_id=self.consumer_tenant.tenant_id,
            incoming_events=10,
            outgoing_services=20,
            db=self.db
        )
        
        self.assertEqual(sub_cost, Decimal('0'))
        self.assertIn('subscription_covered', sub_breakdown)
        
        print(f"✓ Step 8: Subscription pricing tested - usage covered by subscription")
        
        print("\n✅ Integration test completed successfully!")
    
    def test_multiple_app_billing(self):
        """Test billing with multiple applications"""
        
        # Create two applications with different pricing models
        app1 = Application(
            app_id=str(uuid.uuid4()),
            app_name="Subscription App",
            app_type="tenant",
            tenant_id_owner=self.provider_tenant.tenant_id,
            created_by=self.provider_user.user_id,
            auth_type="api_key",
            status="active"
        )
        self.db.add(app1)
        
        app2 = Application(
            app_id=str(uuid.uuid4()),
            app_name="Usage App",
            app_type="tenant",
            tenant_id_owner=self.provider_tenant.tenant_id,
            created_by=self.provider_user.user_id,
            auth_type="oauth2",
            status="active"
        )
        self.db.add(app2)
        
        # Set up different pricing
        pricing1 = ApplicationPricing(
            app_id=app1.app_id,
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('49.99'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing1)
        
        pricing2 = ApplicationPricing(
            app_id=app2.app_id,
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type="per_request",
            incoming_event_cost=Decimal('0.25'),
            outgoing_service_cost=Decimal('0.50'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing2)
        
        # Subscribe to both
        sub1 = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app1.app_id,
            pricing_id=pricing1.pricing_id,
            subscription_start_date=datetime.utcnow() - timedelta(days=15),
            status='active'
        )
        self.db.add(sub1)
        
        sub2 = TenantApplicationSubscription(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app2.app_id,
            pricing_id=pricing2.pricing_id,
            subscription_start_date=datetime.utcnow() - timedelta(days=10),
            status='active'
        )
        self.db.add(sub2)
        
        self.db.commit()
        
        # Generate usage for app2
        for i in range(3):
            cost_calculator.create_cost_log(
                execution_id=str(uuid.uuid4()),
                app_id=app2.app_id,
                tenant_id=self.consumer_tenant.tenant_id,
                flow_id=str(uuid.uuid4()),
                flow_name=f"Multi-app Flow {i+1}",
                trigger_type="api_call",
                incoming_events=2,
                outgoing_services=4,
                db=self.db
            )
        
        # Get combined usage summary
        total_summary = cost_calculator.get_tenant_usage_summary(
            tenant_id=self.consumer_tenant.tenant_id,
            db=self.db
        )
        
        app2_summary = cost_calculator.get_tenant_usage_summary(
            tenant_id=self.consumer_tenant.tenant_id,
            app_id=app2.app_id,
            db=self.db
        )
        
        print(f"\n✓ Multiple app billing test:")
        print(f"  - App1 (Subscription): ${pricing1.base_subscription_cost}/month")
        print(f"  - App2 (Usage): {app2_summary['total_executions']} executions, "
              f"${app2_summary['total_cost']:.2f} total")
        print(f"  - Combined usage cost: ${total_summary['total_cost']:.2f}")
        
        self.assertGreater(app2_summary['total_cost'], Decimal('0'))
        self.assertEqual(
            total_summary['total_cost'],
            app2_summary['total_cost']  # App1 is subscription, no usage cost
        )


if __name__ == "__main__":
    unittest.main(verbose=2)
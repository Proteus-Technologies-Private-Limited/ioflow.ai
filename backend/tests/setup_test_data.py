"""
Setup test data for pricing and billing tests
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import uuid
from decimal import Decimal

from db.database import get_db, init_db
from db.models import User, Tenant, UserRole
from db.application_models import Application
from db.pricing_models import (
    ApplicationPricing, TenantApplicationSubscription,
    ExecutionCostLog, ApplicationInvoice,
    PricingModel, BillingCycle, UsageMetricType, CurrencyType
)
from core.security import get_password_hash
from sqlalchemy.orm import Session


class TestDataSetup:
    def __init__(self):
        self.db = next(get_db())
        self.test_ids = {}
    
    def cleanup_test_data(self):
        """Clean up any existing test data"""
        try:
            # Delete in order of dependencies
            self.db.query(ApplicationInvoice).filter(
                ApplicationInvoice.tenant_id.in_([
                    self.test_ids.get('tenant1_id', ''),
                    self.test_ids.get('tenant2_id', '')
                ])
            ).delete()
            
            self.db.query(ExecutionCostLog).filter(
                ExecutionCostLog.tenant_id.in_([
                    self.test_ids.get('tenant1_id', ''),
                    self.test_ids.get('tenant2_id', '')
                ])
            ).delete()
            
            self.db.query(TenantApplicationSubscription).filter(
                TenantApplicationSubscription.tenant_id.in_([
                    self.test_ids.get('tenant1_id', ''),
                    self.test_ids.get('tenant2_id', '')
                ])
            ).delete()
            
            self.db.query(ApplicationPricing).filter(
                ApplicationPricing.app_id.in_([
                    self.test_ids.get('app1_id', ''),
                    self.test_ids.get('app2_id', '')
                ])
            ).delete()
            
            # Delete test applications
            self.db.query(Application).filter(
                Application.app_id.in_([
                    self.test_ids.get('app1_id', ''),
                    self.test_ids.get('app2_id', '')
                ])
            ).delete()
            
            # Delete test users
            self.db.query(User).filter(
                User.email.in_([
                    'provider@test.com',
                    'tenant1@test.com',
                    'tenant2@test.com',
                    'admin@test.com'
                ])
            ).delete()
            
            # Delete test tenants
            self.db.query(Tenant).filter(
                Tenant.tenant_name.in_(['TestProvider', 'TestTenant1', 'TestTenant2'])
            ).delete()
            
            self.db.commit()
            print("Cleaned up existing test data")
        except Exception as e:
            print(f"Error cleaning up: {e}")
            self.db.rollback()
    
    def create_test_tenants(self):
        """Create test tenants"""
        # Provider tenant
        provider_tenant = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="TestProvider",
            schema_name="test_provider",
            email_domain="provider.test",
            status="active"
        )
        self.db.add(provider_tenant)
        self.test_ids['provider_tenant_id'] = provider_tenant.tenant_id
        
        # Consumer tenant 1
        tenant1 = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="TestTenant1",
            schema_name="test_tenant1",
            email_domain="tenant1.test",
            status="active"
        )
        self.db.add(tenant1)
        self.test_ids['tenant1_id'] = tenant1.tenant_id
        
        # Consumer tenant 2
        tenant2 = Tenant(
            tenant_id=str(uuid.uuid4()),
            tenant_name="TestTenant2",
            schema_name="test_tenant2",
            email_domain="tenant2.test",
            status="active"
        )
        self.db.add(tenant2)
        self.test_ids['tenant2_id'] = tenant2.tenant_id
        
        self.db.commit()
        print("Created test tenants")
    
    def create_test_users(self):
        """Create test users with different roles"""
        # Application provider user
        provider_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Test Provider",
            email="provider@test.com",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password123"),
            tenant_id=self.test_ids['provider_tenant_id'],
            role=UserRole.APPLICATION_PROVIDER,
            is_active=True,
            status='A'
        )
        self.db.add(provider_user)
        self.test_ids['provider_user_id'] = provider_user.user_id
        
        # Tenant 1 project owner
        tenant1_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Tenant1 Owner",
            email="tenant1@test.com",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password123"),
            tenant_id=self.test_ids['tenant1_id'],
            role=UserRole.PROJECT_OWNER,
            is_active=True,
            status='A'
        )
        self.db.add(tenant1_user)
        self.test_ids['tenant1_user_id'] = tenant1_user.user_id
        
        # Tenant 2 project owner
        tenant2_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Tenant2 Owner",
            email="tenant2@test.com",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password123"),
            tenant_id=self.test_ids['tenant2_id'],
            role=UserRole.PROJECT_OWNER,
            is_active=True,
            status='A'
        )
        self.db.add(tenant2_user)
        self.test_ids['tenant2_user_id'] = tenant2_user.user_id
        
        # Admin user
        admin_user = User(
            user_id=str(uuid.uuid4()),
            user_name="Admin User",
            email="admin@test.com",
            auth_provider="email",
            pass_wd_sha=get_password_hash("password123"),
            tenant_id=self.test_ids['provider_tenant_id'],
            role=UserRole.ADMIN,
            is_active=True,
            status='A'
        )
        self.db.add(admin_user)
        self.test_ids['admin_user_id'] = admin_user.user_id
        
        self.db.commit()
        print("Created test users")
    
    def create_test_applications(self):
        """Create test applications"""
        # Application 1 - Subscription based
        app1 = Application(
            app_id=str(uuid.uuid4()),
            app_name="TestApp Subscription",
            app_type="tenant",
            description="Test application with subscription pricing",
            tenant_id_owner=self.test_ids['provider_tenant_id'],
            created_by=self.test_ids['provider_user_id'],
            auth_type="api_key",
            status="active",
            category="productivity"
        )
        self.db.add(app1)
        self.test_ids['app1_id'] = app1.app_id
        
        # Application 2 - Usage based
        app2 = Application(
            app_id=str(uuid.uuid4()),
            app_name="TestApp Usage",
            app_type="tenant",
            description="Test application with usage-based pricing",
            tenant_id_owner=self.test_ids['provider_tenant_id'],
            created_by=self.test_ids['provider_user_id'],
            auth_type="oauth2",
            status="active",
            category="analytics"
        )
        self.db.add(app2)
        self.test_ids['app2_id'] = app2.app_id
        
        self.db.commit()
        print("Created test applications")
    
    def create_test_pricing(self):
        """Create test pricing plans"""
        # Subscription pricing for app1
        pricing1 = ApplicationPricing(
            pricing_id=str(uuid.uuid4()),
            app_id=self.test_ids['app1_id'],
            pricing_model=PricingModel.SUBSCRIPTION.value,
            billing_cycle=BillingCycle.MONTHLY.value,
            base_subscription_cost=Decimal('99.00'),
            incoming_event_cost=Decimal('0.01'),
            outgoing_service_cost=Decimal('0.02'),
            cost_per_kb=Decimal('0.001'),
            cost_per_token=Decimal('0.0001'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing1)
        self.test_ids['pricing1_id'] = pricing1.pricing_id
        
        # Usage-based pricing for app2
        pricing2 = ApplicationPricing(
            pricing_id=str(uuid.uuid4()),
            app_id=self.test_ids['app2_id'],
            pricing_model=PricingModel.PAY_PER_USE.value,
            usage_metric_type=UsageMetricType.PER_REQUEST.value,
            incoming_event_cost=Decimal('0.10'),
            outgoing_service_cost=Decimal('0.20'),
            cost_per_kb=Decimal('0.01'),
            cost_per_token=Decimal('0.001'),
            currency=CurrencyType.USD.value,
            is_active=True
        )
        self.db.add(pricing2)
        self.test_ids['pricing2_id'] = pricing2.pricing_id
        
        self.db.commit()
        print("Created test pricing plans")
    
    def create_test_subscriptions(self):
        """Create test subscriptions"""
        # Tenant1 subscribes to App1
        sub1 = TenantApplicationSubscription(
            subscription_id=str(uuid.uuid4()),
            tenant_id=self.test_ids['tenant1_id'],
            app_id=self.test_ids['app1_id'],
            pricing_id=self.test_ids['pricing1_id'],
            subscription_start_date=datetime.utcnow() - timedelta(days=15),
            status='active',
            invocation_api_key='test-api-key-1',
            api_key_created_at=datetime.utcnow() - timedelta(days=15)
        )
        self.db.add(sub1)
        self.test_ids['subscription1_id'] = sub1.subscription_id
        
        # Tenant2 subscribes to App2
        sub2 = TenantApplicationSubscription(
            subscription_id=str(uuid.uuid4()),
            tenant_id=self.test_ids['tenant2_id'],
            app_id=self.test_ids['app2_id'],
            pricing_id=self.test_ids['pricing2_id'],
            subscription_start_date=datetime.utcnow() - timedelta(days=10),
            status='active',
            invocation_api_key='test-api-key-2',
            api_key_created_at=datetime.utcnow() - timedelta(days=10)
        )
        self.db.add(sub2)
        self.test_ids['subscription2_id'] = sub2.subscription_id
        
        self.db.commit()
        print("Created test subscriptions")
    
    def create_test_execution_logs(self):
        """Create test execution cost logs"""
        # Create multiple execution logs for testing
        for i in range(5):
            # Logs for subscription1 (tenant1, app1)
            log1 = ExecutionCostLog(
                cost_log_id=str(uuid.uuid4()),
                execution_id=str(uuid.uuid4()),
                app_id=self.test_ids['app1_id'],
                tenant_id=self.test_ids['tenant1_id'],
                flow_id=str(uuid.uuid4()),
                flow_name=f"Test Flow {i+1}",
                trigger_type="webhook",
                incoming_event_count=1,
                outgoing_service_count=3,
                incoming_event_cost=Decimal('0.01'),
                outgoing_service_cost=Decimal('0.06'),
                data_transfer_kb=100,
                data_transfer_cost=Decimal('0.10'),
                token_count=1000,
                token_cost=Decimal('0.10'),
                total_cost=Decimal('0.27'),
                currency=CurrencyType.USD.value,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            self.db.add(log1)
            
            # Logs for subscription2 (tenant2, app2)
            log2 = ExecutionCostLog(
                cost_log_id=str(uuid.uuid4()),
                execution_id=str(uuid.uuid4()),
                app_id=self.test_ids['app2_id'],
                tenant_id=self.test_ids['tenant2_id'],
                flow_id=str(uuid.uuid4()),
                flow_name=f"Analytics Flow {i+1}",
                trigger_type="api_call",
                incoming_event_count=2,
                outgoing_service_count=5,
                incoming_event_cost=Decimal('0.20'),
                outgoing_service_cost=Decimal('1.00'),
                data_transfer_kb=500,
                data_transfer_cost=Decimal('5.00'),
                token_count=5000,
                token_cost=Decimal('5.00'),
                total_cost=Decimal('11.20'),
                currency=CurrencyType.USD.value,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            self.db.add(log2)
        
        self.db.commit()
        print("Created test execution logs")
    
    def create_test_invoices(self):
        """Create test invoices"""
        # Invoice for tenant1
        invoice1 = ApplicationInvoice(
            invoice_id=str(uuid.uuid4()),
            tenant_id=self.test_ids['tenant1_id'],
            app_id=self.test_ids['app1_id'],
            subscription_id=self.test_ids['subscription1_id'],
            invoice_number="INV-202401-0001",
            invoice_date=datetime.utcnow() - timedelta(days=5),
            billing_period_start=datetime.utcnow() - timedelta(days=35),
            billing_period_end=datetime.utcnow() - timedelta(days=5),
            subscription_charges=Decimal('99.00'),
            usage_charges=Decimal('1.35'),  # 5 executions * 0.27
            usage_details={
                "executions": 5,
                "incoming_events": 5,
                "outgoing_services": 15,
                "data_transfer_kb": 500,
                "tokens_used": 5000
            },
            subtotal=Decimal('100.35'),
            tax_amount=Decimal('0.00'),
            total_amount=Decimal('100.35'),
            currency=CurrencyType.USD.value,
            payment_status='pending'
        )
        self.db.add(invoice1)
        self.test_ids['invoice1_id'] = invoice1.invoice_id
        
        self.db.commit()
        print("Created test invoices")
    
    def setup_all(self):
        """Run all setup methods"""
        print("Setting up test data...")
        self.cleanup_test_data()
        self.create_test_tenants()
        self.create_test_users()
        self.create_test_applications()
        self.create_test_pricing()
        self.create_test_subscriptions()
        self.create_test_execution_logs()
        self.create_test_invoices()
        print("\nTest data setup completed!")
        print(f"Test IDs: {self.test_ids}")
        return self.test_ids


if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Setup test data
    setup = TestDataSetup()
    test_ids = setup.setup_all()
    
    print("\n=== Test Data Summary ===")
    print(f"Provider Tenant ID: {test_ids['provider_tenant_id']}")
    print(f"Tenant 1 ID: {test_ids['tenant1_id']}")
    print(f"Tenant 2 ID: {test_ids['tenant2_id']}")
    print(f"App 1 ID (Subscription): {test_ids['app1_id']}")
    print(f"App 2 ID (Usage-based): {test_ids['app2_id']}")
    print("\nTest credentials:")
    print("- provider@test.com / password123 (APPLICATION_PROVIDER)")
    print("- tenant1@test.com / password123 (PROJECT_OWNER)")
    print("- tenant2@test.com / password123 (PROJECT_OWNER)")
    print("- admin@test.com / password123 (ADMIN)")
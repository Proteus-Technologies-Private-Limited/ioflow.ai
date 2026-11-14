"""
Migration script to add pricing and billing tables
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings


def run_migration():
    """Create pricing and billing tables"""
    engine = create_engine(settings.database_url)
    
    # Check if we're using SQLite or PostgreSQL
    is_sqlite = settings.database_url.startswith("sqlite")
    
    with engine.connect() as conn:
        # Create application_pricing table
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS application_pricing (
                    pricing_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    pricing_model TEXT NOT NULL,
                    billing_cycle TEXT,
                    usage_metric_type TEXT,
                    incoming_event_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
                    outgoing_service_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
                    base_subscription_cost DECIMAL(10,2),
                    cost_per_kb DECIMAL(10,2),
                    cost_per_token DECIMAL(10,2),
                    currency TEXT NOT NULL DEFAULT 'USD',
                    razorpay_plan_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (app_id) REFERENCES applications(app_id),
                    CHECK (incoming_event_cost >= 0),
                    CHECK (outgoing_service_cost >= 0)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ioflow.application_pricing (
                    pricing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    app_id UUID NOT NULL REFERENCES ioflow.applications(app_id),
                    pricing_model VARCHAR(50) NOT NULL,
                    billing_cycle VARCHAR(50),
                    usage_metric_type VARCHAR(50),
                    incoming_event_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
                    outgoing_service_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
                    base_subscription_cost DECIMAL(10,2),
                    cost_per_kb DECIMAL(10,2),
                    cost_per_token DECIMAL(10,2),
                    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                    razorpay_plan_id VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT check_incoming_cost_positive CHECK (incoming_event_cost >= 0),
                    CONSTRAINT check_outgoing_cost_positive CHECK (outgoing_service_cost >= 0)
                )
            """))
        
        # Create tenant_application_subscriptions table
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_application_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    pricing_id TEXT NOT NULL,
                    razorpay_subscription_id TEXT,
                    razorpay_customer_id TEXT,
                    subscription_start_date TIMESTAMP NOT NULL,
                    subscription_end_date TIMESTAMP,
                    next_billing_date TIMESTAMP,
                    total_usage_cost DECIMAL(10,2) DEFAULT 0,
                    last_invoice_id TEXT,
                    auth_credentials TEXT,
                    subscription_config TEXT,
                    webhook_url TEXT,
                    invocation_api_key TEXT UNIQUE,
                    api_key_created_at TIMESTAMP,
                    api_key_last_used_at TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY (app_id) REFERENCES applications(app_id),
                    FOREIGN KEY (pricing_id) REFERENCES application_pricing(pricing_id)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ioflow.tenant_application_subscriptions (
                    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES ioflow.tenants(tenant_id),
                    app_id UUID NOT NULL REFERENCES ioflow.applications(app_id),
                    pricing_id UUID NOT NULL REFERENCES ioflow.application_pricing(pricing_id),
                    razorpay_subscription_id VARCHAR(255),
                    razorpay_customer_id VARCHAR(255),
                    subscription_start_date TIMESTAMP NOT NULL,
                    subscription_end_date TIMESTAMP,
                    next_billing_date TIMESTAMP,
                    total_usage_cost DECIMAL(10,2) DEFAULT 0,
                    last_invoice_id VARCHAR(36),
                    auth_credentials JSONB,
                    subscription_config JSONB,
                    webhook_url VARCHAR(500),
                    invocation_api_key VARCHAR(255) UNIQUE,
                    api_key_created_at TIMESTAMP,
                    api_key_last_used_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        # Create execution_cost_logs table
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS execution_cost_logs (
                    cost_log_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    incoming_event_count INTEGER DEFAULT 0,
                    outgoing_service_count INTEGER DEFAULT 0,
                    incoming_event_cost DECIMAL(10,2) DEFAULT 0,
                    outgoing_service_cost DECIMAL(10,2) DEFAULT 0,
                    data_transfer_kb INTEGER DEFAULT 0,
                    data_transfer_cost DECIMAL(10,2) DEFAULT 0,
                    token_count INTEGER DEFAULT 0,
                    token_cost DECIMAL(10,2) DEFAULT 0,
                    total_cost DECIMAL(10,2) NOT NULL,
                    currency TEXT NOT NULL,
                    flow_id TEXT,
                    flow_name TEXT,
                    trigger_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (app_id) REFERENCES applications(app_id),
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ioflow.execution_cost_logs (
                    cost_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    execution_id VARCHAR(36) NOT NULL,
                    app_id UUID NOT NULL REFERENCES ioflow.applications(app_id),
                    tenant_id UUID NOT NULL REFERENCES ioflow.tenants(tenant_id),
                    incoming_event_count INTEGER DEFAULT 0,
                    outgoing_service_count INTEGER DEFAULT 0,
                    incoming_event_cost DECIMAL(10,2) DEFAULT 0,
                    outgoing_service_cost DECIMAL(10,2) DEFAULT 0,
                    data_transfer_kb INTEGER DEFAULT 0,
                    data_transfer_cost DECIMAL(10,2) DEFAULT 0,
                    token_count INTEGER DEFAULT 0,
                    token_cost DECIMAL(10,2) DEFAULT 0,
                    total_cost DECIMAL(10,2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    flow_id VARCHAR(36),
                    flow_name VARCHAR(255),
                    trigger_type VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        # Create application_invoices table
        if is_sqlite:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS application_invoices (
                    invoice_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    subscription_id TEXT,
                    invoice_number TEXT UNIQUE NOT NULL,
                    invoice_date TIMESTAMP NOT NULL,
                    billing_period_start TIMESTAMP NOT NULL,
                    billing_period_end TIMESTAMP NOT NULL,
                    subscription_charges DECIMAL(10,2) DEFAULT 0,
                    usage_charges DECIMAL(10,2) DEFAULT 0,
                    usage_details TEXT,
                    subtotal DECIMAL(10,2) NOT NULL,
                    tax_amount DECIMAL(10,2) DEFAULT 0,
                    total_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    payment_date TIMESTAMP,
                    razorpay_invoice_id TEXT,
                    razorpay_payment_id TEXT,
                    razorpay_order_id TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY (app_id) REFERENCES applications(app_id),
                    FOREIGN KEY (subscription_id) REFERENCES tenant_application_subscriptions(subscription_id)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ioflow.application_invoices (
                    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES ioflow.tenants(tenant_id),
                    app_id UUID NOT NULL REFERENCES ioflow.applications(app_id),
                    subscription_id UUID REFERENCES ioflow.tenant_application_subscriptions(subscription_id),
                    invoice_number VARCHAR(50) UNIQUE NOT NULL,
                    invoice_date TIMESTAMP NOT NULL,
                    billing_period_start TIMESTAMP NOT NULL,
                    billing_period_end TIMESTAMP NOT NULL,
                    subscription_charges DECIMAL(10,2) DEFAULT 0,
                    usage_charges DECIMAL(10,2) DEFAULT 0,
                    usage_details JSONB,
                    subtotal DECIMAL(10,2) NOT NULL,
                    tax_amount DECIMAL(10,2) DEFAULT 0,
                    total_amount DECIMAL(10,2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    payment_status VARCHAR(20) DEFAULT 'pending',
                    payment_date TIMESTAMP,
                    razorpay_invoice_id VARCHAR(255),
                    razorpay_payment_id VARCHAR(255),
                    razorpay_order_id VARCHAR(255),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        # Create indexes for better performance
        if not is_sqlite:
            # Indexes for application_pricing
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_app_pricing_app_id ON ioflow.application_pricing(app_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_app_pricing_active ON ioflow.application_pricing(is_active)"))
            
            # Indexes for tenant_application_subscriptions
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_subs_tenant_id ON ioflow.tenant_application_subscriptions(tenant_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_subs_app_id ON ioflow.tenant_application_subscriptions(app_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_subs_status ON ioflow.tenant_application_subscriptions(status)"))
            
            # Indexes for execution_cost_logs
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cost_logs_execution_id ON ioflow.execution_cost_logs(execution_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cost_logs_tenant_id ON ioflow.execution_cost_logs(tenant_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cost_logs_app_id ON ioflow.execution_cost_logs(app_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cost_logs_timestamp ON ioflow.execution_cost_logs(timestamp)"))
            
            # Indexes for application_invoices
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoices_tenant_id ON ioflow.application_invoices(tenant_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoices_subscription_id ON ioflow.application_invoices(subscription_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoices_payment_status ON ioflow.application_invoices(payment_status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoices_date ON ioflow.application_invoices(invoice_date)"))
        
        conn.commit()
        print("Successfully created pricing and billing tables")


if __name__ == "__main__":
    run_migration()
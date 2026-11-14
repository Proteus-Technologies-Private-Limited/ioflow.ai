# Application Pricing and Billing System

## Overview

The IOFlow platform now includes a comprehensive pricing and billing system that allows application providers to monetize their applications through subscription-based or usage-based pricing models. The system is integrated with Razorpay for payment processing and subscription management.

## Key Features

### 1. User Roles
- **APPLICATION_PROVIDER**: New role that allows users to create applications and define pricing
- **ADMIN**: Can manage all applications and their pricing
- **PROJECT_OWNER**: Can subscribe to applications for their tenant
- **EXECUTION_MONITOR**: Can view execution costs but cannot manage subscriptions

### 2. Pricing Models

#### Subscription-Based Pricing
- Fixed cost per billing cycle (daily, monthly, yearly)
- Automatic recurring billing through Razorpay
- Prorated charges for partial periods

#### Usage-Based Pricing (Pay-Per-Use)
- Cost per incoming event
- Cost per outgoing service call
- Cost per KB of data transfer
- Cost per token (for LLM usage)

#### Hybrid Model
- Combination of subscription base cost + usage charges
- Subscription covers base usage with additional charges for excess

### 3. Cost Tracking

The system automatically tracks costs during flow execution:

```python
# Tracked metrics:
- incoming_event_count: Number of events that triggered the flow
- outgoing_service_count: Number of external service calls made
- data_transfer_kb: Amount of data transferred (requests + responses)
- token_count: Number of tokens used for LLM calls
```

### 4. Database Schema

#### ApplicationPricing
- Defines pricing rules for an application
- Multiple pricing plans can exist (only one active at a time)
- Linked to Razorpay plan for subscriptions

#### TenantApplicationSubscription
- Tracks which tenants have subscribed to which applications
- Stores subscription details and usage counters
- Includes API key for secure invocations

#### ExecutionCostLog
- Records cost details for each flow execution
- Provides granular cost breakdown
- Used for usage analytics and billing

#### ApplicationInvoice
- Monthly invoices for subscriptions and usage
- Integration with Razorpay for payment collection
- Detailed usage breakdown

## API Endpoints

### Pricing Management (Application Providers)

```bash
# Create pricing for an application
POST /api/v1/applications/{app_id}/pricing
{
  "pricing_model": "subscription",
  "billing_cycle": "monthly",
  "base_subscription_cost": 99.00,
  "incoming_event_cost": 0.01,
  "outgoing_service_cost": 0.02,
  "currency": "USD"
}

# Get pricing plans
GET /api/v1/applications/{app_id}/pricing

# Update pricing
PUT /api/v1/applications/{app_id}/pricing/{pricing_id}

# Deactivate pricing
DELETE /api/v1/applications/{app_id}/pricing/{pricing_id}
```

### Subscription Management (Tenants)

```bash
# Subscribe to an application
POST /api/v1/applications/{app_id}/subscribe
{
  "pricing_id": "pricing-uuid",
  "auth_credentials": {...},
  "webhook_url": "https://myapp.com/webhook"
}

# Cancel subscription
POST /api/v1/applications/{app_id}/unsubscribe

# View subscriptions
GET /api/v1/tenant/subscriptions
```

### Cost & Billing

```bash
# Get usage costs
GET /api/v1/tenant/usage-costs?start_date=2024-01-01&end_date=2024-01-31

# Get execution cost details
GET /api/v1/executions/{execution_id}/cost

# View invoices
GET /api/v1/tenant/invoices

# Get specific invoice
GET /api/v1/invoices/{invoice_id}
```

## Razorpay Integration

### Configuration

Add these environment variables:

```env
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret
```

### Webhook Endpoint

Configure Razorpay to send webhooks to:
```
https://your-domain.com/api/v1/webhooks/razorpay
```

### Supported Events
- subscription.activated
- subscription.charged
- subscription.cancelled
- subscription.paused
- subscription.resumed
- payment.captured
- payment.failed

## Implementation Guide

### 1. Set Up Application Pricing

```python
# As an application provider
pricing = ApplicationPricing(
    app_id=app.app_id,
    pricing_model="subscription",
    billing_cycle="monthly",
    base_subscription_cost=99.00,
    incoming_event_cost=0.01,
    outgoing_service_cost=0.02,
    currency="USD"
)
```

### 2. Subscribe to an Application

```python
# As a tenant
subscription = TenantApplicationSubscription(
    tenant_id=current_user.tenant_id,
    app_id=app_id,
    pricing_id=pricing_id,
    auth_credentials=encrypted_credentials,
    webhook_url="https://mytenant.com/webhook"
)
```

### 3. Cost Tracking During Execution

The execution engine automatically tracks costs:

```python
# Automatic tracking in execution_engine.py
- Incoming events tracked when flow is triggered
- Outgoing services tracked for each action node
- Data transfer calculated from request/response sizes
- Token usage tracked for LLM calls
```

### 4. Monthly Invoice Generation

Run the billing service monthly:

```python
from services.billing_service import billing_service

# Generate invoices for last month
invoices = billing_service.generate_monthly_invoices()
```

## Security Considerations

1. **API Key Authentication**: Each subscription gets a unique API key for invocations
2. **Encrypted Credentials**: Auth credentials are encrypted in the database
3. **Role-Based Access**: Only APPLICATION_PROVIDER can set pricing
4. **Webhook Verification**: Razorpay webhooks are verified using signatures
5. **Tenant Isolation**: Tenants can only see their own subscriptions and costs

## Migration Steps

1. Run database migrations:
```bash
python migrations/add_pricing_tables.py
python migrations/add_application_owner_tenant.py
```

2. Update existing users to assign APPLICATION_PROVIDER role where needed

3. Configure Razorpay credentials in environment

4. Set up webhook endpoint in Razorpay dashboard

5. Create pricing for existing applications

## Best Practices

1. **Pricing Strategy**
   - Start with simple pricing models
   - Monitor usage patterns before setting prices
   - Consider offering free tiers or trials

2. **Cost Optimization**
   - Batch API calls when possible
   - Implement caching to reduce redundant calls
   - Monitor high-usage tenants

3. **Billing Transparency**
   - Provide detailed usage breakdowns
   - Send notifications before billing
   - Offer usage alerts and limits

## Future Enhancements

1. **Pricing Tiers**: Multiple tiers with different features
2. **Discounts**: Volume discounts and promotional codes
3. **Free Trials**: Time-limited or usage-limited trials
4. **Prepaid Credits**: Allow purchasing credits in advance
5. **Multi-Currency**: Automatic currency conversion
6. **Tax Handling**: Automated tax calculation by region
7. **Usage Limits**: Configurable limits with notifications
8. **Cost Alerts**: Notify when usage exceeds thresholds
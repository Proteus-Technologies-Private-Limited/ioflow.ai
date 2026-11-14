# Pricing and Billing System Tests

This directory contains comprehensive tests for the IOFlow pricing and billing system.

## Test Structure

### Unit Tests

1. **test_pricing_models.py** - Tests for database models
   - ApplicationPricing model
   - TenantApplicationSubscription model
   - ExecutionCostLog model
   - ApplicationInvoice model
   - Model constraints and relationships

2. **test_cost_calculator.py** - Tests for cost calculation service
   - Cost calculation for different pricing models
   - Usage tracking (events, services, data, tokens)
   - Cost log creation
   - Usage summaries

3. **test_razorpay_service.py** - Tests for Razorpay integration (mocked)
   - Subscription plan creation
   - Customer management
   - Subscription lifecycle
   - Payment processing
   - Webhook handling

4. **test_billing_service.py** - Tests for billing service
   - Invoice generation
   - Prorated billing
   - Payment processing
   - Invoice summaries

### API Tests

5. **test_pricing_api.py** - Tests for pricing management APIs
   - Create/update/delete pricing
   - Role-based access control
   - Pricing validation

6. **test_billing_api.py** - Tests for billing APIs
   - Subscription management
   - Usage cost retrieval
   - Invoice management
   - Webhook endpoints

### Integration Tests

7. **test_pricing_integration.py** - End-to-end integration tests
   - Complete pricing flow
   - Multi-application billing
   - Cost tracking through execution

### Setup Scripts

8. **setup_test_data.py** - Creates test data
   - Test tenants and users
   - Applications with pricing
   - Subscriptions and usage logs

9. **run_pricing_tests.py** - Test runner script

## Running Tests

### Run All Tests
```bash
python tests/run_pricing_tests.py
```

### Run Specific Test Suite
```bash
# Database models
python tests/run_pricing_tests.py models

# Cost calculator
python tests/run_pricing_tests.py calculator

# Razorpay service
python tests/run_pricing_tests.py razorpay

# Billing service
python tests/run_pricing_tests.py billing

# Pricing API
python tests/run_pricing_tests.py pricing-api

# Billing API
python tests/run_pricing_tests.py billing-api

# Integration tests
python tests/run_pricing_tests.py integration
```

### Set Up Test Data
```bash
# Just set up test data
python tests/run_pricing_tests.py setup

# Run tests with fresh test data
python tests/run_pricing_tests.py --with-setup
```

### Run Individual Test Files
```bash
python tests/test_pricing_models.py
python tests/test_cost_calculator.py
# ... etc
```

## Test Data

The test suite creates the following test data:

### Users
- `provider@test.com` / `password123` - APPLICATION_PROVIDER role
- `tenant1@test.com` / `password123` - PROJECT_OWNER role
- `tenant2@test.com` / `password123` - PROJECT_OWNER role
- `admin@test.com` / `password123` - ADMIN role

### Applications
- **TestApp Subscription** - Subscription-based pricing ($99/month)
- **TestApp Usage** - Usage-based pricing ($0.10/event, $0.20/service)

### Pricing Models
- Subscription: Monthly/Yearly with base cost
- Pay-per-use: Per request/KB/token
- Hybrid: Base subscription + usage charges

## Prerequisites

1. **Database**: PostgreSQL or SQLite configured
2. **Environment Variables**: Set in `.env` file
   ```
   DATABASE_URL=postgresql://user:pass@localhost/ioflow_test
   RAZORPAY_KEY_ID=test_key
   RAZORPAY_KEY_SECRET=test_secret
   RAZORPAY_WEBHOOK_SECRET=test_webhook_secret
   ```

3. **Dependencies**: Install required packages
   ```bash
   pip install -r requirements.txt
   pip install pytest  # Optional, for pytest runner
   ```

## Test Coverage

The test suite covers:

- ✅ Model creation and validation
- ✅ Cost calculation algorithms
- ✅ Subscription management
- ✅ Invoice generation
- ✅ Payment processing (mocked)
- ✅ API endpoints with authentication
- ✅ Role-based access control
- ✅ Webhook handling
- ✅ Error handling
- ✅ Edge cases (prorating, multiple apps, etc.)

## Troubleshooting

### Database Errors
- Ensure database is running and accessible
- Check DATABASE_URL in environment
- Run migrations: `python migrations/add_pricing_tables.py`

### Import Errors
- Add backend directory to Python path
- Run from backend directory: `cd backend && python tests/run_pricing_tests.py`

### Test Failures
- Check test data setup completed successfully
- Verify no conflicting data in database
- Review specific test output for details

## Continuous Integration

For CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Pricing Tests
  run: |
    cd backend
    python migrations/add_pricing_tables.py
    python tests/run_pricing_tests.py --with-setup
```

## Contributing

When adding new pricing features:

1. Add unit tests for new models/services
2. Add API tests for new endpoints
3. Update integration tests if needed
4. Run full test suite before committing
5. Update this README with new test information
# IOFlow Complete Tutorial

## Table of Contents
1. [Introduction](#introduction)
2. [Recent Updates and Features](#recent-updates-and-features)
3. [Synchronous Flows and API Integration](#synchronous-flows-and-api-integration)
4. [Transform Nodes Deep Dive](#transform-nodes-deep-dive)
5. [Flow Designer UI Enhancements](#flow-designer-ui-enhancements)
6. [Complete Examples](#complete-examples)
7. [Advanced Use Cases](#advanced-use-cases)
8. [Troubleshooting Guide](#troubleshooting-guide)

## Introduction

IOFlow is a powerful workflow automation platform that enables you to create complex integrations and automations through a visual flow designer. This tutorial covers all the latest features and improvements, including synchronous API flows, transform nodes with Python scripting, and enhanced UI capabilities.

## Recent Updates and Features

### 1. Synchronous Flow Support
- **API-like Responses**: Flows can now return data synchronously when triggered via API
- **Response Nodes**: Define what data to return from your flow
- **Timeout Control**: Configure execution timeouts for synchronous flows

### 2. Transform Node Implementation
- **Python Scripting**: Write secure Python code to transform data
- **Variable Management**: Local, global, and node output variables
- **Built-in Functions**: String and math operations
- **Loop Support**: Process arrays and collections

### 3. UI/UX Improvements
- **Variable Selection Dropdown**: Easy selection of variables in response nodes
- **Conditional Node Visibility**: Response nodes only appear for synchronous flows
- **Fixed Delete Functionality**: Delete nodes using button or keyboard shortcuts

## Synchronous Flows and API Integration

### Creating a Synchronous API Flow

1. **Enable Synchronous Mode**
   ```
   ☑ Synchronous (in flow header)
   ```

2. **Configure API Trigger**
   ```json
   {
     "trigger_type": "api_call",
     "method": "POST",
     "endpoint": "/api/custom/process-order"
   }
   ```

3. **Add Response Node**
   - Only available when synchronous is enabled
   - Select variable to return or use string literal
   - Configure HTTP status and headers

### Example: Order Processing API

```yaml
Flow: Process Order API
Type: Synchronous
Timeout: 30 seconds

Nodes:
1. API Trigger
   - Accepts: order_data (JSON)
   
2. Transform Node
   - Validate order
   - Calculate totals
   
3. Action Node
   - Save to database
   
4. Response Node
   - Return: {
       "order_id": "{{node_outputs.action_1.order_id}}",
       "status": "processed",
       "total": "{{node_outputs.transform_1.total}}"
     }
```

### Testing Synchronous Flows

```bash
# Test your synchronous flow
curl -X POST https://your-domain/api/v1/flows/execute/sync/{flow_id} \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_items": [
      {"product": "Widget", "quantity": 2, "price": 10.99}
    ],
    "customer_id": "cust_123"
  }'

# Response
{
  "order_id": "ord_456",
  "status": "processed",
  "total": 21.98
}
```

## Transform Nodes Deep Dive

### Basic Transform Script Structure

```python
# Access input data
name = input.get('name', 'Default')

# Use local variables
local['counter'] = 0
local['items'] = []

# Process data
for item in input.get('items', []):
    local['counter'] += 1
    local['items'].append({
        'id': item['id'],
        'processed': True
    })

# Set result
output['count'] = local['counter']
output['processed_items'] = local['items']

# Set global variable
set_global('total_processed', local['counter'])
```

### Available Functions and Objects

#### String Operations
```python
# String manipulation
output['upper'] = string['upper']('hello')  # HELLO
output['lower'] = string['lower']('WORLD')  # world
output['split'] = string['split']('a,b,c', ',')  # ['a', 'b', 'c']
output['join'] = string['join']('-', ['a', 'b'])  # 'a-b'
output['replace'] = string['replace']('hello world', 'world', 'python')  # 'hello python'
```

#### Math Operations
```python
# Mathematical operations
output['sum'] = math['add'](10, 20)  # 30
output['diff'] = math['subtract'](30, 10)  # 20
output['product'] = math['multiply'](5, 6)  # 30
output['quotient'] = math['divide'](20, 4)  # 5.0
output['power'] = math['power'](2, 8)  # 256
output['sqrt'] = math['sqrt'](16)  # 4.0
```

#### Conditional Logic
```python
# If-else statements
if input.get('age', 0) >= 18:
    output['status'] = 'adult'
    output['can_vote'] = True
else:
    output['status'] = 'minor'
    output['can_vote'] = False

# Multiple conditions
total = input.get('total', 0)
if total > 1000:
    output['tier'] = 'gold'
elif total > 500:
    output['tier'] = 'silver'
else:
    output['tier'] = 'bronze'
```

#### Working with Lists
```python
# Process list of items
local['emails'] = []
local['total_value'] = 0

for user in input.get('users', []):
    # Extract email
    email = user.get('email', '')
    if email and '@' in email:
        local['emails'].append(string['lower'](email))
    
    # Sum values
    local['total_value'] = math['add'](
        local['total_value'], 
        user.get('purchase_value', 0)
    )

output['email_list'] = local['emails']
output['total_revenue'] = local['total_value']
output['average_value'] = math['divide'](
    local['total_value'], 
    len(local['emails'])
) if local['emails'] else 0
```

### Advanced Transform Examples

#### 1. Data Validation and Cleaning
```python
# Validate and clean user data
local['user'] = input.get('user', {})
local['errors'] = []

# Validate email
email = local['user'].get('email', '')
if not email or '@' not in email:
    local['errors'].append('Invalid email')
else:
    output['email'] = string['lower'](string['strip'](email))

# Validate age
age = local['user'].get('age')
if not isinstance(age, (int, float)) or age < 0 or age > 150:
    local['errors'].append('Invalid age')
else:
    output['age'] = int(age)

# Clean phone number
phone = local['user'].get('phone', '')
output['phone'] = string['replace'](
    string['replace'](
        string['replace'](phone, '-', ''),
        ' ', ''
    ),
    '(', ''
)

output['is_valid'] = len(local['errors']) == 0
output['errors'] = local['errors']
```

#### 2. Aggregating Data from Multiple Sources
```python
# Combine data from different nodes
local['orders'] = node_outputs.get('fetch_orders', {}).get('data', [])
local['customer'] = node_outputs.get('fetch_customer', {}).get('data', {})
local['products'] = node_outputs.get('fetch_products', {}).get('data', [])

# Create customer summary
output['customer_summary'] = {
    'name': local['customer'].get('name', 'Unknown'),
    'email': local['customer'].get('email', ''),
    'total_orders': len(local['orders']),
    'total_spent': sum(order.get('total', 0) for order in local['orders'])
}

# Get product statistics
local['product_counts'] = {}
for order in local['orders']:
    for item in order.get('items', []):
        product_id = item.get('product_id')
        if product_id:
            current = local['product_counts'].get(product_id, 0)
            local['product_counts'][product_id] = math['add'](current, item.get('quantity', 0))

# Find top products
output['top_products'] = sorted(
    [{'id': k, 'quantity': v} for k, v in local['product_counts'].items()],
    key=lambda x: x['quantity'],
    reverse=True
)[:5]
```

#### 3. Dynamic Routing Logic
```python
# Determine next action based on complex conditions
local['order'] = input.get('order', {})
local['customer_type'] = global.get('customer_type', 'standard')

# Calculate order metrics
local['total'] = local['order'].get('total', 0)
local['item_count'] = len(local['order'].get('items', []))
local['is_rush'] = local['order'].get('rush_delivery', False)

# Determine processing route
if local['customer_type'] == 'vip' or local['total'] > 1000:
    output['route'] = 'premium'
    output['priority'] = 1
    output['discount'] = 0.15
elif local['is_rush']:
    output['route'] = 'express'
    output['priority'] = 2
    output['discount'] = 0.05
else:
    output['route'] = 'standard'
    output['priority'] = 3
    output['discount'] = 0

# Add processing instructions
output['instructions'] = {
    'notify_warehouse': local['is_rush'] or output['priority'] == 1,
    'quality_check': local['total'] > 500,
    'gift_wrap': local['order'].get('gift', False),
    'insurance': local['total'] > 200
}

# Update global statistics
current_count = global.get(f"{output['route']}_count", 0)
set_global(f"{output['route']}_count", math['add'](current_count, 1))
```

## Flow Designer UI Enhancements

### Variable Selection in Response Nodes

The response node now features an intelligent variable selector that helps you choose from:

1. **String Literals**
   ```
   "Hello World"
   'Success Message'
   ```

2. **Input Variables**
   ```
   input.username
   input.order.id
   ```

3. **Node Outputs**
   ```
   node_outputs.transform_1.result
   node_outputs.action_1.data.user_id
   ```

4. **Global Variables**
   ```
   global.session_id
   global.counters.total
   ```

### Keyboard Shortcuts and Controls

- **Delete/Backspace**: Delete selected nodes or connections
- **Shift + Click**: Multi-select nodes
- **Ctrl/Cmd + Mouse Wheel**: Zoom in/out
- **Space + Drag**: Pan the canvas
- **Escape**: Deselect all

### Flow Validation

The designer now provides real-time validation:
- Red outline on nodes with errors
- Warning icons for missing configurations
- Connection validation (prevents invalid connections)
- Synchronous flow requirements checking

## Complete Examples

### Example 1: E-commerce Order Processing Flow

```yaml
Flow Name: Process E-commerce Order
Type: Synchronous
Description: Validates order, calculates shipping, and returns confirmation

Nodes:

1. API Trigger
   Input Schema:
   - customer_id: string
   - items: array
   - shipping_address: object
   - coupon_code: string (optional)

2. Transform Node - Validate Order
   Script: |
     # Validate required fields
     local['errors'] = []
     
     if not input.get('customer_id'):
         local['errors'].append('Customer ID required')
     
     if not input.get('items') or len(input['items']) == 0:
         local['errors'].append('Order must contain items')
     
     # Calculate totals
     local['subtotal'] = 0
     local['valid_items'] = []
     
     for item in input.get('items', []):
         if item.get('quantity', 0) > 0 and item.get('price', 0) > 0:
             item_total = math['multiply'](item['quantity'], item['price'])
             local['subtotal'] = math['add'](local['subtotal'], item_total)
             local['valid_items'].append(item)
     
     output['is_valid'] = len(local['errors']) == 0
     output['errors'] = local['errors']
     output['subtotal'] = local['subtotal']
     output['items'] = local['valid_items']

3. Condition Node - Check Validation
   Condition: {{node_outputs.transform_1.is_valid}} == true
   True Path: Continue processing
   False Path: Return error response

4. Action Node - Check Inventory
   Application: Database
   Query: SELECT product_id, available_qty FROM inventory WHERE product_id IN (?)

5. Transform Node - Calculate Shipping
   Script: |
     local['subtotal'] = node_outputs['transform_1']['subtotal']
     local['weight'] = sum(item.get('weight', 0) for item in node_outputs['transform_1']['items'])
     
     # Shipping calculation
     if local['weight'] < 1:
         output['shipping'] = 5.99
     elif local['weight'] < 5:
         output['shipping'] = 9.99
     else:
         output['shipping'] = 15.99
     
     # Apply free shipping if eligible
     if local['subtotal'] > 100:
         output['shipping'] = 0
     
     # Calculate tax (8%)
     output['tax'] = math['multiply'](local['subtotal'], 0.08)
     
     # Final total
     output['total'] = math['add'](
         math['add'](local['subtotal'], output['shipping']),
         output['tax']
     )

6. Action Node - Create Order
   Application: Database
   Operation: Insert order record

7. Response Node - Success Response
   Variable: Custom JSON
   {
     "success": true,
     "order_id": "{{node_outputs.action_2.order_id}}",
     "total": "{{node_outputs.transform_2.total}}",
     "shipping": "{{node_outputs.transform_2.shipping}}",
     "estimated_delivery": "{{node_outputs.action_2.delivery_date}}"
   }

8. Response Node - Error Response (from false condition path)
   Variable: Custom JSON
   {
     "success": false,
     "errors": "{{node_outputs.transform_1.errors}}",
     "message": "Order validation failed"
   }
```

### Example 2: Data Pipeline with Transform Nodes

```yaml
Flow Name: Customer Data Enrichment Pipeline
Type: Asynchronous
Description: Enriches customer data from multiple sources

Nodes:

1. Schedule Trigger
   Cron: 0 */6 * * * (every 6 hours)

2. Action Node - Fetch New Customers
   Application: Database
   Query: SELECT * FROM customers WHERE created_at > ?

3. Transform Node - Initialize Processing
   Script: |
     local['customers'] = input.get('data', [])
     output['total_count'] = len(local['customers'])
     output['batch_id'] = f"batch_{input.get('execution_id', 'unknown')}"
     
     # Group by region
     local['by_region'] = {}
     for customer in local['customers']:
         region = customer.get('region', 'unknown')
         if region not in local['by_region']:
             local['by_region'][region] = []
         local['by_region'][region].append(customer)
     
     output['regions'] = local['by_region']
     set_global('batch_size', output['total_count'])

4. Transform Node - Enrich Customer Data
   Script: |
     local['enriched'] = []
     
     for region, customers in input.get('regions', {}).items():
         for customer in customers:
             # Clean and standardize data
             enriched_customer = {
                 'id': customer['id'],
                 'email': string['lower'](string['strip'](customer.get('email', ''))),
                 'name': string['title'](customer.get('name', '')),
                 'region': region,
                 'join_date': customer.get('created_at'),
                 'score': 0
             }
             
             # Calculate engagement score
             local['score'] = 0
             if customer.get('email_verified'):
                 local['score'] = math['add'](local['score'], 20)
             if customer.get('profile_complete'):
                 local['score'] = math['add'](local['score'], 30)
             if customer.get('first_purchase'):
                 local['score'] = math['add'](local['score'], 50)
             
             enriched_customer['score'] = local['score']
             enriched_customer['segment'] = 'high' if local['score'] > 70 else 'medium' if local['score'] > 40 else 'low'
             
             local['enriched'].append(enriched_customer)
     
     output['customers'] = local['enriched']
     output['segment_counts'] = {
         'high': len([c for c in local['enriched'] if c['segment'] == 'high']),
         'medium': len([c for c in local['enriched'] if c['segment'] == 'medium']),
         'low': len([c for c in local['enriched'] if c['segment'] == 'low'])
     }

5. Action Node - Update Database
   Application: Database
   Operation: Bulk update customer records

6. Transform Node - Generate Report
   Script: |
     # Generate summary report
     output['report'] = {
         'batch_id': global.get('batch_id'),
         'processed': global.get('batch_size', 0),
         'segments': node_outputs['transform_2']['segment_counts'],
         'timestamp': str(input.get('execution_time', ''))
     }
     
     # Update global statistics
     total_processed = global.get('total_customers_processed', 0)
     set_global('total_customers_processed', math['add'](total_processed, global.get('batch_size', 0)))

7. Action Node - Send Report
   Application: Email
   Template: enrichment_report
   Data: {{node_outputs.transform_3.report}}
```

## Advanced Use Cases

### 1. Webhook Processing with Conditional Logic

```python
# Transform node for webhook data processing
local['webhook'] = input.get('webhook_data', {})
local['event_type'] = local['webhook'].get('event')

# Route based on event type
if local['event_type'] == 'user.created':
    output['action'] = 'create_welcome_sequence'
    output['data'] = {
        'user_id': local['webhook']['data']['id'],
        'email': local['webhook']['data']['email'],
        'name': local['webhook']['data']['name']
    }
elif local['event_type'] == 'order.completed':
    output['action'] = 'process_order_completion'
    output['data'] = {
        'order_id': local['webhook']['data']['order_id'],
        'amount': local['webhook']['data']['total'],
        'items': local['webhook']['data']['items']
    }
elif string['startswith'](local['event_type'], 'payment.'):
    output['action'] = 'handle_payment_event'
    output['data'] = local['webhook']['data']
else:
    output['action'] = 'log_unknown_event'
    output['data'] = {'event': local['event_type'], 'payload': local['webhook']}

# Set routing flag for condition node
output['route_to'] = output['action']
```

### 2. Batch Processing with Progress Tracking

```python
# Transform node for batch processing
local['items'] = input.get('items', [])
local['batch_size'] = 50
local['processed'] = []
local['failed'] = []

# Process in batches
for i in range(0, len(local['items']), local['batch_size']):
    batch = local['items'][i:i + local['batch_size']]
    
    # Process each item in batch
    for item in batch:
        try:
            # Simulate processing (in real flow, this would be an action node)
            if item.get('valid', True):
                local['processed'].append(item['id'])
            else:
                local['failed'].append({
                    'id': item['id'],
                    'reason': 'Validation failed'
                })
        except:
            local['failed'].append({
                'id': item.get('id', 'unknown'),
                'reason': 'Processing error'
            })
    
    # Update progress
    progress = math['divide'](
        len(local['processed']) + len(local['failed']),
        len(local['items'])
    ) * 100
    
    set_global('batch_progress', progress)

output['summary'] = {
    'total': len(local['items']),
    'processed': len(local['processed']),
    'failed': len(local['failed']),
    'success_rate': math['divide'](
        len(local['processed']),
        len(local['items'])
    ) * 100 if local['items'] else 0
}
output['failed_items'] = local['failed']
```

### 3. Dynamic Configuration Management

```python
# Transform node for dynamic configuration
local['environment'] = input.get('environment', 'production')
local['feature_flags'] = global.get('feature_flags', {})

# Base configuration
output['config'] = {
    'api_version': 'v2',
    'timeout': 30,
    'retry_count': 3,
    'batch_size': 100
}

# Environment-specific overrides
if local['environment'] == 'development':
    output['config']['api_endpoint'] = 'https://dev-api.example.com'
    output['config']['debug'] = True
    output['config']['batch_size'] = 10
elif local['environment'] == 'staging':
    output['config']['api_endpoint'] = 'https://staging-api.example.com'
    output['config']['debug'] = False
    output['config']['batch_size'] = 50
else:  # production
    output['config']['api_endpoint'] = 'https://api.example.com'
    output['config']['debug'] = False
    output['config']['rate_limit'] = 1000

# Apply feature flags
if local['feature_flags'].get('use_new_algorithm'):
    output['config']['algorithm'] = 'v2'
else:
    output['config']['algorithm'] = 'v1'

if local['feature_flags'].get('enable_caching'):
    output['config']['cache_ttl'] = 3600

# Set configuration globally for other nodes
set_global('current_config', output['config'])
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Synchronous Flow Not Returning Response

**Problem**: API returns generic message instead of defined response

**Solution**:
- Ensure flow is marked as synchronous
- Check that response node is properly configured
- Verify variable path or string literal syntax
- Look for execution errors in logs

#### 2. Transform Node Errors

**Problem**: "NameError: name 'x' is not defined"

**Solution**:
```python
# Wrong
total = 0  # Direct assignment not allowed

# Correct
local['total'] = 0  # Use local dictionary
```

**Problem**: "KeyError: 'missing_key'"

**Solution**:
```python
# Wrong
value = input['missing_key']

# Correct
value = input.get('missing_key', 'default_value')
```

#### 3. Variable Path Issues

**Problem**: "Variable not found: node_outputs.transform_1"

**Solution**:
- Ensure the node has executed before accessing its output
- Check node ID matches exactly
- Verify the node actually sets output data

#### 4. Flow Execution Timeouts

**Problem**: Synchronous flow times out

**Solutions**:
- Increase timeout in flow settings (max 300 seconds)
- Optimize transform node scripts
- Move heavy processing to asynchronous flows
- Use pagination for large datasets

### Performance Optimization Tips

1. **Transform Node Optimization**
   ```python
   # Inefficient
   output['items'] = []
   for item in input['items']:
       output['items'].append(process_item(item))
   
   # Efficient
   local['processed'] = []
   for item in input.get('items', []):
       local['processed'].append(process_item(item))
   output['items'] = local['processed']
   ```

2. **Batch Processing**
   - Process items in chunks
   - Use action nodes for bulk operations
   - Implement progress tracking for long operations

3. **Variable Management**
   - Clean up large variables when done
   - Use specific paths instead of entire objects
   - Avoid storing duplicate data

### Debug Mode Best Practices

1. **Add Debug Output**
   ```python
   # Add debug information to results
   if global.get('debug_mode', False):
       output['_debug'] = {
           'input_keys': list(input.keys()),
           'local_vars': list(local.keys()),
           'execution_time': input.get('timestamp')
       }
   ```

2. **Test with Small Datasets**
   - Start with minimal test data
   - Gradually increase complexity
   - Use flow testing interface

3. **Monitor Execution Logs**
   - Check each node's input/output
   - Look for error messages
   - Verify data transformations

## Conclusion

IOFlow's latest features provide powerful capabilities for building sophisticated automation workflows. The combination of synchronous API support, advanced transform nodes, and improved UI makes it suitable for a wide range of use cases from simple data processing to complex business logic implementation.

Key takeaways:
- Use synchronous flows for API-like request/response patterns
- Leverage transform nodes for complex data manipulation
- Take advantage of variable management for maintaining state
- Follow best practices for performance and error handling
- Test thoroughly using the built-in testing tools

For more information, refer to:
- [Flow Designer User Manual](./flow_designer_user_manual.md)
- [Transform Node Guide](../backend/docs/transform_node_guide.md)
- API documentation in your IOFlow instance

Happy automating!
# Flow to Application Publishing System

## Overview

The Flow to Application Publishing System allows users to design flows and publish them as applications that work exactly like seed applications. This enables flows to be reused as building blocks in other flows with automatic parameter mapping and transformation capabilities.

## Key Features

- **Automatic Analysis**: Extracts flow structure, parameters, and transformations
- **Application Generation**: Converts flows to seed application JSON format
- **Parameter Mapping**: Maps flow variables to application service parameters
- **Execution Bridge**: Seamlessly executes flows when called as applications
- **Version Management**: Tracks versions and handles updates
- **Dependency Tracking**: Manages dependencies between published applications

## Architecture

### Core Components

1. **FlowAnalyzer**: Extracts metadata from flow definitions
2. **ApplicationGenerator**: Converts flow analysis to seed applications
3. **FlowPublisher**: Orchestrates the publishing process
4. **ParameterMapper**: Handles parameter transformations
5. **FlowExecutionBridge**: Bridges application calls to flow execution
6. **JsonSeedManager**: Extended to handle flow-based applications

### Database Schema

```sql
-- Published Applications
CREATE TABLE published_applications (
    published_app_id VARCHAR(36) PRIMARY KEY,
    flow_id VARCHAR(36) NOT NULL,
    app_id VARCHAR(36) NOT NULL,
    app_key VARCHAR(255) UNIQUE NOT NULL,
    flow_name VARCHAR(255) NOT NULL,
    published_version VARCHAR(20) DEFAULT '1.0.0',
    flow_analysis TEXT,
    status VARCHAR(20) DEFAULT 'active',
    auto_update BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Version History
CREATE TABLE published_application_versions (
    version_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL,
    version_number VARCHAR(20) NOT NULL,
    flow_definition TEXT,
    generated_application TEXT,
    changes_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parameter Mappings
CREATE TABLE parameter_mappings (
    mapping_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL,
    parameter_name VARCHAR(255) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL,
    flow_variable_path VARCHAR(500) NOT NULL,
    service_parameter_name VARCHAR(255) NOT NULL,
    transformation_rule TEXT,
    is_required BOOLEAN DEFAULT FALSE
);
```

## API Endpoints

### Publishing Flows

#### Preview Publishing
```http
GET /api/v1/flow-publishing/preview?flow_id={flow_id}&app_key={app_key}
```

Returns a preview of what would be created when publishing the flow.

#### Publish Flow
```http
POST /api/v1/flow-publishing/publish
Content-Type: application/json

{
  "flow_id": "flow-123",
  "app_key": "my_custom_app",
  "app_name": "My Custom Application",
  "description": "Auto-generated from flow",
  "category": "Flow Applications",
  "auto_update": false
}
```

### Managing Published Applications

#### List Published Applications
```http
GET /api/v1/flow-publishing/applications
```

#### Get Application Details
```http
GET /api/v1/flow-publishing/applications/{published_app_id}
```

#### Update Published Application
```http
PUT /api/v1/flow-publishing/applications/{published_app_id}/update
Content-Type: application/json

{
  "force_update": false
}
```

#### Unpublish Application
```http
DELETE /api/v1/flow-publishing/applications/{published_app_id}
```

### Version Management

#### Get Version History
```http
GET /api/v1/flow-publishing/applications/{published_app_id}/versions
```

#### Get Dependencies
```http
GET /api/v1/flow-publishing/applications/{published_app_id}/dependencies
```

#### Get Parameter Mappings
```http
GET /api/v1/flow-publishing/applications/{published_app_id}/parameters
```

## Usage Examples

### Example 1: Simple Data Processing Flow

```javascript
// Original flow definition
{
  "flow_name": "Data Validator",
  "trigger_config": {
    "type": "manual",
    "manual_variables": [
      {
        "name": "inputData",
        "type": "object",
        "required": true,
        "description": "Data to validate"
      }
    ]
  },
  "flow_definition": {
    "nodes": [
      {
        "id": "trigger-1",
        "type": "trigger",
        "data": {
          "variables": [
            {
              "name": "inputData",
              "type": "object",
              "required": true
            }
          ]
        }
      },
      {
        "id": "transform-1",
        "type": "transform",
        "data": {
          "code": `
            import re
            
            data = input.get('inputData', {})
            errors = []
            
            # Validate email
            if 'email' in data:
                if not re.match(r'^[^@]+@[^@]+\.[^@]+$', data['email']):
                    errors.append('Invalid email format')
            
            # Validate phone
            if 'phone' in data:
                if not re.match(r'^\+?1?\d{9,15}$', data['phone']):
                    errors.append('Invalid phone format')
            
            output['isValid'] = len(errors) == 0
            output['errors'] = errors
            output['validatedData'] = data if len(errors) == 0 else {}
          `
        }
      }
    ]
  }
}
```

After publishing, this becomes a reusable application:

```json
{
  "key": "data_validator_app",
  "application": {
    "app_name": "Data Validator App",
    "app_type": "global",
    "auth_type": "api_key",
    "flow_based": true
  },
  "services": [
    {
      "service_name": "execute_data_validator",
      "service_type": "api_call",
      "description": "Execute the Data Validator flow",
      "endpoint_url": "/api/v1/flows/flow-123/execute/sync",
      "parameter_schema": {
        "type": "object",
        "properties": {
          "inputData": {
            "type": "object",
            "description": "Data to validate"
          }
        },
        "required": ["inputData"]
      }
    }
  ]
}
```

### Example 2: Customer Notification Flow

```javascript
// Flow with multiple parameters and transformations
{
  "flow_name": "Customer Notification",
  "trigger_config": {
    "type": "manual",
    "manual_variables": [
      {
        "name": "customerEmail",
        "type": "string",
        "required": true
      },
      {
        "name": "customerName", 
        "type": "string",
        "required": true
      },
      {
        "name": "orderAmount",
        "type": "number",
        "required": false,
        "default_value": 0
      }
    ]
  }
}
```

### Using Published Applications in Flows

Once published, the application can be used in other flows:

```javascript
// Action node using the published application
{
  "id": "action-1",
  "type": "action",
  "data": {
    "selectedApp": "data_validator_app",
    "selectedService": "execute_data_validator",
    "parameters": {
      "inputData": "{{input.customerData}}"
    }
  }
}
```

## Parameter Mapping

### Mapping Types

1. **Direct Mapping**: Simple 1:1 parameter mapping
```json
{
  "source_path": "input.customerEmail",
  "target_parameter": "email",
  "mapping_type": "direct"
}
```

2. **Transform Mapping**: With transformation logic
```json
{
  "source_path": "input.customerName",
  "target_parameter": "formatted_name",
  "mapping_type": "transform",
  "transformation_rule": {
    "type": "javascript",
    "code": "value.toUpperCase()"
  }
}
```

3. **Conditional Mapping**: Based on conditions
```json
{
  "source_path": "input.orderAmount",
  "target_parameter": "priority",
  "mapping_type": "conditional",
  "transformation_rule": {
    "condition": "value > 100",
    "true_value": "high",
    "false_value": "normal"
  }
}
```

### Variable Resolution

The system supports complex variable paths:

- `input.customerEmail` - Flow input parameter
- `node_outputs.transform-1.result` - Output from specific node
- `global.apiKey` - Global variable
- `loop.item` - Current loop item (in loop context)

## Best Practices

### 1. Flow Design for Reusability

**Good Practice:**
```javascript
// Clear, descriptive parameter names
{
  "name": "customerEmail",
  "type": "string",
  "description": "Customer email address for notifications"
}
```

**Avoid:**
```javascript
// Vague parameter names
{
  "name": "data",
  "type": "object"
}
```

### 2. Parameter Validation

Use transform nodes to validate inputs:

```python
# Validation transform
email = input.get('customerEmail', '')
if not email or '@' not in email:
    output['error'] = 'Invalid email address'
    output['valid'] = False
else:
    output['validated_email'] = email.lower()
    output['valid'] = True
```

### 3. Error Handling

Include error handling in your flows:

```javascript
// Condition node for error checking
{
  "condition": "node_outputs.validation.valid == true",
  "true_branch": "continue_processing",
  "false_branch": "return_error"
}
```

### 4. Documentation

Add clear descriptions to all parameters and transformations:

```javascript
{
  "name": "orderAmount",
  "type": "number",
  "description": "Order amount in USD. Used to determine notification priority and format."
}
```

## Troubleshooting

### Common Issues

1. **Parameter Mapping Fails**
   - Check variable paths are correct
   - Verify parameter types match
   - Ensure required parameters are provided

2. **Flow Execution Timeout**
   - Increase timeout settings
   - Optimize flow performance
   - Consider using async execution

3. **Validation Errors**
   - Check flow structure is complete
   - Verify all nodes are connected
   - Ensure response nodes exist for sync flows

### Debug Tools

1. **Publishing Preview**: Use the preview endpoint to see what will be generated
2. **Parameter Analysis**: Check the flow analysis output
3. **Execution Logs**: Monitor flow execution for errors
4. **Test Scripts**: Use provided test scripts to verify functionality

## Performance Considerations

### Optimization Tips

1. **Minimize Complexity**: Keep flows simple and focused
2. **Efficient Transformations**: Optimize Python code in transform nodes  
3. **Async Execution**: Use async mode for long-running processes
4. **Caching**: Leverage global variables for caching
5. **Batch Processing**: Group multiple operations when possible

### Limits

- Maximum flow complexity score: 100
- Maximum execution time: 300 seconds
- Maximum parameter count: 50
- Maximum transformation code size: 10KB

## Security

### Authentication

Published applications inherit the flow's authentication requirements:

- API key authentication for flow execution
- Tenant-based access control
- User permission validation

### Data Privacy

- Flow analysis data is stored securely
- Parameter mappings don't expose sensitive data
- Execution logs follow retention policies

## Migration Guide

### From Manual Applications to Flow-Based

1. **Analyze Existing Application**: Document current services and parameters
2. **Design Equivalent Flow**: Create flow with same functionality
3. **Test Flow**: Verify flow works correctly
4. **Publish Flow**: Use publishing system to create application
5. **Migrate Subscriptions**: Update existing subscriptions (if needed)
6. **Retire Old Application**: Safely remove manual application

### Version Updates

When updating published applications:

1. **Soft Update** (default): Preserves subscriptions, updates services
2. **Force Update**: Recreates everything, may break subscriptions
3. **Manual Update**: Review changes before applying

## Future Enhancements

### Planned Features

1. **Visual Parameter Mapping**: UI for configuring parameter mappings
2. **Advanced Transformations**: Support for more transformation types
3. **Application Templates**: Pre-built templates for common patterns
4. **Performance Analytics**: Usage and performance metrics
5. **Marketplace Integration**: Share published applications

### API Extensions

1. **Bulk Operations**: Batch publish multiple flows
2. **Export/Import**: Share published applications between instances
3. **Advanced Filtering**: More sophisticated search and filtering
4. **Webhooks**: Notifications for application events

## Conclusion

The Flow to Application Publishing System provides a powerful way to create reusable components from flows. By following the guidelines in this document, you can create robust, maintainable applications that integrate seamlessly with the IOFlow ecosystem.

For technical support or feature requests, please refer to the project documentation or contact the development team.
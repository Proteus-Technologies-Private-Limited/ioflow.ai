# Parameter Definition System

## Overview
IOFlow now supports comprehensive parameter definitions for applications, events, and services. This allows for flexible data passing methods including JSON payloads, XML payloads, and named URL patterns.

## Key Features

### 1. Multiple Parameter Passing Methods
- **JSON Payload**: Standard REST API JSON body
- **XML Payload**: SOAP or XML-based APIs
- **URL Pattern**: RESTful path parameters (e.g., `/users/{userId}/posts/{postId}`)
- **Form Data**: Form-encoded data
- **Query Parameters**: URL query strings

### 2. Schema Builder
A visual schema builder that allows you to:
- Define parameters with friendly names and descriptions
- Specify data types (string, number, boolean, date, array, object, file)
- Set validation rules (required, min/max length, patterns)
- Choose UI controls (text, dropdown, checkbox, date picker, etc.)
- Group related parameters
- Provide examples and help text

### 3. Parameter Mapper
In the flow designer, the parameter mapper:
- Shows source fields from previous nodes or triggers
- Maps to target service parameters
- Validates type compatibility
- Supports variable references (`{{input.fieldName}}`)
- Provides auto-mapping for matching field names
- Shows errors for missing required fields

### 4. Event Selection in Triggers
Trigger nodes now support:
- **Manual**: Traditional manual trigger
- **Event**: Select application and specific event
- **Schedule**: Cron-based scheduling

When selecting an event trigger:
1. Choose the application
2. Select the specific event
3. Event output schema is automatically available as variables

## How to Use

### For Application Developers

#### 1. Define Service Parameters
```javascript
// In application definition
{
  "service_name": "send_email",
  "parameter_method": "json_payload",
  "parameters": [
    {
      "param_name": "to_email",
      "friendly_name": "Recipient Email",
      "description": "Email address of the recipient",
      "data_type": "string",
      "required": true,
      "ui_control": "email",
      "validation": {
        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
      }
    },
    {
      "param_name": "subject",
      "friendly_name": "Email Subject",
      "data_type": "string",
      "required": true,
      "max_length": 200
    },
    {
      "param_name": "body",
      "friendly_name": "Email Body",
      "data_type": "string",
      "required": true,
      "ui_control": "textarea"
    }
  ]
}
```

#### 2. Define URL Pattern
```javascript
{
  "service_name": "get_user_posts",
  "parameter_method": "url_pattern",
  "url_pattern": "/api/v1/users/{userId}/posts/{postId}",
  "parameters": [
    {
      "param_name": "userId",
      "friendly_name": "User ID",
      "data_type": "string",
      "required": true,
      "url_position": 0
    },
    {
      "param_name": "postId",
      "friendly_name": "Post ID",
      "data_type": "string",
      "required": true,
      "url_position": 1
    }
  ]
}
```

#### 3. Define Event Output Schema
```javascript
{
  "event_name": "new_order",
  "output_schema": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "description": "Unique order identifier"
      },
      "customer": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "email": { "type": "string" }
        }
      },
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "product_id": { "type": "string" },
            "quantity": { "type": "number" }
          }
        }
      }
    }
  }
}
```

### For Flow Designers

#### 1. Configure Event Triggers
- Select trigger node
- Choose "Event" as trigger type
- Select application (only apps with events shown)
- Select specific event
- Event data is automatically available as `{{input.fieldName}}`

#### 2. Map Action Parameters
- Select action node
- Choose application and service
- Parameter mapper shows based on service definition
- Map source fields to target parameters:
  - Direct mapping from previous nodes
  - Use variables like `{{input.order_id}}`
  - Custom expressions for transformations
- Validation shows missing required fields
- Type conversion warnings appear automatically

#### 3. URL Pattern Services
For services with URL patterns:
- Pattern is displayed: `/users/{userId}/posts/{postId}`
- Map each parameter individually
- Use variables or static values

## Advanced Features

### 1. Nested Object Support
Parameters can define nested structures:
```javascript
{
  "param_name": "address",
  "data_type": "object",
  "properties_schema": {
    "street": { "type": "string" },
    "city": { "type": "string" },
    "zip": { "type": "string" }
  }
}
```

### 2. Array Parameters
Support for array inputs with item schemas:
```javascript
{
  "param_name": "tags",
  "data_type": "array",
  "items_schema": {
    "type": "string",
    "maxLength": 50
  }
}
```

### 3. Conditional Parameters
Parameters can be shown/hidden based on other values:
```javascript
{
  "param_name": "notification_email",
  "data_type": "string",
  "show_if": {
    "field": "send_notification",
    "value": true
  }
}
```

### 4. Parameter Groups
Related parameters can be grouped:
```javascript
{
  "param_name": "customer_name",
  "group_name": "Customer Information",
  "display_order": 1
}
```

## Benefits

1. **Type Safety**: Proper validation before execution
2. **Better UX**: Friendly parameter names and descriptions
3. **Flexibility**: Support for various API styles
4. **Reusability**: Define once, use in multiple flows
5. **Documentation**: Self-documenting APIs
6. **Error Prevention**: Catch mapping errors before execution

## Migration Guide

Existing flows will continue to work with the old parameter system. To migrate:

1. Update application definitions with parameter schemas
2. Test existing flows - they'll use backward compatibility
3. New flows will automatically use the parameter mapper
4. Gradually update old flows to use proper mapping

## API Endpoints

- `POST /api/v1/parameters/definitions` - Create parameter definition
- `GET /api/v1/parameters/definitions/{parent_type}/{parent_id}` - List parameters
- `PUT /api/v1/parameters/definitions/{param_id}` - Update parameter
- `DELETE /api/v1/parameters/definitions/{param_id}` - Delete parameter
- `POST /api/v1/parameters/schemas` - Create payload schema
- `POST /api/v1/parameters/schema-builder/json` - Build JSON schema
- `POST /api/v1/parameters/mapping/validate` - Validate parameter mapping

This system provides a robust foundation for handling complex integrations while maintaining ease of use for flow designers.
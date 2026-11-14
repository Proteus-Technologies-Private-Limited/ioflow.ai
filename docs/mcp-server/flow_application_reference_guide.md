# Flow Application Reference Guide

## Overview
This guide explains how to reference applications and services in IOFlow flow design, including the enhanced `get_seed_application` response format.

## Enhanced get_seed_application Response

The `get_seed_application` MCP tool now returns comprehensive information including installation status:

### Request
```json
{
  "app_key": "gmail"
}
```

### Response Structure
```json
{
  "application": {
    "app_key": "gmail",
    "app_name": "Gmail",
    "app_type": "global",
    "category": "Email",
    "auth_type": "oauth2",
    "description": "Google Gmail email service",
    "version": "1.0.0",
    "base_url": "https://gmail.googleapis.com/gmail/v1"
  },
  "services": [
    {
      "service_name": "send_email",
      "service_type": "api_call",
      "description": "Send an email via Gmail",
      "parameter_count": 4,
      "required_parameters": ["to", "subject", "body"],
      "configuration_complexity": "medium"
    }
  ],
  "events": [
    {
      "event_name": "new_email",
      "event_type": "trigger",
      "trigger_category": "polling"
    }
  ],
  "is_installed": true,
  "installation_info": {
    "application_id": "550e8400-e29b-41d4-a716-446655440000",
    "installed_at": "2024-01-15T10:30:00Z",
    "version": "1.0.0",
    "subscriptions_count": 2
  },
  "usage_hints": {...},
  "integration_guide": {...}
}
```

## Key Fields for Flow Design

### 1. **Application Identification**
- **`app_key`**: Unique identifier for the seed application (e.g., "gmail", "google_sheets")
- **`application_id`**: UUID assigned when installed in tenant (only present if installed)
- **`is_installed`**: Boolean indicating if app is available for use in flows

### 2. **Service Reference**
When creating action nodes in flows, reference services using:
- **Application Key**: The `app_key` from the seed application
- **Service Name**: The `service_name` from the services array

## How to Reference Applications in Flow Design

### 1. **In Action Nodes**

Action nodes reference applications and services using this structure:

```json
{
  "id": "action_1",
  "type": "action",
  "data": {
    "label": "Send Email",
    "application": "gmail",           // app_key
    "service": "send_email",          // service_name
    "parameters": {
      "to": "{{input.recipient}}",
      "subject": "{{input.subject}}",
      "body": "{{input.message}}"
    }
  }
}
```

### 2. **In Trigger Nodes**

Trigger nodes reference application events:

```json
{
  "id": "trigger_1",
  "type": "trigger",
  "data": {
    "label": "New Email Received",
    "application": "gmail",           // app_key
    "event": "new_email",            // event_name
    "configuration": {
      "filter": "unread",
      "label": "important"
    }
  }
}
```

### 3. **Dynamic Parameter Mapping**

Use double curly braces to reference data from previous nodes:

```json
{
  "parameters": {
    "spreadsheet_id": "{{input.spreadsheet_id}}",
    "range": "{{node_outputs.transform_1.range}}",
    "values": "{{node_outputs.action_1.data.results}}"
  }
}
```

## Best Practices

### 1. **Check Installation Status**
Always verify `is_installed` is true before using an application in flows:

```python
# In a transform node
if not global.get('gmail_installed'):
    output['error'] = 'Gmail application not installed'
else:
    output['proceed'] = True
```

### 2. **Use Application IDs for API Calls**
When making direct API calls, use the `application_id` from `installation_info`:

```json
{
  "endpoint": "/api/v1/applications/{{application_id}}/subscriptions",
  "method": "GET"
}
```

### 3. **Service Parameter Validation**
Check `required_parameters` to ensure all mandatory fields are provided:

```python
# Transform node validation
required = ['to', 'subject', 'body']
missing = [p for p in required if not input.get(p)]
if missing:
    output['error'] = f"Missing required parameters: {missing}"
```

## Common Patterns

### 1. **Multi-Application Flow**
```json
{
  "nodes": [
    {
      "id": "trigger_1",
      "type": "trigger",
      "data": {
        "application": "google_sheets",
        "event": "row_added"
      }
    },
    {
      "id": "action_1",
      "type": "action",
      "data": {
        "application": "gmail",
        "service": "send_email",
        "parameters": {
          "to": "{{trigger.row.email}}",
          "subject": "New submission received"
        }
      }
    }
  ]
}
```

### 2. **Conditional Application Usage**
```python
# In transform node
app_to_use = 'slack' if input.get('urgent') else 'email'
output['notification_app'] = app_to_use
output['service'] = 'send_message' if app_to_use == 'slack' else 'send_email'
```

### 3. **Application Service Discovery**
Use MCP tools to discover available services:

```python
# First, check if app is installed
response = get_seed_application(app_key="gmail")
if response.is_installed:
    available_services = [s.service_name for s in response.services]
    # Use in flow design
```

## Error Handling

### 1. **Application Not Installed**
```json
{
  "error": "Application 'gmail' not found in tenant",
  "suggestion": "Install the application first using install_application tool"
}
```

### 2. **Service Not Found**
```json
{
  "error": "Service 'send_bulk_email' not found in application 'gmail'",
  "available_services": ["send_email", "create_draft", "list_messages"]
}
```

## Summary

To use applications in flow design:
1. Use `get_seed_application` to check installation status and get details
2. Reference applications by `app_key` in nodes
3. Reference services by `service_name` in action nodes
4. Use `application_id` for direct API operations
5. Always validate installation status before use
6. Use parameter mapping with `{{}}` syntax for dynamic values
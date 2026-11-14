# Seed Application JSON Structure Guide

## Overview

This guide documents the correct JSON structure for creating seed applications in IOFlow. All seed applications MUST follow this exact structure to be recognized by the system.

## File Structure

All seed application JSON files must be placed in the `/backend/seed-applications/` directory.

## Required JSON Schema

### Top-Level Structure

Every seed application JSON file **MUST** follow this exact structure:

```json
{
  "key": "unique_application_key",
  "application": {
    // Application configuration
  },
  "events": [
    // Event definitions (optional)
  ],
  "services": [
    // Service definitions
  ]
}
```

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | **Yes** | Unique identifier for the application (lowercase, no spaces) |
| `application` | object | **Yes** | Application metadata and configuration |
| `events` | array | No | Array of event definitions (webhooks, triggers) |
| `services` | array | **Yes** | Array of service definitions |

### Application Object

The `application` object must contain:

```json
{
  "app_name": "Display Name",
  "app_type": "api",  // database, email, api, file_system, memory, or flow
  "app_scope": "global",  // global, tenant, or user
  "description": "Brief description of the application",
  "category": "Communication",  // See categories below
  "auth_type": "oauth2",  // See auth types below
  "auth_config": {
    // Authentication configuration
  },
  "version": "1.0.0",
  "base_url": "https://api.example.com",  // Optional base URL
  "icon_url": "https://example.com/icon.png",  // Optional icon
  "webhook_config": null  // Optional webhook configuration
}
```

#### Supported Application Types

- `database` - Database applications (PostgreSQL, MySQL, etc.)
- `email` - Email service applications (SMTP, IMAP, POP3)
- `api` - General API integrations
- `file_system` - File system operations
- `memory` - In-memory data storage
- `flow` - Flow-based applications

#### Supported Application Scopes

- `global` - Available to all users system-wide
- `tenant` - Available only to specific organizations/tenants
- `user` - Available only to specific users

#### Supported Categories

- `Communication` - Messaging, chat, email platforms
- `Productivity` - Task management, calendars, documents
- `Analytics` - Data analysis, reporting tools
- `Database` - Database connections
- `Integration` - General integration platforms
- `Other` - Miscellaneous applications

#### Supported Auth Types

- `none` - No authentication required
- `api_key` - Simple API key authentication
- `oauth2` - OAuth 2.0 flow
- `basic` - Username/password authentication
- `token_exchange` - Exchange credentials for tokens
- `custom` - Custom authentication

### Service Object

Each service in the `services` array must follow this structure:

```json
{
  "service_name": "internal_name",
  "display_name": "User-Friendly Name",
  "description": "What this service does",
  "service_type": "api_call",  // See service types below
  "service_config": {
    // Service-specific configuration
  },
  "is_async": false,
  "parameter_schema": {  // NOT input_schema!
    // JSON Schema for input parameters
  },
  "output_schema": {
    // JSON Schema for output structure
  },
  "timeout_seconds": 30,
  "is_active": true
}
```

**IMPORTANT**: Use `parameter_schema`, NOT `input_schema` for defining service parameters!

#### Supported Service Types

- `api_call` - HTTP API calls
- `webhook` - Send webhooks
- `email_send` - Send emails
- `llm_api_call` - LLM API calls
- `mcp_call` - MCP protocol calls
- `database_query` - Database queries

### Parameter Schema

The `parameter_schema` defines the arguments that will appear in the flow designer:

```json
"parameter_schema": {
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "SQL query with :param_name placeholders",
      "example": "SELECT * FROM users WHERE id = :user_id"
    },
    "parameters": {
      "type": "object",
      "description": "Parameter values for placeholders",
      "additionalProperties": true,
      "example": {
        "user_id": 123
      }
    }
  },
  "required": ["sql"]
}
```

### Event Object (Optional)

Events define triggers that can start flows:

```json
{
  "event_name": "internal_name",
  "display_name": "User-Friendly Name",
  "description": "When this event occurs",
  "trigger_type": "webhook",  // webhook, schedule, polling, etc.
  "trigger_config": {
    // Trigger-specific configuration
  },
  "output_schema": {
    // JSON Schema for event payload
  },
  "sample_payload": {
    // Example event data
  },
  "is_active": true
}
```

## Examples

### 1. Database Application (PostgreSQL)

```json
{
  "key": "postgresql",
  "application": {
    "app_name": "PostgreSQL Database",
    "app_type": "global",
    "description": "Connect to PostgreSQL databases",
    "category": "Database",
    "base_url": "postgresql://localhost:5432/postgres",
    "auth_type": "basic",
    "auth_config": {
      "database_type": "postgresql",
      "connection_pool_size": 10,
      "credential_fields": {
        "username": {
          "label": "Database Username",
          "type": "text",
          "required": true
        },
        "password": {
          "label": "Database Password",
          "type": "password",
          "required": true
        }
      }
    },
    "version": "1.0.0"
  },
  "events": [],
  "services": [
    {
      "service_name": "execute_query",
      "display_name": "Execute Query",
      "description": "Execute a SELECT query",
      "service_type": "database_query",
      "service_config": {
        "operation_type": "query",
        "result_format": "json_array"
      },
      "parameter_schema": {
        "type": "object",
        "properties": {
          "sql": {
            "type": "string",
            "description": "SQL query with :param placeholders"
          },
          "parameters": {
            "type": "object",
            "description": "Parameter values",
            "additionalProperties": true
          }
        },
        "required": ["sql"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "success": {"type": "boolean"},
          "data": {"type": "array"},
          "row_count": {"type": "integer"}
        }
      },
      "timeout_seconds": 30,
      "is_active": true
    }
  ]
}
```

### 2. API Service (SendGrid)

```json
{
  "service_name": "Send Email",
  "service_type": "api_call",
  "description": "Send an email through SendGrid",
  "endpoint_template": "{{base_url}}/mail/send",
  "http_method": "POST",
  "request_config": {
    "parameter_method": "json_payload",
    "body_template": {
      "personalizations": [{
        "to": [{"email": "{{to_email}}"}],
        "subject": "{{subject}}"
      }],
      "from": {"email": "{{from_email}}"},
      "content": [{
        "type": "text/html",
        "value": "{{html_content}}"
      }]
    }
  },
  "parameter_schema": {
    "type": "object",
    "properties": {
      "to_email": {
        "type": "string",
        "format": "email",
        "description": "Recipient email"
      },
      "from_email": {
        "type": "string",
        "format": "email",
        "description": "Sender email"
      },
      "subject": {
        "type": "string",
        "description": "Email subject"
      },
      "html_content": {
        "type": "string",
        "description": "Email HTML content"
      }
    },
    "required": ["to_email", "from_email", "subject", "html_content"]
  }
}
```

## Common Mistakes

1. **Using `input_schema` instead of `parameter_schema`** - This will cause parameters not to appear in the flow designer
2. **Missing `key` field** - Every seed application must have a unique key
3. **Wrong structure** - Application config must be nested under `application` key
4. **Missing `additionalProperties: true`** for dynamic objects like database parameters
5. **Invalid service types** - Use only supported service types

## Best Practices

1. **Clear Parameter Descriptions**: Each parameter should have a clear description
2. **Examples**: Include example values in parameter descriptions
3. **Required Fields**: Mark required parameters in the `required` array
4. **Dynamic Parameters**: For services that accept dynamic parameters (like database queries), use `additionalProperties: true`
5. **Descriptive Names**: Use clear `display_name` values that appear in the UI

## Testing Parameters

After creating/updating a seed application:

1. Reinstall the application through the UI
2. Create a new flow
3. Add the service to the flow
4. Verify all parameters appear in the configuration panel
5. Check that parameter descriptions and examples are shown

## Database-Specific Considerations

For database services, parameters typically include:

- `sql` - The SQL query with parameter placeholders
- `parameters` - Object containing values for the placeholders

Example:
```json
"parameter_schema": {
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "SQL query with :param_name placeholders",
      "example": "SELECT * FROM users WHERE status = :status"
    },
    "parameters": {
      "type": "object",
      "description": "Parameter values for the query",
      "additionalProperties": true,
      "example": {
        "status": "active"
      }
    }
  },
  "required": ["sql"]
}
```

This ensures the flow designer shows:
- A text field for the SQL query
- A dynamic object field for parameters
- Clear examples of how to use them
# Comprehensive Guide for Creating Seed Applications

This guide provides detailed instructions on how to properly configure seed applications in IOFlow, with special attention to parameter mapping and service configuration.

## CRITICAL: Parameter Mapping for MCP Clients

When creating seed applications via MCP, it is ESSENTIAL to include proper parameter mappings. Without these mappings, IOFlow cannot correctly transform parameters between your application's format and the external API's format.

📋 **Quick Reference**: See [PARAMETER_MAPPING_QUICK_REFERENCE.md](PARAMETER_MAPPING_QUICK_REFERENCE.md) for a concise checklist and examples.

### Service Configuration Format

Services must use the standardized format with all configuration inside `service_config`:

```json
{
  "service_name": "verify_pan",
  "display_name": "Verify PAN",
  "description": "Verify PAN card details",
  "service_type": "api_call",
  "service_config": {
    "endpoint_template": "{{base_url}}/verify/pan/{{pan_number}}",
    "request_config": {
      "method": "GET",
      "parameter_method": "url_pattern",
      "headers_template": {
        "Authorization": "Bearer {{auth.api_key}}"
      }
    },
    "parameter_schema": {
      "type": "object",
      "properties": {
        "pan_number": {
          "type": "string",
          "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
          "description": "10-character PAN to verify"
        }
      },
      "required": ["pan_number"]
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "valid": {"type": "boolean"},
      "name": {"type": "string"},
      "status": {"type": "string"}
    }
  },
  "timeout_seconds": 30
}
```

### Key Points:
1. **All request configuration** goes inside `service_config.request_config`
2. **HTTP method** is defined as `request_config.method` (not at top level)
3. **URL endpoint** is defined as `service_config.endpoint_template`
4. **Headers** are defined in `request_config.headers_template`
5. **Parameters** are defined in `service_config.parameter_schema`

## Table of Contents

1. [Basic Structure](#basic-structure)
2. [Service Configuration](#service-configuration)
3. [Parameter Mapping](#parameter-mapping)
4. [URL Pattern Parameters](#url-pattern-parameters)
5. [Authentication Configuration](#authentication-configuration)
6. [Response Configuration](#response-configuration)
7. [Event Configuration](#event-configuration)
8. [Complete Examples](#complete-examples)

## Basic Structure

Every seed application must have the following structure:

```json
{
  "key": "unique_app_key",
  "application": {
    "app_name": "Display Name",
    "app_type": "api",
    "app_scope": "global",
    "description": "Application description",
    "category": "Integration",
    "auth_type": "api_key",
    "auth_config": {},
    "version": "1.0.0",
    "base_url": "https://api.example.com"
  },
  "services": [],
  "events": []
}
```

### Required Fields:
- `key`: Unique identifier (lowercase, letters, numbers, underscores only)
- `app_name`: Human-readable name
- `app_type`: One of ["database", "email", "api", "file_system", "memory", "flow"]
- `app_scope`: One of ["global", "tenant", "user"]
- `category`: One of ["Communication", "Productivity", "Analytics", "Database", "Integration", "Development", "API Platform", "Email", "Messaging", "Automation", "Other"]
- `auth_type`: One of ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]
- `version`: Semantic version (e.g., "1.0.0")

## Service Configuration

Services define the API endpoints your application can call. Each service MUST use the standardized format with configuration inside `service_config`:

```json
{
  "service_name": "unique_service_name",
  "display_name": "User Friendly Name",
  "description": "What this service does",
  "service_type": "api_call",
  "service_config": {
    "endpoint_template": "{{base_url}}/api/v1/endpoint",
    "request_config": {
      "method": "POST",
      "parameter_method": "body"
    },
    "parameter_schema": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {}
  },
  "timeout_seconds": 30
}
```

### Service Types:
- `api_call`: REST API endpoint
- `webhook`: Webhook receiver
- `email_send`: Email service
- `database_query`: Database query
- `llm_api_call`: LLM API call
- `mcp_call`: MCP tool call

## Parameter Mapping

This is crucial for proper API integration. In the new format, parameters are defined using JSON Schema:

### Required Configuration for Parameters:

1. **`service_config.parameter_schema`** field: A JSON schema object defining all parameters inside service_config
2. **`service_config.request_config`** field: Configuration specifying how parameters are passed
3. **`service_config.endpoint_template`**: The API endpoint URL template with `{{param_name}}` placeholders for URL parameters

### Parameter Schema Structure:

```json
"service_config": {
  "parameter_schema": {
    "type": "object",
    "properties": {
      "param_name": {
        "type": "string",
        "description": "Parameter description",
        "pattern": "^[A-Z0-9]+$",
        "minLength": 10,
        "maxLength": 10
      }
    },
    "required": ["param_name"],
    "additionalProperties": true
  }
}
```

IOFlow supports two parameter passing methods:

### 1. URL Pattern Parameters

For parameters that go in the URL path:

```json
{
  "service_name": "verify_pan",
  "display_name": "Verify PAN Card",
  "description": "Verify PAN card details",
  "service_type": "api_call",
  "service_config": {
    "endpoint_template": "{{base_url}}/verify/pan/{{pan_number}}",
    "request_config": {
      "method": "GET",
      "parameter_method": "url_pattern",
      "headers_template": {
        "Authorization": "Bearer {{auth.api_key}}"
      }
    },
    "parameter_schema": {
      "type": "object",
      "properties": {
        "pan_number": {
          "type": "string",
          "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
          "description": "10-character PAN to verify"
        }
      },
      "required": ["pan_number"]
    }
  }
}
```

### 2. Request Body/Query Parameters

For parameters in request body or query string:

```json
{
  "service_name": "send_message",
  "display_name": "Send Message",
  "description": "Send a message to recipient",
  "service_type": "api_call",
  "service_config": {
    "endpoint_template": "{{base_url}}/messages/send",
    "request_config": {
      "method": "POST",
      "parameter_method": "body",
      "body_template": {
        "To": "{{recipient}}",
        "Body": "{{message}}"
      }
    },
    "parameter_schema": {
      "type": "object",
      "properties": {
        "recipient": {
          "type": "string",
          "description": "Recipient identifier"
        },
        "message": {
          "type": "string",
          "description": "Message content"
        }
      },
      "required": ["recipient", "message"]
    }
  }
}
```

### Important Notes on Parameter Mapping:

1. **Parameter Name Mapping**: Use the body_template or query_params to map IOFlow parameter names to API parameter names
   - IOFlow parameter: `recipient`
   - API expects: `To`
   - Use in body_template: `"To": "{{recipient}}"`

2. **URL Pattern Parameters**: Use `{{parameter_name}}` directly in the endpoint_template
   - Must set `"parameter_method": "url_pattern"` in service_config.request_config

3. **Body Parameters**: Use body_template with mappings
   - Must set `"parameter_method": "body"` in service_config.request_config

4. **Query Parameters**: Use query_params in service_config.request_config
   ```json
   "service_config": {
     "request_config": {
       "parameter_method": "query",
       "query_params": {
         "api_param": "{{ioflow_param}}"
       }
     }
   }
   ```

## URL Pattern Parameters

For APIs that expect parameters in the URL path (like `/api/verify/{pan}`):

```json
{
  "service_name": "verify_gstin",
  "display_name": "Verify GSTIN",
  "description": "Verify GST identification number",
  "service_type": "api_call",
  "service_config": {
    "endpoint_template": "{{base_url}}/gst/verify/{{gstin}}",
    "request_config": {
      "method": "GET",
      "parameter_method": "url_pattern",
      "headers_template": {
        "Authorization": "Bearer {{auth.api_key}}"
      }
    },
    "parameter_schema": {
      "type": "object",
      "properties": {
        "gstin": {
          "type": "string",
          "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}[A-Z]{1}[0-9]{1}$",
          "description": "15-character GSTIN to verify"
        }
      },
      "required": ["gstin"]
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "valid": {"type": "boolean"},
      "company_name": {"type": "string"},
      "status": {"type": "string"}
    }
  }
}
```

## Complex Nested Body Templates

IOFlow supports complex nested structures in body_template with full template variable substitution at any depth:

### Nested Objects and Arrays

```json
{
  "service_name": "send_template_message",
  "service_config": {
    "endpoint_template": "{{base_url}}/messages/send",
    "request_config": {
      "method": "POST",
      "parameter_method": "json_payload",
      "body_template": {
        "integrated_number": "{{phone_number}}",
        "content_type": "template",
        "payload": {
          "type": "template",
          "template": {
            "name": "{{template_name}}",
            "language": {
              "code": "{{language_code}}",
              "policy": "deterministic"
            },
            "to_and_components": [
              {
                "to": ["{{recipient_number}}"],
                "components": [
                  {
                    "type": "body",
                    "parameters": [
                      {
                        "type": "text",
                        "text": "{{var1}}"
                      },
                      {
                        "type": "text",
                        "text": "{{var2}}"
                      }
                    ]
                  }
                ]
              }
            ]
          },
          "messaging_product": "whatsapp"
        }
      }
    }
  }
}
```

**Key Features:**
- Template variables ({{variable_name}}) are processed at any nesting level
- Works in objects, arrays, and arrays of objects
- Supports complex API formats like WhatsApp Business API
- All template variables are replaced with actual parameter values before sending the request

## Authentication Configuration

### API Key Authentication

```json
{
  "auth_type": "api_key",
  "auth_config": {
    "header_name": "X-API-Key",
    "header_prefix": "Bearer"  // Optional: prefix for the API key (default: "Bearer" for Authorization header, "" for others)
  }
}
```

**Important Notes:**
- `header_prefix`: Specifies the prefix to add before the API key value
  - Default is "Bearer" if header_name is "Authorization"
  - Default is "" (empty) for custom header names
  - Set explicitly to "" if your API expects just the key without any prefix

Examples:
```json
// Standard Bearer token
{
  "auth_type": "api_key",
  "auth_config": {
    "header_name": "Authorization",
    "header_prefix": "Bearer"  // Results in: "Authorization: Bearer YOUR_API_KEY"
  }
}

// Custom header without prefix
{
  "auth_type": "api_key",
  "auth_config": {
    "header_name": "authkey",
    "header_prefix": ""  // Results in: "authkey: YOUR_API_KEY"
  }
}
```

In service configuration:
```json
"service_config": {
  "request_config": {
    "headers_template": {
      "X-API-Key": "{{auth.api_key}}"
    }
  }
}
```

### OAuth2 Authentication

```json
{
  "auth_type": "oauth2",
  "auth_config": {
    "authorization_url": "https://api.example.com/oauth/authorize",
    "token_url": "https://api.example.com/oauth/token",
    "scopes": ["read", "write"],
    "grant_type": "authorization_code",
    "authorization_params": {
      "access_type": "offline",
      "prompt": "consent"
    }
  }
}
```

#### Important OAuth2 Grant Type Notes:

1. **Google APIs (Google Sheets, Gmail, Google Tasks, etc.)**:
   - **Initial Authorization**: Only supports `authorization_code` grant type
   - **Token Refresh**: Automatically uses `refresh_token` grant type (handled by IOFlow)
   - **NOT Supported**: `client_credentials` grant type is NOT supported by Google
   - **Required Settings**:
     - Always set `"grant_type": "authorization_code"`
     - Always include `"access_type": "offline"` to receive refresh tokens
     - Set `"prompt": "consent"` to ensure refresh token is returned

2. **Common OAuth2 Providers**:
   - **Microsoft/Azure**: Supports `authorization_code` and `client_credentials`
   - **Slack**: Supports `authorization_code` only
   - **GitHub**: Supports `authorization_code` only
   - **Custom APIs**: Check provider documentation for supported grant types

3. **Token Refresh Behavior**:
   - IOFlow automatically handles token refresh using the `refresh_token` grant type
   - If no refresh token is available, IOFlow will NOT fallback to `client_credentials`
   - For Google APIs, refresh tokens may expire after 6 months of inactivity
   - Ensure your OAuth2 app has refresh token permissions enabled

4. **Error Prevention**:
   - If you see "unsupported_grant_type" errors, verify the provider supports your configured grant type
   - For Google APIs, this error usually means `client_credentials` was attempted
   - Always store refresh tokens securely when received during initial authorization

### Basic Authentication

```json
{
  "auth_type": "basic",
  "auth_config": {
    "username_field": "username",
    "password_field": "password"
  }
}
```

## Response Configuration

Define how to extract data from API responses:

```json
{
  "response_config": {
    "success_path": "$.status",
    "success_value": "success",
    "data_path": "$.data",
    "error_path": "$.error.message",
    "pagination": {
      "type": "offset",
      "offset_param": "offset",
      "limit_param": "limit",
      "total_path": "$.total"
    }
  }
}
```

## Event Configuration

Events define triggers for your application. Events MUST use the standardized format:

### Important Note on Webhook URLs

Webhook events in IOFlow use a standardized URL format:
- Default webhook URL: `/webhooks/{app_id}/{event_name}`
- Custom endpoint (optional): Specify via `api_endpoint` field
- The `event_configuration` contains webhook-specific settings (method, headers, auth)
- DO NOT put `webhook_url` or `webhook_path` in `event_configuration`

### Webhook Event

```json
{
  "event_name": "message_received",
  "display_name": "Message Received Webhook",
  "description": "Triggered when a message is received",
  "event_type": "webhook",
  "api_endpoint": "/custom/message_received",
  "event_configuration": {
    "webhook_method": "POST",
    "headers": {
      "X-Webhook-Signature": "{{signature}}"
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "from": {"type": "string"},
      "body": {"type": "string"},
      "timestamp": {"type": "string", "format": "date-time"}
    }
  },
  "sample_payload": {
    "from": "+1234567890",
    "body": "Hello",
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "sync_mode": "asynchronous"
}
```

### Scheduled Event

```json
{
  "event_name": "daily_report",
  "display_name": "Daily Report Generator",
  "description": "Runs daily at 9 AM",
  "event_type": "schedule",
  "event_configuration": {
    "schedule": {
      "cron_expression": "0 9 * * *",
      "timezone": "UTC"
    }
  },
  "sync_mode": "asynchronous"
}
```

## MCP Tool Usage Examples

When using MCP tools to create seed applications, ensure you include ALL required fields:

### Creating a Service with URL Parameters via MCP

```python
# Using add_service_to_application MCP tool
await add_service_to_application(
    app_key="vayana_api",
    service_name="verify_pan",
    service_type="api_call",
    description="Verify PAN card details",
    service_config={
        "endpoint_template": "/verify/pan/{{pan_number}}",
        "request_config": {
            "method": "GET",
            "parameter_method": "url_pattern",
            "headers_template": {
                "Authorization": "Bearer {{auth.api_key}}"
            }
        },
        "parameter_schema": {
            "type": "object",
            "properties": {
                "pan_number": {
                    "type": "string",
                    "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
                    "description": "PAN to verify"
                }
            },
            "required": ["pan_number"]
        }
    },
    sample_input={"pan_number": "ABCDE1234F"},
    sample_output={"status": "success", "data": {"name": "John Doe", "pan": "ABCDE1234F"}}
)
```

## Complete Examples

### Example 1: Verification API with URL Parameters

```json
{
  "key": "verification_api",
  "application": {
    "app_name": "Verification API",
    "app_type": "global",
    "description": "Document verification services",
    "category": "API Platform",
    "auth_type": "api_key",
    "auth_config": {
      "header_name": "Authorization"
    },
    "version": "1.0.0",
    "base_url": "https://api.verify.com"
  },
  "services": [
    {
      "service_name": "verify_pan",
      "display_name": "Verify PAN",
      "description": "Verify PAN card details",
      "service_type": "api_call",
      "service_config": {
        "endpoint_template": "/v1/pan/{{pan_number}}/verify",
        "request_config": {
          "method": "GET",
          "parameter_method": "url_pattern",
          "headers_template": {
            "Authorization": "Bearer {{auth.api_key}}",
            "Content-Type": "application/json"
          }
        },
        "parameter_schema": {
          "type": "object",
          "properties": {
            "pan_number": {
              "type": "string",
              "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
              "description": "PAN to verify"
            }
          },
          "required": ["pan_number"]
        }
      },
      "sample_input": "{\"pan_number\": \"ABCDE1234F\"}",
      "sample_output": "{\"status\": \"success\", \"data\": {\"name\": \"John Doe\", \"pan\": \"ABCDE1234F\", \"status\": \"Active\"}}"
    }
  ],
  "events": []
}
```

### Example 2: Messaging API with Body Parameters

```json
{
  "key": "messaging_api",
  "application": {
    "app_name": "Messaging API",
    "app_type": "global",
    "description": "Send messages via multiple channels",
    "category": "Communication",
    "auth_type": "api_key",
    "auth_config": {
      "header_name": "X-API-Key"
    },
    "version": "1.0.0",
    "base_url": "https://api.messaging.com"
  },
  "services": [
    {
      "service_name": "send_whatsapp",
      "display_name": "Send WhatsApp Message",
      "description": "Send WhatsApp message",
      "service_type": "api_call",
      "service_config": {
        "endpoint_template": "/messages/whatsapp",
        "request_config": {
          "method": "POST",
          "parameter_method": "body",
          "headers_template": {
            "X-API-Key": "{{auth.api_key}}",
            "Content-Type": "application/json"
          },
          "body_template": {
            "To": "{{recipient_number}}",
            "Body": "{{message_text}}",
            "MediaUrl": "{{media_url}}"
          }
        },
        "parameter_schema": {
          "type": "object",
          "properties": {
            "recipient_number": {
              "type": "string",
              "pattern": "^\\+[1-9]\\d{1,14}$",
              "description": "WhatsApp number"
            },
            "message_text": {
              "type": "string",
              "description": "Message to send"
            },
            "media_url": {
              "type": "string",
              "format": "uri",
              "description": "Optional media URL"
            }
          },
          "required": ["recipient_number", "message_text"]
        }
      },
      "sample_input": "{\"recipient_number\": \"+1234567890\", \"message_text\": \"Hello from IOFlow!\"}",
      "sample_output": "{\"status\": \"sent\", \"message_id\": \"msg_123456\"}"
    }
  ],
  "events": [
    {
      "event_name": "Message Status Update",
      "display_name": "Message Status Update",
      "description": "Webhook for message delivery status",
      "trigger_type": "webhook",
      "trigger_config": {
        "webhook_path": "/webhooks/message/status"
      },
      "sample_payload": "{\"message_id\": \"msg_123456\", \"status\": \"delivered\", \"timestamp\": \"2024-01-01T00:00:00Z\"}",
      "sync_mode": "asynchronous"
    }
  ]
}
```

## Best Practices

1. **Use standardized structure**: Always put configuration inside `service_config` with `request_config` nested within

2. **Specify parameter_method**: Always set this in `service_config.request_config` to indicate how parameters are passed

3. **Include sample data**: Provide realistic sample_input and sample_output for testing

4. **Document parameter patterns**: Use regex patterns for validation where applicable

5. **Handle optional parameters**: Mark parameters as required: false when appropriate

6. **Use proper data types**: Ensure parameter types match expected API input

7. **Define method in request_config**: HTTP method should be in `request_config.method`, not at top level

## Common Mistakes to Avoid

1. **Incorrect structure**: Configuration must be inside `service_config`, not at top level
2. **Incorrect URL patterns**: Use `{{param}}` not `{param}` for URL parameters
3. **Missing request_config**: Always include `service_config.request_config` with method and parameter_method
4. **Incomplete auth configuration**: Ensure auth headers are properly templated
5. **Wrong method location**: HTTP method goes in `request_config.method`, not at service top level
6. **Missing parameter_schema**: Always include parameter_schema inside service_config
7. **Using deprecated fields**: Don't use old fields like `configuration`, `http_method` at top level

## Troubleshooting Parameter Issues

### Issue: "Configuration not in correct format"
**Cause**: Service configuration is not following the standardized structure.

**Solution**: Ensure all configuration is inside `service_config`:
```json
"service_config": {
  "endpoint_template": "{{base_url}}/api/endpoint",
  "request_config": {
    "method": "POST",
    "parameter_method": "body"
  },
  "parameter_schema": {
    "type": "object",
    "properties": {}
  }
}
```

### Issue: "Service receives parameter in URL, even URL is not mapped"
**Cause**: Missing or incorrect `parameter_method` in `service_config.request_config`.

**Solution**: Set the correct parameter method and use URL patterns:
```json
"service_config": {
  "endpoint_template": "/verify/pan/{{pan_number}}",
  "request_config": {
    "method": "GET",
    "parameter_method": "url_pattern"  ← MUST BE SET
  }
}
```

### Issue: Parameters not appearing in API calls
**Cause**: IOFlow cannot find the parameter configuration.

**Solution**: Ensure these are present inside `service_config`:
1. `parameter_schema` field with proper JSON schema
2. `request_config.method` field with HTTP method
3. `request_config.parameter_method` field

## Validation

Before deploying your seed application:

1. Validate JSON syntax
2. Ensure all required fields are present
3. Test parameter mapping with sample data
4. Verify authentication configuration
5. Test with actual API calls

Use the IOFlow validation endpoint:
```
POST /api/v1/seed-applications/validate
{
  "json_content": "<your seed application JSON>"
}
```
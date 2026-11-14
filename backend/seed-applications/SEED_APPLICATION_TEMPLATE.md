# Seed Application JSON Template

## IMPORTANT: This structure MUST be followed exactly!

```json
{
  "key": "unique_key_lowercase_no_spaces",
  "application": {
    "app_name": "Application Display Name",
    "app_type": "global",
    "description": "Brief description of what this application does",
    "category": "Category",
    "auth_type": "auth_type",
    "auth_config": {
      // Authentication configuration based on auth_type
    },
    "version": "1.0.0",
    "base_url": "https://api.example.com",
    "icon_url": "https://example.com/icon.png",
    "webhook_config": null
  },
  "events": [
    // Optional: Event definitions for webhooks/triggers
  ],
  "services": [
    {
      "service_name": "internal_service_name",
      "display_name": "User-Friendly Service Name",
      "description": "What this service does",
      "service_type": "api_call",
      "service_config": {
        // Service-specific configuration
      },
      "is_async": false,
      "parameter_schema": {
        "type": "object",
        "properties": {
          // Define input parameters
        },
        "required": []
      },
      "output_schema": {
        "type": "object",
        "properties": {
          // Define output structure
        }
      },
      "timeout_seconds": 30,
      "is_active": true
    }
  ]
}
```

## Key Rules:

1. **MUST have `key` field** at top level - unique identifier
2. **MUST have `application` object** - contains app metadata
3. **MUST have `services` array** - defines available services
4. **`events` array is optional** - for webhook/trigger definitions

## Categories:
- Communication
- Productivity
- Analytics
- Database
- Integration
- Other

## Auth Types:
- none
- api_key
- oauth2
- basic
- token_exchange
- custom

## Service Types:
- api_call
- webhook
- email_send
- llm_api_call
- mcp_call
- database_query

## Common Mistakes to Avoid:
❌ Missing `key` field
❌ Putting application fields at top level instead of inside `application` object
❌ Missing `services` array
❌ Using unsupported service types
❌ Invalid JSON syntax

## OAuth2 Grant Type Configuration:

### IMPORTANT for OAuth2 Applications:

1. **Google APIs (Sheets, Gmail, Tasks, Calendar, Drive)**:
   ```json
   "auth_config": {
     "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
     "token_url": "https://oauth2.googleapis.com/token",
     "redirect_uri": "http://localhost:5173/oauth/callback",
     "scopes": ["scope1", "scope2"],
     "grant_type": "authorization_code",  // REQUIRED
     "authorization_params": {            // REQUIRED for Google OAuth2
       "access_type": "offline",          // REQUIRED for refresh tokens
       "prompt": "consent"                // REQUIRED to get refresh token
     }
   }
   ```
   - ⚠️ Google does NOT support `client_credentials` grant type
   - ⚠️ Without `access_type: offline`, you won't get refresh tokens
   - ⚠️ Without refresh tokens, users must re-authenticate when token expires

2. **Other OAuth2 Providers**:
   - Check provider documentation for supported grant types
   - Most only support `authorization_code` for user authentication
   - Some enterprise APIs support `client_credentials` for server-to-server

## Quick Copy Templates:

### API Key Application:
```json
{
  "key": "myapp",
  "application": {
    "app_name": "My Application",
    "app_type": "global",
    "description": "Description here",
    "category": "Integration",
    "auth_type": "api_key",
    "auth_config": {
      "header_name": "Authorization",
      "header_prefix": "Bearer",
      "credential_fields": {
        "api_key": {
          "label": "API Key",
          "type": "password",
          "required": true
        }
      }
    },
    "version": "1.0.0",
    "base_url": "https://api.example.com"
  },
  "events": [],
  "services": []
}
```

### Database Application:
```json
{
  "key": "mydb",
  "application": {
    "app_name": "My Database",
    "app_type": "global",
    "description": "Database connection",
    "category": "Database",
    "base_url": "postgresql://localhost:5432/mydb",
    "auth_type": "basic",
    "auth_config": {
      "database_type": "postgresql",
      "credential_fields": {
        "username": {
          "label": "Username",
          "type": "text",
          "required": true
        },
        "password": {
          "label": "Password",
          "type": "password",
          "required": true
        }
      }
    },
    "version": "1.0.0"
  },
  "events": [],
  "services": []
}
```
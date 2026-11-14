# Seed Applications

This directory contains JSON definitions for seed applications that can be installed into IOFlow.

## Structure

Each seed application is defined in a separate JSON file with the following structure:

```json
{
  "key": "unique_app_key",
  "application": {
    "app_name": "Application Name",
    "app_type": "global",
    "description": "Application description",
    "category": "Communication",
    "auth_type": "oauth2",
    "auth_config": {},
    "version": "1.0.0",
    "base_url": "https://api.example.com",
    "icon_url": "https://example.com/icon.png"
  },
  "services": [
    {
      "service_name": "Service Name",
      "service_type": "api_call",
      "description": "Service description",
      "endpoint_url": "{{base_url}}/endpoint",
      "http_method": "POST",
      "request_config": {
        "parameter_method": "json_payload",
        "body_template": {}
      },
      "response_config": {
        "success_check": {
          "type": "status_code",
          "value": [200]
        }
      },
      "parameter_schema": {
        "type": "object",
        "properties": {}
      },
      "sync_mode": "synchronous"  // or "asynchronous"
    }
  ],
  "events": [
    {
      "event_name": "Event Name",
      "event_type": "webhook",
      "description": "Event description",
      "event_configuration": {
        "webhook_url": "/webhooks/example",
        "verification_type": "hmac_header",
        "verification_config": {}
      },
      "sync_mode": "asynchronous"  // or "synchronous"
    }
  ],
  "metadata": {
    "author": "IOFlow Team",
    "created_at": "2024-01-01",
    "tags": ["integration", "api"]
  }
}
```

## Field Definitions

### sync_mode
The `sync_mode` field is used consistently across services and events:
- `"synchronous"` - The operation completes immediately and returns the result
- `"asynchronous"` - The operation runs in the background and returns immediately

Note: While the JSON uses `sync_mode` consistently, internally:
- ApplicationService stores this as `is_async` (boolean)
- ApplicationEvent stores this as `sync_mode` (string)

The seed manager handles this conversion automatically.

## Adding New Applications

To add a new seed application:
1. Create a new JSON file with the application key as the filename (e.g., `slack.json`)
2. Follow the structure above
3. Use `sync_mode` consistently for both services and events
4. Run the refresh cache command in the admin UI to load the new application
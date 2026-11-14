# Application Management System API Documentation

## Overview
The Application Management System allows you to manage integrations with external applications in IOFlow.

## Authentication
All endpoints require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <your-access-token>
```

## Endpoints

### Applications

#### List Applications
```
GET /api/v1/applications/
```

Query Parameters:
- `app_type`: Filter by type (global, tenant)
- `category`: Filter by category (Communication, Productivity, etc.)
- `status`: Filter by status (active, inactive, deprecated)

Response:
```json
[
  {
    "app_id": "9c91f84b-...",
    "app_name": "Slack",
    "app_type": "global",
    "description": "Team communication and collaboration platform",
    "icon_url": "https://...",
    "category": "Communication",
    "auth_type": "oauth2",
    "auth_config": {
      "oauth_url": "https://slack.com/oauth/v2/authorize",
      "token_url": "https://slack.com/api/oauth.v2.access",
      "scopes": ["channels:read", "chat:write"]
    },
    "status": "active",
    "version": "2.0.0",
    "created_at": "2025-06-23T18:49:28",
    "updated_at": "2025-06-23T18:49:28"
  }
]
```

#### Get Application
```
GET /api/v1/applications/{app_id}
```

#### Create Application
```
POST /api/v1/applications/
```

Request Body:
```json
{
  "app_name": "Custom CRM",
  "app_type": "tenant",
  "description": "Our custom CRM system",
  "category": "CRM",
  "auth_type": "api_key",
  "auth_config": {
    "api_key_header": "X-API-Key",
    "api_key_required": true
  }
}
```

#### Update Application
```
PUT /api/v1/applications/{app_id}
```

#### Delete Application
```
DELETE /api/v1/applications/{app_id}
```

### Events

#### List Application Events
```
GET /api/v1/applications/{app_id}/events
```

Response:
```json
[
  {
    "event_id": "abc123...",
    "app_id": "9c91f84b-...",
    "event_name": "new_message",
    "display_name": "New Message",
    "description": "Triggers when a new message is posted",
    "trigger_type": "webhook",
    "trigger_config": {
      "event_types": ["message"],
      "filter_bot_messages": true
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "text": {"type": "string"},
        "user": {"type": "string"}
      }
    },
    "is_active": true,
    "created_at": "2025-06-23T18:49:28"
  }
]
```

#### Create Event
```
POST /api/v1/applications/{app_id}/events
```

Request Body:
```json
{
  "event_name": "user_joined",
  "display_name": "User Joined Channel",
  "description": "Triggers when a user joins a channel",
  "trigger_type": "webhook",
  "trigger_config": {
    "event_types": ["member_joined_channel"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "user": {"type": "string"},
      "channel": {"type": "string"}
    }
  }
}
```

#### Update Event
```
PUT /api/v1/applications/{app_id}/events/{event_id}
```

#### Delete Event
```
DELETE /api/v1/applications/{app_id}/events/{event_id}
```

### Services

#### List Application Services
```
GET /api/v1/applications/{app_id}/services
```

Response:
```json
[
  {
    "service_id": "def456...",
    "app_id": "9c91f84b-...",
    "service_name": "send_message",
    "display_name": "Send Message",
    "description": "Send a message to a Slack channel",
    "service_type": "action",
    "http_method": "POST",
    "endpoint_template": "https://slack.com/api/chat.postMessage",
    "headers_template": {
      "Authorization": "Bearer {{auth.access_token}}"
    },
    "body_template": {
      "channel": "{{input.channel}}",
      "text": "{{input.text}}"
    },
    "input_schema": {
      "type": "object",
      "properties": {
        "channel": {"type": "string"},
        "text": {"type": "string"}
      },
      "required": ["channel", "text"]
    },
    "is_active": true,
    "created_at": "2025-06-23T18:49:28"
  }
]
```

#### Create Service
```
POST /api/v1/applications/{app_id}/services
```

#### Update Service
```
PUT /api/v1/applications/{app_id}/services/{service_id}
```

#### Delete Service
```
DELETE /api/v1/applications/{app_id}/services/{service_id}
```

### Subscriptions

#### List My Subscriptions
```
GET /api/v1/applications/subscriptions/
```

Response:
```json
[
  {
    "subscription_id": "xyz789...",
    "app_id": "9c91f84b-...",
    "tenant_id": "638417dc-...",
    "auth_credentials": {
      "access_token": "xoxb-..."
    },
    "subscription_config": {
      "webhook_secret": "abc123"
    },
    "webhook_url": "https://myapp.com/webhooks/slack",
    "status": "active",
    "subscribed_at": "2025-06-23T19:00:00"
  }
]
```

#### Create Subscription
```
POST /api/v1/applications/subscriptions/
```

Request Body:
```json
{
  "app_id": "9c91f84b-...",
  "auth_credentials": {
    "access_token": "xoxb-your-token"
  },
  "subscription_config": {
    "webhook_secret": "your-secret"
  },
  "webhook_url": "https://yourapp.com/webhooks/slack"
}
```

#### Update Subscription
```
PUT /api/v1/applications/subscriptions/{subscription_id}
```

#### Delete Subscription
```
DELETE /api/v1/applications/subscriptions/{subscription_id}
```

## Error Responses

All endpoints return standard HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 409: Conflict (e.g., duplicate names)
- 500: Internal Server Error

Error Response Format:
```json
{
  "detail": "Error message here"
}
```

## Permissions

- **Global Applications**: Only admins can create, update, or delete
- **Tenant Applications**: Users can manage applications owned by their tenant
- **Subscriptions**: Users can only manage subscriptions for their own tenant

## Template Variables

In service templates, you can use:
- `{{auth.field}}`: Access authentication credentials
- `{{input.field}}`: Access input parameters
- `{{trigger.field}}`: Access trigger data (in flows)
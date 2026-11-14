# Seed Applications API Documentation

## Overview

The Seed Applications API provides endpoints for managing seed applications in IOFlow. Seed applications are pre-configured application templates that can be installed, updated, and uninstalled.

## Authentication

All endpoints require authentication via Bearer token:

```
Authorization: Bearer <your-api-key>
```

## Endpoints

### List Seed Applications

```
GET /api/v1/seed-applications/
```

Lists all available seed applications and their installation status.

**Response:**
```json
{
  "applications": [
    {
      "key": "sendgrid",
      "name": "SendGrid",
      "description": "Email delivery and management service",
      "category": "Communication",
      "auth_type": "api_key",
      "version": "1.0.0",
      "status": "installed",
      "installed_version": "1.0.0",
      "subscription_count": 2,
      "service_count": 2,
      "event_count": 1
    }
  ],
  "total": 10,
  "installed_count": 3
}
```

### Get Seed Application Details

```
GET /api/v1/seed-applications/{application_key}
```

Get detailed information about a specific seed application.

### Install Seed Application

```
POST /api/v1/seed-applications/install
```

Install or reinstall a seed application.

**Request Body:**
```json
{
  "application_key": "sendgrid",
  "force_reinstall": false
}
```

**Note:** If `force_reinstall` is true, all existing subscriptions will be deleted!

### Uninstall Seed Application

```
POST /api/v1/seed-applications/{application_key}/uninstall
```

Uninstall an installed seed application.

**Query Parameters:**
- `force` (boolean, default: false): Force uninstall even if subscriptions exist

**Response:**
```json
{
  "success": true,
  "message": "Successfully uninstalled application 'sendgrid'",
  "deleted": {
    "app_id": "app_123",
    "services": 2,
    "events": 1,
    "subscriptions": 0
  }
}
```

**Error Response (if subscriptions exist and force=false):**
```json
{
  "detail": {
    "message": "Cannot uninstall application with 2 active subscriptions",
    "subscription_count": 2,
    "suggestion": "Use force=true to uninstall anyway (this will delete all subscriptions)"
  }
}
```

### Create Seed Application

```
POST /api/v1/seed-applications/create
```

Create a new seed application (admin only).

### Update Seed Application

```
PUT /api/v1/seed-applications/{application_key}
```

Update an existing seed application (admin only).

### Delete Seed Application

```
DELETE /api/v1/seed-applications/{application_key}
```

Delete a seed application file. The application must be uninstalled first.

### Refresh Cache

```
POST /api/v1/seed-applications/refresh-cache
```

Refresh the seed applications cache after adding new files.

## Permissions

- **View/List**: All authenticated users
- **Install/Uninstall**: Instance Admin only
- **Create/Update/Delete**: Instance Admin only

## Error Codes

- `400`: Bad Request (e.g., trying to uninstall with active subscriptions)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (application not found)
- `409`: Conflict (application already installed)
- `500`: Internal Server Error
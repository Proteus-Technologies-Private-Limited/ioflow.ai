# Seed Applications Guide

## Overview

Seed applications are pre-configured application templates that can be installed by INSTANCE_ADMIN users. They provide ready-to-use integrations with popular services.

## Available Seed Applications

1. **Atlascore** - Indian government services integration
2. **Gmail** - Email integration with Gmail
3. **SendGrid** - Email delivery service
4. **GitHub** - GitHub API integration
5. **Slack** - Slack messaging integration

## API Endpoints

### Seed Applications Management
- `GET /api/v1/seed-applications/` - List available seed applications and their status
- `GET /api/v1/seed-applications/{key}` - Get details of a specific seed application
- `POST /api/v1/seed-applications/install` - Install a seed application (INSTANCE_ADMIN only)
- `POST /api/v1/seed-applications/refresh-cache` - Refresh seed applications cache (INSTANCE_ADMIN only)

### Regular Applications
- `GET /api/v1/applications/` - List all installed applications (both global and tenant-specific)

## Installation Status

When listing seed applications, each application shows one of these statuses:
- `NOT_INSTALLED` - Application is available but not installed
- `INSTALLED` - Application is installed and up to date
- `UPDATE_AVAILABLE` - A newer version is available in the seed files

## Current Status in Your System

Based on the database check:
- Several seed applications are already **installed as global applications**:
  - Slack (global)
  - SendGrid (global)
  - GitHub (global)
  - Gmail (appears to be installed based on the test)
  - Atlascore (appears to be installed based on the test)

## Frontend Integration

The frontend should show seed applications in two places:

1. **Seed Applications Section** (for INSTANCE_ADMIN only)
   - Shows available seed applications from `/api/v1/seed-applications/`
   - Allows installation of new seed applications
   - Shows update status for installed applications

2. **Applications Section** (for all users based on permissions)
   - Shows installed applications from `/api/v1/applications/`
   - Global applications visible to all users
   - Tenant applications visible to tenant members

## Troubleshooting

If seed applications are not visible in the frontend:

1. **Check User Role**: Ensure you're logged in as INSTANCE_ADMIN
2. **Check Frontend Route**: Look for a "Seed Applications" menu item or section
3. **Check Browser Console**: Look for any API errors
4. **Verify API Access**: Test the endpoint directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:7001/api/v1/seed-applications/
   ```

## For Frontend Developers

To display seed applications:

1. Call `/api/v1/seed-applications/` to get available seeds
2. Only show this section to users with `role === 'INSTANCE_ADMIN'`
3. Display installation status and allow install/update actions
4. After installation, applications appear in the regular applications list

## Note on Permissions

- Only INSTANCE_ADMIN users can:
  - View seed applications
  - Install seed applications
  - Refresh seed cache
- All users can view installed global applications (based on their role permissions)
# OAuth Connection Workflow Improvements

## Summary

The OAuth connection workflow has been simplified to provide a better user experience and clearer architecture.

## Changes Made

### 1. Unified Connection Modal
- **Before**: Users had to use separate modals (CredentialsModal, ConnectionSettingsModal, UpdateCredentialsModal)
- **After**: Single `ConnectionModal` component handles all connection operations
- **Location**: `/frontend/src/components/applications/ConnectionModal.js`

### 2. OAuth Credential Hierarchy
- **Application-level defaults**: OAuth credentials can be stored at the application level
- **Tenant-level override**: Tenants can optionally provide their own OAuth credentials
- **Clear indication**: UI shows whether default or custom credentials are being used

### 3. Backend Changes
- **Subscription creation**: Automatically uses app-level default credentials if tenant doesn't provide custom ones
- **Credential flag**: `subscription_config.using_default_credentials` tracks which credentials are being used
- **Auth config structure**: Added `default_credentials` to application auth_config

### 4. UI/UX Improvements
- **Single-step process**: Connect button opens one modal with all settings
- **Tabbed interface**: Connection, Authentication, and Advanced tabs
- **Visual indicators**: 
  - Blue info box when default credentials are available
  - Toggle to use custom credentials
  - Grayed out fields when using defaults
  - "Setup Required" vs "Connected" status

### 5. Database Structure

```json
// Application.auth_config now includes:
{
  "oauth_url": "...",
  "token_url": "...",
  "scopes": [...],
  "default_credentials": {
    "client_id": "app-default-client-id",
    "client_secret": "app-default-secret",
    "description": "Default OAuth credentials for all tenants"
  },
  "allow_credential_override": true,
  "credential_help_text": "Custom credentials recommended for production"
}
```

## User Flow

1. User clicks "Connect" on an application
2. ConnectionModal opens with three tabs:
   - **Connection**: Webhook URL, Base URL, Test endpoint
   - **Authentication**: Shows default credentials available, toggle for custom
   - **Advanced**: Custom parameters (headers, query, body)
3. If using defaults, credentials are pre-filled and grayed out
4. If using custom, user enters their own OAuth credentials
5. Test connection button available to verify setup
6. Single "Connect" button completes the process

## Benefits

1. **Simplified UX**: One modal instead of multiple, clearer flow
2. **Flexibility**: Supports both shared app credentials and tenant-specific
3. **Security**: Tenants can use their own OAuth apps for production
4. **Backward Compatible**: Existing subscriptions continue to work
5. **Clear Communication**: Users understand what credentials are being used

## Migration

Run the migration script to add default credential support:
```bash
python scripts/add_default_oauth_credentials.py
```

To set default credentials for testing:
```bash
python scripts/set_default_oauth_creds.py
```

## Architecture Decision

**Q: Should OAuth credentials be per-tenant or per-application?**

**A: Both!** The new architecture supports:
- **Default credentials at app level**: Useful for development, testing, and small deployments
- **Custom credentials at tenant level**: Essential for production, multi-tenant SaaS

This hybrid approach provides the best of both worlds:
- Easy onboarding with default credentials
- Enterprise-ready with tenant isolation
- Clear upgrade path from default to custom
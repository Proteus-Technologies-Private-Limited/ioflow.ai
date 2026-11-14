# OAuth2 Default Credentials Flow

## Overview

When using default OAuth2 credentials, users still need to complete the authorization flow to obtain access and refresh tokens. The default credentials only provide the `client_id` and `client_secret`, not the tokens.

## User Flow

### 1. Initial Connection
- User clicks "Connect" on Google Sheets (or any OAuth2 app)
- ConnectionModal opens showing default credentials are available
- User clicks "Connect" → Subscription created with default `client_id` and `client_secret`
- Status shows "Auth Required" (yellow warning)

### 2. OAuth2 Authorization
- User clicks settings icon to open ConnectionModal again
- In the Authentication tab, they see:
  - Info box explaining default credentials are being used
  - Warning that authorization is still required
  - "Authorize with Google" button
- User clicks the authorize button → OAuth2 popup opens
- User authorizes in Google → Callback saves access and refresh tokens
- Status changes to "Connected" (green)

### 3. Using the Connection
- With valid tokens, API calls work correctly
- Tokens are automatically refreshed using the refresh token
- If refresh fails, user must re-authorize

## Technical Details

### Why This Happens
Google OAuth2 requires user consent to access their data. Even with valid OAuth app credentials (`client_id`/`client_secret`), you need:
1. User authorization to get initial tokens
2. `access_token` for API calls (expires in ~1 hour)
3. `refresh_token` to get new access tokens without re-authorization

### Token Storage
```json
// After initial connection (default credentials)
{
  "client_id": "default-client-id",
  "client_secret": "default-client-secret"
  // No tokens yet!
}

// After OAuth2 authorization
{
  "client_id": "default-client-id",
  "client_secret": "default-client-secret",
  "access_token": "ya29.xxx...",
  "refresh_token": "1//xxx...",
  "token_type": "Bearer",
  "expires_at": 1234567890
}
```

### Error Prevention
The system now:
1. Shows "Auth Required" status when tokens are missing
2. Always displays the OAuth2 authorize button for OAuth2 apps
3. Provides clear messaging about the need to authorize
4. Reminds users after connection to complete authorization

## Benefits of Default Credentials

1. **Easier Setup**: Users don't need to create their own Google Cloud project
2. **Shared Limits**: Uses IOFlow's API quotas (good for testing)
3. **Quick Start**: Immediate connection without OAuth app setup

## When to Use Custom Credentials

1. **Production**: Always use your own OAuth app in production
2. **Higher Limits**: When you need your own API quotas
3. **Branding**: Custom consent screen with your company info
4. **Security**: Full control over OAuth app settings
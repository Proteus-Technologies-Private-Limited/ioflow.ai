# OAuth2 Grant Types Reference for IOFlow

## Quick Reference

### ⚠️ Critical Information for MCP and Claude Desktop Users

When creating seed applications with OAuth2 authentication, you MUST configure the grant type correctly to avoid authentication errors.

## Google APIs Configuration

All Google APIs (Sheets, Gmail, Tasks, Calendar, Drive, etc.) require:

```json
"auth_config": {
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
  "token_url": "https://oauth2.googleapis.com/token",
  "redirect_uri": "http://localhost:5173/oauth/callback",
  "scopes": ["appropriate_scope_here"],
  "grant_type": "authorization_code",  // REQUIRED - Google does NOT support client_credentials
  "authorization_params": {
    "access_type": "offline",          // REQUIRED - to receive refresh tokens
    "prompt": "consent"                // REQUIRED - ensures refresh token is returned
  }
}
```

### Why This Matters

1. **Initial Authorization**: Google only supports `authorization_code` grant type
2. **Token Refresh**: IOFlow automatically uses `refresh_token` grant type (this is handled internally)
3. **Common Error**: If you see `"error": "unsupported_grant_type"`, it means IOFlow tried to use `client_credentials` which Google doesn't support

## Supported Grant Types by Provider

| Provider | authorization_code | client_credentials | refresh_token | Notes |
|----------|-------------------|-------------------|---------------|-------|
| Google | ✅ | ❌ | ✅ (automatic) | Requires offline access |
| Microsoft | ✅ | ✅ | ✅ (automatic) | Both user and app-only flows |
| Slack | ✅ | ❌ | ✅ (automatic) | User authentication only |
| GitHub | ✅ | ❌ | ❌ | No refresh tokens |
| Salesforce | ✅ | ✅ | ✅ (automatic) | Supports multiple flows |

## Error Messages and Solutions

### Error: "unsupported_grant_type"
**Cause**: The OAuth2 provider doesn't support the grant type being used.

**For Google APIs**:
- This usually means `client_credentials` was attempted
- Solution: Ensure the user has a valid refresh token by reconnecting the application

### Error: "OAuth2 refresh token missing"
**Cause**: No refresh token is available to get a new access token.

**Solution**:
1. User must disconnect and reconnect the application
2. Ensure the following structure is in the auth_config:
   ```json
   "authorization_params": {
     "access_type": "offline",
     "prompt": "consent"
   }
   ```

## IOFlow's Token Refresh Logic

1. When access token expires, IOFlow checks for a refresh token
2. If refresh token exists → Uses `refresh_token` grant type
3. If no refresh token → Fails with error (does NOT fallback to `client_credentials`)

## Best Practices

1. **Always Configure for Refresh Tokens**:
   ```json
   "authorization_params": {
     "access_type": "offline",
     "prompt": "consent"
   }
   ```

2. **Store Application Type Info**:
   - User-facing apps: Use `authorization_code`
   - Server-to-server: Use `client_credentials` (if supported)

3. **Test Token Refresh**:
   - Connect the application
   - Wait for access token to expire
   - Verify refresh works without user intervention

## Template for New OAuth2 Applications

```json
{
  "auth_type": "oauth2",
  "auth_config": {
    "authorization_url": "https://provider.com/oauth/authorize",
    "token_url": "https://provider.com/oauth/token",
    "redirect_uri": "http://localhost:5173/oauth/callback",
    "scopes": ["scope1", "scope2"],
    "grant_type": "authorization_code",
    "authorization_params": {
      "access_type": "offline",  // Add if provider supports it
      "prompt": "consent"        // Add if provider supports it
    }
  }
}
```

## Provider-Specific Notes

### Google
- Always requires user consent flow
- Refresh tokens expire after 6 months of inactivity
- Test apps limited to 100 users unless verified

### Microsoft
- Supports app-only authentication with client_credentials
- Refresh tokens have sliding expiration

### Slack
- No refresh tokens for classic apps
- New apps support refresh tokens

## Debugging Tips

1. Check the OAuth2 provider's documentation for supported grant types
2. Use the provider's OAuth2 playground to test
3. Monitor network requests to see exact error responses
4. Check stored credentials to ensure refresh_token is present

## References

- [Google OAuth2 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [OAuth2 Grant Types Specification](https://oauth.net/2/grant-types/)
- [IOFlow OAuth2 Integration Guide](/docs/OAuth.md)
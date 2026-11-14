# OAuth2 Integration Guide for IOFlow

This guide explains how to set up OAuth2 authentication for applications in IOFlow, with a specific focus on Google Sheets integration.

## Table of Contents
- [Overview](#overview)
- [Google Sheets OAuth2 Setup](#google-sheets-oauth2-setup)
- [OAuth2 Flow Implementation](#oauth2-flow-implementation)
- [Troubleshooting](#troubleshooting)
- [Alternative Solutions](#alternative-solutions)

## Overview

IOFlow supports OAuth2 authentication for connecting to third-party applications. OAuth2 allows users to grant IOFlow access to their data without sharing passwords.

### Current Implementation Status

- ✅ OAuth2 credentials storage (Client ID, Client Secret)
- ✅ Token refresh mechanism
- ✅ Basic OAuth2 callback handler
- ⚠️ UI for OAuth2 flow (partial - manual process required)

## Google Sheets OAuth2 Setup

### Prerequisites

1. A Google Cloud Console account
2. A project with Google Sheets API enabled
3. OAuth2 credentials (Client ID and Client Secret)

### Step 1: Create OAuth2 Credentials in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select or create a project
3. Navigate to **APIs & Services** > **Library**
4. Search for "Google Sheets API" and enable it
5. Go to **APIs & Services** > **Credentials**
6. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
7. Choose **Web application**
8. Add the following to **Authorized redirect URIs**:
   ```
   http://localhost:8000/api/v1/oauth2/callback
   ```
9. Save and copy your **Client ID** and **Client Secret**

### Step 2: Connect Google Sheets in IOFlow

1. In IOFlow UI, go to **Applications**
2. Find **Google Sheets** and click **Connect**
3. Enter your OAuth2 credentials:
   - **Client ID**: Your OAuth2 client ID (ends with `.apps.googleusercontent.com`)
   - **Client Secret**: Your OAuth2 client secret (typically starts with `GOCSPX-`)
4. Click **Connect**

### Step 3: Complete OAuth2 Authorization

Since the UI doesn't have a complete OAuth2 flow yet, you need to manually initiate it:

#### Option A: Using the OAuth2 Endpoint

1. Get your Google Sheets app ID:
   ```bash
   sqlite3 /path/to/ioflow.db "SELECT app_id FROM applications WHERE app_name = 'Google Sheets';"
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000/api/v1/oauth2/authorize?app_id=YOUR_APP_ID&redirect_uri=http://localhost:3000/applications
   ```
   Replace `YOUR_APP_ID` with the actual ID from step 1.

3. You'll be redirected to Google's authorization page
4. Grant the requested permissions
5. You'll be redirected back to IOFlow with tokens saved

#### Option B: Using the Manual Token Setup Script

1. Navigate to the backend directory:
   ```bash
   cd /path/to/IOFlow/backend
   ```

2. Run the setup script:
   ```bash
   python3 scripts/setup_google_sheets_tokens.py
   ```

3. Follow the instructions to get tokens from [Google OAuth Playground](https://developers.google.com/oauthplayground/):
   - Click the gear icon and check "Use your own OAuth credentials"
   - Enter your Client ID and Client Secret
   - Select "Google Sheets API v4" scope
   - Authorize and exchange code for tokens
   - Copy the Access Token and Refresh Token when prompted

## OAuth2 Flow Implementation

### Backend Components

#### 1. OAuth2 Manager (`services/oauth2_manager.py`)
Handles token refresh and validation:
- Checks token expiration
- Refreshes tokens using refresh_token grant
- Stores updated tokens securely

#### 2. OAuth2 Callback Handler (`api/oauth2_callback.py`)
Manages the OAuth2 authorization flow:
- `/api/v1/oauth2/authorize` - Initiates OAuth2 flow
- `/api/v1/oauth2/callback` - Handles provider callback

#### 3. Service Executors (`services/service_executors.py`)
Automatically handles token refresh during API calls:
- Detects 401 errors
- Attempts token refresh
- Retries the request

### Frontend Components

Currently, the frontend expects tokens to be already configured. Full OAuth2 flow UI is not yet implemented.

## Using Google Sheets in Flows

Once OAuth2 is set up, you can use Google Sheets services in your flows:

### Add Row Service

**Parameters:**
- `spreadsheet_id`: The ID from your Google Sheets URL
  - Example: If URL is `https://docs.google.com/spreadsheets/d/1ABC123/edit`, the ID is `1ABC123`
- `range`: Where to append data (e.g., "Sheet1" or "Sheet1!A:A")
- `values`: 2D array of data (e.g., `[["col1", "col2", "col3"]]`)

**Example:**
```json
{
  "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "range": "Sheet1",
  "values": [["John", "Doe", "john@example.com"]]
}
```

## Troubleshooting

### Common Errors

#### 1. "Failed to obtain new OAuth2 token: No refresh token available"
**Cause:** OAuth2 authorization was never completed
**Solution:** Complete the OAuth2 flow using one of the methods above

#### 2. "Authentication failed"
**Cause:** Invalid or expired credentials
**Solution:** 
- Verify Client ID and Client Secret are correct
- Re-authorize the application
- Check if Google Sheets API is enabled

#### 3. "Token refresh failed"
**Cause:** Refresh token is invalid or revoked
**Solution:** 
- Disconnect and reconnect Google Sheets
- Complete the OAuth2 flow again

### Debugging Tips

1. Check stored credentials:
   ```bash
   sqlite3 /path/to/ioflow.db "SELECT auth_credentials FROM application_subscriptions WHERE app_id IN (SELECT app_id FROM applications WHERE app_name = 'Google Sheets');"
   ```

2. Check backend logs for OAuth2 errors:
   ```bash
   tail -f /path/to/backend/logs/app.log | grep -i oauth
   ```

3. Verify Google Cloud Console settings:
   - Redirect URI is exactly `http://localhost:8000/api/v1/oauth2/callback`
   - Google Sheets API is enabled
   - OAuth consent screen is configured

## Alternative Solutions

### Using Service Account (No OAuth2 Flow Required)

Instead of OAuth2, you can use a Google Service Account:

1. In Google Cloud Console, create a Service Account
2. Download the JSON key file
3. Share your Google Sheet with the service account email
4. Use service account authentication instead of OAuth2

**Advantages:**
- No OAuth2 flow required
- No token refresh needed
- Better for automated/backend processes

**Disadvantages:**
- Requires sharing sheets with service account
- Less suitable for user-specific data access

### Direct API Key (Limited Use)

Some Google APIs support API keys, but Google Sheets API requires OAuth2 for write operations.

## Future Improvements

1. **Complete OAuth2 UI Flow**
   - Add "Authorize" button in application connections
   - Handle callback in frontend
   - Show authorization status

2. **Token Management UI**
   - Display token status
   - Manual refresh option
   - Revoke access option

3. **Multi-tenant OAuth2**
   - Separate credentials per tenant
   - Tenant-specific redirect URIs

4. **Enhanced Error Handling**
   - Better error messages
   - Automatic retry with backoff
   - User notifications for auth issues

## Security Considerations

1. **Credential Storage**
   - All credentials are encrypted using AES-256
   - Encryption keys are stored separately
   - Database access should be restricted

2. **Token Handling**
   - Access tokens have short expiration
   - Refresh tokens are long-lived and should be protected
   - Always use HTTPS in production

3. **Scope Management**
   - Request minimum required scopes
   - Google Sheets typically needs: `https://www.googleapis.com/auth/spreadsheets`
   - Review and audit granted permissions regularly

## References

- [Google OAuth2 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [OAuth2 RFC](https://tools.ietf.org/html/rfc6749)
- [IOFlow Documentation](https://github.com/yourusername/ioflow)
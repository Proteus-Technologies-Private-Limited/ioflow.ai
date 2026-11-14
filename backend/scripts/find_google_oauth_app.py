#!/usr/bin/env python3
"""
Help users find their OAuth2 app in Google permissions
"""

print("""
🔍 Finding Your OAuth2 App in Google Permissions
================================================

The app name shown in Google permissions (https://myaccount.google.com/permissions) 
is NOT "IOFlow" - it's the name you gave your OAuth2 app in Google Cloud Console.

Here's how to find it:

1. Go to Google Cloud Console:
   https://console.cloud.google.com/apis/credentials

2. Look for your OAuth 2.0 Client ID that you're using with IOFlow

3. Click on it to see the details

4. The "Name" field is what appears in Google permissions
   (e.g., "My App", "Test Application", "Web client 1", etc.)

5. If you can't find it in permissions, it might be because:
   - You haven't completed a successful OAuth2 flow yet
   - The authorization failed before completion
   - You're looking in the wrong Google account

Alternative ways to find connected apps:

1. Check Google Account Security:
   https://myaccount.google.com/security
   → Look for "Third-party apps with account access"

2. Check Google Dashboard:
   https://myaccount.google.com/dashboard
   → Scroll down to see connected apps

3. Search by the Client ID:
   - Your Client ID looks like: 123456789-abc.apps.googleusercontent.com
   - The first part (before the dash) is unique to your project

📝 NOTE: If you still can't find it, you can use the "Force Reconnect" 
button in IOFlow which will revoke any existing tokens and start fresh.
""")
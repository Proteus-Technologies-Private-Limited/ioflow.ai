#!/usr/bin/env python3
"""
Test Google OAuth2 flow to verify refresh token is being returned
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from urllib.parse import urlencode

def test_google_oauth_params():
    """Test if Google OAuth2 URL has correct parameters"""
    
    # Google OAuth2 configuration from seed_applications.py
    oauth_config = {
        "oauth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
        "authorization_params": {
            "access_type": "offline",
            "prompt": "consent"
        }
    }
    
    # Build authorization URL parameters
    params = {
        'client_id': 'YOUR_CLIENT_ID_HERE',
        'redirect_uri': 'http://localhost:8000/api/v1/oauth2/callback',
        'response_type': 'code',
        'state': 'test_state',
        'scope': ' '.join(oauth_config['scopes'])
    }
    
    # Add authorization parameters
    params.update(oauth_config['authorization_params'])
    
    # Build full URL
    auth_url = f"{oauth_config['oauth_url']}?{urlencode(params)}"
    
    print("Google OAuth2 Authorization URL:")
    print(auth_url)
    print("\nParameters breakdown:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Key parameters for refresh token:")
    print(f"  - access_type: {params.get('access_type', 'NOT SET')} (should be 'offline')")
    print(f"  - prompt: {params.get('prompt', 'NOT SET')} (should be 'consent')")
    
    print("\n📝 When you authorize with this URL:")
    print("  1. Google should show a consent screen")
    print("  2. After authorization, the token response should include a refresh_token")
    print("  3. The refresh_token is only provided on first authorization or with prompt=consent")
    
    print("\n⚠️  Common issues:")
    print("  1. If you've already authorized the app without access_type=offline, you won't get a refresh token")
    print("  2. You need to revoke access and re-authorize to get a refresh token")
    print("  3. Visit https://myaccount.google.com/permissions to revoke access to your app")

if __name__ == "__main__":
    test_google_oauth_params()
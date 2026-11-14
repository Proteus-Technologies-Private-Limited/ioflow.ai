#!/usr/bin/env python3
"""
Setup OAuth tokens for Gmail subscription
This script adds test OAuth tokens to the Gmail subscription for testing purposes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from datetime import datetime, timedelta
from utils.crypto_utils import encrypt_credentials

def setup_gmail_oauth():
    """Setup OAuth tokens for Gmail subscription"""
    
    conn = sqlite3.connect('ioflow.db')
    cursor = conn.cursor()
    
    try:
        # Find Gmail app
        cursor.execute("""
            SELECT app_id, app_name, auth_config 
            FROM applications 
            WHERE app_name = 'Gmail' AND auth_type = 'oauth2'
        """)
        
        gmail_app = cursor.fetchone()
        if not gmail_app:
            print("Gmail application not found")
            return False
            
        app_id = gmail_app[0]
        auth_config = json.loads(gmail_app[2])
        
        print(f"Found Gmail app: {app_id}")
        
        # Get default credentials from auth_config
        default_creds = auth_config.get('default_credentials', {})
        client_id = default_creds.get('client_id')
        client_secret = default_creds.get('client_secret')
        
        if not client_id or not client_secret:
            print("No default credentials found in Gmail app configuration")
            return False
            
        print(f"Using client_id: {client_id[:20]}...")
        
        # Find subscription
        cursor.execute("""
            SELECT subscription_id, tenant_id, auth_credentials, status
            FROM application_subscriptions
            WHERE app_id = ?
        """, (app_id,))
        
        subscription = cursor.fetchone()
        if not subscription:
            print("No Gmail subscription found")
            return False
            
        sub_id = subscription[0]
        tenant_id = subscription[1]
        
        print(f"Found subscription: {sub_id}")
        print(f"Tenant ID: {tenant_id}")
        
        # Create OAuth credentials
        # Note: In a real scenario, these would come from the OAuth flow
        # For testing, we'll need to get valid tokens through proper OAuth
        oauth_credentials = {
            'client_id': client_id,
            'client_secret': client_secret,
            'access_token': None,  # Need valid token
            'refresh_token': None,  # Need valid refresh token
            'token_type': 'Bearer',
            'expires_at': None,  # Will be set when we get real token
            'scope': ' '.join(auth_config.get('scopes', []))
        }
        
        print("\nIMPORTANT: This script prepares the OAuth structure but requires valid tokens.")
        print("To get valid tokens, you need to:")
        print("1. Go through the OAuth flow in the UI")
        print("2. Or use the OAuth callback endpoint with valid authorization code")
        print("\nFor now, the subscription will be updated with the OAuth structure but no tokens.")
        
        # Encrypt credentials
        encrypted_creds = encrypt_credentials(oauth_credentials)
        
        # Update subscription
        cursor.execute("""
            UPDATE application_subscriptions
            SET auth_credentials = ?
            WHERE subscription_id = ?
        """, (encrypted_creds, sub_id))
        
        conn.commit()
        print(f"\nSubscription {sub_id} updated with OAuth structure")
        print("Next step: Complete OAuth flow to get valid tokens")
        
        # Get tenant owner for OAuth flow
        cursor.execute("""
            SELECT owner_email FROM tenants WHERE id = ?
        """, (tenant_id,))
        
        tenant = cursor.fetchone()
        if tenant:
            print(f"Tenant owner: {tenant[0]}")
            print(f"\nTo complete OAuth:")
            print(f"1. Login as {tenant[0]}")
            print(f"2. Go to Applications > Gmail > Connect")
            print(f"3. Complete the OAuth authorization")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = setup_gmail_oauth()
    sys.exit(0 if success else 1)
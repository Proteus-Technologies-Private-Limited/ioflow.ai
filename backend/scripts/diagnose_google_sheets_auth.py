#!/usr/bin/env python3
"""
Diagnose Google Sheets OAuth2 Authentication Issues

This script helps diagnose and fix OAuth2 authentication issues with Google Sheets.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from db.database import get_db
from db.application_models import ApplicationSubscription, Application
from utils.crypto_utils import decrypt_credentials
import json
from datetime import datetime


def diagnose_google_sheets_auth(tenant_id: str = None):
    """Diagnose Google Sheets authentication issues"""
    
    db = next(get_db())
    try:
        # Find Google Sheets application
        google_sheets_app = db.query(Application).filter(
            Application.app_name == "Google Sheets"
        ).first()
        
        if not google_sheets_app:
            print("❌ Google Sheets application not found in database")
            return
        
        print(f"✅ Found Google Sheets application (ID: {google_sheets_app.app_id})")
        
        # Check auth configuration
        auth_config = json.loads(google_sheets_app.auth_config)
        print("\n📋 OAuth2 Configuration:")
        print(f"  - OAuth URL: {auth_config.get('oauth_url')}")
        print(f"  - Token URL: {auth_config.get('token_url')}")
        print(f"  - Scopes: {auth_config.get('scopes')}")
        print(f"  - Authorization params: {auth_config.get('authorization_params')}")
        
        # Check if offline access is configured
        auth_params = auth_config.get('authorization_params', {})
        if auth_params.get('access_type') == 'offline':
            print("  ✅ Offline access is configured (required for refresh tokens)")
        else:
            print("  ❌ Offline access NOT configured - refresh tokens won't be issued!")
        
        if auth_params.get('prompt') == 'consent':
            print("  ✅ Consent prompt is configured (ensures refresh token on re-auth)")
        else:
            print("  ⚠️  Consent prompt not configured - might not get refresh token on re-auth")
        
        # Find subscriptions
        query = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == google_sheets_app.app_id
        )
        
        if tenant_id:
            query = query.filter(ApplicationSubscription.tenant_id == tenant_id)
        
        subscriptions = query.all()
        
        if not subscriptions:
            print(f"\n❌ No subscriptions found for Google Sheets{' for tenant ' + tenant_id if tenant_id else ''}")
            return
        
        print(f"\n📊 Found {len(subscriptions)} subscription(s)")
        
        for i, sub in enumerate(subscriptions):
            print(f"\n--- Subscription {i+1} ---")
            print(f"ID: {sub.subscription_id}")
            print(f"Tenant: {sub.tenant_id}")
            print(f"Status: {sub.status}")
            print(f"Created: {sub.created_at}")
            
            if not sub.auth_credentials:
                print("❌ No credentials stored")
                continue
            
            try:
                creds = decrypt_credentials(sub.auth_credentials)
                print("\n🔐 Credentials analysis:")
                
                # Check what we have
                has_client_id = bool(creds.get('client_id'))
                has_client_secret = bool(creds.get('client_secret'))
                has_access_token = bool(creds.get('access_token'))
                has_refresh_token = bool(creds.get('refresh_token'))
                
                print(f"  - Client ID: {'✅ Present' if has_client_id else '❌ Missing'}")
                print(f"  - Client Secret: {'✅ Present' if has_client_secret else '❌ Missing'}")
                print(f"  - Access Token: {'✅ Present' if has_access_token else '❌ Missing'}")
                print(f"  - Refresh Token: {'✅ Present' if has_refresh_token else '❌ Missing'}")
                
                # Check token expiration
                if has_access_token and creds.get('expires_at'):
                    expires_at = datetime.fromtimestamp(creds['expires_at'])
                    now = datetime.utcnow()
                    
                    if expires_at > now:
                        time_left = expires_at - now
                        print(f"  - Token expires in: {time_left}")
                    else:
                        time_past = now - expires_at
                        print(f"  - Token expired: {time_past} ago")
                
                # Diagnose the issue
                print("\n🔍 Diagnosis:")
                
                if not has_client_id or not has_client_secret:
                    print("❌ Missing OAuth2 client credentials. User needs to configure Client ID and Secret.")
                elif not has_access_token and not has_refresh_token:
                    print("❌ No tokens present. User needs to complete OAuth2 authorization flow.")
                elif not has_refresh_token:
                    print("❌ No refresh token available. This is the main issue!")
                    print("\n📋 Solution:")
                    print("1. User needs to disconnect and reconnect Google Sheets")
                    print("2. During re-authorization, Google will provide a new refresh token")
                    print("3. Make sure the authorization URL includes:")
                    print("   - access_type=offline")
                    print("   - prompt=consent")
                elif has_access_token and has_refresh_token:
                    print("✅ Both tokens present. Authentication should work.")
                    if creds.get('expires_at') and datetime.fromtimestamp(creds['expires_at']) < datetime.utcnow():
                        print("⚠️  Access token is expired, but refresh token should allow automatic renewal.")
                
            except Exception as e:
                print(f"❌ Error decrypting credentials: {str(e)}")
    
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose Google Sheets OAuth2 authentication issues")
    parser.add_argument("--tenant-id", help="Specific tenant ID to check")
    
    args = parser.parse_args()
    
    diagnose_google_sheets_auth(args.tenant_id)
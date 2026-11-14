#!/usr/bin/env python3
"""
Diagnose OAuth2 token issues for subscriptions
"""

import json
import sqlite3
import sys
from datetime import datetime
import os

def diagnose_oauth_tokens(tenant_id=None):
    """Diagnose OAuth2 token issues for all subscriptions or a specific tenant"""
    try:
        # Connect to SQLite database
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../ioflow.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                s.subscription_id,
                s.tenant_id,
                s.app_id,
                s.auth_credentials,
                a.app_name,
                a.auth_type
            FROM application_subscriptions s
            JOIN applications a ON s.app_id = a.app_id
            WHERE a.auth_type = 'oauth2'
        """
        
        params = []
        if tenant_id:
            query += " AND s.tenant_id = ?"
            params.append(tenant_id)
        
        cursor.execute(query, params)
        subscriptions = cursor.fetchall()
        
        if not subscriptions:
            print("No OAuth2 subscriptions found")
            return
        
        print(f"\nFound {len(subscriptions)} OAuth2 subscription(s)\n")
        print("-" * 80)
        
        issues_found = False
        
        for sub in subscriptions:
            subscription_id, tenant_id, app_id, auth_creds_encrypted, app_name, auth_type = sub
            
            print(f"\n📱 Application: {app_name}")
            print(f"   Subscription ID: {subscription_id}")
            print(f"   Tenant ID: {tenant_id}")
            
            if not auth_creds_encrypted:
                print("   ❌ No credentials stored")
                issues_found = True
                continue
            
            # Try to decrypt and analyze credentials
            # Note: In a real scenario, you'd use the proper decryption function
            # For this diagnostic, we'll just check if certain fields exist
            try:
                # Assuming credentials are stored as JSON (simplified for diagnostic)
                # In production, these would be encrypted
                if isinstance(auth_creds_encrypted, str) and auth_creds_encrypted.startswith('{'):
                    creds = json.loads(auth_creds_encrypted)
                else:
                    print("   ⚠️  Credentials are encrypted (good for security)")
                    print("   ℹ️  Cannot analyze token details without decryption")
                    continue
                
                has_client_id = bool(creds.get('client_id'))
                has_client_secret = bool(creds.get('client_secret'))
                has_access_token = bool(creds.get('access_token'))
                has_refresh_token = bool(creds.get('refresh_token'))
                
                print(f"   Client ID: {'✅' if has_client_id else '❌'}")
                print(f"   Client Secret: {'✅' if has_client_secret else '❌'}")
                print(f"   Access Token: {'✅' if has_access_token else '❌'}")
                print(f"   Refresh Token: {'✅' if has_refresh_token else '❌'}")
                
                if has_access_token:
                    expires_at = creds.get('expires_at')
                    if expires_at:
                        is_expired = datetime.utcnow().timestamp() > expires_at
                        expiry_date = datetime.fromtimestamp(expires_at)
                        print(f"   Token Expires: {expiry_date} ({'EXPIRED' if is_expired else 'VALID'})")
                
                # Diagnose issues
                if not has_refresh_token and app_name == "Google Sheets":
                    print("\n   🚨 ISSUE: Missing refresh token for Google Sheets!")
                    print("   📋 Solution:")
                    print("      1. Go to https://myaccount.google.com/permissions")
                    print("      2. Find and remove access for your OAuth application")
                    print("      3. Reconnect Google Sheets in IOFlow")
                    print("      4. Make sure to approve all requested permissions")
                    issues_found = True
                
                elif not has_access_token and not has_refresh_token:
                    print("\n   🚨 ISSUE: No valid tokens found!")
                    print("   📋 Solution: Reconnect the application in IOFlow")
                    issues_found = True
                
            except json.JSONDecodeError:
                print("   ⚠️  Could not parse credentials (may be encrypted)")
            except Exception as e:
                print(f"   ⚠️  Error analyzing credentials: {str(e)}")
        
        print("\n" + "-" * 80)
        
        if issues_found:
            print("\n⚠️  Issues found! Please follow the solutions provided above.")
        else:
            print("\n✅ No obvious issues found with OAuth tokens.")
            print("   If you're still experiencing issues, try reconnecting the application.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error running diagnostic: {str(e)}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Diagnose OAuth2 token issues')
    parser.add_argument('--tenant-id', help='Specific tenant ID to diagnose')
    args = parser.parse_args()
    
    diagnose_oauth_tokens(args.tenant_id)

if __name__ == "__main__":
    main()
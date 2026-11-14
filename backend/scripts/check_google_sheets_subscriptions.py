#!/usr/bin/env python3
"""
Check and diagnose Google Sheets subscriptions
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import settings
from utils.crypto_utils import decrypt_credentials
from datetime import datetime

def check_subscriptions():
    """Check existing Google Sheets subscriptions"""
    
    # Use SQLite database
    database_url = "sqlite:///backend/ioflow.db"
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get Google Sheets app ID
        app_result = session.execute(
            text("SELECT app_id, app_name FROM applications WHERE app_name = 'Google Sheets'")
        ).fetchone()
        
        if not app_result:
            print("❌ Google Sheets application not found")
            return
            
        app_id, app_name = app_result
        print(f"✓ Found {app_name} (ID: {app_id})")
        
        # Check subscriptions
        subs = session.execute(
            text("""
                SELECT subscription_id, tenant_id, status, auth_credentials, created_at, updated_at
                FROM application_subscriptions 
                WHERE app_id = :app_id
            """),
            {'app_id': app_id}
        ).fetchall()
        
        if not subs:
            print("\n📌 No subscriptions found for Google Sheets")
            print("   You need to connect Google Sheets first.")
            return
        
        print(f"\n📋 Found {len(subs)} subscription(s):")
        
        for sub_id, tenant_id, status, auth_creds, created_at, updated_at in subs:
            print(f"\n  Subscription ID: {sub_id}")
            print(f"  Tenant: {tenant_id}")
            print(f"  Status: {status}")
            print(f"  Created: {created_at}")
            print(f"  Updated: {updated_at}")
            
            if auth_creds:
                try:
                    creds = decrypt_credentials(auth_creds)
                    print(f"  Credentials:")
                    print(f"    - Has access_token: {bool(creds.get('access_token'))}")
                    print(f"    - Has refresh_token: {bool(creds.get('refresh_token'))}")
                    print(f"    - Has client_id: {bool(creds.get('client_id'))}")
                    print(f"    - Has client_secret: {bool(creds.get('client_secret'))}")
                    
                    if creds.get('expires_at'):
                        expires_at = datetime.fromtimestamp(creds['expires_at'])
                        is_expired = datetime.utcnow() > expires_at
                        print(f"    - Token expires at: {expires_at}")
                        print(f"    - Token expired: {is_expired}")
                    
                    if not creds.get('refresh_token'):
                        print("\n  ⚠️  WARNING: No refresh token found!")
                        print("     This subscription will fail when the access token expires.")
                        print("     To fix:")
                        print("     1. Go to https://myaccount.google.com/permissions")
                        print("     2. Revoke access to 'IOFlow'")
                        print("     3. Re-connect Google Sheets in IOFlow")
                except Exception as e:
                    print(f"  ❌ Error decrypting credentials: {e}")
            else:
                print("  ❌ No credentials stored")
        
        # Check OAuth states (pending authorizations)
        oauth_states = session.execute(
            text("""
                SELECT state_token, created_at, expires_at
                FROM oauth_states
                WHERE app_id = :app_id
                ORDER BY created_at DESC
                LIMIT 5
            """),
            {'app_id': app_id}
        ).fetchall()
        
        if oauth_states:
            print(f"\n📌 Recent OAuth authorization attempts:")
            for state_token, created_at, expires_at in oauth_states:
                print(f"  - State: {state_token[:10]}...")
                print(f"    Created: {created_at}")
                print(f"    Expires: {expires_at}")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    print("🔍 Google Sheets Subscriptions Check")
    print("=" * 50)
    check_subscriptions()
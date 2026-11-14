#!/usr/bin/env python3
"""
Fix Google Sheets OAuth2 configuration to ensure proper grant_type and authorization params
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import settings
from datetime import datetime

def fix_google_sheets_oauth():
    """Fix Google Sheets OAuth2 configuration"""
    
    # Create database connection
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check current Google Sheets configuration
        result = session.execute(
            text("SELECT app_id, app_name, auth_config, version FROM applications WHERE app_name = 'Google Sheets'")
        ).fetchone()
        
        if not result:
            print("❌ Google Sheets application not found in database")
            print("\nTo fix this, you need to:")
            print("1. Install the Google Sheets seed application")
            print("2. Run: python3 backend/scripts/seed_manager.py install google_sheets")
            return False
            
        app_id, app_name, auth_config_str, version = result
        print(f"✓ Found {app_name} (ID: {app_id}, Version: {version})")
        
        # Parse auth config
        auth_config = json.loads(auth_config_str) if isinstance(auth_config_str, str) else auth_config_str
        
        # Check current configuration
        print("\n📋 Current OAuth2 Configuration:")
        print(f"  - Authorization URL: {auth_config.get('authorization_url', 'NOT SET')}")
        print(f"  - Token URL: {auth_config.get('token_url', 'NOT SET')}")
        print(f"  - Grant Type: {auth_config.get('grant_type', 'NOT SET')}")
        
        auth_params = auth_config.get('authorization_params', {})
        print(f"  - Authorization Params:")
        print(f"    - access_type: {auth_params.get('access_type', 'NOT SET')}")
        print(f"    - prompt: {auth_params.get('prompt', 'NOT SET')}")
        
        # Fix configuration
        needs_update = False
        
        # Ensure grant_type is set
        if auth_config.get('grant_type') != 'authorization_code':
            print("\n⚠️  Missing or incorrect grant_type, adding 'authorization_code'")
            auth_config['grant_type'] = 'authorization_code'
            needs_update = True
        
        # Ensure authorization_params are set for offline access
        if 'authorization_params' not in auth_config:
            auth_config['authorization_params'] = {}
            needs_update = True
        
        if auth_config['authorization_params'].get('access_type') != 'offline':
            print("⚠️  Missing or incorrect access_type, setting to 'offline'")
            auth_config['authorization_params']['access_type'] = 'offline'
            needs_update = True
            
        if auth_config['authorization_params'].get('prompt') != 'consent':
            print("⚠️  Missing or incorrect prompt, setting to 'consent'")
            auth_config['authorization_params']['prompt'] = 'consent'
            needs_update = True
        
        # Ensure proper scopes
        expected_scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        
        current_scopes = auth_config.get('scopes', [])
        if set(current_scopes) != set(expected_scopes):
            print("⚠️  Updating scopes to include all required permissions")
            auth_config['scopes'] = expected_scopes
            needs_update = True
        
        if needs_update:
            # Update the database
            auth_config_json = json.dumps(auth_config)
            
            session.execute(
                text("""
                    UPDATE applications 
                    SET auth_config = :auth_config,
                        updated_at = :updated_at
                    WHERE app_id = :app_id
                """),
                {
                    'auth_config': auth_config_json,
                    'updated_at': datetime.utcnow(),
                    'app_id': app_id
                }
            )
            session.commit()
            print("\n✅ Successfully updated Google Sheets OAuth2 configuration")
        else:
            print("\n✅ Google Sheets OAuth2 configuration is already correct")
        
        # Show final configuration
        print("\n📋 Final OAuth2 Configuration:")
        print(f"  - Grant Type: {auth_config.get('grant_type')}")
        print(f"  - Authorization Params:")
        print(f"    - access_type: {auth_config['authorization_params'].get('access_type')}")
        print(f"    - prompt: {auth_config['authorization_params'].get('prompt')}")
        print(f"  - Scopes: {len(auth_config.get('scopes', []))} scopes configured")
        
        # Check for existing subscriptions that might need re-authorization
        subs_result = session.execute(
            text("""
                SELECT COUNT(*) FROM application_subscriptions 
                WHERE app_id = :app_id
            """),
            {'app_id': app_id}
        ).fetchone()
        
        if subs_result and subs_result[0] > 0:
            print(f"\n⚠️  Found {subs_result[0]} existing subscription(s) for Google Sheets")
            print("   These subscriptions may need to be re-authorized:")
            print("   1. Go to https://myaccount.google.com/permissions")
            print("   2. Revoke access to 'IOFlow' or your app")
            print("   3. Re-connect Google Sheets in IOFlow")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def check_google_apis():
    """Check if Google APIs are properly configured"""
    print("\n🔍 Checking Google APIs Configuration:")
    
    # Check for other Google services
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        google_apps = session.execute(
            text("""
                SELECT app_name, version 
                FROM applications 
                WHERE app_name IN ('Google Sheets', 'Google Drive', 'Gmail', 'Google Tasks')
                ORDER BY app_name
            """)
        ).fetchall()
        
        if google_apps:
            print("\n📱 Installed Google Applications:")
            for app_name, version in google_apps:
                print(f"  - {app_name} v{version}")
        else:
            print("  No Google applications found")
            
    finally:
        session.close()

if __name__ == "__main__":
    print("🔧 Google Sheets OAuth2 Configuration Fix")
    print("=" * 50)
    
    # Fix the configuration
    success = fix_google_sheets_oauth()
    
    if success:
        # Check other Google APIs
        check_google_apis()
        
        print("\n✅ Configuration fixed successfully!")
        print("\n📌 Next Steps:")
        print("1. If you have an existing Google Sheets connection, disconnect it")
        print("2. Go to https://myaccount.google.com/permissions and revoke IOFlow access")
        print("3. Re-connect Google Sheets in IOFlow")
        print("4. Make sure to authorize all requested permissions")
    else:
        print("\n❌ Failed to fix configuration")
        sys.exit(1)
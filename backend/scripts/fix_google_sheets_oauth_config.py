#!/usr/bin/env python3
"""
Fix Google Sheets OAuth2 configuration to request refresh tokens
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from db.database import get_db
from db.application_models import Application
import json


def fix_google_sheets_oauth_config():
    """Update Google Sheets OAuth2 config to request refresh tokens"""
    
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
        
        # Get current auth config
        current_config = json.loads(google_sheets_app.auth_config) if google_sheets_app.auth_config else {}
        
        print("\n📋 Current OAuth2 Configuration:")
        print(json.dumps(current_config, indent=2))
        
        # Update auth config with required parameters
        updated_config = current_config.copy()
        
        # Add authorization_params if not present
        if 'authorization_params' not in updated_config:
            updated_config['authorization_params'] = {}
        
        # Set required parameters for refresh token
        updated_config['authorization_params']['access_type'] = 'offline'
        updated_config['authorization_params']['prompt'] = 'consent'
        
        # Ensure we have all required OAuth2 URLs
        if 'oauth_url' not in updated_config:
            updated_config['oauth_url'] = 'https://accounts.google.com/o/oauth2/v2/auth'
        
        if 'token_url' not in updated_config:
            updated_config['token_url'] = 'https://oauth2.googleapis.com/token'
        
        if 'scopes' not in updated_config:
            updated_config['scopes'] = ['https://www.googleapis.com/auth/spreadsheets']
        
        print("\n📋 Updated OAuth2 Configuration:")
        print(json.dumps(updated_config, indent=2))
        
        # Update the database
        google_sheets_app.auth_config = json.dumps(updated_config)
        db.commit()
        
        print("\n✅ Successfully updated Google Sheets OAuth2 configuration!")
        print("\n📋 Next Steps:")
        print("1. Users with existing Google Sheets connections need to:")
        print("   - Disconnect Google Sheets (this will revoke current tokens)")
        print("   - Reconnect Google Sheets (this will get new tokens WITH refresh token)")
        print("2. New users connecting Google Sheets will automatically get refresh tokens")
        
    except Exception as e:
        print(f"❌ Error updating configuration: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Fixing Google Sheets OAuth2 Configuration")
    print("=" * 50)
    
    # Auto-proceed for script execution
    print("\n✅ Proceeding with update...")
    fix_google_sheets_oauth_config()
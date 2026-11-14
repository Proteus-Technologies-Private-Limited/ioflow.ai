#!/usr/bin/env python3
"""
Add support for default OAuth credentials in application auth_config
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.application_models import Application
from core.config import settings

def update_auth_config_structure():
    """Update auth_config to support default OAuth credentials"""
    
    # Create database engine
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all OAuth2 applications
        oauth_apps = session.query(Application).filter(
            Application.auth_type == 'oauth2'
        ).all()
        
        print(f"Found {len(oauth_apps)} OAuth2 applications")
        
        for app in oauth_apps:
            # Parse current auth_config
            if isinstance(app.auth_config, str):
                auth_config = json.loads(app.auth_config)
            else:
                auth_config = app.auth_config or {}
            
            # Add default credentials structure if not present
            if 'default_credentials' not in auth_config:
                auth_config['default_credentials'] = {
                    'client_id': None,
                    'client_secret': None,
                    'description': 'Default OAuth credentials for all tenants (optional)'
                }
                
                # Add credential override settings
                auth_config['allow_credential_override'] = True
                auth_config['credential_help_text'] = (
                    "You can use the default credentials or provide your own. "
                    "Custom credentials are recommended for production use."
                )
                
                # Update the application
                if settings.database_url.startswith("sqlite"):
                    app.auth_config = json.dumps(auth_config)
                else:
                    app.auth_config = auth_config
                
                print(f"✅ Updated {app.app_name}")
            else:
                print(f"⏭️  {app.app_name} already has default_credentials")
        
        session.commit()
        print("\n✅ Successfully updated auth_config structure")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    update_auth_config_structure()
#!/usr/bin/env python3
"""
Simulate OAuth flow to see exact URL
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
import secrets
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.application_models import Application, OAuthState
from services.oauth2_service import OAuth2Service
from core.config import settings

# Create a database session
db = SessionLocal()

try:
    # Get Gmail application
    app = db.query(Application).filter(
        Application.app_name == 'Gmail',
        Application.auth_type == 'oauth2'
    ).first()
    
    if not app:
        print("Gmail application not found")
        sys.exit(1)
    
    auth_config = json.loads(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
    
    # Get credentials
    default_creds = auth_config.get('default_credentials', {})
    client_id = default_creds.get('client_id')
    client_secret = default_creds.get('client_secret')
    
    print("Simulating OAuth Flow")
    print("=" * 60)
    print(f"Application: {app.app_name}")
    print(f"Client ID: {client_id}")
    print()
    
    # Create OAuth state (simulating what happens in the authorize endpoint)
    state_token = secrets.token_urlsafe(32)
    
    oauth_state = OAuthState(
        state_token=state_token,
        app_id=app.app_id,
        redirect_uri="http://localhost:7001/applications",  # Frontend URL
        user_id=None,
        tenant_id=None,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        provider_params=json.dumps(auth_config.get('authorization_params', {})),
        temp_credentials=json.dumps({
            'client_id': client_id,
            'client_secret': client_secret
        })
    )
    
    # Build authorization URL
    print("Building Authorization URL...")
    authorization_url = OAuth2Service.build_authorization_url(
        app=app,
        state_token=state_token,
        client_id=client_id,
        code_verifier=None,
        provider_params=auth_config.get('authorization_params', {})
    )
    
    print(f"\nFull Authorization URL:")
    print(authorization_url)
    print()
    
    # Parse the URL to show individual parameters
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(authorization_url)
    params = parse_qs(parsed.query)
    
    print("OAuth Parameters:")
    for key, value in params.items():
        if key == 'scope':
            print(f"  {key}: {value[0][:100]}...")  # Truncate long scope
        else:
            print(f"  {key}: {value[0]}")
    
    print()
    print("Key Points:")
    print(f"1. Redirect URI sent to Google: {params.get('redirect_uri', ['Not found'])[0]}")
    print(f"2. This must EXACTLY match what's in Google Console")
    print(f"3. Current setting: {settings.oauth_callback_base_url}")
    
finally:
    db.close()
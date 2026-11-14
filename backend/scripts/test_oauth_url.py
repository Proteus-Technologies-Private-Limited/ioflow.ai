#!/usr/bin/env python3
"""
Test OAuth URL generation to debug redirect_uri_mismatch
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from urllib.parse import urlencode, quote, urlparse, parse_qs
from core.config import settings

# Get Gmail OAuth config
conn = sqlite3.connect('ioflow.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT auth_config 
    FROM applications 
    WHERE app_name = 'Gmail' AND auth_type = 'oauth2'
''')

result = cursor.fetchone()
if result:
    auth_config = json.loads(result[0])
    
    # Get client ID
    client_id = auth_config.get('default_credentials', {}).get('client_id', '')
    
    print("OAuth URL Generation Test")
    print("=" * 60)
    print(f"Client ID: {client_id}")
    print(f"Settings redirect URI: {settings.oauth_callback_base_url}")
    print()
    
    # Test different encoding methods
    redirect_uri = settings.oauth_callback_base_url
    
    # Method 1: Direct string
    print("Method 1 - Direct string:")
    print(f"  {redirect_uri}")
    print()
    
    # Method 2: URL encoded
    print("Method 2 - URL encoded:")
    print(f"  {quote(redirect_uri, safe='')}")
    print()
    
    # Method 3: As it would appear in params
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(auth_config.get('scopes', [])),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': 'test_state'
    }
    
    auth_url = auth_config.get('authorization_url', '')
    full_url = f'{auth_url}?{urlencode(params)}'
    
    print("Method 3 - Full OAuth URL:")
    print(f"  {full_url[:200]}...")
    print()
    
    # Parse the URL to see what redirect_uri is actually being sent
    parsed = urlparse(full_url)
    query_params = parse_qs(parsed.query)
    
    print("Parsed redirect_uri from URL:")
    print(f"  {query_params.get('redirect_uri', ['Not found'])[0]}")
    print()
    
    # Check for any special characters or encoding issues
    print("Redirect URI Analysis:")
    print(f"  Length: {len(redirect_uri)}")
    print(f"  Has trailing slash: {redirect_uri.endswith('/')}")
    print(f"  Has spaces: {' ' in redirect_uri}")
    print(f"  Protocol: {urlparse(redirect_uri).scheme}")
    print(f"  Host: {urlparse(redirect_uri).netloc}")
    print(f"  Path: {urlparse(redirect_uri).path}")
    print()
    
    # Common issues
    print("Common Issues to Check:")
    print("1. Trailing slash mismatch (Google is strict about this)")
    print("2. HTTP vs HTTPS mismatch")
    print("3. Port number mismatch")
    print("4. Path case sensitivity")
    print("5. URL encoding issues")
    print()
    
    print("Redirect URIs to try in Google Console:")
    print(f"  - {redirect_uri}")
    print(f"  - {redirect_uri.rstrip('/')}")  # Without trailing slash
    print(f"  - {redirect_uri}/")  # With trailing slash if not present
    print(f"  - http://localhost:7001/api/v1/oauth2/callback")  # HTTP version
    
conn.close()
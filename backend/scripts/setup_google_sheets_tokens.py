#!/usr/bin/env python3
"""
Quick script to manually set up Google Sheets tokens
This is a temporary solution until proper OAuth2 flow is implemented
"""
import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.crypto_utils import encrypt_credentials, decrypt_credentials

def setup_tokens():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "ioflow.db")
    
    print("Google Sheets Token Setup")
    print("========================")
    print("\nThis script will help you manually set up tokens for Google Sheets.")
    print("\nFirst, go to: https://developers.google.com/oauthplayground/")
    print("1. Click the gear icon and check 'Use your own OAuth credentials'")
    print("2. Enter your Client ID and Client Secret")
    print("3. In Step 1, select 'Google Sheets API v4' and check the spreadsheets scope")
    print("4. Click 'Authorize APIs' and grant permissions")
    print("5. In Step 2, click 'Exchange authorization code for tokens'")
    print("6. Copy the Access Token and Refresh Token\n")
    
    access_token = input("Enter Access Token: ").strip()
    refresh_token = input("Enter Refresh Token: ").strip()
    
    if not access_token or not refresh_token:
        print("Error: Both tokens are required!")
        return
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get Google Sheets subscription
    cursor.execute("""
        SELECT subscription_id, auth_credentials 
        FROM application_subscriptions 
        WHERE app_id IN (SELECT app_id FROM applications WHERE app_name = 'Google Sheets')
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    if not result:
        print("Error: No Google Sheets subscription found. Please connect Google Sheets first.")
        return
    
    subscription_id, encrypted_creds = result
    
    # Decrypt existing credentials
    if isinstance(encrypted_creds, str):
        encrypted_creds = json.loads(encrypted_creds)
    
    creds = decrypt_credentials(encrypted_creds)
    
    # Update with tokens
    creds['access_token'] = access_token
    creds['refresh_token'] = refresh_token
    creds['token_type'] = 'Bearer'
    creds['expires_at'] = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    
    # Encrypt and save
    encrypted_updated = encrypt_credentials(creds)
    
    cursor.execute("""
        UPDATE application_subscriptions 
        SET auth_credentials = ? 
        WHERE subscription_id = ?
    """, (json.dumps(encrypted_updated), subscription_id))
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Successfully updated tokens for subscription {subscription_id}")
    print("You can now use Google Sheets in your flows!")

if __name__ == "__main__":
    setup_tokens()
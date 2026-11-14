#!/usr/bin/env python3
"""
Update Google Sheets OAuth configuration to include proper authorization parameters
for obtaining refresh tokens.
"""

import json
import sqlite3
import sys

def update_google_sheets_oauth_config():
    try:
        # Connect to SQLite database
        import os
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../ioflow.db')
        print(f"Connecting to database at: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find Google Sheets application
        cursor.execute("""
            SELECT app_id, auth_config 
            FROM applications 
            WHERE app_name = 'Google Sheets'
        """)
        
        result = cursor.fetchone()
        if not result:
            print("❌ Google Sheets application not found")
            return False
        
        app_id, auth_config_str = result
        auth_config = json.loads(auth_config_str)
        
        print(f"Current auth_config: {json.dumps(auth_config, indent=2)}")
        
        # Update authorization parameters
        if 'authorization_params' not in auth_config:
            auth_config['authorization_params'] = {}
        
        # Add required parameters for refresh token
        auth_config['authorization_params']['access_type'] = 'offline'
        auth_config['authorization_params']['prompt'] = 'consent'
        
        # Update the database
        cursor.execute("""
            UPDATE applications 
            SET auth_config = ?, updated_at = CURRENT_TIMESTAMP
            WHERE app_id = ?
        """, (json.dumps(auth_config), app_id))
        
        conn.commit()
        
        print("✅ Updated Google Sheets OAuth configuration")
        print(f"New auth_config: {json.dumps(auth_config, indent=2)}")
        
        # Verify the update
        cursor.execute("""
            SELECT auth_config 
            FROM applications 
            WHERE app_id = ?
        """, (app_id,))
        
        updated_config = json.loads(cursor.fetchone()[0])
        if updated_config.get('authorization_params', {}).get('access_type') == 'offline':
            print("✅ Verification successful: access_type is set to 'offline'")
        else:
            print("❌ Verification failed: access_type not properly set")
            return False
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating Google Sheets OAuth config: {str(e)}")
        return False

if __name__ == "__main__":
    success = update_google_sheets_oauth_config()
    sys.exit(0 if success else 1)
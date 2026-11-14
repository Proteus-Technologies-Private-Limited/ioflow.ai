#!/usr/bin/env python3
"""
Script to update Slack configuration with improved settings based on API verification
"""

import sqlite3
import json
import sys
import os

def update_slack_config(db_path):
    """Update Slack application configuration with verified settings"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Updated OAuth configuration with more scopes and refresh token support
        improved_auth_config = {
            "oauth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "scopes": [
                # Original scopes
                "channels:read",
                "channels:write", 
                "chat:write",
                "users:read",
                # Additional recommended scopes
                "channels:history",     # Read channel messages
                "groups:read",         # Access private channels
                "groups:write",        # Manage private channels
                "im:read",            # Access direct messages
                "im:write",           # Send direct messages
                "users:read.email",    # Get user email addresses
                "files:read",         # Access files
                "files:write",        # Upload files
                "reactions:read",      # Read reactions
                "reactions:write"      # Add reactions
            ],
            "client_id_required": True,
            "client_secret_required": True,
            "response_type": "code",
            "grant_types": ["authorization_code", "refresh_token"],  # Added refresh token
            "authorization_params": {},
            "token_params": {},
            "pkce_required": False
        }
        
        # Update the Slack application auth config
        cursor.execute("""
            UPDATE applications 
            SET auth_config = ?, 
                updated_at = CURRENT_TIMESTAMP
            WHERE app_name = 'Slack'
        """, (json.dumps(improved_auth_config),))
        
        print("✅ Updated Slack OAuth configuration with additional scopes and refresh token support")
        
        # Get Slack app ID for adding more events and services
        cursor.execute("SELECT app_id FROM applications WHERE app_name = 'Slack'")
        slack_app = cursor.fetchone()
        
        if not slack_app:
            print("❌ Slack application not found")
            return
            
        slack_app_id = slack_app[0]
        
        # Additional events to add
        new_events = [
            {
                "event_name": "message_changed",
                "display_name": "Message Edited",
                "description": "Triggers when a message is edited",
                "trigger_type": "webhook",
                "trigger_config": json.dumps({
                    "event_types": ["message"],
                    "subtype": "message_changed"
                }),
                "output_schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "event": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "subtype": {"type": "string"},
                                "message": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "user": {"type": "string"},
                                        "edited": {
                                            "type": "object",
                                            "properties": {
                                                "user": {"type": "string"},
                                                "ts": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "previous_message": {"type": "object"},
                                "channel": {"type": "string"},
                                "ts": {"type": "string"}
                            }
                        }
                    }
                })
            },
            {
                "event_name": "reaction_added",
                "display_name": "Reaction Added",
                "description": "Triggers when an emoji reaction is added to a message",
                "trigger_type": "webhook",
                "trigger_config": json.dumps({
                    "event_types": ["reaction_added"]
                }),
                "output_schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "event": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "user": {"type": "string"},
                                "reaction": {"type": "string"},
                                "item": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "channel": {"type": "string"},
                                        "ts": {"type": "string"}
                                    }
                                },
                                "event_ts": {"type": "string"}
                            }
                        }
                    }
                })
            }
        ]
        
        # Additional services to add
        new_services = [
            {
                "service_name": "update_message",
                "display_name": "Update Message",
                "description": "Update an existing message",
                "service_type": "action",
                "http_method": "POST",
                "endpoint_template": "https://slack.com/api/chat.update",
                "headers_template": json.dumps({
                    "Authorization": "Bearer {{auth.access_token}}",
                    "Content-Type": "application/json"
                }),
                "body_template": json.dumps({
                    "channel": "{{input.channel}}",
                    "ts": "{{input.ts}}",
                    "text": "{{input.text}}"
                }),
                "input_schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "ts": {"type": "string"},
                        "text": {"type": "string"}
                    },
                    "required": ["channel", "ts", "text"]
                })
            },
            {
                "service_name": "list_channels",
                "display_name": "List Channels",
                "description": "Get list of channels in workspace",
                "service_type": "search",
                "http_method": "GET",
                "endpoint_template": "https://slack.com/api/conversations.list",
                "headers_template": json.dumps({
                    "Authorization": "Bearer {{auth.access_token}}"
                }),
                "output_schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "channels": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "is_private": {"type": "boolean"},
                                    "is_member": {"type": "boolean"}
                                }
                            }
                        }
                    }
                })
            },
            {
                "service_name": "get_user_info",
                "display_name": "Get User Info",
                "description": "Get information about a user",
                "service_type": "search",
                "http_method": "GET",
                "endpoint_template": "https://slack.com/api/users.info?user={{input.user_id}}",
                "headers_template": json.dumps({
                    "Authorization": "Bearer {{auth.access_token}}"
                }),
                "input_schema": json.dumps({
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"}
                    },
                    "required": ["user_id"]
                })
            }
        ]
        
        # Note: In a real update, you would add these events and services
        # For now, we'll just print what would be added
        print(f"\n📝 Would add {len(new_events)} new events:")
        for event in new_events:
            print(f"   - {event['display_name']}")
            
        print(f"\n🔧 Would add {len(new_services)} new services:")
        for service in new_services:
            print(f"   - {service['display_name']}")
        
        conn.commit()
        print("\n✅ Slack configuration update completed!")
        
    except Exception as e:
        print(f"❌ Error updating Slack config: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default path
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "ioflow.db")
    
    update_slack_config(db_path)
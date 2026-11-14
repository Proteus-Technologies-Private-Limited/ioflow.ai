"""
Simplified Soft Update Manager for Seed Applications

This version uses direct SQL queries to avoid ORM issues while preserving subscriptions.
"""

import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from core.config import settings

logger = logging.getLogger(__name__)


class SimpleSoftUpdateManager:
    """Manages soft updates of seed applications preserving user data"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Use the correct database path from environment or settings
            import os
            
            # First try to get from environment variable
            database_url = os.environ.get("DATABASE_URL")
            
            # If not in environment, get from settings
            if not database_url:
                database_url = settings.database_url
            
            if database_url and database_url.startswith("sqlite"):
                # Extract the database path from the SQLite URL
                # Handle both sqlite:/// and sqlite://// formats
                if database_url.startswith("sqlite:////"):
                    db_path = database_url.replace("sqlite:////", "/")
                elif database_url.startswith("sqlite:///"):
                    db_path = database_url.replace("sqlite:///", "")
                else:
                    db_path = database_url.replace("sqlite://", "")
            else:
                # Fallback to default path
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ioflow.db")
        self.db_path = db_path
    
    def soft_update_application(
        self, 
        application_key: str,
        seed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Soft update an application preserving subscriptions and tokens.
        
        Only updates:
        - Application metadata (version, description, etc.)
        - Services (adds new, updates existing)
        - Events (adds new, updates existing)
        
        Preserves:
        - All user subscriptions
        - All authentication credentials
        - All tokens
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            app_config = seed_data.get("application", {})
            app_name = app_config.get("app_name")
            app_type = app_config.get("app_type", "global")
            
            if not app_name:
                return {
                    "success": False,
                    "error": f"Application name not found in seed data for '{application_key}'"
                }
            
            # Find existing application
            cursor.execute("""
                SELECT app_id, version, auth_type
                FROM applications 
                WHERE app_name = ? AND app_type = ?
            """, (app_name, app_type))
            
            existing_app = cursor.fetchone()
            if not existing_app:
                return {
                    "success": False,
                    "error": f"Application '{app_name}' not found in database"
                }
            
            app_id = existing_app[0]
            old_version = existing_app[1]
            
            logger.info(f"Soft updating '{app_name}' from v{old_version} to v{app_config.get('version')}")
            
            # Track changes
            changes = {
                "services": {"added": [], "updated": [], "removed": []},
                "events": {"added": [], "updated": [], "removed": []},
                "metadata_updated": False,
                "subscriptions_preserved": 0
            }
            
            # 1. Count subscriptions before update
            cursor.execute("""
                SELECT COUNT(*) FROM application_subscriptions
                WHERE app_id = ?
            """, (app_id,))
            
            subscription_count = cursor.fetchone()[0]
            changes["subscriptions_preserved"] = subscription_count
            logger.info(f"Preserving {subscription_count} subscription(s)")
            
            # 2. Update application metadata (safe fields only)
            # First, handle auth_config updates for Google applications
            auth_config_to_update = None
            if app_config.get("auth_type") == "oauth2" and app_name in ['Google Drive', 'Google Sheets', 'Google Tasks']:
                # Get the auth_config from seed data
                auth_config = app_config.get("auth_config", {})
                
                # Add Google OAuth credentials from settings
                if settings.google_client_id and settings.google_client_secret:
                    auth_config['default_credentials'] = {
                        'client_id': settings.google_client_id,
                        'client_secret': settings.google_client_secret
                    }
                    logger.info(f"Adding Google OAuth credentials from settings for {app_name}")
                    auth_config_to_update = json.dumps(auth_config)
            
            # Update with or without auth_config
            if auth_config_to_update:
                cursor.execute("""
                    UPDATE applications 
                    SET version = ?,
                        description = ?,
                        icon_url = ?,
                        base_url = ?,
                        category = ?,
                        auth_config = ?,
                        updated_at = ?
                    WHERE app_id = ?
                """, (
                    app_config.get("version", old_version),
                    app_config.get("description"),
                    app_config.get("icon_url"),
                    app_config.get("base_url"),
                    app_config.get("category"),
                    auth_config_to_update,
                    datetime.now(),
                    app_id
                ))
            else:
                cursor.execute("""
                    UPDATE applications 
                    SET version = ?,
                        description = ?,
                        icon_url = ?,
                        base_url = ?,
                        category = ?,
                        updated_at = ?
                    WHERE app_id = ?
                """, (
                    app_config.get("version", old_version),
                    app_config.get("description"),
                    app_config.get("icon_url"),
                    app_config.get("base_url"),
                    app_config.get("category"),
                    datetime.now(),
                    app_id
                ))
            
            if cursor.rowcount > 0:
                changes["metadata_updated"] = True
                if auth_config_to_update:
                    changes["auth_config_updated"] = True
                logger.info("Updated application metadata")
            
            # 3. Update Services
            changes["services"] = self._update_services(
                cursor, app_id, seed_data.get("services", [])
            )
            
            # 4. Update Events
            changes["events"] = self._update_events(
                cursor, app_id, seed_data.get("events", [])
            )
            
            # 5. Verify subscriptions are still there
            cursor.execute("""
                SELECT COUNT(*) FROM application_subscriptions
                WHERE app_id = ?
            """, (app_id,))
            
            final_subscription_count = cursor.fetchone()[0]
            
            if final_subscription_count != subscription_count:
                logger.warning(f"Subscription count changed: {subscription_count} → {final_subscription_count}")
                changes["subscriptions_preserved"] = final_subscription_count
            
            # Commit all changes
            conn.commit()
            
            logger.info(f"Successfully soft-updated application '{app_name}'")
            logger.info(f"Changes: {changes}")
            
            return {
                "success": True,
                "message": f"Application '{app_name}' updated successfully",
                "changes": changes,
                "application": {
                    "app_id": app_id,
                    "app_name": app_name,
                    "old_version": old_version,
                    "new_version": app_config.get("version"),
                    "subscriptions_preserved": final_subscription_count
                }
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error soft-updating application: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()
    
    def _update_services(
        self, 
        cursor, 
        app_id: str, 
        new_services: List[Dict]
    ) -> Dict[str, List[str]]:
        """Update services for an application"""
        
        changes = {"added": [], "updated": [], "removed": []}
        
        # Get existing services
        cursor.execute("""
            SELECT service_id, service_name 
            FROM application_services
            WHERE app_id = ?
        """, (app_id,))
        
        existing_services = {row[1]: row[0] for row in cursor.fetchall()}
        services_in_seed = set()
        
        for service_data in new_services:
            service_name = service_data.get("service_name")
            if not service_name:
                continue
                
            services_in_seed.add(service_name)
            
            # Build service config - include ALL seed configuration fields
            request_config = service_data.get('request_config', {})
            combined_config = {
                'endpoint_template': service_data.get('endpoint_template', ''),
                'request_config': request_config,
                'parameter_schema': service_data.get('parameter_schema', {}),
                'parameter_method': request_config.get('parameter_method', 'none'),
                'response_config': service_data.get('response_config', {}),
                'timeout_seconds': service_data.get('timeout_seconds', 30),
                'service_type': service_data.get('service_type', 'api_call'),
                'sync_mode': service_data.get('sync_mode', 'synchronous'),
                'base_url': service_data.get('base_url', ''),
                'service_name': service_data.get('service_name', service_name)
            }
            
            if service_name in existing_services:
                # Update existing service - including all fields from seed
                cursor.execute("""
                    UPDATE application_services
                    SET display_name = ?,
                        description = ?,
                        service_type = ?,
                        service_config = ?,
                        response_config = ?,
                        input_schema = ?,
                        output_schema = ?,
                        sample_input = ?,
                        sample_output = ?,
                        timeout_seconds = ?,
                        is_async = ?
                    WHERE service_id = ?
                """, (
                    service_data.get("display_name", service_name),
                    service_data.get("description"),
                    service_data.get("service_type", "api_call"),
                    json.dumps(combined_config),
                    json.dumps(service_data.get('response_config', {})),
                    json.dumps(service_data.get('parameter_schema', {})),
                    json.dumps(service_data.get('output_schema', {})),
                    json.dumps(service_data.get('sample_input', {})),
                    json.dumps(service_data.get('sample_output', {})),
                    service_data.get('timeout_seconds', 30),
                    service_data.get('is_async', False),
                    existing_services[service_name]
                ))
                
                changes["updated"].append(service_name)
                logger.info(f"Updated service: {service_name}")
                
            else:
                # Add new service
                service_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO application_services
                    (service_id, app_id, service_name, display_name, service_type,
                     description, service_config, response_config, input_schema, 
                     output_schema, sample_input, sample_output, is_async, timeout_seconds, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    service_id,
                    app_id,
                    service_name,
                    service_data.get("display_name", service_name),
                    service_data.get("service_type", "api_call"),
                    service_data.get("description"),
                    json.dumps(combined_config),
                    json.dumps(service_data.get('response_config', {})),
                    json.dumps(service_data.get('parameter_schema', {})),
                    json.dumps(service_data.get('output_schema', {})),
                    json.dumps(service_data.get('sample_input', {})),
                    json.dumps(service_data.get('sample_output', {})),
                    service_data.get('sync_mode') == 'asynchronous',
                    service_data.get('timeout_seconds', 30),
                    datetime.now()
                ))
                
                changes["added"].append(service_name)
                logger.info(f"Added new service: {service_name}")
        
        # Mark removed services as deprecated
        for service_name in existing_services:
            if service_name not in services_in_seed:
                cursor.execute("""
                    UPDATE application_services
                    SET description = '[[DEPRECATED]] ' || COALESCE(description, '')
                    WHERE service_id = ?
                """, (existing_services[service_name],))
                
                changes["removed"].append(f"{service_name} (marked deprecated)")
                logger.info(f"Marked service as deprecated: {service_name}")
        
        return changes
    
    def _update_events(
        self, 
        cursor, 
        app_id: str, 
        new_events: List[Dict]
    ) -> Dict[str, List[str]]:
        """Update events for an application"""
        
        changes = {"added": [], "updated": [], "removed": []}
        
        # Get existing events
        cursor.execute("""
            SELECT event_id, event_name 
            FROM application_events
            WHERE app_id = ?
        """, (app_id,))
        
        existing_events = {row[1]: row[0] for row in cursor.fetchall()}
        events_in_seed = set()
        
        for event_data in new_events:
            event_name = event_data.get("event_name")
            if not event_name:
                continue
                
            events_in_seed.add(event_name)
            
            if event_name in existing_events:
                # Update existing event
                cursor.execute("""
                    UPDATE application_events
                    SET display_name = ?,
                        description = ?,
                        event_configuration = ?,
                        sample_payload = ?,
                        output_schema = ?
                    WHERE event_id = ?
                """, (
                    event_data.get("display_name", event_name),
                    event_data.get("description"),
                    json.dumps(event_data.get("event_configuration", {})),
                    json.dumps(event_data.get("sample_payload", {})),
                    json.dumps(event_data.get("output_schema", {})),
                    existing_events[event_name]
                ))
                
                changes["updated"].append(event_name)
                logger.info(f"Updated event: {event_name}")
                
            else:
                # Add new event
                event_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO application_events
                    (event_id, app_id, event_name, display_name, event_type,
                     description, event_configuration, sample_payload, output_schema,
                     sync_mode, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    app_id,
                    event_name,
                    event_data.get("display_name", event_name),
                    event_data.get("event_type", "manual"),
                    event_data.get("description"),
                    json.dumps(event_data.get("event_configuration", {})),
                    json.dumps(event_data.get("sample_payload", {})),
                    json.dumps(event_data.get("output_schema", {})),
                    event_data.get("sync_mode", "asynchronous"),
                    True,
                    datetime.now()
                ))
                
                changes["added"].append(event_name)
                logger.info(f"Added new event: {event_name}")
        
        # Mark removed events as deprecated
        for event_name in existing_events:
            if event_name not in events_in_seed:
                cursor.execute("""
                    UPDATE application_events
                    SET description = '[[DEPRECATED]] ' || COALESCE(description, '')
                    WHERE event_id = ?
                """, (existing_events[event_name],))
                
                changes["removed"].append(f"{event_name} (marked deprecated)")
                logger.info(f"Marked event as deprecated: {event_name}")
        
        return changes


# Create singleton instance
simple_soft_update_manager = SimpleSoftUpdateManager()
"""
Soft Update Manager for Seed Applications

This module provides functionality to update seed applications without losing
user subscriptions, tokens, or authentication credentials.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
import uuid

from core.config import settings

# Import models - PostgreSQL Only
from db.application_models import (
    Application, ApplicationService, ApplicationEvent,
    ApplicationSubscription, AppType, AuthType, TriggerType, ServiceType
)
from db.models import User, Tenant

logger = logging.getLogger(__name__)


class SoftUpdateManager:
    """Manages soft updates of seed applications preserving user data"""
    
    def soft_update_application(
        self, 
        db: Session,
        application_key: str,
        seed_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Soft update an application preserving subscriptions and tokens.
        
        Only updates:
        - Application metadata (version, description, etc.)
        - Services (adds new, updates existing, removes deleted)
        - Events (adds new, updates existing, removes deleted)
        
        Preserves:
        - All user subscriptions
        - All authentication credentials
        - All tokens
        - All webhook configurations
        
        Args:
            db: Database session
            application_key: Key of the application to update
            seed_data: New seed application data
            user_id: ID of user performing update
            
        Returns:
            Update result with statistics
        """
        try:
            # Get existing application
            # First try to get the app_name from seed data
            app_config = seed_data.get("application", {})
            app_name = app_config.get("app_name")
            app_type = app_config.get("app_type", "global")
            
            if not app_name:
                return {
                    "success": False,
                    "error": f"Application name not found in seed data for '{application_key}'"
                }
            
            # Find application by name and type (same as install logic)
            existing_app = db.query(Application).filter(
                Application.app_name == app_name,
                Application.app_type == app_type
            ).first()
            
            if not existing_app:
                return {
                    "success": False,
                    "error": f"Application '{app_name}' not found in database"
                }
            
            # Track changes
            changes = {
                "services": {"added": [], "updated": [], "removed": []},
                "events": {"added": [], "updated": [], "removed": []},
                "metadata_updated": False,
                "subscriptions_preserved": 0
            }
            
            # 1. Update application metadata (preserving critical fields)
            logger.info(f"Updating metadata for application '{existing_app.app_name}'")
            
            # Only update safe fields that don't affect subscriptions
            safe_updates = {
                "description": app_config.get("description"),
                "version": app_config.get("version"),
                "icon_url": app_config.get("icon_url"),
                "base_url": app_config.get("base_url"),
                "category": app_config.get("category"),
                "display_name": app_config.get("display_name", app_config.get("app_name")),
                "updated_at": datetime.utcnow()
            }
            
            # Update auth_config only if structure remains compatible
            if "auth_config" in app_config:
                existing_auth_type = existing_app.auth_type
                new_auth_type = app_config.get("auth_type")
                
                if existing_auth_type == new_auth_type:
                    # Safe to update auth_config for same auth type
                    safe_updates["auth_config"] = json.dumps(app_config["auth_config"])
                else:
                    logger.warning(f"Skipping auth_config update due to auth_type change: {existing_auth_type} -> {new_auth_type}")
            
            for field, value in safe_updates.items():
                if value is not None and hasattr(existing_app, field):
                    setattr(existing_app, field, value)
                    changes["metadata_updated"] = True
            
            # 2. Update Services
            changes["services"] = self._update_services(
                db, existing_app.app_id, seed_data.get("services", [])
            )
            
            # 3. Update Events
            changes["events"] = self._update_events(
                db, existing_app.app_id, seed_data.get("events", [])
            )
            
            # 4. Count preserved subscriptions
            subscription_count = db.query(ApplicationSubscription).filter(
                ApplicationSubscription.app_id == existing_app.app_id
            ).count()
            changes["subscriptions_preserved"] = subscription_count
            
            # Commit all changes
            db.commit()
            
            logger.info(f"Successfully soft-updated application '{existing_app.app_name}'")
            logger.info(f"Changes: {changes}")
            
            return {
                "success": True,
                "message": f"Application '{existing_app.app_name}' updated successfully",
                "changes": changes,
                "application": {
                    "app_id": str(existing_app.app_id),
                    "app_name": existing_app.app_name,
                    "version": existing_app.version,
                    "subscriptions_preserved": subscription_count
                }
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error soft-updating application: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _update_services(
        self, 
        db: Session, 
        app_id: str, 
        new_services: List[Dict]
    ) -> Dict[str, List[str]]:
        """Update services for an application"""
        
        changes = {"added": [], "updated": [], "removed": []}
        
        # Get existing services
        existing_services = {
            s.service_name: s 
            for s in db.query(ApplicationService).filter(
                ApplicationService.app_id == app_id
            ).all()
        }
        
        # Track which services are in the new definition
        services_in_seed = set()
        
        for service_data in new_services:
            service_name = service_data.get("service_name")
            if not service_name:
                continue
                
            services_in_seed.add(service_name)
            
            if service_name in existing_services:
                # Update existing service
                service = existing_services[service_name]
                self._update_service_fields(service, service_data)
                changes["updated"].append(service_name)
                logger.info(f"Updated service: {service_name}")
                
            else:
                # Add new service
                service = ApplicationService(
                    service_id=str(uuid.uuid4()),
                    app_id=app_id,
                    service_name=service_name,
                    display_name=service_data.get("display_name", service_name),
                    description=service_data.get("description"),
                    service_type=service_data.get("service_type", "api_call"),
                    configuration=json.dumps(self._build_service_config(service_data)),
                    parameters=json.dumps(service_data.get("parameter_schema", {})),
                    sample_input=json.dumps(service_data.get("sample_input", {})),
                    sample_output=json.dumps(service_data.get("sample_output", {})),
                    created_at=datetime.utcnow()
                )
                db.add(service)
                changes["added"].append(service_name)
                logger.info(f"Added new service: {service_name}")
        
        # Remove services not in seed (optional - you may want to keep them)
        for service_name, service in existing_services.items():
            if service_name not in services_in_seed:
                # Option 1: Delete removed services
                # db.delete(service)
                # changes["removed"].append(service_name)
                # logger.info(f"Removed service: {service_name}")
                
                # Option 2: Mark as deprecated but keep (safer)
                service.description = f"[DEPRECATED] {service.description or ''}"
                changes["removed"].append(f"{service_name} (marked deprecated)")
                logger.info(f"Marked service as deprecated: {service_name}")
        
        return changes
    
    def _update_service_fields(self, service: ApplicationService, service_data: Dict):
        """Update fields of an existing service"""
        
        # Update safe fields
        if "display_name" in service_data:
            service.display_name = service_data["display_name"]
        
        if "description" in service_data:
            service.description = service_data["description"]
        
        # Update configuration
        service.configuration = json.dumps(self._build_service_config(service_data))
        
        # Update schemas
        if "parameter_schema" in service_data:
            service.parameters = json.dumps(service_data["parameter_schema"])
        
        if "sample_input" in service_data:
            service.sample_input = json.dumps(service_data["sample_input"])
        
        if "sample_output" in service_data:
            service.sample_output = json.dumps(service_data["sample_output"])
        
        service.updated_at = datetime.utcnow()
    
    def _build_service_config(self, service_data: Dict) -> Dict:
        """Build service configuration from seed data"""
        
        config = {
            "request_config": service_data.get("request_config", {}),
            "parameter_schema": service_data.get("parameter_schema", {}),
            "endpoint_template": service_data.get("endpoint_template", ""),
            "timeout_seconds": service_data.get("timeout_seconds", 30)
        }
        
        # Add any additional config fields
        for key in ["url_pattern", "headers_template", "body_template", 
                    "query_params_template", "parameter_method"]:
            if key in service_data:
                config[key] = service_data[key]
        
        return config
    
    def _update_events(
        self, 
        db: Session, 
        app_id: str, 
        new_events: List[Dict]
    ) -> Dict[str, List[str]]:
        """Update events for an application"""
        
        changes = {"added": [], "updated": [], "removed": []}
        
        # Get existing events
        existing_events = {
            e.event_name: e 
            for e in db.query(ApplicationEvent).filter(
                ApplicationEvent.app_id == app_id
            ).all()
        }
        
        # Track which events are in the new definition
        events_in_seed = set()
        
        for event_data in new_events:
            event_name = event_data.get("event_name")
            if not event_name:
                continue
                
            events_in_seed.add(event_name)
            
            if event_name in existing_events:
                # Update existing event
                event = existing_events[event_name]
                self._update_event_fields(event, event_data)
                changes["updated"].append(event_name)
                logger.info(f"Updated event: {event_name}")
                
            else:
                # Add new event
                event = ApplicationEvent(
                    event_id=str(uuid.uuid4()),
                    app_id=app_id,
                    event_name=event_name,
                    display_name=event_data.get("display_name", event_name),
                    description=event_data.get("description"),
                    trigger_type=event_data.get("trigger_type", "webhook"),
                    configuration=json.dumps(event_data.get("configuration", {})),
                    sample_payload=json.dumps(event_data.get("sample_payload", {})),
                    created_at=datetime.utcnow()
                )
                db.add(event)
                changes["added"].append(event_name)
                logger.info(f"Added new event: {event_name}")
        
        # Handle removed events
        for event_name, event in existing_events.items():
            if event_name not in events_in_seed:
                # Mark as deprecated instead of deleting
                event.description = f"[DEPRECATED] {event.description or ''}"
                changes["removed"].append(f"{event_name} (marked deprecated)")
                logger.info(f"Marked event as deprecated: {event_name}")
        
        return changes
    
    def _update_event_fields(self, event: ApplicationEvent, event_data: Dict):
        """Update fields of an existing event"""
        
        if "display_name" in event_data:
            event.display_name = event_data["display_name"]
        
        if "description" in event_data:
            event.description = event_data["description"]
        
        if "configuration" in event_data:
            event.configuration = json.dumps(event_data["configuration"])
        
        if "sample_payload" in event_data:
            event.sample_payload = json.dumps(event_data["sample_payload"])
        
        event.updated_at = datetime.utcnow()


# Create singleton instance
soft_update_manager = SoftUpdateManager()
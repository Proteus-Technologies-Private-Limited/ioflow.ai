"""
Flow Publisher Service

Orchestrates the process of converting flows to published applications,
managing versions, dependencies, and integration with the seed application system.
"""

import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from .flow_analyzer import FlowAnalyzer, FlowAnalysis
from .application_generator import ApplicationGenerator
from .json_seed_manager import JsonSeedManager
from db.application_models import (
    PublishedApplication, PublishedApplicationVersion, FlowApplicationDependency,
    ParameterMapping, Application, ApplicationService, ApplicationEvent
)
from db.models import Flow, User
from core.config import settings

logger = logging.getLogger(__name__)


class PublishingError(Exception):
    """Custom exception for publishing errors"""
    pass


class FlowPublisher:
    """Main service for publishing flows as applications"""
    
    def __init__(self):
        self.analyzer = FlowAnalyzer()
        self.generator = ApplicationGenerator()
        self.seed_manager = JsonSeedManager()
    
    def publish_flow(self, 
                    db: Session,
                    flow_id: str,
                    app_key: str,
                    user_id: str,
                    app_name: str = None,
                    description: str = None,
                    category: str = "Flow Applications",
                    app_scope: str = "tenant",
                    icon_url: str = None,
                    auto_update: bool = False,
                    generation_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Publish a flow as an application
        
        Args:
            db: Database session
            flow_id: ID of the flow to publish
            app_key: Unique key for the application
            user_id: ID of the user publishing the flow
            app_name: Name for the application
            description: Application description
            category: Application category
            app_scope: Application scope (global, tenant, or user)
            icon_url: URL to application icon
            auto_update: Whether to auto-update when flow changes
            generation_config: Configuration for generation process
            
        Returns:
            Dictionary with publishing result
        """
        logger.info(f"Starting flow publishing: flow_id={flow_id}, app_key={app_key}")
        
        try:
            # 1. Validate inputs
            self._validate_publishing_inputs(db, flow_id, app_key, user_id)
            
            # 2. Get flow information
            flow = self._get_flow_data(db, flow_id)
            
            # 3. Analyze the flow
            analysis = self._analyze_flow(flow)
            analysis.flow_id = flow_id
            
            # 4. Generate application definition
            seed_app = self.generator.generate_application(
                analysis=analysis,
                app_key=app_key,
                app_name=app_name or f"{flow['flow_name']} App",
                category=category,
                description=description,
                icon_url=icon_url
            )
            
            # 5. Validate generated application
            validation_result = self.generator.validate_generated_application(seed_app)
            if not validation_result["valid"]:
                raise PublishingError(f"Generated application validation failed: {validation_result['errors']}")
            
            # 6. Create application in database
            app_id = self._create_application_in_db(db, seed_app, user_id, app_scope)
            
            # 7. Create published application record
            published_app = self._create_published_application_record(
                db=db,
                flow_id=flow_id,
                app_id=app_id,
                app_key=app_key,
                flow_name=flow['flow_name'],
                analysis=analysis,
                generation_config=generation_config or {},
                user_id=user_id,
                auto_update=auto_update
            )
            
            # 8. Create parameter mappings
            self._create_parameter_mappings(db, published_app.published_app_id, analysis, app_id)
            
            # 9. Create dependencies
            self._create_dependencies(db, published_app.published_app_id, analysis)
            
            # 10. Create version record
            self._create_version_record(
                db=db,
                published_app_id=published_app.published_app_id,
                version="1.0.0",
                flow_definition=flow,
                generated_application=seed_app
            )
            
            # 11. Save as seed application file
            self._save_seed_application_file(app_key, seed_app)
            
            # 12. Refresh seed manager cache
            self.seed_manager.refresh_cache()
            
            # 13. Commit the transaction
            db.commit()
            
            logger.info(f"Successfully published flow {flow_id} as application {app_key}")
            
            return {
                "success": True,
                "message": f"Flow '{flow['flow_name']}' successfully published as application '{app_key}'",
                "published_app_id": published_app.published_app_id,
                "app_id": app_id,
                "app_key": app_key,
                "version": "1.0.0",
                "services_created": len(seed_app.get("services", [])),
                "events_created": len(seed_app.get("events", [])),
                "warnings": validation_result.get("warnings", [])
            }
            
        except Exception as e:
            logger.error(f"Error publishing flow {flow_id}: {str(e)}")
            db.rollback()
            raise PublishingError(f"Failed to publish flow: {str(e)}")
    
    def update_published_application(self,
                                   db: Session,
                                   published_app_id: str,
                                   user_id: str,
                                   force_update: bool = False) -> Dict[str, Any]:
        """
        Update a published application from its source flow
        
        Args:
            db: Database session
            published_app_id: ID of the published application
            user_id: ID of the user requesting update
            force_update: Force update even if no changes detected
            
        Returns:
            Dictionary with update result
        """
        logger.info(f"Updating published application: {published_app_id}")
        
        try:
            # Get published application
            published_app = db.query(PublishedApplication).filter(
                PublishedApplication.published_app_id == published_app_id
            ).first()
            
            if not published_app:
                raise PublishingError(f"Published application {published_app_id} not found")
            
            # Get current flow data
            flow = self._get_flow_data(db, published_app.flow_id)
            
            # Analyze current flow
            current_analysis = self._analyze_flow(flow)
            current_analysis.flow_id = published_app.flow_id
            
            # Get previous analysis
            previous_analysis_data = json.loads(published_app.flow_analysis) if published_app.flow_analysis else {}
            
            # Check if update is needed
            if not force_update and not self._has_significant_changes(current_analysis, previous_analysis_data):
                return {
                    "success": True,
                    "message": "No significant changes detected, update skipped",
                    "updated": False
                }
            
            # Generate new application definition
            seed_app = self.generator.generate_application(
                analysis=current_analysis,
                app_key=published_app.app_key,
                app_name=published_app.application.app_name,
                category=published_app.application.category,
                description=published_app.application.description,
                icon_url=published_app.application.icon_url
            )
            
            # Increment version
            new_version = self._increment_version(published_app.published_version)
            seed_app["application"]["version"] = new_version
            
            # Update application in database
            self._update_application_in_db(db, published_app.app_id, seed_app)
            
            # Update published application record
            published_app.published_version = new_version
            published_app.flow_analysis = json.dumps(current_analysis.to_dict())
            published_app.last_sync_at = datetime.now()
            published_app.updated_at = datetime.now()
            
            # Create new version record
            changes_summary = self._generate_changes_summary(current_analysis, previous_analysis_data)
            self._create_version_record(
                db=db,
                published_app_id=published_app_id,
                version=new_version,
                flow_definition=flow,
                generated_application=seed_app,
                changes_summary=changes_summary
            )
            
            # Update parameter mappings
            self._update_parameter_mappings(db, published_app_id, current_analysis, published_app.app_id)
            
            # Update dependencies
            self._update_dependencies(db, published_app_id, current_analysis)
            
            # Update seed application file
            self._save_seed_application_file(published_app.app_key, seed_app)
            
            # Refresh cache
            self.seed_manager.refresh_cache()
            
            db.commit()
            
            logger.info(f"Successfully updated published application {published_app_id} to version {new_version}")
            
            return {
                "success": True,
                "message": f"Published application updated to version {new_version}",
                "updated": True,
                "previous_version": published_app.published_version,
                "new_version": new_version,
                "changes": changes_summary
            }
            
        except Exception as e:
            logger.error(f"Error updating published application {published_app_id}: {str(e)}")
            db.rollback()
            raise PublishingError(f"Failed to update published application: {str(e)}")
    
    def unpublish_application(self,
                            db: Session,
                            published_app_id: str,
                            user_id: str,
                            keep_seed_file: bool = False) -> Dict[str, Any]:
        """
        Unpublish an application (remove from system)
        
        Args:
            db: Database session
            published_app_id: ID of the published application
            user_id: ID of the user requesting unpublish
            keep_seed_file: Whether to keep the seed application file
            
        Returns:
            Dictionary with unpublish result
        """
        logger.info(f"Unpublishing application: {published_app_id}")
        
        try:
            # Get published application
            published_app = db.query(PublishedApplication).filter(
                PublishedApplication.published_app_id == published_app_id
            ).first()
            
            if not published_app:
                raise PublishingError(f"Published application {published_app_id} not found")
            
            app_key = published_app.app_key
            app_id = published_app.app_id
            
            # Check for active subscriptions
            from db.application_models import ApplicationSubscription
            subscription_count = db.query(ApplicationSubscription).filter(
                ApplicationSubscription.app_id == app_id
            ).count()
            
            if subscription_count > 0:
                logger.warning(f"Unpublishing application with {subscription_count} active subscriptions")
            
            # Delete related records (in correct order)
            # 1. Parameter mappings
            db.query(ParameterMapping).filter(
                ParameterMapping.published_app_id == published_app_id
            ).delete()
            
            # 2. Dependencies
            db.query(FlowApplicationDependency).filter(
                FlowApplicationDependency.published_app_id == published_app_id
            ).delete()
            
            # 3. Versions
            db.query(PublishedApplicationVersion).filter(
                PublishedApplicationVersion.published_app_id == published_app_id
            ).delete()
            
            # 4. Application services and events
            db.query(ApplicationService).filter(
                ApplicationService.app_id == app_id
            ).delete()
            
            db.query(ApplicationEvent).filter(
                ApplicationEvent.app_id == app_id
            ).delete()
            
            # 5. Application subscriptions
            db.query(ApplicationSubscription).filter(
                ApplicationSubscription.app_id == app_id
            ).delete()
            
            # 6. Application itself
            db.query(Application).filter(
                Application.app_id == app_id
            ).delete()
            
            # 7. Published application record
            db.delete(published_app)
            
            # Remove seed application file
            if not keep_seed_file:
                self._remove_seed_application_file(app_key)
            
            # Refresh cache
            self.seed_manager.refresh_cache()
            
            db.commit()
            
            logger.info(f"Successfully unpublished application {published_app_id}")
            
            return {
                "success": True,
                "message": f"Application '{app_key}' successfully unpublished",
                "app_key": app_key,
                "subscriptions_removed": subscription_count
            }
            
        except Exception as e:
            logger.error(f"Error unpublishing application {published_app_id}: {str(e)}")
            db.rollback()
            raise PublishingError(f"Failed to unpublish application: {str(e)}")
    
    def get_published_applications(self,
                                 db: Session,
                                 user_id: str = None,
                                 status: str = None,
                                 flow_id: str = None) -> List[Dict[str, Any]]:
        """Get list of published applications with optional filters"""
        query = db.query(PublishedApplication).join(Application)
        
        if user_id:
            query = query.filter(PublishedApplication.created_by == user_id)
        
        if status:
            query = query.filter(PublishedApplication.status == status)
        
        if flow_id:
            query = query.filter(PublishedApplication.flow_id == flow_id)
        
        published_apps = query.all()
        
        result = []
        for pub_app in published_apps:
            result.append({
                "published_app_id": pub_app.published_app_id,
                "flow_id": pub_app.flow_id,
                "flow_name": pub_app.flow_name,
                "app_key": pub_app.app_key,
                "app_id": pub_app.app_id,  # Add the missing app_id field
                "app_name": pub_app.application.app_name,
                "version": pub_app.published_version,
                "status": pub_app.status,
                "auto_update": pub_app.auto_update,
                "usage_count": pub_app.usage_count,
                "created_at": pub_app.created_at.isoformat(),
                "updated_at": pub_app.updated_at.isoformat(),
                "last_sync_at": pub_app.last_sync_at.isoformat() if pub_app.last_sync_at else None
            })
        
        return result
    
    def get_publishing_preview(self,
                             db: Session,
                             flow_id: str,
                             app_key: str) -> Dict[str, Any]:
        """Generate a preview of what would be created when publishing a flow"""
        try:
            # Get flow data
            flow = self._get_flow_data(db, flow_id)
            
            # Analyze flow
            analysis = self._analyze_flow(flow)
            analysis.flow_id = flow_id
            
            # Generate preview
            preview = self.generator.generate_application_preview(
                analysis=analysis,
                app_key=app_key,
                app_name=f"{flow['flow_name']} App"
            )
            
            return {
                "success": True,
                "preview": preview,
                "analysis": analysis.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error generating preview for flow {flow_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Private helper methods
    
    def _validate_publishing_inputs(self, db: Session, flow_id: str, app_key: str, user_id: str):
        """Validate inputs for publishing"""
        # Check if flow exists
        flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise PublishingError(f"Flow {flow_id} not found")
        
        # Check if user exists
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise PublishingError(f"User {user_id} not found")
        
        # Note: We no longer check for unique app_key here as we allow republishing
    
    def _get_flow_data(self, db: Session, flow_id: str) -> Dict[str, Any]:
        """Get flow data from database"""
        flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
        if not flow:
            raise PublishingError(f"Flow {flow_id} not found")
        
        # Convert flow to dictionary
        flow_data = {
            "flow_id": flow.flow_id,
            "flow_name": flow.flow_name,
            "description": flow.description,
            "flow_definition": json.loads(flow.flow_definition) if isinstance(flow.flow_definition, str) else flow.flow_definition,
            "trigger_config": json.loads(flow.trigger_config) if isinstance(flow.trigger_config, str) else flow.trigger_config,
            "is_synchronous": flow.is_synchronous,
            "sync_timeout": flow.sync_timeout
        }
        
        return flow_data
    
    def _analyze_flow(self, flow_data: Dict[str, Any]) -> FlowAnalysis:
        """Analyze flow and return analysis object"""
        return self.analyzer.analyze_flow(
            flow_definition=flow_data["flow_definition"],
            trigger_config=flow_data["trigger_config"],
            flow_name=flow_data["flow_name"],
            description=flow_data.get("description", ""),
            is_synchronous=flow_data.get("is_synchronous", False)
        )
    
    def _create_application_in_db(self, db: Session, seed_app: Dict[str, Any], user_id: str, app_scope: str = "tenant") -> str:
        """Create or update application record in database"""
        app_config = seed_app["application"]
        app_key = seed_app["key"]
        
        # Check if application with this key already exists
        existing_published_app = db.query(PublishedApplication).filter(
            PublishedApplication.app_key == app_key
        ).first()
        
        if existing_published_app:
            # Update existing application
            logger.info(f"Updating existing application with key '{app_key}', app_id: {existing_published_app.app_id}")
            app_id = existing_published_app.app_id
            
            # Update the Application record
            application = db.query(Application).filter(Application.app_id == app_id).first()
            if application:
                application.app_name = app_config["app_name"]
                application.app_scope = app_scope
                application.app_type = app_config.get("app_type", "flow")
                application.description = app_config.get("description")
                application.icon_url = app_config.get("icon_url")
                application.category = app_config.get("category")
                application.base_url = app_config.get("base_url")
                application.auth_type = app_config["auth_type"]
                application.auth_config = json.dumps(app_config.get("auth_config", {}))
                application.version = app_config.get("version", "1.0.0")
                
                # Update existing services or create new ones
                self._update_application_services(db, app_id, seed_app.get("services", []))
                
                # Update existing events or create new ones
                self._update_application_events(db, app_id, seed_app.get("events", []))
            
        else:
            # Create new application
            app_id = str(uuid.uuid4())
            logger.info(f"Creating new application with key '{app_key}', app_id: {app_id}")
            
            application = Application(
                app_id=app_id,
                app_name=app_config["app_name"],
                app_scope=app_scope,
                app_type=app_config.get("app_type", "flow"),
                description=app_config.get("description"),
                icon_url=app_config.get("icon_url"),
                category=app_config.get("category"),
                base_url=app_config.get("base_url"),
                auth_type=app_config["auth_type"],
                auth_config=json.dumps(app_config.get("auth_config", {})),
                version=app_config.get("version", "1.0.0"),
                created_by=user_id,
                status="active"
            )
            
            db.add(application)
            db.flush()  # Get the ID
            
            # Create services
            self._create_application_services(db, app_id, seed_app.get("services", []))
            
            # Create events
            self._create_application_events(db, app_id, seed_app.get("events", []))
        
        return app_id
    
    def _create_application_services(self, db: Session, app_id: str, services_data: List[Dict[str, Any]]):
        """Create application services"""
        for service_data in services_data:
            service = ApplicationService(
                service_id=str(uuid.uuid4()),
                app_id=app_id,
                service_name=service_data["service_name"],
                display_name=service_data.get("display_name", service_data["service_name"]),
                description=service_data.get("description"),
                service_type=service_data["service_type"],
                service_config=json.dumps(service_data),
                timeout_seconds=service_data.get("timeout_seconds", 30),
                is_active=True
            )
            db.add(service)
    
    def _update_application_services(self, db: Session, app_id: str, services_data: List[Dict[str, Any]]):
        """Update application services while maintaining stable IDs"""
        # Get existing services
        existing_services = db.query(ApplicationService).filter(ApplicationService.app_id == app_id).all()
        existing_services_by_name = {svc.service_name: svc for svc in existing_services}
        
        # Track which services we've processed
        processed_service_names = set()
        
        for service_data in services_data:
            service_name = service_data["service_name"]
            processed_service_names.add(service_name)
            
            if service_name in existing_services_by_name:
                # Update existing service (maintain same service_id)
                existing_service = existing_services_by_name[service_name]
                logger.info(f"Updating existing service '{service_name}' with ID {existing_service.service_id}")
                
                existing_service.display_name = service_data.get("display_name", service_data["service_name"])
                existing_service.description = service_data.get("description")
                existing_service.service_type = service_data["service_type"]
                existing_service.service_config = json.dumps(service_data)
                existing_service.timeout_seconds = service_data.get("timeout_seconds", 30)
                existing_service.is_active = True
            else:
                # Create new service
                logger.info(f"Creating new service '{service_name}'")
                service = ApplicationService(
                    service_id=str(uuid.uuid4()),
                    app_id=app_id,
                    service_name=service_data["service_name"],
                    display_name=service_data.get("display_name", service_data["service_name"]),
                    description=service_data.get("description"),
                    service_type=service_data["service_type"],
                    service_config=json.dumps(service_data),
                    timeout_seconds=service_data.get("timeout_seconds", 30),
                    is_active=True
                )
                db.add(service)
        
        # Deactivate services that are no longer needed
        for service_name, existing_service in existing_services_by_name.items():
            if service_name not in processed_service_names:
                logger.info(f"Deactivating unused service '{service_name}'")
                existing_service.is_active = False
    
    def _create_application_events(self, db: Session, app_id: str, events_data: List[Dict[str, Any]]):
        """Create application events"""
        for event_data in events_data:
            event = ApplicationEvent(
                event_id=str(uuid.uuid4()),
                app_id=app_id,
                event_name=event_data["event_name"],
                display_name=event_data.get("display_name", event_data["event_name"]),
                description=event_data.get("description"),
                event_type=event_data["trigger_type"],
                event_configuration=json.dumps(event_data.get("trigger_config", {})),
                sync_mode=event_data.get("sync_mode", "async"),
                is_active=True
            )
            db.add(event)
    
    def _update_application_events(self, db: Session, app_id: str, events_data: List[Dict[str, Any]]):
        """Update application events while maintaining stable IDs"""
        # Get existing events
        existing_events = db.query(ApplicationEvent).filter(ApplicationEvent.app_id == app_id).all()
        existing_events_by_name = {evt.event_name: evt for evt in existing_events}
        
        # Track which events we've processed
        processed_event_names = set()
        
        for event_data in events_data:
            event_name = event_data["event_name"]
            processed_event_names.add(event_name)
            
            if event_name in existing_events_by_name:
                # Update existing event (maintain same event_id)
                existing_event = existing_events_by_name[event_name]
                logger.info(f"Updating existing event '{event_name}' with ID {existing_event.event_id}")
                
                existing_event.display_name = event_data.get("display_name", event_data["event_name"])
                existing_event.description = event_data.get("description")
                existing_event.event_type = event_data["trigger_type"]
                existing_event.event_configuration = json.dumps(event_data.get("trigger_config", {}))
                existing_event.sync_mode = event_data.get("sync_mode", "async")
                existing_event.is_active = True
            else:
                # Create new event
                logger.info(f"Creating new event '{event_name}'")
                event = ApplicationEvent(
                    event_id=str(uuid.uuid4()),
                    app_id=app_id,
                    event_name=event_data["event_name"],
                    display_name=event_data.get("display_name", event_data["event_name"]),
                    description=event_data.get("description"),
                    event_type=event_data["trigger_type"],
                    event_configuration=json.dumps(event_data.get("trigger_config", {})),
                    sync_mode=event_data.get("sync_mode", "async"),
                    is_active=True
                )
                db.add(event)
        
        # Deactivate events that are no longer needed
        for event_name, existing_event in existing_events_by_name.items():
            if event_name not in processed_event_names:
                logger.info(f"Deactivating unused event '{event_name}'")
                existing_event.is_active = False
    
    def _update_application_in_db(self, db: Session, app_id: str, seed_app: Dict[str, Any]):
        """Update existing application in database"""
        app_config = seed_app["application"]
        
        # Update application
        application = db.query(Application).filter(Application.app_id == app_id).first()
        if application:
            application.app_name = app_config["app_name"]
            application.description = app_config.get("description")
            application.version = app_config.get("version", "1.0.0")
            application.updated_at = datetime.now()
        
        # Update services (simple approach: delete and recreate)
        db.query(ApplicationService).filter(ApplicationService.app_id == app_id).delete()
        for service_data in seed_app.get("services", []):
            service = ApplicationService(
                service_id=str(uuid.uuid4()),
                app_id=app_id,
                service_name=service_data["service_name"],
                display_name=service_data.get("display_name", service_data["service_name"]),
                description=service_data.get("description"),
                service_type=service_data["service_type"],
                service_config=json.dumps(service_data),
                timeout_seconds=service_data.get("timeout_seconds", 30),
                is_active=True
            )
            db.add(service)
        
        # Update events
        db.query(ApplicationEvent).filter(ApplicationEvent.app_id == app_id).delete()
        for event_data in seed_app.get("events", []):
            event = ApplicationEvent(
                event_id=str(uuid.uuid4()),
                app_id=app_id,
                event_name=event_data["event_name"],
                display_name=event_data.get("display_name", event_data["event_name"]),
                description=event_data.get("description"),
                event_type=event_data["trigger_type"],
                event_configuration=json.dumps(event_data.get("trigger_config", {})),
                sync_mode=event_data.get("sync_mode", "async"),
                is_active=True
            )
            db.add(event)
    
    def _create_published_application_record(self, **kwargs) -> PublishedApplication:
        """Create or update published application record"""
        db = kwargs["db"]
        app_key = kwargs["app_key"]
        
        # Check if published application already exists
        existing_published_app = db.query(PublishedApplication).filter(
            PublishedApplication.app_key == app_key
        ).first()
        
        if existing_published_app:
            # Update existing published application record
            logger.info(f"Updating existing published application record for key '{app_key}'")
            existing_published_app.flow_id = kwargs["flow_id"]
            existing_published_app.app_id = kwargs["app_id"]
            existing_published_app.flow_name = kwargs["flow_name"]
            existing_published_app.flow_analysis = json.dumps(kwargs["analysis"].to_dict())
            existing_published_app.generation_config = json.dumps(kwargs["generation_config"])
            existing_published_app.auto_update = kwargs["auto_update"]
            existing_published_app.status = "active"
            existing_published_app.updated_at = datetime.now()
            
            return existing_published_app
        else:
            # Create new published application record
            logger.info(f"Creating new published application record for key '{app_key}'")
            published_app = PublishedApplication(
                published_app_id=str(uuid.uuid4()),
                flow_id=kwargs["flow_id"],
                app_id=kwargs["app_id"],
                app_key=kwargs["app_key"],
                flow_name=kwargs["flow_name"],
                flow_analysis=json.dumps(kwargs["analysis"].to_dict()),
                generation_config=json.dumps(kwargs["generation_config"]),
                created_by=kwargs["user_id"],
                auto_update=kwargs["auto_update"],
                status="active"
            )
            
            db.add(published_app)
            db.flush()
            
            return published_app
    
    def _create_parameter_mappings(self, db: Session, published_app_id: str, 
                                 analysis: FlowAnalysis, app_id: str):
        """Create parameter mappings for the published application"""
        # Get services for the application
        services = db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id
        ).all()
        
        primary_service = services[0] if services else None
        
        if primary_service:
            # Create input parameter mappings
            for param in analysis.input_parameters:
                mapping = ParameterMapping(
                    mapping_id=str(uuid.uuid4()),
                    published_app_id=published_app_id,
                    service_id=primary_service.service_id,
                    parameter_name=param.name,
                    parameter_type="input",
                    flow_variable_path=f"input.{param.name}",
                    service_parameter_name=param.name,
                    is_required=param.required,
                    description=param.description
                )
                db.add(mapping)
            
            # Create output parameter mappings
            for output in analysis.output_parameters:
                mapping = ParameterMapping(
                    mapping_id=str(uuid.uuid4()),
                    published_app_id=published_app_id,
                    service_id=primary_service.service_id,
                    parameter_name=output.name,
                    parameter_type="output",
                    flow_variable_path=output.path,
                    service_parameter_name=output.name,
                    description=output.description
                )
                db.add(mapping)
    
    def _update_parameter_mappings(self, db: Session, published_app_id: str, 
                                 analysis: FlowAnalysis, app_id: str):
        """Update parameter mappings"""
        # Delete existing mappings
        db.query(ParameterMapping).filter(
            ParameterMapping.published_app_id == published_app_id
        ).delete()
        
        # Create new mappings
        self._create_parameter_mappings(db, published_app_id, analysis, app_id)
    
    def _create_dependencies(self, db: Session, published_app_id: str, analysis: FlowAnalysis):
        """Create dependency records"""
        for dep_app_name in analysis.dependencies:
            # Find the application by name
            app = db.query(Application).filter(
                Application.app_name == dep_app_name
            ).first()
            
            if app:
                dependency = FlowApplicationDependency(
                    dependency_id=str(uuid.uuid4()),
                    published_app_id=published_app_id,
                    depends_on_app_id=app.app_id,
                    dependency_type="service",
                    dependency_name=dep_app_name,
                    is_required=True
                )
                db.add(dependency)
    
    def _update_dependencies(self, db: Session, published_app_id: str, analysis: FlowAnalysis):
        """Update dependencies"""
        # Delete existing dependencies
        db.query(FlowApplicationDependency).filter(
            FlowApplicationDependency.published_app_id == published_app_id
        ).delete()
        
        # Create new dependencies
        self._create_dependencies(db, published_app_id, analysis)
    
    def _create_version_record(self, db: Session, published_app_id: str, version: str,
                             flow_definition: Dict[str, Any], generated_application: Dict[str, Any],
                             changes_summary: Dict[str, Any] = None):
        """Create version record"""
        version_record = PublishedApplicationVersion(
            version_id=str(uuid.uuid4()),
            published_app_id=published_app_id,
            version_number=version,
            flow_definition=json.dumps(flow_definition),
            generated_application=json.dumps(generated_application),
            changes_summary=json.dumps(changes_summary or {}),
            is_active=True
        )
        db.add(version_record)
    
    def _save_seed_application_file(self, app_key: str, seed_app: Dict[str, Any]):
        """Save seed application to file system"""
        import os
        
        seed_dir = self.seed_manager._applications_path
        os.makedirs(seed_dir, exist_ok=True)
        
        file_path = os.path.join(seed_dir, f"{app_key}.json")
        with open(file_path, 'w') as f:
            json.dump(seed_app, f, indent=2)
        
        logger.info(f"Saved seed application file: {file_path}")
    
    def _remove_seed_application_file(self, app_key: str):
        """Remove seed application file"""
        import os
        
        file_path = os.path.join(self.seed_manager._applications_path, f"{app_key}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Removed seed application file: {file_path}")
    
    def _has_significant_changes(self, current_analysis: FlowAnalysis, 
                               previous_analysis_data: Dict[str, Any]) -> bool:
        """Check if there are significant changes between analyses"""
        if not previous_analysis_data:
            return True
        
        # Compare key aspects
        current_dict = current_analysis.to_dict()
        
        # Check input parameters
        if len(current_dict.get("input_parameters", [])) != len(previous_analysis_data.get("input_parameters", [])):
            return True
        
        # Check transformations
        if len(current_dict.get("transformations", [])) != len(previous_analysis_data.get("transformations", [])):
            return True
        
        # Check dependencies
        if set(current_dict.get("dependencies", [])) != set(previous_analysis_data.get("dependencies", [])):
            return True
        
        # Check complexity score change
        current_complexity = current_dict.get("complexity_score", 0)
        previous_complexity = previous_analysis_data.get("complexity_score", 0)
        if abs(current_complexity - previous_complexity) > 5:  # Significant complexity change
            return True
        
        return False
    
    def _increment_version(self, current_version: str) -> str:
        """Increment version number"""
        try:
            parts = current_version.split(".")
            major = int(parts[0]) if len(parts) > 0 else 1
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            
            patch += 1
            return f"{major}.{minor}.{patch}"
        except:
            return "1.0.1"
    
    def _generate_changes_summary(self, current_analysis: FlowAnalysis, 
                                previous_analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of changes between versions"""
        changes = {
            "timestamp": datetime.now().isoformat(),
            "changes": []
        }
        
        if not previous_analysis_data:
            changes["changes"].append("Initial version")
            return changes
        
        current_dict = current_analysis.to_dict()
        
        # Check parameter changes
        current_params = len(current_dict.get("input_parameters", []))
        previous_params = len(previous_analysis_data.get("input_parameters", []))
        if current_params != previous_params:
            changes["changes"].append(f"Parameter count changed: {previous_params} → {current_params}")
        
        # Check transformation changes
        current_transforms = len(current_dict.get("transformations", []))
        previous_transforms = len(previous_analysis_data.get("transformations", []))
        if current_transforms != previous_transforms:
            changes["changes"].append(f"Transformation count changed: {previous_transforms} → {current_transforms}")
        
        # Check dependency changes
        current_deps = set(current_dict.get("dependencies", []))
        previous_deps = set(previous_analysis_data.get("dependencies", []))
        if current_deps != previous_deps:
            added = current_deps - previous_deps
            removed = previous_deps - current_deps
            if added:
                changes["changes"].append(f"Added dependencies: {', '.join(added)}")
            if removed:
                changes["changes"].append(f"Removed dependencies: {', '.join(removed)}")
        
        if not changes["changes"]:
            changes["changes"].append("Minor updates")
        
        return changes
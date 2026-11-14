"""
JSON-based Seed Application Manager

Reads seed applications from JSON files in the seed-applications directory
"""
import os
import re
import json
import glob
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from db.database import get_db
from db.application_models import Application, ApplicationService, ApplicationEvent, ApplicationSubscription, OAuthState
from schemas.seed_schemas import SeedApplicationInfo, InstallationStatus
from core.config import settings
import logging
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_server'))
from validators.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


def serialize_json_field(value: Any) -> Any:
    """Serialize JSON field for SQLite compatibility"""
    if settings.database_url.startswith("sqlite") and isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def deserialize_json_field(value: Any) -> Any:
    """The inverse of serialize_json_field: a JSON string (SQLite) back to an object."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


class JsonSeedManager:
    """Manages JSON-based seed applications"""
    
    def __init__(self):
        self._applications_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._applications_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'seed-applications'
        )
        self.schema_validator = SchemaValidator()
    
    def discover_applications(self) -> Dict[str, Dict[str, Any]]:
        """Discover all available seed applications from JSON files"""
        if self._applications_cache is not None:
            return self._applications_cache
        
        applications = {}
        
        try:
            # Create directory if it doesn't exist
            if not os.path.exists(self._applications_path):
                logger.info(f"Creating seed applications directory: {self._applications_path}")
                os.makedirs(self._applications_path)
                return applications
            
            # Find all JSON files
            json_files = glob.glob(os.path.join(self._applications_path, "*.json"))
            
            for json_file in json_files:
                if os.path.basename(json_file) == "README.md":
                    continue
                    
                try:
                    with open(json_file, 'r') as f:
                        app_data = json.load(f)
                    
                    # Validate required fields
                    if 'key' not in app_data or 'application' not in app_data:
                        logger.warning(f"Skipping {json_file}: missing 'key' or 'application' field")
                        continue
                    
                    app_key = app_data['key']
                    
                    # Validate the application structure
                    validation_result = self.schema_validator.validate_seed_application(app_data)
                    
                    # Add validation status to the application data
                    app_data['_validation'] = {
                        'valid': validation_result["valid"],
                        'errors': validation_result.get("errors", []),
                        'warnings': validation_result.get("warnings", []),
                        'validated_at': datetime.now().isoformat()
                    }
                    
                    if not validation_result["valid"]:
                        logger.warning(f"Seed application '{app_key}' has validation errors: {validation_result['errors']}")
                        # Still load it but log the issues
                    
                    if validation_result.get("warnings"):
                        logger.warning(f"Seed application '{app_key}' has validation warnings: {validation_result['warnings']}")
                    
                    applications[app_key] = app_data
                    logger.info(f"Discovered seed application: {app_key} from {os.path.basename(json_file)}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON file {json_file}: {e}")
                except Exception as e:
                    logger.error(f"Error loading seed application from {json_file}: {e}")
            
            self._applications_cache = applications
            logger.info(f"Discovered {len(applications)} seed applications")
            return applications
            
        except Exception as e:
            logger.error(f"Error discovering seed applications: {e}")
            return {}
    
    def discover_seed_applications(self) -> Dict[str, Dict[str, Any]]:
        """Alias for discover_applications() to maintain backward compatibility"""
        return self.discover_applications()
    
    def list_applications(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all applications, optionally filtered by category"""
        applications = self.discover_applications()
        result = []
        
        for key, app_data in applications.items():
            app_info = {
                'key': key,
                'name': app_data['application']['app_name'],
                'description': app_data['application'].get('description', ''),
                'category': app_data['application'].get('category', 'Other'),
                'auth_type': app_data['application'].get('auth_type', 'none'),
                'version': app_data['application'].get('version', '1.0.0'),
                'icon_url': app_data['application'].get('icon_url'),
                'ui_config': app_data['application'].get('ui_config'),
                'service_count': len(app_data.get('services', [])),
                'event_count': len(app_data.get('events', []))
            }
            
            if category is None or app_info['category'] == category:
                result.append(app_info)
        
        return result
    
    def get_application(self, app_key: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific application"""
        applications = self.discover_applications()
        return applications.get(app_key)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for seed applications"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["key", "application"],
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Unique identifier for the seed application"
                },
                "application": {
                    "type": "object",
                    "required": ["app_name", "app_type"],
                    "properties": {
                        "app_name": {"type": "string"},
                        "app_type": {"type": "string", "enum": ["global", "user", "tenant"]},
                        "description": {"type": "string"},
                        "icon_url": {"type": "string"},
                        "category": {"type": "string"},
                        "base_url": {"type": "string"},
                        "auth_type": {"type": "string", "enum": ["none", "api_key", "oauth", "basic"]},
                        "auth_config": {"type": "object"},
                        "version": {"type": "string"}
                    }
                },
                "services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["service_name", "service_type"],
                        "properties": {
                            "service_name": {"type": "string"},
                            "display_name": {"type": "string"},
                            "service_type": {"type": "string"},
                            "description": {"type": "string"},
                            "endpoint_url": {"type": "string"},
                            "http_method": {"type": "string"},
                            "request_config": {"type": "object"},
                            "response_config": {"type": "object"},
                            "parameter_schema": {"type": "object"},
                            "output_schema": {"type": "object"},
                            "sync_mode": {"type": "string"},
                            "timeout_seconds": {"type": "integer"}
                        }
                    }
                },
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["event_name", "trigger_type"],
                        "properties": {
                            "event_name": {"type": "string"},
                            "display_name": {"type": "string"},
                            "trigger_type": {"type": "string"},
                            "description": {"type": "string"},
                            "trigger_config": {"type": "object"},
                            "sync_mode": {"type": "string"}
                        }
                    }
                }
            }
        }
    
    def get_seed_applications(self, db: Session, tenant_id: str = None) -> List[SeedApplicationInfo]:
        """Get list of all available seed applications with their status

        Args:
            db: Database session
            tenant_id: Optional tenant ID to filter subscription count by tenant
        """
        applications_data = self.discover_applications()
        applications = []

        for key, app_data in applications_data.items():
            try:
                app_config = app_data['application']
                services = app_data.get('services', [])
                events = app_data.get('events', [])

                # Check if application is installed - first try by seed_key (most reliable)
                existing_app = db.query(Application).filter(
                    Application.seed_key == key,
                    Application.app_scope != 'tenant'
                ).first()

                # Fall back to app_name matching for backward compatibility
                if not existing_app:
                    existing_app = db.query(Application).filter(
                        Application.app_name == app_config['app_name'],
                        Application.app_scope != 'tenant'
                    ).first()

                if existing_app:
                    # Get subscription count - filter by tenant_id if provided
                    subscription_query = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
                        ApplicationSubscription.app_id == existing_app.app_id
                    )
                    if tenant_id:
                        subscription_query = subscription_query.filter(
                            ApplicationSubscription.tenant_id == str(tenant_id)
                        )
                    subscription_count = subscription_query.scalar() or 0
                    
                    # Check version
                    if existing_app.version == app_config.get('version', '1.0.0'):
                        status = InstallationStatus.INSTALLED
                    else:
                        status = InstallationStatus.UPDATE_AVAILABLE
                    
                    installed_version = existing_app.version
                    installed_at = existing_app.created_at.isoformat() if existing_app.created_at else None
                else:
                    status = InstallationStatus.NOT_INSTALLED
                    installed_version = None
                    installed_at = None
                    subscription_count = 0
                
                # Get metadata fields
                metadata = app_data.get('metadata', {})
                
                app_info = SeedApplicationInfo(
                    key=key,
                    name=app_config['app_name'],
                    description=app_config.get('description', ''),
                    category=app_config.get('category', 'Other'),
                    auth_type=app_config.get('auth_type', 'none'),
                    version=app_config.get('version', '1.0.0'),
                    icon_url=app_config.get('icon_url'),
                    status=status,
                    installed_version=installed_version,
                    installed_at=installed_at,
                    app_id=str(existing_app.app_id) if existing_app else None,
                    subscription_count=subscription_count,
                    service_count=len(services),
                    event_count=len(events),
                    created_at=metadata.get('created_at'),
                    last_modified=metadata.get('last_modified')
                )
                
                applications.append(app_info)
                
            except Exception as e:
                logger.error(f"Error processing seed application {key}: {e}")
        
        return applications
    
    def get_installation_warning(self, db: Session, application_key: str) -> Optional[Dict[str, Any]]:
        """Check if application is already installed and return warning"""
        applications_data = self.discover_applications()

        if application_key not in applications_data:
            return None

        app_config = applications_data[application_key]['application']

        # Check if already installed - first try by seed_key (most reliable)
        existing_app = db.query(Application).filter(
            Application.seed_key == application_key,
            Application.app_scope != 'tenant'
        ).first()

        # Fall back to app_name matching for backward compatibility
        if not existing_app:
            existing_app = db.query(Application).filter(
                Application.app_name == app_config['app_name'],
                Application.app_scope != 'tenant'
            ).first()
        
        if not existing_app:
            return None
        
        # Get subscription count
        subscription_count = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
            ApplicationSubscription.app_id == existing_app.app_id
        ).scalar() or 0
        
        return {
            'application_name': app_config['app_name'],
            'message': f"Application '{app_config['app_name']}' is already installed. Reinstalling will delete all existing subscriptions and data.",
            'subscription_count': subscription_count,
            'installed_version': existing_app.version,
            'new_version': app_config.get('version', '1.0.0')
        }
    
    def install_application(self, db: Session, application_key: str, force_reinstall: bool = False, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Install or reinstall a seed application from JSON"""
        applications_data = self.discover_applications()
        
        if application_key not in applications_data:
            return {
                'success': False,
                'message': f"Seed application '{application_key}' not found"
            }
        
        app_data = applications_data[application_key]
        app_config = app_data['application']
        services = app_data.get('services', [])
        events = app_data.get('events', [])
        
        try:
            # Check if already installed - first try by seed_key (most reliable)
            existing_app = db.query(Application).filter(
                Application.seed_key == application_key,
                Application.app_scope != 'tenant'
            ).first()

            # Fall back to app_name matching for backward compatibility
            if not existing_app:
                existing_app = db.query(Application).filter(
                    Application.app_name == app_config['app_name'],
                    Application.app_scope != 'tenant'
                ).first()

            if existing_app and not force_reinstall:
                # Get subscription count for warning
                subscription_count = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
                    ApplicationSubscription.app_id == existing_app.app_id
                ).scalar() or 0
                
                warnings = []
                if subscription_count > 0:
                    warnings.append(f"Application has {subscription_count} active subscriptions that will be deleted")
                
                return {
                    'success': False,
                    'message': f"Application '{app_config['app_name']}' is already installed. Use force_reinstall=true to reinstall.",
                    'warnings': warnings
                }
            
            deleted_subscriptions = 0
            
            if existing_app and force_reinstall:
                logger.info(f"Force reinstalling application '{app_config['app_name']}'")
                
                # Delete all OAuth states for this application first
                # This prevents foreign key constraint issues
                deleted_oauth_states = db.query(OAuthState).filter(
                    OAuthState.app_id == existing_app.app_id
                ).delete()
                if deleted_oauth_states > 0:
                    logger.info(f"Deleted {deleted_oauth_states} OAuth states for application")
                
                # Delete all subscriptions first
                deleted_subscriptions = db.query(ApplicationSubscription).filter(
                    ApplicationSubscription.app_id == existing_app.app_id
                ).delete()
                
                # Delete events
                db.query(ApplicationEvent).filter(
                    ApplicationEvent.app_id == existing_app.app_id
                ).delete()
                
                # Delete services
                db.query(ApplicationService).filter(
                    ApplicationService.app_id == existing_app.app_id
                ).delete()
                
                # Delete application
                db.delete(existing_app)
                db.commit()
                
                logger.info(f"Deleted existing application and {deleted_subscriptions} subscriptions")
            
            # Validate OAuth2 configuration
            auth_type = app_config.get('auth_type', 'none')
            auth_config = app_config.get('auth_config', {})
            
            if auth_type == 'oauth2':
                # Check for required OAuth2 fields
                authorization_url = auth_config.get('authorization_url') or auth_config.get('auth_url')
                token_url = auth_config.get('token_url')
                
                if not authorization_url:
                    return {
                        'success': False,
                        'message': f"OAuth2 application '{app_config['app_name']}' is missing required 'authorization_url' in auth_config"
                    }
                
                if not token_url:
                    return {
                        'success': False,
                        'message': f"OAuth2 application '{app_config['app_name']}' is missing required 'token_url' in auth_config"
                    }
                
                # Ensure authorization_url is present for OAuth2
                if auth_type == 'oauth2' and 'authorization_url' not in auth_config:
                    raise ValueError(f"Application '{app_config['app_name']}' is missing required 'authorization_url' field in auth_config")
            
            # Add default_custom_params if provided in the seed application
            if 'default_custom_params' in app_config:
                auth_config['default_custom_params'] = app_config['default_custom_params']
            
            # Add Google OAuth credentials from settings for Google applications
            from core.config import settings
            if app_config['app_name'] in ['Google Drive', 'Google Sheets', 'Google Tasks'] and auth_type == 'oauth2':
                if settings.google_client_id and settings.google_client_secret:
                    auth_config['default_credentials'] = {
                        'client_id': settings.google_client_id,
                        'client_secret': settings.google_client_secret
                    }
                    logger.info(f"Added Google OAuth credentials from settings for {app_config['app_name']}")
            
            # Create new application
            new_app = Application(
                app_name=app_config['app_name'],
                app_type=app_config.get('app_type', 'global'),
                description=app_config.get('description'),
                icon_url=app_config.get('icon_url'),
                category=app_config.get('category', 'Other'),
                base_url=app_config.get('base_url'),
                auth_type=auth_type,
                auth_config=serialize_json_field(auth_config),
                # Application-level webhook_config (e.g. {"signature": {...}} for inbound
                # webhook HMAC checks). Only read from application.webhook_config.
                webhook_config=serialize_json_field(app_config['webhook_config']) if isinstance(app_config.get('webhook_config'), dict) else None,
                version=app_config.get('version', '1.0.0'),
                seed_key=application_key,  # Store the seed key for cross-instance portability
                is_seed_app=True,  # Mark as seed application
                instance_number=1,  # First instance
                total_instances=0,  # No instances yet
                created_by=user_id
            )
            db.add(new_app)
            db.flush()  # Get the app_id
            
            # Validate services before creating any database records
            service_errors = []
            for i, service_config in enumerate(services):
                service_identifier = service_config.get('service_name') or service_config.get('name') or f"Service #{i+1}"
                
                # Validate required fields
                if not service_config.get('service_name'):
                    service_errors.append(f"Service '{service_identifier}' missing required 'service_name' field")
                
                # Validate parameter_schema if present
                parameter_schema = service_config.get('parameter_schema', {})
                if parameter_schema and not isinstance(parameter_schema, dict):
                    service_errors.append(f"Service '{service_identifier}' has invalid parameter_schema format (must be object)")
                
                # Validate request_config if present
                request_config = service_config.get('request_config', {})
                if request_config and not isinstance(request_config, dict):
                    service_errors.append(f"Service '{service_identifier}' has invalid request_config format (must be object)")
                
                # Validate parameters JSON if present
                parameters_json_str = service_config.get('parameters')
                if parameters_json_str and isinstance(parameters_json_str, str):
                    try:
                        params_list = json.loads(parameters_json_str)
                        if not isinstance(params_list, list):
                            service_errors.append(f"Service '{service_identifier}' parameters must be a JSON array")
                    except json.JSONDecodeError:
                        service_errors.append(f"Service '{service_identifier}' has invalid parameters JSON format")
            
            # Validate events before creating any database records
            event_errors = []
            for i, event_config in enumerate(events):
                event_identifier = event_config.get('event_name') or event_config.get('name') or f"Event #{i+1}"
                
                # Validate required fields
                if not (event_config.get('event_name') or event_config.get('name')):
                    event_errors.append(f"Event '{event_identifier}' missing required 'event_name' field")
                
                # Validate sample_payload if present
                sample_payload = event_config.get('sample_payload')
                if sample_payload is not None:
                    if isinstance(sample_payload, str):
                        try:
                            json.loads(sample_payload)
                        except json.JSONDecodeError:
                            event_errors.append(f"Event '{event_identifier}' has invalid sample_payload JSON format")
                    elif not isinstance(sample_payload, (dict, list)):
                        event_errors.append(f"Event '{event_identifier}' sample_payload must be a JSON object, array, or valid JSON string")
                
                # Validate event_configuration if present
                event_config_field = event_config.get('event_configuration', event_config.get('trigger_config', event_config.get('webhook_config')))
                if event_config_field and not isinstance(event_config_field, dict):
                    event_errors.append(f"Event '{event_identifier}' has invalid event_configuration format (must be object)")
            
            # If there are validation errors, rollback and return errors
            all_errors = service_errors + event_errors
            if all_errors:
                # Rollback the application creation
                if new_app.app_id:
                    try:
                        db.delete(new_app)
                        db.commit()
                        logger.info(f"Rolled back application creation due to validation errors: {new_app.app_name}")
                    except Exception as rollback_error:
                        logger.error(f"Error during rollback: {rollback_error}")
                        db.rollback()
                
                return {
                    'success': False,
                    'message': f"Seed application validation failed during installation",
                    'errors': all_errors,
                    'rollback_performed': True
                }
            
            # Create services - all validation passed
            created_services = []
            for i, service_config in enumerate(services):
                try:
                    service = ApplicationService(
                        app_id=new_app.app_id,
                        **self._service_row_fields(service_config)
                    )
                    db.add(service)
                    created_services.append(service)
                except Exception as e:
                    # Rollback all created services and the application
                    try:
                        for created_service in created_services:
                            db.delete(created_service)
                        db.delete(new_app)
                        db.commit()
                        logger.info(f"Rolled back application and {len(created_services)} services due to service creation error")
                    except Exception as rollback_error:
                        logger.error(f"Error during service rollback: {rollback_error}")
                        db.rollback()
                    
                    service_identifier = service_config.get('name') or service_config.get('service_name') or f"Service #{i+1}"
                    return {
                        'success': False,
                        'message': f"Failed to create service '{service_identifier}': {str(e)}",
                        'errors': [f"Service creation error: {str(e)}"],
                        'rollback_performed': True
                    }
            
            # Create events - all validation passed
            created_events = []
            for i, event_config in enumerate(events):
                try:
                    event = ApplicationEvent(
                        app_id=new_app.app_id,
                        **self._event_row_fields(event_config)
                    )
                    db.add(event)
                    created_events.append(event)
                except Exception as e:
                    # Rollback all created services, events, and the application
                    try:
                        for created_event in created_events:
                            db.delete(created_event)
                        for created_service in created_services:
                            db.delete(created_service)
                        db.delete(new_app)
                        db.commit()
                        logger.info(f"Rolled back application, {len(created_services)} services, and {len(created_events)} events due to event creation error")
                    except Exception as rollback_error:
                        logger.error(f"Error during event rollback: {rollback_error}")
                        db.rollback()
                    
                    event_identifier = event_config.get('event_name') or event_config.get('name') or f"Event #{i+1}"
                    return {
                        'success': False,
                        'message': f"Failed to create event '{event_identifier}': {str(e)}",
                        'errors': [f"Event creation error: {str(e)}"],
                        'rollback_performed': True
                    }
            
            db.commit()
            
            result = {
                'success': True,
                'message': f"Successfully installed application '{app_config['app_name']}'",
                'app_id': new_app.app_id,
                'services_created': len(services),
                'events_created': len(events)
            }
            
            if deleted_subscriptions > 0:
                result['deleted_subscriptions'] = deleted_subscriptions
                result['warnings'] = [f"Deleted {deleted_subscriptions} existing subscriptions"]
            
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error installing application {application_key}: {e}", exc_info=True)
            
            # Provide more context about the error
            error_message = str(e)
            errors = []
            
            # Check if it's a KeyError and provide more context
            if isinstance(e, KeyError):
                error_message = f"Missing required field '{e.args[0]}' in application configuration"
                errors.append(error_message)
            elif isinstance(e, ValueError):
                error_message = str(e)
                errors.append(error_message)
            elif "service_name" in error_message or "'name'" in error_message:
                error_message = "Service configuration error: Each service must have a 'service_name' field"
                errors.append(error_message)
            elif "event_name" in error_message:
                error_message = "Event configuration error: Each event must have an 'event_name' field"
                errors.append(error_message)
            else:
                errors.append(f"Unexpected error: {error_message}")
            
            return {
                'success': False,
                'message': f"Failed to install application '{app_config.get('app_name', application_key)}': {error_message}",
                'errors': errors,
                'rollback_performed': True
            }
    
    def _service_row_fields(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """ApplicationService column values for one seed-JSON service.

        Shared by the global install and the tenant install so a service means
        the same thing whichever catalog it came from.
        """
        # Handle different field names between JSON and model
        # Combine request_config into service_config
        request_config = service_config.get('request_config', {})
        parameter_method = request_config.get('parameter_method', 'none')
        endpoint_template = service_config.get('endpoint_template', '') or service_config.get('endpoint_url', '')

        # Extract parameters from both 'parameters' field and parameter_schema
        parameters = []
        parameter_schema = service_config.get('parameter_schema', {})

        # Extract parameters directly from schema (unified approach)
        if parameter_method == 'url_pattern' and endpoint_template:
            import re
            # Find all {{param}} patterns in the URL
            url_params = re.findall(r'\{\{(\w+)\}\}', endpoint_template)
            schema_properties = parameter_schema.get('properties', {})

            for param_name in url_params:
                param_def = schema_properties.get(param_name, {})
                parameters.append({
                    'param_name': param_name,
                    'friendly_name': param_name.replace('_', ' ').title(),
                    'description': param_def.get('description', ''),
                    'data_type': param_def.get('type', 'string'),
                    'required': param_name in parameter_schema.get('required', []),
                    'pattern': param_def.get('pattern'),
                    'example': param_def.get('example'),
                    'ui_control': 'text'
                })
        elif parameter_schema.get('properties'):
            # For all other service types, extract all properties from schema
            schema_properties = parameter_schema.get('properties', {})
            required_fields = parameter_schema.get('required', [])

            for param_name, param_def in schema_properties.items():
                # Determine UI control based on type and format
                ui_control = 'text'
                data_type = param_def.get('type', 'string')

                if data_type == 'boolean':
                    ui_control = 'checkbox'
                elif data_type == 'number' or data_type == 'integer':
                    ui_control = 'number'
                elif param_def.get('format') == 'date':
                    ui_control = 'date'
                elif param_def.get('format') == 'email':
                    ui_control = 'email'
                elif param_def.get('enum'):
                    ui_control = 'select'
                elif data_type == 'array':
                    ui_control = 'array'
                elif data_type == 'object':
                    ui_control = 'object'
                elif param_def.get('format') == 'sql' or param_name == 'sql':
                    ui_control = 'textarea'

                parameters.append({
                    'param_name': param_name,
                    'friendly_name': param_name.replace('_', ' ').title(),
                    'description': param_def.get('description', ''),
                    'data_type': data_type,
                    'required': param_name in required_fields,
                    'pattern': param_def.get('pattern'),
                    'example': param_def.get('example'),
                    'ui_control': ui_control,
                    'enum_values': param_def.get('enum'),
                    'format': param_def.get('format'),
                    'default': param_def.get('default'),
                    'min_value': param_def.get('minimum'),
                    'max_value': param_def.get('maximum'),
                })

        # Keep the full request_config including headers_template
        combined_service_config = {
            'endpoint_template': endpoint_template,
            'request_config': request_config,  # Keep the full config including headers_template
            'parameter_schema': service_config.get('parameter_schema', {}),
            'parameter_method': parameter_method,
            'parameters': parameters,  # Include extracted parameters
            'url_pattern': endpoint_template if parameter_method == 'url_pattern' else None
        }

        # Map sync_mode to is_async
        sync_mode = service_config.get('sync_mode', 'synchronous')
        is_async = sync_mode == 'asynchronous'

        # Only accept 'service_name' field - reject old format
        service_name = service_config.get('service_name')
        if not service_name:
            raise ValueError(f"Service missing required 'service_name' field: {service_config}")

        return dict(
            service_name=service_name,
            display_name=service_config.get('display_name', service_name),
            service_type=service_config.get('service_type', 'api_call'),
            description=service_config.get('description'),
            service_config=serialize_json_field(combined_service_config),  # Main config field
            # Legacy fields removed - all configuration is in service_config
            response_config=serialize_json_field(service_config.get('response_config', {})),
            input_schema=serialize_json_field(service_config.get('parameter_schema', {})),
            output_schema=serialize_json_field(service_config.get('output_schema', {})),
            sample_input=serialize_json_field(service_config.get('sample_input', {})),
            sample_output=serialize_json_field(service_config.get('sample_output', {})),
            is_async=is_async,  # Boolean field
            timeout_seconds=service_config.get('timeout_seconds', 30)
        )

    def _event_row_fields(self, event_config: Dict[str, Any]) -> Dict[str, Any]:
        """ApplicationEvent column values for one seed-JSON event (see above)."""
        # Handle both 'event_name' and 'name' fields for backward compatibility
        event_name = event_config.get('event_name') or event_config.get('name')
        if not event_name:
            raise ValueError(f"Event missing required 'event_name' field: {event_config}")

        # Create unified output_schema for ALL event types
        output_schema = self._create_unified_event_schema(event_config)

        return dict(
            event_name=event_name,
            display_name=event_config.get('display_name', event_name),
            event_type=event_config.get('event_type', event_config.get('trigger_type', 'manual')),
            description=event_config.get('description'),
            event_configuration=serialize_json_field(event_config.get('event_configuration', event_config.get('trigger_config', event_config.get('webhook_config', {})))),
            extraction_configuration=None,  # DEPRECATED: Now using unified output_schema
            output_schema=serialize_json_field(output_schema),
            sample_payload=serialize_json_field(event_config.get('sample_payload')),
            api_endpoint=event_config.get('api_endpoint'),
            sync_mode=event_config.get('sync_mode', 'asynchronous'),
            is_active=True
        )

    # ------------------------------------------------------------------
    # Tenant-scoped seed applications
    #
    # A global seed application is one JSON file every tenant shares, so only
    # an instance admin may write one. A tenant's own connector lives in
    # ``seed-applications/tenants/<tenant_id>/<key>.json``: only that tenant
    # sees it, and installing it creates an application with
    # ``app_scope='tenant'`` owned by that tenant. The tenant folder is a
    # sub-directory, so the global discovery glob ("*.json" in the top folder)
    # never picks a tenant file up.
    # ------------------------------------------------------------------

    _TENANT_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
    _SEED_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,99}$")

    def _tenant_dir(self, tenant_id: str) -> str:
        tenant_id = str(tenant_id or "")
        if not self._TENANT_ID_RE.match(tenant_id):
            raise ValueError("A valid tenant is required for a tenant seed application")
        return os.path.join(self._applications_path, "tenants", tenant_id)

    def _tenant_file(self, tenant_id: str, app_key: str) -> str:
        if not self._SEED_KEY_RE.match(str(app_key or "")):
            raise ValueError(
                "Seed application key must be lowercase letters, digits and underscores "
                "(2-100 characters, starting with a letter or digit)"
            )
        return os.path.join(self._tenant_dir(tenant_id), f"{app_key}.json")

    def list_tenant_applications(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Every seed application the tenant owns (full JSON, newest edit first)."""
        folder = self._tenant_dir(tenant_id)
        if not os.path.isdir(folder):
            return []
        result = []
        for path in glob.glob(os.path.join(folder, "*.json")):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("key") and isinstance(data.get("application"), dict):
                    result.append(data)
            except Exception as e:
                logger.error(f"Error loading tenant seed application {path}: {e}")
        result.sort(key=lambda d: (d.get("metadata") or {}).get("last_modified") or "", reverse=True)
        return result

    def get_tenant_application(self, tenant_id: str, app_key: str) -> Optional[Dict[str, Any]]:
        path = self._tenant_file(tenant_id, app_key)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

    def validate_seed_document(self, seed: Dict[str, Any]) -> Dict[str, Any]:
        """The one validation every seed write runs (global or tenant)."""
        if not isinstance(seed, dict):
            return {"valid": False, "errors": ["Seed application must be a JSON object"], "warnings": []}
        result = self.schema_validator.validate_seed_application(seed)
        errors = list(result.get("errors") or [])
        # Field-level checks the installer would otherwise only hit half way
        # through a write (it builds every row before touching the database).
        for i, svc in enumerate(seed.get("services") or []):
            try:
                self._service_row_fields(svc if isinstance(svc, dict) else {})
            except Exception as e:
                errors.append(f"services[{i}]: {e}")
            if isinstance(svc, dict) and "input_schema" in svc and "parameter_schema" not in svc:
                errors.append(f"services[{i}]: use 'parameter_schema', not 'input_schema'")
        for i, ev in enumerate(seed.get("events") or []):
            if not isinstance(ev, dict) or not (ev.get("event_name") or ev.get("name")):
                errors.append(f"events[{i}]: missing required 'event_name'")
        warnings = list(result.get("warnings") or [])
        app = seed.get("application") if isinstance(seed.get("application"), dict) else {}
        auth_config = app.get("auth_config") if isinstance(app.get("auth_config"), dict) else {}
        if (app.get("app_type") == "api" and app.get("auth_type") not in (None, "none")
                and not auth_config.get("test_endpoint")):
            warnings.append(
                "Optional: application.auth_config.test_endpoint is not set. If the API has a cheap "
                "read-only GET that needs the credential (e.g. '/users/me'), set it so 'Test Connection' "
                "checks the credential; otherwise the test calls the bare base_url. Safe to leave unset "
                "when no such endpoint exists."
            )
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def save_tenant_application(self, tenant_id: str, seed: Dict[str, Any],
                                user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create or replace a tenant seed application from its full JSON.

        Validated first; nothing is written when it is invalid. A key that a
        GLOBAL seed application already uses is refused — two connectors with
        one key would make every key-based lookup ambiguous.
        """
        seed = json.loads(json.dumps(seed or {}))  # private copy
        seed.pop("_validation", None)
        key = str(seed.get("key") or "")
        path = self._tenant_file(tenant_id, key)
        if key in self.discover_applications():
            return {"success": False, "key": key,
                    "errors": [f"'{key}' is a global seed application key; choose another key"]}
        validation = self.validate_seed_document(seed)
        if not validation["valid"]:
            return {"success": False, "key": key, **validation}

        existing = None
        if os.path.exists(path):
            with open(path, "r") as f:
                existing = json.load(f)
        now = datetime.now().isoformat()
        meta = dict(seed.get("metadata") or {})
        meta.update({
            "scope": "tenant",
            "tenant_id": str(tenant_id),
            "created_at": ((existing or {}).get("metadata") or {}).get("created_at") or meta.get("created_at") or now,
            "created_by": ((existing or {}).get("metadata") or {}).get("created_by") or user_id,
            "last_modified": now,
            "last_modified_by": user_id,
        })
        seed["metadata"] = meta
        seed.setdefault("services", [])
        seed.setdefault("events", [])

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(seed, f, indent=2)
        os.replace(tmp, path)
        return {"success": True, "key": key, "created": existing is None,
                "warnings": validation["warnings"], "seed": seed}

    def delete_tenant_application(self, tenant_id: str, app_key: str) -> bool:
        path = self._tenant_file(tenant_id, app_key)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True

    def find_tenant_installation(self, db: Session, tenant_id: str, app_key: str) -> Optional[Application]:
        return db.query(Application).filter(
            Application.seed_key == app_key,
            Application.app_scope == "tenant",
            Application.tenant_id_owner == str(tenant_id),
        ).first()

    def install_tenant_application(self, db: Session, tenant_id: str, app_key: str,
                                   user_id: Optional[str] = None) -> Dict[str, Any]:
        """Install a tenant seed application, or bring its installation up to date.

        Unlike the global reinstall this is NON-destructive: the application,
        its services and its events keep their ids (flows reference them) and
        subscriptions are never touched. Services/events missing from the JSON
        are deactivated rather than deleted, for the same reason.
        """
        seed = self.get_tenant_application(tenant_id, app_key)
        if not seed:
            return {"success": False, "message": f"Tenant seed application '{app_key}' not found"}
        validation = self.validate_seed_document(seed)
        if not validation["valid"]:
            return {"success": False, "message": "Seed application is invalid", **validation}

        app_config = seed["application"]
        auth_type = app_config.get("auth_type", "none")
        auth_config = dict(app_config.get("auth_config") or {})
        if "default_custom_params" in app_config:
            auth_config["default_custom_params"] = app_config["default_custom_params"]
        if auth_type == "oauth2":
            if not (auth_config.get("authorization_url") or auth_config.get("auth_url")) or not auth_config.get("token_url"):
                return {"success": False,
                        "message": "OAuth2 applications need 'authorization_url' and 'token_url' in auth_config"}

        try:
            service_rows = [self._service_row_fields(s) for s in seed.get("services") or []]
            event_rows = [self._event_row_fields(e) for e in seed.get("events") or []]
        except Exception as e:
            return {"success": False, "message": str(e), "errors": [str(e)]}

        app_fields = dict(
            app_name=app_config["app_name"],
            app_type=app_config.get("app_type", "api"),
            description=app_config.get("description"),
            icon_url=app_config.get("icon_url"),
            category=app_config.get("category", "Other"),
            base_url=app_config.get("base_url"),
            auth_type=auth_type,
            auth_config=serialize_json_field(auth_config),
            webhook_config=serialize_json_field(app_config["webhook_config"]) if isinstance(app_config.get("webhook_config"), dict) else None,
            version=app_config.get("version", "1.0.0"),
        )
        try:
            app = self.find_tenant_installation(db, tenant_id, app_key)
            created = app is None
            if created:
                app = Application(
                    seed_key=app_key, app_scope="tenant", tenant_id_owner=str(tenant_id),
                    is_seed_app=True, instance_number=1, total_instances=0,
                    created_by=user_id, **app_fields,
                )
                db.add(app)
                db.flush()
            else:
                for k, v in app_fields.items():
                    setattr(app, k, v)

            counts = self._sync_services_and_events(db, app, service_rows, event_rows)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error installing tenant seed application {app_key}: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to install '{app_key}': {e}", "errors": [str(e)]}

        return {
            "success": True,
            "message": f"{'Installed' if created else 'Updated'} tenant application '{app_config['app_name']}'",
            "app_id": str(app.app_id),
            "app_key": app_key,
            "created": created,
            "warnings": validation["warnings"],
            **counts,
        }

    def _sync_services_and_events(self, db: Session, app: Application,
                                  service_rows: List[Dict[str, Any]],
                                  event_rows: List[Dict[str, Any]]) -> Dict[str, int]:
        """Bring an installed application's services and events IN PLACE to a seed.

        Matching rows (by name) are updated and keep their ids — flows reference
        them; new ones are added; rows the seed no longer has are deactivated,
        never deleted. Subscriptions are not touched. Does not commit.
        Shared by the tenant install and the global soft update.
        """
        counts = {"services_created": 0, "services_updated": 0, "services_deactivated": 0,
                  "events_created": 0, "events_updated": 0, "events_deactivated": 0}
        existing_services = {s.service_name: s for s in db.query(ApplicationService).filter(
            ApplicationService.app_id == app.app_id).all()}
        for row in service_rows:
            current = existing_services.pop(row["service_name"], None)
            if current is None:
                db.add(ApplicationService(app_id=app.app_id, is_active=True, **row))
                counts["services_created"] += 1
            else:
                for k, v in row.items():
                    setattr(current, k, v)
                current.is_active = True
                counts["services_updated"] += 1
        for leftover in existing_services.values():
            if leftover.is_active:
                leftover.is_active = False
                counts["services_deactivated"] += 1

        existing_events = {e.event_name: e for e in db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == app.app_id).all()}
        for row in event_rows:
            current = existing_events.pop(row["event_name"], None)
            if current is None:
                db.add(ApplicationEvent(app_id=app.app_id, **row))
                counts["events_created"] += 1
            else:
                for k, v in row.items():
                    setattr(current, k, v)
                counts["events_updated"] += 1
        for leftover in existing_events.values():
            if leftover.is_active:
                leftover.is_active = False
                counts["events_deactivated"] += 1
        return counts

    def soft_update_global_application(self, db: Session, application_key: str) -> Dict[str, Any]:
        """Soft-update an installed GLOBAL application to its seed's current version.

        The same in-place update a tenant install does, through the request's
        own session — so it works on every database IOFlow runs on (the older
        ``soft_update_manager_simple`` opened a SQLite file and failed on
        PostgreSQL). Keeps app/service/event ids, subscriptions and tokens; the
        auth configuration follows the seed except credentials the platform
        injected at install time (``default_credentials``), which are kept.
        """
        seed = self.discover_applications().get(application_key)
        if not seed:
            return {"success": False, "message": f"Seed application '{application_key}' not found"}
        app_config = seed.get("application") or {}
        app = db.query(Application).filter(
            Application.seed_key == application_key, Application.app_scope != "tenant").first()
        if app is None:
            app = db.query(Application).filter(
                Application.app_name == app_config.get("app_name"),
                Application.app_scope != "tenant").first()
        if app is None:
            return {"success": False, "message": f"Application '{application_key}' is not installed"}
        try:
            service_rows = [self._service_row_fields(x) for x in seed.get("services") or []]
            event_rows = [self._event_row_fields(x) for x in seed.get("events") or []]
        except Exception as e:
            return {"success": False, "message": str(e), "errors": [str(e)]}

        previous_version = app.version
        auth_config = dict(app_config.get("auth_config") or {})
        if "default_custom_params" in app_config:
            auth_config["default_custom_params"] = app_config["default_custom_params"]
        current_auth = deserialize_json_field(app.auth_config) or {}
        if isinstance(current_auth, dict) and current_auth.get("default_credentials"):
            auth_config["default_credentials"] = current_auth["default_credentials"]
        try:
            subscriptions = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
                ApplicationSubscription.app_id == app.app_id).scalar() or 0
            app.version = app_config.get("version", previous_version)
            for field in ("description", "icon_url", "base_url", "category"):
                if field in app_config:
                    setattr(app, field, app_config.get(field))
            if app_config.get("auth_type"):
                app.auth_type = app_config["auth_type"]
            app.auth_config = serialize_json_field(auth_config)
            if isinstance(app_config.get("webhook_config"), dict):
                app.webhook_config = serialize_json_field(app_config["webhook_config"])
            if not app.seed_key:
                app.seed_key = application_key
            counts = self._sync_services_and_events(db, app, service_rows, event_rows)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error soft-updating seed application {application_key}: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to update '{application_key}': {e}", "errors": [str(e)]}
        return {"success": True, "app_id": str(app.app_id), "previous_version": previous_version,
                "new_version": app.version, "subscriptions_preserved": subscriptions, **counts}

    def uninstall_tenant_application(self, db: Session, tenant_id: str, app_key: str) -> Dict[str, Any]:
        """Remove a tenant installation. Refused while it still has subscriptions."""
        app = self.find_tenant_installation(db, tenant_id, app_key)
        if app is None:
            return {"success": True, "removed": False}
        subs = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
            ApplicationSubscription.app_id == app.app_id).scalar() or 0
        if subs:
            return {"success": False, "removed": False,
                    "message": f"'{app_key}' still has {subs} subscription(s); disconnect them first"}
        db.query(OAuthState).filter(OAuthState.app_id == app.app_id).delete()
        db.query(ApplicationEvent).filter(ApplicationEvent.app_id == app.app_id).delete()
        db.query(ApplicationService).filter(ApplicationService.app_id == app.app_id).delete()
        db.delete(app)
        db.commit()
        return {"success": True, "removed": True}

    def refresh_cache(self):
        """Clear the applications cache to force re-discovery"""
        self._applications_cache = None
        logger.info("Cleared seed applications cache")

    def get_single_application(self, app_key: str) -> Optional[Dict[str, Any]]:
        """Load a single seed application directly from its JSON file, bypassing full discovery.

        This is much faster than discover_applications() when you only need one app,
        especially during batch operations like adding multiple services.
        """
        json_file = os.path.join(self._applications_path, f"{app_key}.json")
        if not os.path.exists(json_file):
            return None
        try:
            with open(json_file, 'r') as f:
                app_data = json.load(f)
            if 'key' not in app_data or 'application' not in app_data:
                return None
            return app_data
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading single seed application {app_key}: {e}")
            return None

    def update_cache_entry(self, app_key: str, app_data: Dict[str, Any]):
        """Update a single entry in the cache without re-reading all files.

        If the cache is populated, updates just this one entry.
        If the cache is None, does nothing (next full discovery will pick it up).
        """
        if self._applications_cache is not None:
            self._applications_cache[app_key] = app_data
            logger.debug(f"Updated cache entry for {app_key}")
        else:
            # Cache hasn't been populated yet, no need to update
            logger.debug(f"Cache not populated, skipping update for {app_key}")
    
    def delete_seed_application(self, application_key: str) -> Dict[str, Any]:
        """Delete a seed application JSON file"""
        try:
            # Discover current applications
            applications = self.discover_applications()
            
            if application_key not in applications:
                return {
                    'success': False,
                    'message': f"Seed application '{application_key}' not found"
                }
            
            # Get the file path
            json_file = os.path.join(self._applications_path, f"{application_key}.json")
            
            # Check if file exists
            if not os.path.exists(json_file):
                return {
                    'success': False,
                    'message': f"Seed application file not found: {json_file}"
                }
            
            # Delete the file
            os.remove(json_file)
            logger.info(f"Deleted seed application file: {json_file}")
            
            # Clear cache to reflect changes
            self.refresh_cache()
            
            return {
                'success': True,
                'message': f"Successfully deleted seed application '{application_key}'",
                'deleted_file': json_file
            }
            
        except Exception as e:
            logger.error(f"Error deleting seed application {application_key}: {e}")
            return {
                'success': False,
                'message': f"Failed to delete seed application: {str(e)}"
            }


    def _create_unified_event_schema(self, event_config: dict) -> dict:
        """Create unified output_schema for ALL event types."""
        # Start with provided output_schema or create empty structure
        output_schema = event_config.get('output_schema', {
            'type': 'object',
            'properties': {},
            'required': []
        })
        
        # Ensure basic structure
        if 'type' not in output_schema:
            output_schema['type'] = 'object'
        if 'properties' not in output_schema:
            output_schema['properties'] = {}
        if 'required' not in output_schema:
            output_schema['required'] = []
        
        # Handle legacy extraction_configuration
        extraction_config = event_config.get('extraction_configuration', {})
        if extraction_config:
            mappings = {}
            
            # Extract mappings from various legacy formats
            if 'parameter_mappings' in extraction_config:
                mappings.update(extraction_config['parameter_mappings'])
            elif 'mappings' in extraction_config:
                mappings.update(extraction_config['mappings'])
            elif 'path_mappings' in extraction_config:
                mappings.update(extraction_config['path_mappings'])
            elif 'fields' in extraction_config:
                # Convert field-based mappings to path mappings
                for field in extraction_config['fields']:
                    if 'path' in field and 'name' in field:
                        mappings[field['name']] = field['path']
            
            # Add parameter extraction to schema if we have mappings
            if mappings:
                output_schema['parameter_extraction'] = {
                    'method': extraction_config.get('method', 'json_path'),
                    'mappings': mappings
                }
                
                # Also add to properties with mapping info
                for param_name, mapping_path in mappings.items():
                    if param_name not in output_schema['properties']:
                        output_schema['properties'][param_name] = {
                            'type': 'string',
                            'description': f'Parameter extracted from {mapping_path}',
                            'mapping': mapping_path
                        }
        
        # Handle webhook events specifically 
        event_type = event_config.get('event_type', event_config.get('trigger_type', 'manual'))
        if event_type == 'webhook' and 'parameter_extraction' not in output_schema:
            # Ensure webhook events have parameter extraction structure
            output_schema.setdefault('parameter_extraction', {
                'method': 'json_path',
                'mappings': {}
            })
        
        return output_schema
    
    def is_flow_based_application(self, app_data: Dict[str, Any]) -> bool:
        """Check if an application is flow-based"""
        app_config = app_data.get('application', {})
        metadata = app_data.get('metadata', {})
        
        # Check for flow-based indicators
        return (
            app_config.get('flow_based', False) or
            metadata.get('generated_from_flow', False) or
            'source_flow_id' in app_config or
            'flow_id' in metadata
        )
    
    def get_flow_based_applications(self, db: Session, tenant_id: str = None) -> List[Dict[str, Any]]:
        """Get all flow-based applications"""
        all_apps = self.get_seed_applications(db, tenant_id=tenant_id)
        applications_data = self.discover_applications()

        flow_based_apps = []
        for app in all_apps:
            app_data = applications_data.get(app.key, {})
            if self.is_flow_based_application(app_data):
                flow_based_apps.append({
                    **app.__dict__,
                    'metadata': app_data.get('metadata', {}),
                    'flow_info': self._extract_flow_info(app_data)
                })

        return flow_based_apps

    def get_traditional_applications(self, db: Session, tenant_id: str = None) -> List[Dict[str, Any]]:
        """Get all traditional (non-flow-based) applications"""
        all_apps = self.get_seed_applications(db, tenant_id=tenant_id)
        applications_data = self.discover_applications()

        traditional_apps = []
        for app in all_apps:
            app_data = applications_data.get(app.key, {})
            if not self.is_flow_based_application(app_data):
                traditional_apps.append(app.__dict__)

        return traditional_apps
    
    def _extract_flow_info(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract flow-related information from application data"""
        app_config = app_data.get('application', {})
        metadata = app_data.get('metadata', {})
        
        flow_info = {
            'is_flow_based': True,
            'source_flow_id': app_config.get('source_flow_id') or metadata.get('flow_id'),
            'flow_name': metadata.get('flow_name'),
            'generated_at': metadata.get('generated_at'),
            'complexity_score': app_config.get('complexity_score') or metadata.get('complexity_score'),
            'estimated_execution_time': app_config.get('estimated_execution_time') or metadata.get('estimated_execution_time'),
            'transformations_count': metadata.get('transformations_count'),
            'dependencies': metadata.get('dependencies', []),
            'auto_generated': True
        }
        
        return flow_info
    
    def validate_flow_based_application(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a flow-based application"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'flow_specific_issues': []
        }
        
        # Basic validation first
        basic_validation = self.schema_validator.validate_seed_application(app_data)
        validation_result['valid'] = basic_validation['valid']
        validation_result['errors'].extend(basic_validation.get('errors', []))
        validation_result['warnings'].extend(basic_validation.get('warnings', []))
        
        if not self.is_flow_based_application(app_data):
            validation_result['warnings'].append("Application is not marked as flow-based")
            return validation_result
        
        # Flow-specific validations
        app_config = app_data.get('application', {})
        metadata = app_data.get('metadata', {})
        
        # Check for required flow metadata
        if not app_config.get('source_flow_id') and not metadata.get('flow_id'):
            validation_result['flow_specific_issues'].append("Missing source flow ID")
        
        # Check for flow-based services
        services = app_data.get('services', [])
        flow_based_services = [s for s in services if s.get('flow_based', False)]
        if not flow_based_services:
            validation_result['warnings'].append("No flow-based services found")
        
        # Check for execution endpoints
        for service in services:
            if service.get('flow_based', False):
                endpoint = service.get('endpoint_url', '')
                if not ('/execute' in endpoint or '/transform' in endpoint):
                    validation_result['flow_specific_issues'].append(
                        f"Flow-based service '{service.get('service_name')}' missing execution endpoint"
                    )
        
        # Check metadata completeness
        expected_metadata = ['generated_from_flow', 'flow_name', 'generated_at']
        missing_metadata = [field for field in expected_metadata if not metadata.get(field)]
        if missing_metadata:
            validation_result['warnings'].append(f"Missing metadata fields: {', '.join(missing_metadata)}")
        
        # If there are flow-specific issues, mark as invalid
        if validation_result['flow_specific_issues']:
            validation_result['valid'] = False
            validation_result['errors'].extend(validation_result['flow_specific_issues'])
        
        return validation_result
    
    def get_application_execution_info(self, app_key: str) -> Optional[Dict[str, Any]]:
        """Get execution information for an application"""
        applications_data = self.discover_applications()
        app_data = applications_data.get(app_key)
        
        if not app_data:
            return None
        
        if not self.is_flow_based_application(app_data):
            return {
                'is_flow_based': False,
                'execution_type': 'traditional',
                'services': len(app_data.get('services', [])),
                'events': len(app_data.get('events', []))
            }
        
        metadata = app_data.get('metadata', {})
        app_config = app_data.get('application', {})
        
        return {
            'is_flow_based': True,
            'execution_type': 'flow',
            'source_flow_id': app_config.get('source_flow_id') or metadata.get('flow_id'),
            'complexity_score': app_config.get('complexity_score') or metadata.get('complexity_score', 0),
            'estimated_execution_time': app_config.get('estimated_execution_time') or metadata.get('estimated_execution_time', 30),
            'dependencies': metadata.get('dependencies', []),
            'services': len(app_data.get('services', [])),
            'events': len(app_data.get('events', [])),
            'transformations_count': metadata.get('transformations_count', 0)
        }
    
    def sync_flow_based_application(self, db: Session, app_key: str, 
                                  updated_flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync a flow-based application when its source flow changes"""
        try:
            # This method would be called by the FlowPublisher when auto-update is enabled
            # For now, we'll just validate and log
            
            applications_data = self.discover_applications()
            app_data = applications_data.get(app_key)
            
            if not app_data:
                return {'success': False, 'error': f'Application {app_key} not found'}
            
            if not self.is_flow_based_application(app_data):
                return {'success': False, 'error': f'Application {app_key} is not flow-based'}
            
            # Here we would typically trigger the FlowPublisher to update the application
            # For now, just return success
            logger.info(f"Flow-based application {app_key} sync requested")
            
            return {
                'success': True,
                'message': f'Flow-based application {app_key} sync completed',
                'sync_required': True
            }
            
        except Exception as e:
            logger.error(f"Error syncing flow-based application {app_key}: {e}")
            return {'success': False, 'error': str(e)}


# Create singleton instance
json_seed_manager = JsonSeedManager()
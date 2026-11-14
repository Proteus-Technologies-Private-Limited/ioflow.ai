"""
API endpoints for seed application management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any

from db.database import get_db
from db.models import User, UserRole
from db.application_models import Application, ApplicationSubscription
from schemas.seed_schemas import (
    SeedApplicationList,
    SeedApplicationInfo,
    InstallApplicationRequest,
    InstallApplicationResponse,
    ApplicationInstallationWarning,
    InstallationStatus,
    CreateSeedApplicationRequest,
    UpdateSeedApplicationRequest,
    ImportSeedApplicationRequest,
    SeedApplicationResponse,
    ValidateSeedApplicationResponse
)
from services.json_seed_manager import json_seed_manager as seed_manager
from .auth import get_current_user
import logging
import json
from pathlib import Path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_server'))
from validators.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

# Initialize the schema validator
schema_validator = SchemaValidator()

router = APIRouter(
    prefix="/api/v1/seed-applications",
    tags=["seed-applications"],
    responses={404: {"description": "Not found"}},
)


@router.post("/refresh-cache")
async def refresh_seed_cache(
    current_user: User = Depends(get_current_user)
):
    """
    Refresh the seed applications cache to pick up any JSON file changes
    
    **Note**: Only admins can refresh the cache
    """
    # Check if user is admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only admins can refresh the seed cache"
        )
    
    seed_manager.refresh_cache()
    return {"success": True, "message": "Seed applications cache refreshed successfully"}


@router.get("/", response_model=SeedApplicationList)
async def list_seed_applications(
    search: str = None,
    sort_by: str = "last_modified",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all available seed applications with search and sort capabilities
    
    Parameters:
    - search: Search query for filtering by name, category, or description
    - sort_by: Field to sort by (app_name, category, last_modified, created_at, status)
    - sort_order: Sort order (asc or desc)
    
    Returns:
    - List of seed applications with installation status
    - Shows which applications are installed, not installed, or have updates
    """
    try:
        applications = seed_manager.get_seed_applications(db, tenant_id=str(current_user.tenant_id))

        # Add validation status to each application
        applications_data = seed_manager.discover_applications()
        for app in applications:
            if app.key in applications_data:
                app_data = applications_data[app.key]
                validation_info = app_data.get('_validation', {})
                # Add validation info to the response
                app.validation_status = {
                    'valid': validation_info.get('valid', True),
                    'errors': validation_info.get('errors', []),
                    'warnings': validation_info.get('warnings', [])
                }
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            applications = [
                app for app in applications
                if (search_lower in app.name.lower() or
                    (app.category and search_lower in app.category.lower()) or
                    (app.description and search_lower in app.description.lower()))
            ]
        
        # Apply sorting
        reverse_order = sort_order.lower() == "desc"
        
        if sort_by == "app_name":
            applications.sort(key=lambda x: x.name.lower(), reverse=reverse_order)
        elif sort_by == "category":
            applications.sort(key=lambda x: (x.category or "").lower(), reverse=reverse_order)
        elif sort_by == "status":
            applications.sort(key=lambda x: x.status.value, reverse=reverse_order)
        elif sort_by == "installed_at":
            applications.sort(key=lambda x: x.installed_at or "", reverse=reverse_order)
        elif sort_by == "created_at":
            applications.sort(key=lambda x: x.created_at or "", reverse=reverse_order)
        else:  # Default to last_modified
            applications.sort(key=lambda x: x.last_modified or x.created_at or "", reverse=reverse_order)
        
        installed_count = sum(1 for app in applications if app.status != InstallationStatus.NOT_INSTALLED)
        
        return SeedApplicationList(
            applications=applications,
            total=len(applications),
            installed_count=installed_count
        )
    except Exception as e:
        logger.error(f"Error listing seed applications: {e}")
        raise HTTPException(status_code=500, detail="Failed to list seed applications")


@router.get("/{application_key}", response_model=SeedApplicationInfo)
async def get_seed_application(
    application_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific seed application
    """
    applications = seed_manager.get_seed_applications(db, tenant_id=str(current_user.tenant_id))

    for app in applications:
        if app.key == application_key:
            return app

    raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")


@router.get("/{application_key}/installation-warning", response_model=Optional[ApplicationInstallationWarning])
async def get_installation_warning(
    application_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get installation warning if application is already installed
    
    Returns warning with subscription count that will be deleted
    """
    warning = seed_manager.get_installation_warning(db, application_key)
    
    if warning:
        logger.info(f"Installation warning data: {warning}")
        # Ensure application_name is present
        if 'application_name' not in warning and 'app_name' in warning:
            warning['application_name'] = warning['app_name']
        return ApplicationInstallationWarning(**warning)
    
    return None


@router.get("/guides/application")
async def get_seed_application_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for creating seed applications with all valid values and structure.

    IMPORTANT: Always call this FIRST before creating any seed application to understand:
    - Valid app_type values
    - Valid category values
    - Valid auth_type values
    - Required fields and structure
    """
    return {
        "purpose": "Guide for creating IOFlow seed applications",
        "structure": {
            "key": {
                "description": "Unique application identifier",
                "pattern": "^[a-z0-9_]+$",
                "example": "shopify",
                "rules": "lowercase letters, numbers, and underscores only"
            },
            "application": {
                "required_fields": ["app_name", "app_type", "category", "auth_type", "version"],
                "fields": {
                    "app_name": {
                        "type": "string",
                        "description": "Human-readable application name",
                        "example": "Shopify"
                    },
                    "app_type": {
                        "type": "string",
                        "enum": ["database", "email", "api", "file_system", "memory", "flow", "ai_agent", "ssh", "mqtt"],
                        "description": "Type of application",
                        "example": "api"
                    },
                    "app_scope": {
                        "type": "string",
                        "enum": ["global", "tenant", "user"],
                        "description": "Scope of application availability",
                        "default": "global"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["AI/ML", "Communication", "Productivity", "Analytics", "Database", "Integration", "Development", "API Platform", "Email", "Messaging", "Automation", "Data Extraction", "Other"],
                        "description": "Application category",
                        "example": "Integration"
                    },
                    "auth_type": {
                        "type": "string",
                        "enum": ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"],
                        "description": "Authentication method",
                        "example": "api_key"
                    },
                    "version": {
                        "type": "string",
                        "pattern": "^\\d+\\.\\d+\\.\\d+$",
                        "description": "Semantic version",
                        "example": "1.0.0"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief application description",
                        "example": "E-commerce platform integration"
                    },
                    "base_url": {
                        "type": "string",
                        "description": "Base API URL (optional)",
                        "example": "https://api.shopify.com"
                    },
                    "auth_config": {
                        "type": "object",
                        "description": "Authentication configuration (structure varies by auth_type)",
                        "test_endpoint": {
                            "type": "string",
                            "description": "Path (relative to base_url) that 'Test Connection' calls with the user's credential. Optional but recommended for authenticated APIs: a cheap read-only GET that requires the credential, e.g. '/users/me' or '/v1/account'. Without it the test calls the bare base_url, which often returns 404 even for a valid credential. Only use an endpoint the API documents; if none fits, omit it.",
                            "example": "/users/me"
                        },
                        "required_by_auth_type": {
                            "oauth2": {
                                "required_fields": ["authorization_url", "token_url"],
                                "example": {
                                    "authorization_url": "https://example.com/oauth/authorize",
                                    "token_url": "https://example.com/oauth/token",
                                    "scopes": ["read", "write"]
                                }
                            },
                            "api_key": {
                                "optional_fields": ["header_name", "header_prefix", "query_param", "test_endpoint"],
                                "example": {"header_name": "X-API-Key", "header_prefix": "", "test_endpoint": "/v1/me"}
                            },
                            "basic": {
                                "example": {}
                            },
                            "none": {
                                "example": {}
                            }
                        }
                    }
                }
            }
        },
        "important_notes": [
            "CRITICAL: app_type must be 'api' NOT 'api_service'",
            "Always use lowercase with underscores for keys",
            "Version must follow semantic versioning (e.g., 1.0.0)",
            "CRITICAL: For OAuth2, auth_config MUST include 'authorization_url' and 'token_url'",
            "For OAuth2, use 'authorization_url' NOT 'auth_url'",
            "Missing required auth_config fields will cause validation errors",
            "Optional: set auth_config.test_endpoint (a documented read-only GET that needs the credential) when the API has one, so 'Test Connection' gives a real answer; omit it if none exists"
        ],
        "examples": {
            "api_key_example": {
                "app_key": "shopify",
                "app_name": "Shopify",
                "app_type": "api",
                "category": "Integration",
                "description": "E-commerce platform for online stores",
                "version": "1.0.0",
                "auth_type": "api_key",
                "auth_config": {"header_name": "X-Shopify-Access-Token", "header_prefix": "", "test_endpoint": "/admin/api/2024-01/shop.json"},
                "base_url": "https://api.shopify.com"
            },
            "oauth2_example": {
                "app_key": "github",
                "app_name": "GitHub",
                "app_type": "api",
                "category": "Development",
                "description": "Code hosting platform",
                "version": "1.0.0",
                "auth_type": "oauth2",
                "auth_config": {
                    "authorization_url": "https://github.com/login/oauth/authorize",
                    "token_url": "https://github.com/login/oauth/access_token",
                    "scopes": ["repo", "user"],
                    "test_endpoint": "/user"
                },
                "base_url": "https://api.github.com"
            }
        }
    }


@router.get("/guides/service")
async def get_service_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for creating application services with all valid values.

    IMPORTANT: Always call this FIRST before adding services to understand:
    - Valid service_type values
    - Required fields per service type
    - Correct structure for request_config, response_config, parameter_schema
    """
    return {
        "purpose": "Guide for adding services to IOFlow applications",
        "service_types": {
            "valid_values": ["api_call", "webhook", "email_send", "database_query", "llm_api_call", "mcp_call", "smtp_send", "pop3_receive", "imap_receive", "file_operation", "ai_agent_execute", "graphql", "ssh_command"],
            "most_common": "api_call"
        },
        "required_fields": ["service_name", "display_name", "description", "service_type"],
        "fields": {
            "service_name": {
                "description": "Unique service identifier",
                "pattern": "^[a-zA-Z0-9_\\s]+$",
                "example": "create_product"
            },
            "display_name": {
                "description": "Human-readable service name",
                "example": "Create Product"
            },
            "description": {
                "description": "What the service does",
                "example": "Creates a new product in Shopify"
            },
            "service_type": {
                "description": "Type of service operation",
                "example": "api_call"
            },
            "endpoint_template": {
                "description": "API endpoint path (for api_call services, at service level NOT in service_config)",
                "example": "/admin/api/2024-01/products.json",
                "note": "Can include {{parameter}} placeholders"
            },
            "request_config": {
                "description": "HTTP request configuration (at service level for api_call)",
                "required_fields": ["method"],
                "structure": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "example": "POST"
                    },
                    "headers_template": {
                        "type": "object",
                        "example": {"Content-Type": "application/json"}
                    },
                    "body_template": {
                        "type": "object or string",
                        "example": {"product": {"title": "{{title}}"}}
                    }
                }
            },
            "response_config": {
                "description": "Response handling configuration",
                "structure": {
                    "success_check": {
                        "type": {
                            "description": "Type of success check",
                            "example": "status_code"
                        },
                        "success_status_codes": {
                            "description": "HTTP status codes considered successful",
                            "note": "IMPORTANT: Use 'success_status_codes' NOT 'value'",
                            "example": [200, 201]
                        }
                    }
                }
            },
            "parameter_schema": {
                "description": "JSON schema for service parameters (CRITICAL: use parameter_schema NOT input_schema)",
                "structure": {
                    "type": "object",
                    "properties": {
                        "param_name": {
                            "type": "string",
                            "description": "Parameter description",
                            "required": True
                        }
                    },
                    "required": ["param_name"]
                }
            }
        },
        "example": {
            "service_name": "create_product",
            "display_name": "Create Product",
            "description": "Creates a new product in Shopify",
            "service_type": "api_call",
            "endpoint_template": "/admin/api/2024-01/products.json",
            "request_config": {
                "method": "POST",
                "headers_template": {"Content-Type": "application/json"}
            },
            "response_config": {
                "success_check": {
                    "type": "status_code",
                    "success_status_codes": [200, 201]
                }
            },
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Product title"
                    },
                    "price": {
                        "type": "number",
                        "description": "Product price"
                    }
                },
                "required": ["title"]
            }
        },
        "important_notes": [
            "CRITICAL: Use 'parameter_schema' NOT 'input_schema'",
            "CRITICAL: In response_config, use 'success_status_codes' NOT 'value'",
            "For api_call services: endpoint_template and request_config go at SERVICE LEVEL, not in service_config",
            "For other service types: configuration goes in service_config object"
        ]
    }


@router.get("/guides/event")
async def get_event_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for creating application events/webhooks with all valid values.

    IMPORTANT: Always call this FIRST before adding events to understand:
    - Valid event_type values
    - Required fields per event type
    - Correct structure for event_configuration
    """
    return {
        "purpose": "Guide for adding events/webhooks to IOFlow applications",
        "event_types": {
            "valid_values": ["webhook", "schedule", "polling", "manual", "email", "form", "api_call", "mqtt"],
            "most_common": "webhook"
        },
        "required_fields": ["event_name", "display_name", "description", "event_type", "event_configuration"],
        "fields": {
            "event_name": {
                "description": "Unique event identifier",
                "pattern": "^[a-zA-Z0-9_\\s]+$",
                "example": "order_created"
            },
            "display_name": {
                "description": "Human-readable event name",
                "example": "Order Created"
            },
            "description": {
                "description": "When this event is triggered",
                "example": "Triggered when a new order is created in Shopify"
            },
            "event_type": {
                "description": "Type of event",
                "example": "webhook"
            },
            "event_configuration": {
                "description": "Event-specific configuration (varies by event_type)",
                "webhook": {
                    "webhook_method": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "headers": "object",
                    "authentication": "object"
                },
                "schedule": {
                    "schedule": "cron expression (required)",
                    "timezone": "string",
                    "example": "0 0 * * *"
                },
                "polling": {
                    "polling_service": "string (required) — the service_name of one of this application's services; the poller calls it",
                    "interval_seconds": "integer (min: 60, required)",
                    "polling_parameters": "object — fixed arguments for that service; a flow overrides them in its trigger's polling_overrides",
                    "change_detection": {
                        "method": "new_items (default) | modified_since",
                        "identifier_field": "field identifying an item (default id); items already seen are skipped",
                        "cursor_field": "optional — a field whose value only grows (e.g. a tweet id); the newest is remembered and passed to the next poll as since_id",
                        "dispatch": "optional — 'batch' runs the flow ONCE per batch of new items with {items, includes, meta, count}; default runs it once per item",
                        "batch_size": "optional integer — items per batch with dispatch 'batch'"
                    },
                    "pagination": {
                        "token_path": "path to the next-page token in the response, e.g. meta.next_token",
                        "param": "the service parameter that takes the token, e.g. next_token",
                        "max_pages": "integer — pages followed per poll (items and 'includes' lists are merged)"
                    },
                    "example": {
                        "polling_service": "search_tweets",
                        "interval_seconds": 600,
                        "polling_parameters": {"max_results": 100},
                        "pagination": {"token_path": "meta.next_token", "param": "next_token", "max_pages": 5},
                        "change_detection": {"method": "new_items", "identifier_field": "id",
                                             "cursor_field": "id", "dispatch": "batch", "batch_size": 100}
                    },
                    "legacy_keys": "service_name / service_params / comparison_field / comparison_type are still read (mapped onto the keys above) but do not author them"
                }
            }
        },
        "example": {
            "event_name": "order_created",
            "display_name": "Order Created",
            "description": "Triggered when a new order is created in Shopify",
            "event_type": "webhook",
            "event_configuration": {
                "webhook_method": "POST",
                "headers": {"Content-Type": "application/json"}
            }
        },
        "important_notes": [
            "event_configuration structure varies by event_type",
            "For schedule events: must include valid cron expression",
            "For polling events: interval_seconds must be >= 60 and polling_service must name one of the application's services",
            "For polling events that feed AI or bulk writes, use change_detection.dispatch 'batch' so one flow run handles many items",
            "For webhook events: configuration is optional but recommended"
        ]
    }


@router.post("/install", response_model=InstallApplicationResponse)
async def install_application(
    request: InstallApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Install or reinstall a seed application
    
    - If application is not installed: Installs it
    - If application is installed and force_reinstall=false: Returns error with warning
    - If application is installed and force_reinstall=true: Deletes all subscriptions and reinstalls
    
    **Warning**: Reinstalling will delete all existing subscriptions and their data!
    """
    # Only admins can install applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can install applications")
    
    try:
        # First, validate the seed application JSON
        applications = seed_manager.discover_applications()
        if request.application_key not in applications:
            raise HTTPException(status_code=404, detail=f"Seed application '{request.application_key}' not found")
        
        app_data = applications[request.application_key]
        validation_result = schema_validator.validate_seed_application(app_data)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Seed application validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", []),
                    "validation_phase": "pre_installation",
                    "rollback_performed": False,
                    "note": "Installation prevented - no database changes were made"
                }
            )
        
        # Log warnings if any
        if validation_result.get("warnings"):
            logger.warning(f"Validation warnings for {request.application_key}: {validation_result['warnings']}")
        
        result = seed_manager.install_application(
            db=db,
            application_key=request.application_key,
            force_reinstall=request.force_reinstall,
            user_id=current_user.user_id
        )
        
        if not result['success']:
            # Check if it's a validation error during installation
            if 'validation' in result.get('message', '').lower():
                raise HTTPException(
                    status_code=400,
                    detail={
                        'message': result['message'],
                        'errors': result.get('errors', []),
                        'warnings': result.get('warnings', []),
                        'rollback_performed': result.get('rollback_performed', False)
                    }
                )
            # If it's because app is already installed, return 409 Conflict
            elif 'already installed' in result['message']:
                raise HTTPException(
                    status_code=409,
                    detail={
                        'message': result['message'],
                        'warnings': result.get('warnings', [])
                    }
                )
            else:
                # General installation failure
                raise HTTPException(
                    status_code=400, 
                    detail={
                        'message': result['message'],
                        'errors': result.get('errors', []),
                        'rollback_performed': result.get('rollback_performed', False)
                    }
                )
        
        # Get updated application info
        applications = seed_manager.get_seed_applications(db, tenant_id=str(current_user.tenant_id))
        app_info = None
        for app in applications:
            if app.key == request.application_key:
                app_info = app
                break
        
        return InstallApplicationResponse(
            success=result['success'],
            message=result['message'],
            application=app_info,
            warnings=result.get('warnings'),
            deleted_subscriptions=result.get('deleted_subscriptions')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error installing application {request.application_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to install application: {str(e)}")


@router.post("/refresh-cache")
async def refresh_seeders_cache(
    current_user: User = Depends(get_current_user)
):
    """
    Refresh the seed applications cache
    
    Use this if you've added new seed applications and want them to appear
    """
    # Only admins can refresh cache
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can refresh seed cache")
    
    try:
        # Clear the cache
        seed_manager.refresh_cache()
        
        # Re-discover applications
        applications = seed_manager.discover_applications()
        
        return {
            'success': True,
            'message': f'Successfully refreshed seed applications cache',
            'applications_found': len(applications),
            'applications': list(applications.keys())
        }
    except Exception as e:
        logger.error(f"Error refreshing seed cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh seed cache")


@router.delete("/{application_key}")
async def delete_seed_application(
    application_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a seed application
    
    Only instance admins can delete seed applications
    """
    # Only admins can delete seed applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can delete seed applications")
    
    # Check if the application is installed
    app_data = seed_manager.discover_applications().get(application_key)
    if app_data:
        app_config = app_data.get('application', {})
        existing_app = db.query(Application).filter(
            Application.app_name == app_config.get('app_name'),
            Application.app_type == app_config.get('app_type', 'global')
        ).first()
        
        if existing_app:
            # Get subscription count
            subscription_count = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
                ApplicationSubscription.app_id == existing_app.app_id
            ).scalar() or 0
            
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": f"Cannot delete seed application '{application_key}' because it is currently installed",
                    "installed_app_id": existing_app.app_id,
                    "subscription_count": subscription_count,
                    "suggestion": "Please uninstall the application first before deleting the seed application"
                }
            )
    
    # Delete the seed application
    result = seed_manager.delete_seed_application(application_key)
    
    if result['success']:
        return result
    else:
        raise HTTPException(status_code=404 if 'not found' in result['message'] else 500, detail=result['message'])


@router.post("/{application_key}/update")
async def update_installed_application(
    application_key: str,
    force_reinstall: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an installed application to the latest seed version
    
    By default, this performs a soft update that preserves all user subscriptions and tokens.
    Only updates services and events while keeping authentication intact.
    
    Args:
        application_key: The key of the seed application to update
        force_reinstall: If True, completely reinstalls (deletes all subscriptions). Default False.
        
    Only instance admins can update applications
    """
    # Only admins can update applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can update applications")
    
    try:
        # Get the seed application data
        app_data = seed_manager.discover_applications().get(application_key)
        if not app_data:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        app_config = app_data.get('application', {})

        # Find the installed GLOBAL application — by seed key first, as the
        # installer does; never a tenant's own application of the same name.
        existing_app = db.query(Application).filter(
            Application.seed_key == application_key,
            Application.app_scope != 'tenant'
        ).first() or db.query(Application).filter(
            Application.app_name == app_config.get('app_name'),
            Application.app_type == app_config.get('app_type', 'global'),
            Application.app_scope != 'tenant'
        ).first()

        if not existing_app:
            raise HTTPException(
                status_code=400,
                detail=f"Application '{application_key}' is not installed"
            )

        # Check if update is available
        seed_version = app_config.get('version', '1.0.0')
        if existing_app.version == seed_version:
            return {
                "success": True,
                "message": f"Application '{app_config['app_name']}' is already up to date",
                "version": seed_version
            }
        
        # Store previous version for response
        previous_version = existing_app.version
        
        if force_reinstall:
            # Original behavior - complete reinstall (deletes subscriptions)
            logger.warning(f"Force reinstalling application '{application_key}' - all subscriptions will be deleted!")
            result = seed_manager.install_application(
                db=db,
                application_key=application_key,
                force_reinstall=True,
                user_id=current_user.user_id
            )
            
            if not result['success']:
                raise HTTPException(status_code=400, detail=result['message'])
            
            return {
                "success": True,
                "message": f"Successfully reinstalled application '{app_config['app_name']}' from version {previous_version} to {seed_version}",
                "previous_version": previous_version,
                "new_version": seed_version,
                "update_type": "force_reinstall",
                "deleted_subscriptions": result.get('deleted_subscriptions', 0),
                "warning": "All user subscriptions and tokens were deleted"
            }
        else:
            # Soft update - preserves subscriptions and tokens. Runs through
            # this request's session, so it works on every database IOFlow
            # runs on (soft_update_manager_simple opened a SQLite file and
            # failed with "no such table" on PostgreSQL).
            logger.info(f"Soft updating application '{application_key}' - preserving all subscriptions")
            result = seed_manager.soft_update_global_application(db, application_key)
            if not result['success']:
                raise HTTPException(status_code=400, detail=result.get('message', 'Update failed'))

            changes = {k: result[k] for k in (
                "services_created", "services_updated", "services_deactivated",
                "events_created", "events_updated", "events_deactivated") if k in result}
            return {
                "success": True,
                "message": f"Successfully updated application '{app_config['app_name']}' from version {previous_version} to {seed_version}",
                "previous_version": previous_version,
                "new_version": seed_version,
                "update_type": "soft_update",
                "changes": changes,
                "subscriptions_preserved": result.get("subscriptions_preserved", 0)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating application {application_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update application: {str(e)}")


@router.post("/{application_key}/uninstall")
async def uninstall_seed_application(
    application_key: str,
    force: bool = Query(False, description="Force uninstall even if subscriptions exist"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uninstall an installed seed application
    
    This will remove the application from the system, including:
    - All services
    - All events
    - All subscriptions (if force=true)
    
    Only instance admins can uninstall applications
    """
    # Only admins can uninstall applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can uninstall applications")
    
    try:
        # Get the seed application data
        app_data = seed_manager.discover_applications().get(application_key)
        if not app_data:
            raise HTTPException(
                status_code=404, 
                detail={
                    "message": f"Seed application '{application_key}' not found",
                    "suggestion": "Please check the application key and ensure the seed application exists."
                }
            )
        
        app_config = app_data.get('application', {})
        
        # Find the installed application
        existing_app = db.query(Application).filter(
            Application.app_name == app_config.get('app_name'),
            Application.app_type == app_config.get('app_type', 'global')
        ).first()
        
        if not existing_app:
            # Check if any applications are installed with this key
            key_based_app = db.query(Application).filter(
                Application.key == application_key
            ).first()
            
            if key_based_app:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": f"Application '{application_key}' found but with different configuration",
                        "expected_name": app_config.get('app_name'),
                        "actual_name": key_based_app.name,
                        "expected_type": app_config.get('app_type', 'global'),
                        "actual_type": key_based_app.app_type,
                        "suggestion": "The installed application has different name/type than the seed application. Please check the application details."
                    }
                )
            else:
                # Check if there are any user installations
                from db.application_models import ApplicationInstallation
                user_install = db.query(ApplicationInstallation).join(
                    Application, ApplicationInstallation.application_id == Application.app_id
                ).filter(
                    Application.key == application_key
                ).first()
                
                if user_install:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "message": f"Application '{application_key}' is installed by users but not as a global application",
                            "suggestion": "This application has user-specific installations. Admin uninstall is not applicable for user-installed applications."
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "message": f"Application '{application_key}' is not installed",
                            "seed_app_name": app_config.get('app_name'),
                            "seed_app_type": app_config.get('app_type', 'global'),
                            "suggestion": "This seed application has not been installed yet. You can only uninstall applications that are currently installed."
                        }
                    )
        
        # Check for active subscriptions
        subscription_count = db.query(func.count(ApplicationSubscription.subscription_id)).filter(
            ApplicationSubscription.app_id == existing_app.app_id
        ).scalar() or 0
        
        if subscription_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Cannot uninstall application with {subscription_count} active subscriptions",
                    "subscription_count": subscription_count,
                    "suggestion": "Use force=true to uninstall anyway (this will delete all subscriptions)"
                }
            )
        
        # Delete subscriptions if force=true
        if subscription_count > 0 and force:
            db.query(ApplicationSubscription).filter(
                ApplicationSubscription.app_id == existing_app.app_id
            ).delete()
            logger.info(f"Deleted {subscription_count} subscriptions for application {application_key}")
        
        # Delete events
        from db.application_models import ApplicationEvent
        event_count = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == existing_app.app_id
        ).delete()
        
        # Delete services
        from db.application_models import ApplicationService
        service_count = db.query(ApplicationService).filter(
            ApplicationService.app_id == existing_app.app_id
        ).delete()
        
        # Delete the application
        db.delete(existing_app)
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully uninstalled application '{application_key}'",
            "deleted": {
                "app_id": existing_app.app_id,
                "services": service_count,
                "events": event_count,
                "subscriptions": subscription_count if force else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uninstalling application {application_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to uninstall application: {str(e)}")


@router.get("/{application_key}/json")
async def get_seed_application_json(
    application_key: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the raw JSON content of a seed application
    
    Returns the complete JSON structure that can be edited
    """
    # Only admins can access raw JSON
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can access seed application JSON")
    
    try:
        # Get the application data
        applications = seed_manager.discover_applications()
        
        if application_key not in applications:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        return applications[application_key]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting seed application JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{application_key}/json")
async def update_seed_application_json(
    application_key: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a seed application with raw JSON content
    
    This allows complete control over the seed application structure
    Auto-increments version if the application is installed
    """
    # Only admins can update seed applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can update seed applications")
    
    try:
        # Check if application exists
        seed_dir = Path(seed_manager._applications_path)
        file_path = seed_dir / f"{application_key}.json"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        # Load existing application to check version
        with open(file_path, 'r') as f:
            existing_app = json.load(f)
        
        # Validate the new JSON structure
        if 'key' not in request:
            request['key'] = application_key
        elif request['key'] != application_key:
            raise HTTPException(status_code=400, detail="Application key in JSON does not match URL parameter")
        
        if 'application' not in request:
            raise HTTPException(status_code=400, detail="Missing required 'application' field")
        
        # Auto-increment version if content has changed
        existing_version = existing_app.get('application', {}).get('version', '1.0.0')
        
        # Compare the content (excluding version) to detect changes
        existing_copy = json.loads(json.dumps(existing_app))
        request_copy = json.loads(json.dumps(request))
        
        # Remove version from comparison
        if 'application' in existing_copy and 'version' in existing_copy['application']:
            del existing_copy['application']['version']
        if 'application' in request_copy and 'version' in request_copy['application']:
            del request_copy['application']['version']
        
        # If content has changed, increment version
        if existing_copy != request_copy:
            version_parts = existing_version.split('.')
            try:
                # Increment patch version
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                patch += 1
                new_version = f"{major}.{minor}.{patch}"
            except:
                # If version format is invalid, use a default
                new_version = "1.0.1"
            
            request['application']['version'] = new_version
            logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {application_key}")
        else:
            # No changes, keep existing version
            request['application']['version'] = existing_version
        
        # Validate using schema validator
        validation_result = schema_validator.validate_seed_application(request)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Seed application validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            )
        
        # Save the updated JSON
        with open(file_path, 'w') as f:
            json.dump(request, f, indent=2)
        
        # Refresh cache
        seed_manager.refresh_cache()
        
        return {
            "success": True,
            "message": f"Successfully updated seed application '{application_key}'",
            "version": request['application']['version'],
            "warnings": validation_result.get("warnings", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating seed application JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=SeedApplicationResponse)
async def create_seed_application(
    request: CreateSeedApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new seed application
    
    Only instance admins can create seed applications
    """
    # Only admins can create seed applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can create seed applications")
    
    try:
        # Build the seed application structure
        seed_app = {
            "key": request.app_key,
            "application": {
                "app_name": request.app_name,
                "app_type": request.app_type,
                "category": request.category,
                "auth_type": request.auth_type,
                "description": request.description,
                "base_url": request.base_url,
                "version": request.version,
                "auth_config": request.auth_config or _get_default_auth_config(request.auth_type)
            },
            "services": [service.dict() for service in (request.services or [])],
            "events": [event.dict() for event in (request.events or [])]
        }
        
        # Save to file
        seed_dir = Path(seed_manager._applications_path)
        seed_dir.mkdir(exist_ok=True)
        file_path = seed_dir / f"{request.app_key}.json"
        
        # Check if already exists
        if file_path.exists():
            raise HTTPException(status_code=400, detail=f"Seed application '{request.app_key}' already exists")
        
        # Validate the seed application before saving
        validation_result = schema_validator.validate_seed_application(seed_app)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Seed application validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            )
        
        # Save the file
        with open(file_path, 'w') as f:
            json.dump(seed_app, f, indent=2)
        
        # Refresh cache
        seed_manager.refresh_cache()
        
        return SeedApplicationResponse(
            success=True,
            message=f"Successfully created seed application '{request.app_key}'",
            application=seed_app
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating seed application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{application_key}", response_model=SeedApplicationResponse)
async def update_seed_application(
    application_key: str,
    request: UpdateSeedApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing seed application
    
    Only instance admins can update seed applications
    """
    # Only admins can update seed applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can update seed applications")
    
    try:
        # Check if application exists
        seed_dir = Path(seed_manager._applications_path)
        file_path = seed_dir / f"{application_key}.json"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        # Load existing application
        with open(file_path, 'r') as f:
            seed_app = json.load(f)
        
        # Keep track of whether any changes were made
        original_app = json.loads(json.dumps(seed_app))
        
        # Update fields
        if request.app_name is not None:
            seed_app["application"]["app_name"] = request.app_name
        if request.app_type is not None:
            seed_app["application"]["app_type"] = request.app_type
        if request.category is not None:
            seed_app["application"]["category"] = request.category
        if request.auth_type is not None:
            seed_app["application"]["auth_type"] = request.auth_type
            if request.auth_config is None:
                seed_app["application"]["auth_config"] = _get_default_auth_config(request.auth_type)
        if request.description is not None:
            seed_app["application"]["description"] = request.description
        if request.base_url is not None:
            seed_app["application"]["base_url"] = request.base_url
        if request.auth_config is not None:
            seed_app["application"]["auth_config"] = request.auth_config
        if request.services is not None:
            seed_app["services"] = [service.dict() for service in request.services]
        if request.events is not None:
            seed_app["events"] = [event.dict() for event in request.events]
        
        # Auto-increment version if content has changed
        if request.version is None:
            # Compare the content (excluding version) to detect changes
            original_copy = json.loads(json.dumps(original_app))
            updated_copy = json.loads(json.dumps(seed_app))
            
            # Remove version from comparison
            if 'application' in original_copy and 'version' in original_copy['application']:
                del original_copy['application']['version']
            if 'application' in updated_copy and 'version' in updated_copy['application']:
                del updated_copy['application']['version']
            
            # If content has changed, increment version
            if original_copy != updated_copy:
                existing_version = original_app.get('application', {}).get('version', '1.0.0')
                version_parts = existing_version.split('.')
                try:
                    # Increment patch version
                    major = int(version_parts[0]) if len(version_parts) > 0 else 1
                    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                    patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                    patch += 1
                    new_version = f"{major}.{minor}.{patch}"
                except:
                    # If version format is invalid, use a default
                    new_version = "1.0.1"
                
                seed_app["application"]["version"] = new_version
                logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {application_key}")
        else:
            # Use the provided version
            seed_app["application"]["version"] = request.version
        
        # Validate the updated seed application before saving
        validation_result = schema_validator.validate_seed_application(seed_app)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Seed application validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            )
        
        # Save the updated file
        with open(file_path, 'w') as f:
            json.dump(seed_app, f, indent=2)
        
        # Refresh cache
        seed_manager.refresh_cache()
        
        # Also update any installed applications to preserve subscriptions
        # Check if this seed application is installed and update it to preserve subscriptions
        try:
            # Get application config to find the app name
            app_config = seed_app.get("application", {})
            app_name = app_config.get("app_name")
            app_type = app_config.get("app_type", "global")
            
            if app_name:
                # Check if application is installed
                from db.application_models import Application
                from sqlalchemy.orm import Session
                
                existing_app = db.query(Application).filter(
                    Application.app_name == app_name,
                    Application.app_type == app_type
                ).first()
                
                if existing_app:
                    logger.info(f"Found installed application '{app_name}', performing soft update to preserve subscriptions")
                    
                    # Use soft update manager to preserve subscriptions
                    from services.soft_update_manager_simple import simple_soft_update_manager
                    
                    soft_update_result = simple_soft_update_manager.soft_update_application(
                        application_key=application_key,
                        seed_data=seed_app
                    )
                    
                    if soft_update_result['success']:
                        preserved_subscriptions = soft_update_result['changes']['subscriptions_preserved']
                        logger.info(f"Successfully preserved {preserved_subscriptions} subscription(s) during seed update")
                        
                        return SeedApplicationResponse(
                            success=True,
                            message=f"Successfully updated seed application '{application_key}' and preserved {preserved_subscriptions} subscription(s)",
                            application=seed_app
                        )
                    else:
                        logger.warning(f"Soft update failed: {soft_update_result.get('error', 'Unknown error')}")
                        # Continue with normal response if soft update fails
                
        except Exception as soft_update_error:
            logger.warning(f"Error during soft update of installed application: {soft_update_error}")
            # Continue with normal response if soft update fails
        
        return SeedApplicationResponse(
            success=True,
            message=f"Successfully updated seed application '{application_key}'",
            application=seed_app
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating seed application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{application_key}/services")
async def add_service_to_seed_application(
    application_key: str,
    service_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a service to an existing seed application

    This endpoint includes full processing logic for services including:
    - Service uniqueness validation
    - Template syntax fixes (${var} -> {{var}})
    - Configuration normalization
    - Auto version incrementing
    - Schema validation

    Only instance admins can modify seed applications
    """
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can modify seed applications")

    try:
        # Load existing application
        seed_dir = Path(seed_manager._applications_path)
        file_path = seed_dir / f"{application_key}.json"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")

        # Load app data
        seed_apps = seed_manager.discover_seed_applications()
        if application_key not in seed_apps:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")

        app_data = seed_apps[application_key]

        # Extract service info from service_data
        service_name = service_data.get("service_name")
        service_type = service_data.get("service_type")

        if not service_name:
            raise HTTPException(status_code=400, detail="service_name is required")
        if not service_type:
            raise HTTPException(status_code=400, detail="service_type is required")

        # Validate service name uniqueness
        existing_services = []
        for s in app_data.get("services", []):
            existing_name = s.get("service_name") or s.get("name")
            if existing_name:
                existing_services.append(existing_name)

        if service_name in existing_services:
            raise HTTPException(status_code=400, detail=f"Service '{service_name}' already exists")

        # Validate service type
        valid_service_types = [
            "api_call", "webhook", "email_send", "smtp_send",
            "pop3_receive", "imap_receive", "database_query",
            "llm_api_call", "mcp_call", "ssh_command",
            "file_operation", "ai_agent_execute", "graphql"
        ]
        if service_type not in valid_service_types:
            raise HTTPException(status_code=400, detail={
                "error": f"Invalid service_type: '{service_type}'",
                "valid_values": valid_service_types
            })

        # Process service_data - fix template syntax and normalize structure
        new_service = service_data.copy()

        # Fix template syntax in request_config if present
        if "request_config" in new_service and isinstance(new_service["request_config"], dict):
            request_config = new_service["request_config"]

            # Fix headers_template
            if "headers_template" in request_config and isinstance(request_config["headers_template"], dict):
                for key, value in request_config["headers_template"].items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        request_config["headers_template"][key] = f"{{{{{var_name}}}}}"

            # Fix body_template
            if "body_template" in request_config and isinstance(request_config["body_template"], dict):
                body_template = request_config["body_template"]
                for key, value in body_template.items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        body_template[key] = f"{{{{{var_name}}}}}"

            # Fix query_params_template
            if "query_params_template" in request_config and isinstance(request_config["query_params_template"], dict):
                for key, value in request_config["query_params_template"].items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        request_config["query_params_template"][key] = f"{{{{{var_name}}}}}"

        # Fix endpoint_template syntax if present
        if "endpoint_template" in new_service:
            endpoint = new_service["endpoint_template"]
            if isinstance(endpoint, str) and "${base_url}" in endpoint:
                new_service["endpoint_template"] = endpoint.replace("${base_url}", "{{base_url}}")

        # Add service to services array
        if "services" not in app_data:
            app_data["services"] = []

        app_data["services"].append(new_service)

        # Auto-increment version since we added a service
        existing_version = app_data.get('application', {}).get('version', '1.0.0')
        version_parts = existing_version.split('.')
        try:
            major = int(version_parts[0]) if len(version_parts) > 0 else 1
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0
            patch += 1
            new_version = f"{major}.{minor}.{patch}"
        except:
            new_version = "1.0.1"

        app_data["application"]["version"] = new_version
        logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {application_key}")

        # Update metadata
        if "metadata" not in app_data:
            app_data["metadata"] = {}

        from datetime import datetime
        app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
        app_data["metadata"]["services_count"] = len(app_data["services"])

        # Validate before saving
        validation_result = schema_validator.validate_seed_application(app_data)
        if not validation_result["valid"]:
            # Remove the service we just added
            app_data["services"].pop()
            raise HTTPException(status_code=400, detail={
                "error": "Service validation failed",
                "validation_errors": validation_result["errors"],
                "warnings": validation_result.get("warnings", [])
            })

        # Save updated application
        with open(file_path, 'w') as f:
            json.dump(app_data, f, indent=2)

        # Refresh cache
        seed_manager.refresh_cache()

        return {
            "success": True,
            "app_key": application_key,
            "service_name": service_name,
            "service": new_service,
            "total_services": len(app_data["services"]),
            "version": new_version
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{application_key}/events")
async def add_event_to_seed_application(
    application_key: str,
    event_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add an event to an existing seed application

    This endpoint includes full processing logic for events including:
    - Event uniqueness validation
    - Event type validation
    - Default extraction configuration for webhooks
    - Auto version incrementing
    - Schema validation

    Only instance admins can modify seed applications
    """
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can modify seed applications")

    try:
        # Load existing application
        seed_dir = Path(seed_manager._applications_path)
        file_path = seed_dir / f"{application_key}.json"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")

        # Load app data
        seed_apps = seed_manager.discover_seed_applications()
        if application_key not in seed_apps:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")

        app_data = seed_apps[application_key]

        # Extract event info
        event_name = event_data.get("event_name")
        event_type = event_data.get("event_type", "webhook")

        if not event_name:
            raise HTTPException(status_code=400, detail="event_name is required")

        # Validate event name uniqueness
        existing_events = [e.get("event_name", e.get("name", "")) for e in app_data.get("events", [])]
        if event_name in existing_events:
            raise HTTPException(status_code=400, detail=f"Event '{event_name}' already exists")

        # Validate event type
        valid_event_types = [
            "webhook", "schedule", "polling", "manual", "email", "form", "mqtt"
        ]
        if event_type not in valid_event_types:
            raise HTTPException(status_code=400, detail={
                "error": f"Invalid event_type: '{event_type}'",
                "valid_values": valid_event_types,
                "descriptions": {
                    "webhook": "HTTP POST callback from external service",
                    "schedule": "Cron-based scheduled trigger",
                    "polling": "Poll at regular intervals",
                    "manual": "Manual trigger by user",
                    "email": "Triggered by incoming email",
                    "form": "Triggered by form submission",
                    "mqtt": "Triggered by a message published to an MQTT topic"
                }
            })

        # Create event structure
        new_event = event_data.copy()

        # Add default extraction for webhooks if not present
        if event_type == "webhook" and "extraction_configuration" not in new_event:
            new_event["extraction_configuration"] = {
                "path_mappings": {
                    "event_id": "$.id",
                    "event_type": "$.type",
                    "data": "$.data"
                }
            }

        # Add to events
        if "events" not in app_data:
            app_data["events"] = []

        app_data["events"].append(new_event)

        # Auto-increment version since we added an event
        existing_version = app_data.get('application', {}).get('version', '1.0.0')
        version_parts = existing_version.split('.')
        try:
            major = int(version_parts[0]) if len(version_parts) > 0 else 1
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0
            patch += 1
            new_version = f"{major}.{minor}.{patch}"
        except:
            new_version = "1.0.1"

        app_data["application"]["version"] = new_version
        logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {application_key} after adding event")

        # Update metadata
        if "metadata" not in app_data:
            app_data["metadata"] = {}

        from datetime import datetime
        app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
        app_data["metadata"]["events_count"] = len(app_data["events"])

        # Validate before saving
        validation_result = schema_validator.validate_seed_application(app_data)
        if not validation_result["valid"]:
            # Remove the event we just added
            app_data["events"].pop()
            raise HTTPException(status_code=400, detail={
                "error": "Event validation failed",
                "validation_errors": validation_result["errors"],
                "warnings": validation_result.get("warnings", [])
            })

        # Save updated application
        with open(file_path, 'w') as f:
            json.dump(app_data, f, indent=2)

        # Refresh cache
        seed_manager.refresh_cache()

        return {
            "success": True,
            "app_key": application_key,
            "event_name": event_name,
            "event": new_event,
            "total_events": len(app_data["events"]),
            "version": new_version
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import", response_model=SeedApplicationResponse)
async def import_seed_application(
    request: ImportSeedApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import a seed application from JSON
    
    - Validates the JSON structure
    - Optionally saves the application
    - Only instance admins can import seed applications
    """
    # Only admins can import seed applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can import seed applications")
    
    try:
        # Parse JSON
        try:
            seed_app = json.loads(request.json_content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        
        # Validate structure
        validation_result = _validate_seed_application(seed_app)
        
        if not validation_result["valid"]:
            return SeedApplicationResponse(
                success=False,
                message="Validation failed",
                errors=validation_result["errors"]
            )
        
        # If validate_only, return validation result
        if request.validate_only:
            return SeedApplicationResponse(
                success=True,
                message="Validation successful",
                application=seed_app
            )
        
        # Check if application exists
        app_key = seed_app.get("key")
        seed_dir = Path(seed_manager._applications_path)
        seed_dir.mkdir(exist_ok=True)
        file_path = seed_dir / f"{app_key}.json"
        
        if file_path.exists() and not request.overwrite:
            raise HTTPException(status_code=400, detail=f"Seed application '{app_key}' already exists. Set overwrite=true to replace.")
        
        # Save the file
        with open(file_path, 'w') as f:
            json.dump(seed_app, f, indent=2)
        
        # Refresh cache
        seed_manager.refresh_cache()
        
        return SeedApplicationResponse(
            success=True,
            message=f"Successfully imported seed application '{app_key}'",
            application=seed_app
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing seed application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateSeedApplicationResponse)
async def validate_seed_application(
    request: Dict[str, str],  # Accept as body parameter
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate a seed application JSON structure
    
    Returns validation errors and warnings
    """
    try:
        json_content = request.get("json_content", "")
        # Parse JSON
        try:
            seed_app = json.loads(json_content)
        except json.JSONDecodeError as e:
            return ValidateSeedApplicationResponse(
                valid=False,
                errors=[f"Invalid JSON: {str(e)}"],
                warnings=[]
            )
        
        # Validate structure
        result = _validate_seed_application(seed_app)
        
        return ValidateSeedApplicationResponse(
            valid=result["valid"],
            errors=result["errors"],
            warnings=result["warnings"],
            application=seed_app if result["valid"] else None
        )
    except Exception as e:
        logger.error(f"Error validating seed application: {e}")
        return ValidateSeedApplicationResponse(
            valid=False,
            errors=[str(e)],
            warnings=[]
        )


@router.get("/{application_key}/validate", response_model=ValidateSeedApplicationResponse)
async def validate_seed_application_by_key(
    application_key: str,
    current_user: User = Depends(get_current_user)
):
    """
    Validate a specific seed application by key
    
    Returns detailed validation errors and warnings
    """
    try:
        # Get the application data
        applications = seed_manager.discover_applications()
        
        if application_key not in applications:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        app_data = applications[application_key]
        
        # Get the validation info that was stored during discovery
        validation_info = app_data.get('_validation', {})
        
        # Re-validate to get fresh results
        validation_result = schema_validator.validate_seed_application(app_data)
        
        return ValidateSeedApplicationResponse(
            valid=validation_result["valid"],
            errors=validation_result.get("errors", []),
            warnings=validation_result.get("warnings", []),
            application=app_data if validation_result["valid"] else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating seed application {application_key}: {e}")
        return ValidateSeedApplicationResponse(
            valid=False,
            errors=[str(e)],
            warnings=[]
        )


@router.get("/{application_key}/verify")
async def verify_installed_application(
    application_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify that an installed application matches its seed application JSON
    
    Returns detailed comparison including parameter mappings
    """
    # Only admins can verify applications
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can verify applications")
    
    try:
        # Get the seed application data
        applications = seed_manager.discover_applications()
        if application_key not in applications:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        seed_data = applications[application_key]
        app_config = seed_data.get('application', {})
        
        # Find the installed application
        installed_app = db.query(Application).filter(
            Application.app_name == app_config.get('app_name'),
            Application.app_type == app_config.get('app_type', 'global')
        ).first()
        
        if not installed_app:
            return {
                "installed": False,
                "message": f"Application '{application_key}' is not installed"
            }
        
        # Get installed services
        from db.application_models import ApplicationService
        installed_services = db.query(ApplicationService).filter(
            ApplicationService.app_id == installed_app.app_id
        ).all()
        
        # Compare services
        seed_services = seed_data.get('services', [])
        verification_results = {
            "installed": True,
            "app_id": installed_app.app_id,
            "app_name": installed_app.app_name,
            "service_comparison": [],
            "mismatches": []
        }
        
        # Create a map of installed services by name
        installed_service_map = {s.service_name: s for s in installed_services}
        
        for seed_service in seed_services:
            service_name = seed_service.get('name') or seed_service.get('service_name')
            if not service_name:
                continue
                
            comparison = {
                "service_name": service_name,
                "found_in_installed": service_name in installed_service_map,
                "seed_parameters": [],
                "installed_parameters": [],
                "parameter_mismatches": []
            }
            
            # Extract parameters from seed
            seed_params_str = seed_service.get('parameters', '')
            seed_param_mappings = {}
            if seed_params_str and isinstance(seed_params_str, str):
                try:
                    seed_params_list = json.loads(seed_params_str)
                    if isinstance(seed_params_list, list):
                        for param in seed_params_list:
                            param_name = param.get('name', '')
                            if param_name:
                                seed_param_mappings[param_name] = {
                                    "mapping": param.get('mapping', param_name),
                                    "description": param.get('description', ''),
                                    "type": param.get('type', 'string')
                                }
                                comparison["seed_parameters"].append({
                                    "name": param_name,
                                    "mapping": param.get('mapping', param_name),
                                    "description": param.get('description', ''),
                                    "type": param.get('type', 'string')
                                })
                except json.JSONDecodeError:
                    verification_results["mismatches"].append(f"Failed to parse parameters JSON for seed service '{service_name}'")
            
            # Check installed service
            if service_name in installed_service_map:
                installed_service = installed_service_map[service_name]
                
                # Parse service_config if it's a string
                service_config = installed_service.service_config
                if isinstance(service_config, str):
                    try:
                        service_config = json.loads(service_config)
                    except json.JSONDecodeError:
                        service_config = {}
                elif service_config is None:
                    service_config = {}
                
                # Extract parameters from installed service
                installed_params = service_config.get('parameters', [])
                for param in installed_params:
                    comparison["installed_parameters"].append({
                        "name": param.get('param_name', ''),
                        "mapping": param.get('mapping', param.get('param_name', '')),
                        "description": param.get('description', ''),
                        "type": param.get('data_type', 'string')
                    })
                
                # Compare parameters
                installed_param_map = {p.get('param_name'): p for p in installed_params}
                
                for seed_param_name, seed_param_info in seed_param_mappings.items():
                    if seed_param_name not in installed_param_map:
                        comparison["parameter_mismatches"].append({
                            "param_name": seed_param_name,
                            "issue": "missing_in_installed",
                            "seed_mapping": seed_param_info["mapping"]
                        })
                    else:
                        installed_param = installed_param_map[seed_param_name]
                        installed_mapping = installed_param.get('mapping', seed_param_name)
                        
                        if installed_mapping != seed_param_info["mapping"]:
                            comparison["parameter_mismatches"].append({
                                "param_name": seed_param_name,
                                "issue": "mapping_mismatch",
                                "seed_mapping": seed_param_info["mapping"],
                                "installed_mapping": installed_mapping
                            })
            
            verification_results["service_comparison"].append(comparison)
            
            if comparison["parameter_mismatches"]:
                verification_results["mismatches"].append(f"Service '{service_name}' has {len(comparison['parameter_mismatches'])} parameter mismatches")
        
        # Add summary
        verification_results["summary"] = {
            "total_seed_services": len(seed_services),
            "total_installed_services": len(installed_services),
            "services_with_issues": sum(1 for c in verification_results["service_comparison"] if c["parameter_mismatches"]),
            "total_mismatches": len(verification_results["mismatches"])
        }
        
        return verification_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying application {application_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_default_auth_config(auth_type: str) -> Dict[str, Any]:
    """Get default auth configuration based on auth type"""
    auth_configs = {
        "api_key": {"header_name": "X-API-Key"},
        "oauth2": {
            "authorization_url": "https://example.com/oauth/authorize",
            "token_url": "https://example.com/oauth/token",
            "scopes": []
        },
        "basic": {},
        "token_exchange": {"exchange_url": ""},
        "none": {},
        "custom": {}
    }
    return auth_configs.get(auth_type, {})


def _validate_seed_application(seed_app: Dict[str, Any]) -> Dict[str, Any]:
    """Validate seed application structure using schema validator"""
    return schema_validator.validate_seed_application(seed_app)


@router.get("/raw/all")
async def get_all_seed_applications_raw(
    current_user: User = Depends(get_current_user)
):
    """
    Get all seed applications as raw JSON data.
    
    This endpoint returns the complete JSON structure for all seed applications,
    similar to what seed_manager.discover_applications() returns.
    Used by MCP tools that need access to raw seed application data.
    
    Returns:
        Dictionary mapping application keys to their complete JSON data
    """
    try:
        # Get all seed applications with their raw JSON data
        applications = seed_manager.discover_applications()
        return applications
    except Exception as e:
        logger.error(f"Error getting raw seed applications: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get seed applications: {str(e)}")


@router.get("/raw/{application_key}")
async def get_seed_application_raw(
    application_key: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific seed application as raw JSON data.
    
    This endpoint returns the complete JSON structure for a specific seed application.
    Used by MCP tools that need access to raw seed application data.
    
    Args:
        application_key: The key of the seed application to retrieve
    
    Returns:
        Complete JSON data for the specified seed application
    """
    try:
        # Get all seed applications
        applications = seed_manager.discover_applications()
        
        if application_key not in applications:
            raise HTTPException(status_code=404, detail=f"Seed application '{application_key}' not found")
        
        return applications[application_key]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting raw seed application: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get seed application: {str(e)}")
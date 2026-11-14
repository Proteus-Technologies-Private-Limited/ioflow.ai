"""
Frontend Flow Application Service

Core business logic for managing frontend/public flow applications.
Handles creation, management, access control, and execution of public applications.
"""

import json
import uuid
import hashlib
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ipaddress import ip_address, ip_network

from core.config import settings
from db.db_compat import parse_json_field

# Import models - PostgreSQL Only
from db.models import User, Tenant
from db.application_models import (
    PublishedApplication, FrontendFlowApplication,
    FrontendAppAccessLog, FrontendAppEmbedConfig
)

logger = logging.getLogger(__name__)


class FrontendAppError(Exception):
    """Custom exception for frontend application errors"""
    pass


class AccessDeniedError(FrontendAppError):
    """Exception raised when access is denied"""
    pass


class RateLimitExceededError(FrontendAppError):
    """Exception raised when rate limit is exceeded"""
    pass


class FrontendAppService:
    """Main service for managing frontend flow applications"""
    
    def __init__(self):
        self.rate_limit_window = timedelta(hours=1)
    
    def create_frontend_application(self,
                                  db: Session,
                                  user_id: str,
                                  frontend_app_name: str,
                                  access_type: str,
                                  published_app_id: str = None,
                                  flow_id: str = None,
                                  access_config: Dict[str, Any] = None,
                                  public_url_slug: str = None,
                                  description: str = None,
                                  rate_limit_per_hour: int = 100,
                                  custom_styling: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new frontend flow application from a published application or directly from a flow

        Args:
            db: Database session
            user_id: ID of the user creating the frontend app
            frontend_app_name: Display name for the frontend app
            access_type: Type of access control (public_url, organization, specific_users, tenant_list)
            published_app_id: ID of the published application (optional if flow_id provided)
            flow_id: ID of the flow (optional if published_app_id provided)
            access_config: Configuration for access control
            public_url_slug: Custom URL slug (auto-generated if not provided)
            description: Description of the frontend app
            rate_limit_per_hour: Rate limit per IP per hour
            custom_styling: Custom CSS/styling configuration

        Returns:
            Dictionary with creation result
        """
        logger.info(f"Creating frontend application: published_app_id={published_app_id}, flow_id={flow_id}")

        try:
            # Validate that either published_app_id or flow_id is provided
            if not published_app_id and not flow_id:
                raise FrontendAppError("Either published_app_id or flow_id must be provided")

            # If published_app_id is provided, validate it exists
            flow_name = None
            if published_app_id:
                published_app = db.query(PublishedApplication).filter(
                    PublishedApplication.published_app_id == published_app_id
                ).first()

                if not published_app:
                    raise FrontendAppError(f"Published application {published_app_id} not found")

                flow_name = published_app.flow_name
                # Get flow_id from published app if not provided
                if not flow_id:
                    flow_id = published_app.flow_id

            # If flow_id is provided, validate it exists
            if flow_id:
                from db.models import Flow
                flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                if not flow:
                    raise FrontendAppError(f"Flow {flow_id} not found")
                if not flow_name:
                    flow_name = flow.flow_name

            # Get user info for tenant_id
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                raise FrontendAppError(f"User {user_id} not found")

            # Generate URL slug if not provided
            if not public_url_slug:
                public_url_slug = self._generate_url_slug(db, frontend_app_name)
            else:
                # Validate slug uniqueness
                existing = db.query(FrontendFlowApplication).filter(
                    FrontendFlowApplication.public_url_slug == public_url_slug
                ).first()
                if existing:
                    raise FrontendAppError(f"URL slug '{public_url_slug}' is already in use")

            # Validate access type and config
            self._validate_access_configuration(access_type, access_config)

            # Create the frontend application
            frontend_app = FrontendFlowApplication(
                frontend_app_id=str(uuid.uuid4()),
                published_app_id=published_app_id,  # Can be None
                flow_id=flow_id,  # Direct flow reference
                created_by=user_id,
                tenant_id=user.tenant_id,
                public_url_slug=public_url_slug,
                frontend_app_name=frontend_app_name,
                description=description or f"Public interface for {flow_name}",
                access_type=access_type,
                access_config=json.dumps(access_config or {}),
                rate_limit_per_hour=rate_limit_per_hour,
                custom_styling=json.dumps(custom_styling or {}),
                is_active=True
            )
            
            db.add(frontend_app)
            db.commit()
            
            logger.info(f"Successfully created frontend application {frontend_app.frontend_app_id}")
            
            # Debug logging
            logger.info(f"DEBUG: settings.base_url = {settings.base_url}")
            public_url = f"{settings.base_url}/public-app/{public_url_slug}"
            logger.info(f"DEBUG: Generated public_url = {public_url}")
            
            return {
                "success": True,
                "message": f"Frontend application '{frontend_app_name}' created successfully",
                "frontend_app_id": frontend_app.frontend_app_id,
                "public_url_slug": public_url_slug,
                "public_url": public_url,
                "access_type": access_type
            }
            
        except Exception as e:
            logger.error(f"Error creating frontend application: {str(e)}")
            db.rollback()
            raise FrontendAppError(f"Failed to create frontend application: {str(e)}")
    
    def get_frontend_application_by_slug(self,
                                       db: Session,
                                       public_url_slug: str) -> Optional[Dict[str, Any]]:
        """Get frontend application by its public URL slug"""
        frontend_app = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.public_url_slug == public_url_slug,
            FrontendFlowApplication.is_active == True
        ).first()
        
        if not frontend_app:
            return None
        
        # Build the base response
        response = {
            "frontend_app_id": frontend_app.frontend_app_id,
            "published_app_id": frontend_app.published_app_id,
            "frontend_app_name": frontend_app.frontend_app_name,
            "description": frontend_app.description,
            "access_type": frontend_app.access_type,
            "access_config": parse_json_field(frontend_app.access_config) or {},
            "custom_styling": parse_json_field(frontend_app.custom_styling) or {},
            "rate_limit_per_hour": frontend_app.rate_limit_per_hour,
            "usage_count": frontend_app.usage_count,
            "created_at": frontend_app.created_at.isoformat()
        }
        
        # Add published application info only if it exists (not for direct frontend apps)
        if frontend_app.published_app_id is not None and frontend_app.published_application:
            response["published_application"] = {
                "flow_id": frontend_app.published_application.flow_id,
                "flow_name": frontend_app.published_application.flow_name,
                "app_key": frontend_app.published_application.app_key
            }
        else:
            # For direct frontend apps, we don't have published application info
            response["published_application"] = None
        
        return response
    
    def validate_access_permission(self,
                                 db: Session,
                                 frontend_app: Dict[str, Any],
                                 ip_address: str,
                                 user_id: str = None,
                                 tenant_id: str = None) -> bool:
        """
        Validate if access is permitted based on the application's access configuration
        
        Args:
            db: Database session
            frontend_app: Frontend application data
            ip_address: Client IP address
            user_id: User ID if authenticated (optional)
            tenant_id: Tenant ID if authenticated (optional)
            
        Returns:
            True if access is permitted, False otherwise
        """
        access_type = frontend_app["access_type"]
        access_config = frontend_app["access_config"]
        
        logger.info(f"Validating access for {access_type} from IP {ip_address}")
        
        try:
            if access_type == "public_url":
                # Public access - always allow
                return True
            
            elif access_type == "organization":
                # Organization access - must be from same tenant as creator
                if not tenant_id:
                    return False
                
                # Get the creator's tenant from the frontend app
                frontend_app_record = db.query(FrontendFlowApplication).filter(
                    FrontendFlowApplication.frontend_app_id == frontend_app["frontend_app_id"]
                ).first()
                
                return tenant_id == frontend_app_record.tenant_id
            
            elif access_type == "specific_users":
                # Specific users - must be in the allowed users list
                if not user_id:
                    return False
                
                allowed_users = access_config.get("allowed_users", [])
                return user_id in allowed_users
            
            elif access_type == "tenant_list":
                # Tenant list - must be from one of the allowed tenants
                if not tenant_id:
                    return False
                
                allowed_tenants = access_config.get("allowed_tenants", [])
                return tenant_id in allowed_tenants
            
            else:
                logger.warning(f"Unknown access type: {access_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating access permission: {str(e)}")
            return False
    
    def check_rate_limit(self,
                        db: Session,
                        frontend_app_id: str,
                        ip_address: str) -> bool:
        """
        Check if the IP address has exceeded the rate limit
        
        Args:
            db: Database session
            frontend_app_id: Frontend application ID
            ip_address: Client IP address
            
        Returns:
            True if rate limit is OK, False if exceeded
        """
        try:
            # Get the frontend app to check rate limit
            frontend_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == frontend_app_id
            ).first()
            
            if not frontend_app:
                return False
            
            # Check access logs in the last hour
            since_time = datetime.now() - self.rate_limit_window
            
            access_count = db.query(FrontendAppAccessLog).filter(
                and_(
                    FrontendAppAccessLog.frontend_app_id == frontend_app_id,
                    FrontendAppAccessLog.ip_address == ip_address,
                    FrontendAppAccessLog.access_type == 'execute',
                    FrontendAppAccessLog.accessed_at >= since_time
                )
            ).count()
            
            return access_count < frontend_app.rate_limit_per_hour
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return False
    
    def log_access(self,
                  db: Session,
                  frontend_app_id: str,
                  ip_address: str,
                  user_agent: str,
                  access_type: str,
                  execution_success: bool = None,
                  execution_time_ms: int = None,
                  error_message: str = None):
        """Log access attempt"""
        try:
            log_entry = FrontendAppAccessLog(
                log_id=str(uuid.uuid4()),
                frontend_app_id=frontend_app_id,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,  # Truncate if too long
                access_type=access_type,
                execution_success=execution_success,
                execution_time_ms=execution_time_ms,
                error_message=error_message
            )
            
            db.add(log_entry)
            db.commit()
            
            # Update usage count if execution was successful
            if access_type == 'execute' and execution_success:
                db.query(FrontendFlowApplication).filter(
                    FrontendFlowApplication.frontend_app_id == frontend_app_id
                ).update({
                    "usage_count": FrontendFlowApplication.usage_count + 1,
                    "last_accessed_at": datetime.now()
                })
                db.commit()
                
        except Exception as e:
            logger.error(f"Error logging access: {str(e)}")
            db.rollback()
    
    def get_frontend_applications_for_published_app(self,
                                                  db: Session,
                                                  published_app_id: str) -> List[Dict[str, Any]]:
        """Get all frontend applications for a published application"""
        frontend_apps = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.published_app_id == published_app_id
        ).all()
        
        # Debug logging
        logger.info(f"DEBUG get_frontend_applications: settings.base_url = {settings.base_url}")
        
        result = []
        for app in frontend_apps:
            public_url = f"{settings.base_url}/public-app/{app.public_url_slug}"
            logger.info(f"DEBUG: Generated public_url for {app.frontend_app_name} = {public_url}")
            result.append({
                "frontend_app_id": app.frontend_app_id,
                "frontend_app_name": app.frontend_app_name,
                "public_url_slug": app.public_url_slug,
                "public_url": public_url,
                "access_type": app.access_type,
                "is_active": app.is_active,
                "usage_count": app.usage_count,
                "created_at": app.created_at.isoformat()
            })
        
        return result
    
    def update_frontend_application(self,
                                  db: Session,
                                  frontend_app_id: str,
                                  user_id: str,
                                  **updates) -> Dict[str, Any]:
        """Update a frontend application"""
        try:
            frontend_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == frontend_app_id
            ).first()
            
            if not frontend_app:
                raise FrontendAppError(f"Frontend application {frontend_app_id} not found")
            
            # Check permissions
            if frontend_app.created_by != user_id:
                raise FrontendAppError("You don't have permission to update this application")
            
            # Update allowed fields
            allowed_updates = [
                'frontend_app_name', 'description', 'access_type', 'access_config',
                'rate_limit_per_hour', 'custom_styling', 'is_active'
            ]
            
            for field, value in updates.items():
                if field in allowed_updates:
                    if field in ['access_config', 'custom_styling'] and value is not None:
                        setattr(frontend_app, field, json.dumps(value))
                    else:
                        setattr(frontend_app, field, value)
            
            frontend_app.updated_at = datetime.now()
            db.commit()
            
            return {
                "success": True,
                "message": "Frontend application updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error updating frontend application: {str(e)}")
            db.rollback()
            raise FrontendAppError(f"Failed to update frontend application: {str(e)}")
    
    def delete_frontend_application(self,
                                  db: Session,
                                  frontend_app_id: str,
                                  user_id: str) -> Dict[str, Any]:
        """Delete a frontend application"""
        try:
            frontend_app = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.frontend_app_id == frontend_app_id
            ).first()
            
            if not frontend_app:
                raise FrontendAppError(f"Frontend application {frontend_app_id} not found")
            
            # Check permissions
            if frontend_app.created_by != user_id:
                raise FrontendAppError("You don't have permission to delete this application")
            
            # Delete related records (cascade should handle this, but be explicit)
            db.query(FrontendAppAccessLog).filter(
                FrontendAppAccessLog.frontend_app_id == frontend_app_id
            ).delete()
            
            db.query(FrontendAppEmbedConfig).filter(
                FrontendAppEmbedConfig.frontend_app_id == frontend_app_id
            ).delete()
            
            # Delete the frontend application
            db.delete(frontend_app)
            db.commit()
            
            return {
                "success": True,
                "message": "Frontend application deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting frontend application: {str(e)}")
            db.rollback()
            raise FrontendAppError(f"Failed to delete frontend application: {str(e)}")
    
    # Private helper methods
    
    def _generate_url_slug(self, db: Session, app_name: str) -> str:
        """Generate a unique URL slug for the application"""
        # Create base slug from app name
        base_slug = app_name.lower().replace(' ', '-').replace('_', '-')
        # Remove non-alphanumeric characters except hyphens
        import re
        base_slug = re.sub(r'[^a-z0-9-]', '', base_slug)
        # Remove multiple consecutive hyphens
        base_slug = re.sub(r'-+', '-', base_slug)
        # Remove leading/trailing hyphens
        base_slug = base_slug.strip('-')
        
        # Ensure minimum length
        if len(base_slug) < 3:
            base_slug = f"app-{base_slug}"
        
        # Check uniqueness and append counter if needed
        slug = base_slug
        counter = 1
        
        while True:
            existing = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.public_url_slug == slug
            ).first()
            
            if not existing:
                return slug
            
            counter += 1
            slug = f"{base_slug}-{counter}"
    
    def _validate_access_configuration(self, access_type: str, access_config: Dict[str, Any]):
        """Validate access configuration"""
        valid_access_types = ["public_url", "organization", "specific_users", "tenant_list"]
        
        if access_type not in valid_access_types:
            raise FrontendAppError(f"Invalid access type. Must be one of: {valid_access_types}")
        
        if access_config is None:
            access_config = {}
        
        if access_type == "specific_users":
            if not access_config.get("allowed_users"):
                raise FrontendAppError("specific_users access type requires allowed_users list")
        
        elif access_type == "tenant_list":
            if not access_config.get("allowed_tenants"):
                raise FrontendAppError("tenant_list access type requires allowed_tenants list")
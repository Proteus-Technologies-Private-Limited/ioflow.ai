from functools import wraps
from typing import List, Optional, Callable
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, UserRole
from api.auth import get_current_user

# Permission definitions for each role
ROLE_PERMISSIONS = {
    UserRole.INSTANCE_ADMIN: {
        "global_apps": ["create", "read", "update", "delete"],
        "tenant_apps": ["create", "read", "update", "delete"],
        "flows": ["create", "read", "update", "delete", "execute"],
        "executions": ["create", "read", "update", "delete", "cancel"],
        "users": ["create", "read", "update", "delete"],
        "tenants": ["create", "read", "update", "delete"],
        "billing": ["create", "read", "update", "delete"],
        "seed_apps": ["create", "read", "update", "delete"],
        "pricing": ["create", "read", "update", "delete"],
        "hitl_roles": ["create", "read", "update", "delete"],
        "hitl_tasks": ["create", "read", "update", "delete", "complete", "cancel", "reassign"]
    },
    UserRole.TENANT_ADMIN: {
        "global_apps": ["read"],
        "tenant_apps": ["create", "read", "update", "delete"],
        "flows": ["create", "read", "update", "delete", "execute"],
        "executions": ["create", "read", "update", "delete", "cancel"],
        "users": ["create", "read", "update", "delete"],  # Only within tenant
        "tenants": ["read"],  # Only own tenant
        "billing": ["read"],  # Only own tenant
        "seed_apps": [],
        "pricing": ["read"],
        "hitl_roles": ["create", "read", "update", "delete"],
        "hitl_tasks": ["create", "read", "update", "delete", "complete", "cancel", "reassign"]
    },
    UserRole.APPLICATION_PROVIDER: {
        "global_apps": ["read"],
        "tenant_apps": ["create", "read", "update", "delete"],  # Only own apps
        "flows": ["read"],
        "executions": ["read"],
        "users": [],
        "tenants": [],
        "billing": ["read"],
        "seed_apps": [],
        "pricing": ["create", "read", "update", "delete"],  # Only own apps
        "hitl_roles": ["read"],
        "hitl_tasks": ["read", "complete"]
    },
    UserRole.FLOW_DESIGNER: {
        "global_apps": ["read"],
        "tenant_apps": ["read"],
        "flows": ["create", "read", "update", "delete", "execute"],
        "executions": ["create", "read", "cancel"],
        "users": [],
        "tenants": [],
        "billing": [],
        "seed_apps": [],
        "pricing": [],
        "hitl_roles": ["read"],
        "hitl_tasks": ["read", "complete", "cancel", "reassign"]
    },
    UserRole.EXECUTION_MONITOR: {
        "global_apps": ["read"],
        "tenant_apps": ["read"],
        "flows": ["read", "execute"],
        "executions": ["create", "read"],
        "users": [],
        "tenants": [],
        "billing": [],
        "seed_apps": [],
        "pricing": [],
        "hitl_roles": ["read"],
        "hitl_tasks": ["read", "complete"]
    },
    UserRole.FLOW_EXECUTOR: {
        # Execute-only role: can run flows and view execution logs, nothing else.
        "global_apps": ["read"],
        "tenant_apps": ["read"],
        "flows": ["read", "execute"],
        "executions": ["create", "read"],
        "users": [],
        "tenants": [],
        "billing": [],
        "seed_apps": [],
        "pricing": [],
        "hitl_roles": ["read"],
        "hitl_tasks": ["read", "complete"]
    }
}

def has_permission(user: User, resource: str, action: str) -> bool:
    """Check if user has permission for a specific resource and action"""
    if not user.role:
        return False
    
    permissions = ROLE_PERMISSIONS.get(user.role, {})
    resource_permissions = permissions.get(resource, [])
    
    return action in resource_permissions

def require_permission(resource: str, action: str):
    """Decorator to check permissions for API endpoints"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not has_permission(current_user, resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have permission to {action} {resource}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_any_permission(permissions: List[tuple]):
    """Decorator to check if user has any of the specified permissions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check if user has any of the required permissions
            for resource, action in permissions:
                if has_permission(current_user, resource, action):
                    return await func(*args, **kwargs)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action"
            )
        return wrapper
    return decorator

def require_role(roles: List[UserRole]):
    """Decorator to check if user has one of the required roles"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have the required role to perform this action"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def check_tenant_isolation(user: User, tenant_id: str) -> bool:
    """Check if user has access to the specified tenant"""
    # Instance admin has access to all tenants
    if user.role == UserRole.INSTANCE_ADMIN:
        return True
    
    # All other users can only access their own tenant
    return user.tenant_id == tenant_id

def require_tenant_access(func: Callable) -> Callable:
    """Decorator to ensure tenant isolation"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Get current user and tenant_id from kwargs
        current_user = None
        tenant_id = kwargs.get('tenant_id')
        
        for key, value in kwargs.items():
            if isinstance(value, User):
                current_user = value
                break
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # If no tenant_id in kwargs, use user's tenant
        if not tenant_id:
            tenant_id = current_user.tenant_id
        
        if not check_tenant_isolation(current_user, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant's data"
            )
        
        return await func(*args, **kwargs)
    return wrapper

# Convenience functions for common permission checks
def is_instance_admin(user: User) -> bool:
    """Check if user is instance admin"""
    return user.role == UserRole.INSTANCE_ADMIN

def is_tenant_admin(user: User) -> bool:
    """Check if user is tenant admin"""
    return user.role == UserRole.TENANT_ADMIN

def is_application_provider(user: User) -> bool:
    """Check if user is application provider"""
    return user.role == UserRole.APPLICATION_PROVIDER

def can_manage_users(user: User) -> bool:
    """Check if user can manage other users"""
    return user.role in [UserRole.INSTANCE_ADMIN, UserRole.TENANT_ADMIN]

def can_create_global_apps(user: User) -> bool:
    """Check if user can create global applications"""
    return user.role == UserRole.INSTANCE_ADMIN

def can_manage_flows(user: User) -> bool:
    """Check if user can create/edit flows"""
    return user.role not in [UserRole.EXECUTION_MONITOR, UserRole.FLOW_EXECUTOR]
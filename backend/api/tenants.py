from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import uuid
import logging

from db.database import get_db
from db.models import Tenant, User, UserRole
from api.auth import get_current_user
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])

# Pydantic models
class TenantCreate(BaseModel):
    tenant_name: str
    email_domain: str
    web_site: Optional[str] = None
    gst_no: Optional[str] = None
    address: Optional[str] = None

class TenantUpdate(BaseModel):
    tenant_name: Optional[str] = None
    email_domain: Optional[str] = None
    web_site: Optional[str] = None
    gst_no: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None

class TenantResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    schema_name: str
    email_domain: Optional[str]
    web_site: Optional[str]
    gst_no: Optional[str]
    address: Optional[str]
    user_id_own: Optional[str]
    created_at: datetime
    status: str
    user_count: Optional[int] = 0

    class Config:
        from_attributes = True

class UserStatusUpdate(BaseModel):
    is_active: bool

def check_instance_admin(current_user: User) -> None:
    """Check if current user is instance admin"""
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance administrators can perform this action"
        )

def check_tenant_access(current_user: User, tenant_id: str) -> None:
    """Check if user has access to tenant"""
    if current_user.role == UserRole.INSTANCE_ADMIN:
        return
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id == tenant_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this tenant"
    )

@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all tenants (instance admin) or own tenant (tenant admin)"""
    try:
        if current_user.role == UserRole.INSTANCE_ADMIN:
            tenants = db.query(Tenant).all()
        elif current_user.role == UserRole.TENANT_ADMIN:
            tenants = db.query(Tenant).filter(Tenant.tenant_id == current_user.tenant_id).all()
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view tenants"
            )
    except Exception as e:
        logger.error(f"Error querying tenants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
    # Add user count for each tenant
    result = []
    try:
        for tenant in tenants:
            user_count = db.query(User).filter(User.tenant_id == tenant.tenant_id).count()
            result.append(TenantResponse(
                tenant_id=tenant.tenant_id,
                tenant_name=tenant.tenant_name,
                schema_name=tenant.schema_name,
                email_domain=tenant.email_domain,
                web_site=tenant.web_site,
                gst_no=tenant.gst_no,
                address=tenant.address,
                user_id_own=tenant.user_id_own,
                created_at=tenant.created_at,
                status=tenant.status,
                user_count=user_count
            ))
    except Exception as e:
        logger.error(f"Error building tenant response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building response: {str(e)}"
        )
    
    return result

@router.post("/", response_model=TenantResponse)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new tenant (instance admin only)"""
    check_instance_admin(current_user)
    
    # Validate input
    if not tenant_data.tenant_name or not tenant_data.tenant_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant name cannot be empty"
        )
    
    if not tenant_data.email_domain or not tenant_data.email_domain.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email domain cannot be empty"
        )
    
    # Check if tenant name already exists
    existing_tenant = db.query(Tenant).filter(Tenant.tenant_name == tenant_data.tenant_name).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant with this name already exists"
        )
    
    # Generate tenant ID and schema name
    tenant_id = str(uuid.uuid4())
    # Sanitize tenant name for schema: remove special chars, replace spaces with underscore
    import re
    sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', tenant_data.tenant_name.lower())
    sanitized_name = re.sub(r'_+', '_', sanitized_name)  # Replace multiple underscores with single
    sanitized_name = sanitized_name.strip('_')[:50]  # Remove leading/trailing underscores and limit length
    schema_name = f"tenant_{sanitized_name}"
    
    # Check if schema name already exists
    existing_schema = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
    if existing_schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A tenant with similar name already exists (schema conflict: {schema_name})"
        )
    
    # Create tenant
    new_tenant = Tenant(
        tenant_id=tenant_id,
        tenant_name=tenant_data.tenant_name,
        schema_name=schema_name,
        email_domain=tenant_data.email_domain,
        web_site=tenant_data.web_site,
        gst_no=tenant_data.gst_no,
        address=tenant_data.address,
        user_id_own=current_user.user_id,
        status='active'
    )
    
    try:
        db.add(new_tenant)
        db.commit()
        
        # Create tenant schema and tables
        if not settings.database_url.startswith("sqlite"):
            from db.database import create_schema, create_tenant_tables
            create_schema(schema_name)
            create_tenant_tables(schema_name)
        
        db.refresh(new_tenant)
        return TenantResponse(
            tenant_id=new_tenant.tenant_id,
            tenant_name=new_tenant.tenant_name,
            schema_name=new_tenant.schema_name,
            email_domain=new_tenant.email_domain,
            web_site=new_tenant.web_site,
            gst_no=new_tenant.gst_no,
            address=new_tenant.address,
            user_id_own=new_tenant.user_id_own,
            created_at=new_tenant.created_at,
            status=new_tenant.status,
            user_count=0
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating tenant: {str(e)}")
        error_message = str(e)
        # Check for specific database errors
        if "UNIQUE constraint failed" in error_message:
            if "tenant_name" in error_message:
                detail = "A tenant with this name already exists"
            elif "schema_name" in error_message:
                detail = "A tenant with this schema name already exists"
            elif "email_domain" in error_message:
                detail = "A tenant with this email domain already exists"
            else:
                detail = f"Duplicate tenant: {error_message}"
        else:
            detail = f"Failed to create tenant: {error_message}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tenant details"""
    check_tenant_access(current_user, tenant_id)
    
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    return TenantResponse(**tenant.__dict__, user_count=user_count)

@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update tenant details"""
    check_tenant_access(current_user, tenant_id)
    
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Update fields
    update_data = tenant_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    try:
        db.commit()
        db.refresh(tenant)
        user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
        return TenantResponse(**tenant.__dict__, user_count=user_count)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating tenant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant"
        )

@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a tenant (instance admin only)"""
    check_instance_admin(current_user)
    
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if tenant has users
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant with {user_count} active users"
        )
    
    try:
        db.delete(tenant)
        db.commit()
        
        # TODO: Drop tenant schema if using PostgreSQL
        
        return {"message": "Tenant deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting tenant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant"
        )

@router.get("/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users in a tenant"""
    check_tenant_access(current_user, tenant_id)
    
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    
    return [
        {
            "user_id": user.user_id,
            "email": user.email,
            "user_name": user.user_name,
            "role": user.role.value if user.role else None,
            "is_active": user.is_active,
            "status": user.status,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at
        }
        for user in users
    ]

@router.put("/{tenant_id}/users/{user_id}/activate")
async def update_user_status(
    tenant_id: str,
    user_id: str,
    status_update: UserStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user"""
    check_tenant_access(current_user, tenant_id)
    
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this tenant"
        )
    
    # Prevent deactivating instance admin
    if user.role == UserRole.INSTANCE_ADMIN and not status_update.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate instance administrator"
        )
    
    # Update user status
    user.is_active = status_update.is_active
    user.status = 'A' if status_update.is_active else 'N'
    
    try:
        db.commit()
        return {
            "message": f"User {'activated' if status_update.is_active else 'deactivated'} successfully",
            "user_id": user_id,
            "is_active": user.is_active
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )
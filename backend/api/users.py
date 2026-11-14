from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

from db.database import get_db
from db.models import User, UserRole, Tenant
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# Pydantic models
class UserUpdate(BaseModel):
    user_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserRoleUpdate(BaseModel):
    role: str

class UserResponse(BaseModel):
    user_id: str
    user_name: str
    email: str
    role: str
    tenant_id: str
    tenant_name: Optional[str] = None
    is_active: bool
    status: str
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

def check_user_management_permission(current_user: User, target_user: User = None) -> None:
    """Check if current user can manage users"""
    if current_user.role == UserRole.INSTANCE_ADMIN:
        return
    
    if current_user.role == UserRole.TENANT_ADMIN:
        if target_user and target_user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users in your own tenant"
            )
        return
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to manage users"
    )

def validate_role_change(current_user: User, target_user: User, new_role: str) -> None:
    """Validate if role change is allowed"""
    try:
        new_role_enum = UserRole(new_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {new_role}"
        )
    
    # Instance admin can assign any role
    if current_user.role == UserRole.INSTANCE_ADMIN:
        return
    
    # Tenant admin can only assign roles within their tenant
    if current_user.role == UserRole.TENANT_ADMIN:
        if target_user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users in your own tenant"
            )
        
        # Tenant admin cannot assign INSTANCE_ADMIN role
        if new_role_enum == UserRole.INSTANCE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only instance administrators can assign instance admin role"
            )
        
        # Tenant admin cannot change another tenant admin's role
        if target_user.role == UserRole.TENANT_ADMIN and target_user.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change another tenant administrator's role"
            )
        
        return
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to change user roles"
    )

@router.get("/", response_model=List[UserResponse])
async def list_users(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users based on permissions"""
    query = db.query(User).join(Tenant, User.tenant_id == Tenant.tenant_id)

    # Apply permission-based filtering
    if current_user.role == UserRole.INSTANCE_ADMIN:
        # Instance admin can see all users
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
    elif current_user.role == UserRole.TENANT_ADMIN:
        # Tenant admin can only see users in their tenant
        query = query.filter(User.tenant_id == current_user.tenant_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view users"
        )

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.user_name.ilike(search_term)) | (User.email.ilike(search_term))
        )

    # Apply additional filters
    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.all()
    
    return [
        UserResponse(
            user_id=user.user_id,
            user_name=user.user_name,
            email=user.email,
            role=user.role.value if user.role else "FLOW_DESIGNER",
            tenant_id=user.tenant_id,
            tenant_name=user.tenant.tenant_name if user.tenant else None,
            is_active=user.is_active,
            status=user.status,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )
        for user in users
    ]

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    return UserResponse(
        user_id=current_user.user_id,
        user_name=current_user.user_name,
        email=current_user.email,
        role=current_user.role.value if current_user.role else "FLOW_DESIGNER",
        tenant_id=current_user.tenant_id,
        tenant_name=current_user.tenant.tenant_name if current_user.tenant else None,
        is_active=current_user.is_active,
        status=current_user.status,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user details"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    check_user_management_permission(current_user, user)
    
    return UserResponse(
        user_id=user.user_id,
        user_name=user.user_name,
        email=user.email,
        role=user.role.value if user.role else "FLOW_DESIGNER",
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.tenant_name if user.tenant else None,
        is_active=user.is_active,
        status=user.status,
        created_at=user.created_at,
        last_login_at=user.last_login_at
    )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user details"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    check_user_management_permission(current_user, user)
    
    # Prevent changing own role if not instance admin
    if user_update.role and user_id == current_user.user_id and current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role"
        )
    
    # Validate role change if role is being updated
    if user_update.role:
        validate_role_change(current_user, user, user_update.role)
        user.role = UserRole(user_update.role)
    
    # Update other fields
    if user_update.user_name is not None:
        user.user_name = user_update.user_name
    
    if user_update.email is not None:
        # Check if email already exists
        existing_user = db.query(User).filter(
            User.email == user_update.email,
            User.user_id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = user_update.email
    
    if user_update.is_active is not None:
        # Prevent deactivating instance admin
        if user.role == UserRole.INSTANCE_ADMIN and not user_update.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate instance administrator"
            )
        user.is_active = user_update.is_active
        user.status = 'A' if user_update.is_active else 'N'
    
    try:
        db.commit()
        db.refresh(user)
        
        return UserResponse(
            user_id=user.user_id,
            user_name=user.user_name,
            email=user.email,
            role=user.role.value if user.role else "FLOW_DESIGNER",
            tenant_id=user.tenant_id,
            tenant_name=user.tenant.tenant_name if user.tenant else None,
            is_active=user.is_active,
            status=user.status,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user role"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    check_user_management_permission(current_user, user)
    validate_role_change(current_user, user, role_update.role)
    
    # Prevent changing own role if not instance admin
    if user_id == current_user.user_id and current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role"
        )
    
    try:
        user.role = UserRole(role_update.role)
        db.commit()
        db.refresh(user)
        
        return UserResponse(
            user_id=user.user_id,
            user_name=user.user_name,
            email=user.email,
            role=user.role.value if user.role else "FLOW_DESIGNER",
            tenant_id=user.tenant_id,
            tenant_name=user.tenant.tenant_name if user.tenant else None,
            is_active=user.is_active,
            status=user.status,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a user"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    check_user_management_permission(current_user, user)
    
    # Prevent deleting instance admin
    if user.role == UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete instance administrator"
        )
    
    # Prevent deleting self
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    try:
        db.delete(user)
        db.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
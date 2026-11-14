"""
API Key Management Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import hashlib

from db.database import get_db
from core.config import settings

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import User, APIKey
else:
    from db.models import User, APIKey

from schemas.api_key_schemas import (
    APIKeyCreate, APIKeyResponse, APIKeyCreateResponse, 
    APIKeyUpdate, APIKeyList
)
from core.auth_utils import get_current_user_required as get_current_user
import json

router = APIRouter(
    prefix="/api/v1/api-keys",
    tags=["api-keys"]
)


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (full_key, key_hash, key_prefix)
    """
    # Generate random token
    raw_key = secrets.token_urlsafe(32)
    
    # Create the full key
    full_key = f"ioflow_{raw_key}"
    
    # Hash the key for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    
    # Get prefix for identification
    key_prefix = full_key[:12]
    
    return full_key, key_hash, key_prefix


@router.post("/", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new API key for the current user"""
    
    # Generate the API key
    full_key, key_hash, key_prefix = generate_api_key()
    
    # Calculate expiration if specified
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    # Create the API key record
    db_key = APIKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_data.name,
        description=key_data.description,
        user_id=current_user.user_id,
        scopes=json.dumps(key_data.scopes) if key_data.scopes else json.dumps(["read"]),
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    
    # Parse scopes back from JSON
    scopes = json.loads(db_key.scopes) if db_key.scopes else []
    
    # Return the response with the actual key (only shown once!)
    return APIKeyCreateResponse(
        id=db_key.id,
        key_prefix=db_key.key_prefix,
        name=db_key.name,
        description=db_key.description,
        scopes=scopes,
        is_active=db_key.is_active,
        created_at=db_key.created_at,
        expires_at=db_key.expires_at,
        last_used_at=db_key.last_used_at,
        usage_count=db_key.usage_count,
        api_key=full_key  # This is the only time the full key is shown!
    )


@router.get("/", response_model=APIKeyList)
async def list_api_keys(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all API keys for the current user"""
    
    # Get all API keys for the user
    api_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.user_id
    ).offset(skip).limit(limit).all()
    
    # Convert to response format
    response_keys = []
    for key in api_keys:
        scopes = json.loads(key.scopes) if key.scopes else []
        response_keys.append(APIKeyResponse(
            id=key.id,
            key_prefix=key.key_prefix,
            name=key.name,
            description=key.description,
            scopes=scopes,
            is_active=key.is_active,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            usage_count=key.usage_count
        ))
    
    total_count = db.query(APIKey).filter(
        APIKey.user_id == current_user.user_id
    ).count()
    
    return APIKeyList(api_keys=response_keys, total_count=total_count)


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific API key"""
    
    api_key = db.query(APIKey).filter(
        and_(
            APIKey.id == key_id,
            APIKey.user_id == current_user.user_id
        )
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    scopes = json.loads(api_key.scopes) if api_key.scopes else []
    
    return APIKeyResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        description=api_key.description,
        scopes=scopes,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count
    )


@router.patch("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    key_update: APIKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an API key"""
    
    api_key = db.query(APIKey).filter(
        and_(
            APIKey.id == key_id,
            APIKey.user_id == current_user.user_id
        )
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Update fields if provided
    if key_update.name is not None:
        api_key.name = key_update.name
    
    if key_update.description is not None:
        api_key.description = key_update.description
    
    if key_update.scopes is not None:
        api_key.scopes = json.dumps(key_update.scopes)
    
    if key_update.is_active is not None:
        api_key.is_active = key_update.is_active
    
    db.commit()
    db.refresh(api_key)
    
    scopes = json.loads(api_key.scopes) if api_key.scopes else []
    
    return APIKeyResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        description=api_key.description,
        scopes=scopes,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an API key"""
    
    api_key = db.query(APIKey).filter(
        and_(
            APIKey.id == key_id,
            APIKey.user_id == current_user.user_id
        )
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    db.delete(api_key)
    db.commit()
    
    return None


@router.post("/{key_id}/deactivate", response_model=APIKeyResponse)
async def deactivate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate an API key without deleting it"""
    
    api_key = db.query(APIKey).filter(
        and_(
            APIKey.id == key_id,
            APIKey.user_id == current_user.user_id
        )
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    
    scopes = json.loads(api_key.scopes) if api_key.scopes else []
    
    return APIKeyResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        description=api_key.description,
        scopes=scopes,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count
    )
"""
Enhanced authentication utilities supporting both JWT tokens and API keys.
"""
from typing import Optional, Union
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from jose import JWTError
import hashlib
import json

from db.database import get_db
from db.models import User, APIKey
from core.security import AuthService
from core.config import settings


class BearerAuth(HTTPBearer):
    """Custom Bearer authentication that supports both JWT tokens and API keys."""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)


async def get_current_user_enhanced(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(BearerAuth(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Enhanced authentication that supports both JWT tokens and API keys.
    
    The Authorization header should be in the format:
    - For JWT: "Bearer <jwt_token>"
    - For API Key: "Bearer <api_key>"
    
    API keys are distinguished from JWT tokens by their format (they start with "ioflow_").
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Check if it's an API key (starts with specific prefix)
    if token.startswith("ioflow_"):
        return await authenticate_api_key(token, db)
    else:
        # Assume it's a JWT token
        return await authenticate_jwt_token(token, db)


async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user_enhanced)
) -> User:
    """Ensures that a user is authenticated, raises 401 if not."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def authenticate_api_key(api_key: str, db: Session) -> Optional[User]:
    """Authenticate using API key."""
    try:
        # Hash the API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find the API key in database
        api_key_obj = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if API key is expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last used timestamp and usage count
        api_key_obj.last_used_at = datetime.utcnow()
        api_key_obj.usage_count += 1
        db.commit()
        
        # Get the user with tenant relationship
        user = db.query(User).options(joinedload(User.tenant)).filter(
            User.user_id == api_key_obj.user_id
        ).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def authenticate_jwt_token(token: str, db: Session) -> Optional[User]:
    """Authenticate using JWT token."""
    try:
        user = AuthService.get_current_user(db, token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def check_api_key_scopes(api_key: APIKey, required_scopes: list[str]) -> bool:
    """Check if API key has required scopes."""
    if not api_key.scopes:
        return False
    
    try:
        key_scopes = json.loads(api_key.scopes)
        return all(scope in key_scopes for scope in required_scopes)
    except:
        return False


# Backward compatibility aliases
get_current_user = get_current_user_enhanced

# Optional authentication for use in API routes directly (not as dependency)
async def get_current_user_optional_direct(
    request,
    db: Session
) -> Optional[User]:
    """
    Optional authentication that returns None if user is not authenticated.
    For direct use in API routes (not as a FastAPI dependency).
    """
    try:
        # Extract authorization header directly from request
        authorization = request.headers.get("Authorization", "")
        if not authorization or not authorization.startswith("Bearer "):
            return None

        token = authorization.replace("Bearer ", "")

        # Check if it's an API key (starts with specific prefix)
        if token.startswith("ioflow_"):
            return await authenticate_api_key(token, db)
        else:
            # Assume it's a JWT token
            return await authenticate_jwt_token(token, db)
    except Exception:
        return None

# Optional authentication as FastAPI dependency
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(BearerAuth(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication that returns None if user is not authenticated.
    Used as a FastAPI dependency.
    """
    if not credentials:
        return None

    return await get_current_user_enhanced(credentials, db)
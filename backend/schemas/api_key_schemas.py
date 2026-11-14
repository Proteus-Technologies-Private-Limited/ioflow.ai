"""
API Key Schemas for IOFlow
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key"""
    name: str = Field(..., min_length=1, max_length=255, description="Name for the API key")
    description: Optional[str] = Field(None, description="Description of the API key's purpose")
    scopes: Optional[List[str]] = Field(default=["read"], description="List of permission scopes")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")


class APIKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)"""
    id: int
    key_prefix: str = Field(..., description="First 8 characters of the key for identification")
    name: str
    description: Optional[str]
    scopes: Optional[List[str]]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int

    class Config:
        from_attributes = True


class APIKeyCreateResponse(APIKeyResponse):
    """Schema for API key creation response (includes the actual key)"""
    api_key: str = Field(..., description="The actual API key - only shown once!")
    
    
class APIKeyUpdate(BaseModel):
    """Schema for updating an API key"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: Optional[List[str]] = None
    is_active: Optional[bool] = None


class APIKeyList(BaseModel):
    """Schema for listing API keys"""
    api_keys: List[APIKeyResponse]
    total_count: int
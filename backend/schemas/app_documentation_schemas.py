"""
Pydantic schemas for app documentation pages API
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import re


class PageTypeEnum(str, Enum):
    """Documentation page types"""
    USER_GUIDE = "user_guide"
    SPECIFICATIONS = "specifications"
    PREREQUISITES = "prerequisites"
    API_DOCS = "api_docs"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    CHANGELOG = "changelog"
    CUSTOM = "custom"


class DocumentationPageCreate(BaseModel):
    """Schema for creating a new documentation page"""
    page_type: PageTypeEnum = PageTypeEnum.CUSTOM
    page_title: str = Field(..., min_length=1, max_length=255, description="Title of the documentation page")
    page_slug: Optional[str] = Field(None, max_length=255, description="URL-friendly slug (auto-generated if not provided)")
    content: str = Field(..., min_length=1, description="HTML content from WYSIWYG editor")
    display_order: int = Field(default=0, ge=0, description="Order for displaying pages")
    is_published: bool = Field(default=True, description="Whether the page is published")

    @validator('page_slug')
    def validate_slug(cls, v, values):
        """Generate slug from title if not provided, or validate provided slug"""
        if v is None:
            # Auto-generate from title
            if 'page_title' in values:
                title = values['page_title']
                # Convert to lowercase and replace spaces/special chars with hyphens
                slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                return slug
        else:
            # Validate provided slug
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v

    @validator('content')
    def validate_content_length(cls, v):
        """Validate content length (max 500KB)"""
        if len(v) > 500000:
            raise ValueError('Content exceeds maximum size of 500KB')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "page_type": "user_guide",
                "page_title": "Getting Started Guide",
                "page_slug": "getting-started",
                "content": "<h1>Welcome</h1><p>This is a guide...</p>",
                "display_order": 0,
                "is_published": True
            }
        }


class DocumentationPageUpdate(BaseModel):
    """Schema for updating an existing documentation page"""
    page_title: Optional[str] = Field(None, min_length=1, max_length=255)
    page_slug: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    display_order: Optional[int] = Field(None, ge=0)
    is_published: Optional[bool] = None

    @validator('page_slug')
    def validate_slug(cls, v):
        """Validate slug format"""
        if v is not None and not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v

    @validator('content')
    def validate_content_length(cls, v):
        """Validate content length"""
        if v is not None and len(v) > 500000:
            raise ValueError('Content exceeds maximum size of 500KB')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "page_title": "Updated Title",
                "content": "<h1>Updated Content</h1>",
                "is_published": True
            }
        }


class DocumentationPageResponse(BaseModel):
    """Schema for documentation page API responses"""
    page_id: str
    frontend_app_id: str
    page_type: str
    page_title: str
    page_slug: str
    content: str
    display_order: int
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True  # For Pydantic v2 (orm_mode in v1)
        json_schema_extra = {
            "example": {
                "page_id": "123e4567-e89b-12d3-a456-426614174000",
                "frontend_app_id": "app-123",
                "page_type": "user_guide",
                "page_title": "Getting Started",
                "page_slug": "getting-started",
                "content": "<h1>Welcome</h1>",
                "display_order": 0,
                "is_published": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z"
            }
        }


class DocumentationPageSummary(BaseModel):
    """Lightweight schema for listing documentation pages (without content)"""
    page_id: str
    page_type: str
    page_title: str
    page_slug: str
    display_order: int
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentationPageReorder(BaseModel):
    """Schema for reordering documentation pages"""
    page_orders: List[dict] = Field(..., description="List of {page_id: str, display_order: int}")

    @validator('page_orders')
    def validate_page_orders(cls, v):
        """Validate that all entries have page_id and display_order"""
        for entry in v:
            if 'page_id' not in entry or 'display_order' not in entry:
                raise ValueError('Each entry must have page_id and display_order')
            if not isinstance(entry['display_order'], int) or entry['display_order'] < 0:
                raise ValueError('display_order must be a non-negative integer')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "page_orders": [
                    {"page_id": "page-1", "display_order": 0},
                    {"page_id": "page-2", "display_order": 1},
                    {"page_id": "page-3", "display_order": 2}
                ]
            }
        }


class DocumentationPagesListResponse(BaseModel):
    """Schema for listing all documentation pages of an app"""
    app_id: str
    app_name: str
    total_pages: int
    pages: List[DocumentationPageSummary]

    class Config:
        json_schema_extra = {
            "example": {
                "app_id": "app-123",
                "app_name": "My Awesome App",
                "total_pages": 3,
                "pages": [
                    {
                        "page_id": "page-1",
                        "page_type": "user_guide",
                        "page_title": "Getting Started",
                        "page_slug": "getting-started",
                        "display_order": 0,
                        "is_published": True,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": None
                    }
                ]
            }
        }

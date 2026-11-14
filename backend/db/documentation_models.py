"""
Database models for app documentation pages - PostgreSQL and SQLite

NOTE: AppDocumentationPage is now defined in application_models.py
This file re-exports it for backward compatibility and defines the PageType enum.
"""
from enum import Enum

# Re-export AppDocumentationPage from application_models for backward compatibility
from .application_models import AppDocumentationPage


class PageType(str, Enum):
    """Documentation page types"""
    USER_GUIDE = "user_guide"
    SPECIFICATIONS = "specifications"
    PREREQUISITES = "prerequisites"
    API_DOCS = "api_docs"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    CHANGELOG = "changelog"
    CUSTOM = "custom"

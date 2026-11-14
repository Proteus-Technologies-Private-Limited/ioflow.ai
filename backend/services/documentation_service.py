"""
Service layer for app documentation pages management
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict
import uuid
import bleach
from datetime import datetime

from db.documentation_models import AppDocumentationPage, PageType
from db.application_models import FrontendFlowApplication
from schemas.app_documentation_schemas import (
    DocumentationPageCreate,
    DocumentationPageUpdate,
    DocumentationPageReorder
)


# HTML sanitization configuration
ALLOWED_TAGS = [
    'p', 'br', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 's', 'strike', 'b', 'i',
    'ul', 'ol', 'li',
    'a', 'img',
    'blockquote', 'code', 'pre',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'hr',
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'style'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['border', 'cellpadding', 'cellspacing'],
}

ALLOWED_STYLES = [
    'color', 'background-color',
    'font-size', 'font-weight', 'font-style', 'font-family',
    'text-align', 'text-decoration',
    'margin', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right',
    'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
    'border', 'border-color', 'border-width', 'border-style',
    'width', 'height', 'max-width', 'max-height',
]


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks while preserving formatting.

    Args:
        html_content: Raw HTML content from WYSIWYG editor

    Returns:
        Sanitized HTML content
    """
    # Add 'style' to allowed attributes for inline styling
    allowed_attrs_with_style = ALLOWED_ATTRIBUTES.copy()
    # Allow style attribute on all tags that support it
    style_tags = ['p', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th']
    for tag in style_tags:
        if tag in allowed_attrs_with_style:
            if 'style' not in allowed_attrs_with_style[tag]:
                allowed_attrs_with_style[tag].append('style')
        else:
            allowed_attrs_with_style[tag] = ['style']

    # Clean HTML with bleach (without styles parameter for compatibility)
    clean_html = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=allowed_attrs_with_style,
        strip=True  # Strip disallowed tags instead of escaping
    )

    # Link rel safety (prevent tabnabbing)
    clean_html = bleach.linkify(
        clean_html,
        callbacks=[lambda attrs, new: attrs if attrs.get((None, 'href'), '').startswith(('#', '/')) else {**attrs, (None, 'rel'): 'noopener noreferrer'}]
    )

    return clean_html


def create_documentation_page(
    db: Session,
    frontend_app_id: str,
    user_id: str,
    page_data: DocumentationPageCreate
) -> AppDocumentationPage:
    """
    Create a new documentation page for an app.

    Args:
        db: Database session
        frontend_app_id: ID of the app
        user_id: ID of the user creating the page
        page_data: Page creation data

    Returns:
        Created documentation page

    Raises:
        ValueError: If user doesn't own the app or validation fails
    """
    # Verify app exists and user owns it
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()

    if not app:
        raise ValueError("App not found")

    if str(app.created_by) != str(user_id):
        raise ValueError("You don't have permission to modify this app")

    # Check for duplicate slug within the same app
    existing_page = db.query(AppDocumentationPage).filter(
        and_(
            AppDocumentationPage.frontend_app_id == frontend_app_id,
            AppDocumentationPage.page_slug == page_data.page_slug
        )
    ).first()

    if existing_page:
        raise ValueError(f"A page with slug '{page_data.page_slug}' already exists for this app")

    # Sanitize HTML content
    sanitized_content = sanitize_html(page_data.content)

    # Create new page
    new_page = AppDocumentationPage(
        page_id=str(uuid.uuid4()),
        frontend_app_id=frontend_app_id,
        page_type=page_data.page_type,
        page_title=page_data.page_title,
        page_slug=page_data.page_slug,
        content=sanitized_content,
        display_order=page_data.display_order,
        is_published=page_data.is_published
    )

    db.add(new_page)
    db.commit()
    db.refresh(new_page)

    return new_page


def update_documentation_page(
    db: Session,
    page_id: str,
    user_id: str,
    updates: DocumentationPageUpdate
) -> AppDocumentationPage:
    """
    Update an existing documentation page.

    Args:
        db: Database session
        page_id: ID of the page to update
        user_id: ID of the user updating the page
        updates: Update data

    Returns:
        Updated documentation page

    Raises:
        ValueError: If page not found or user doesn't have permission
    """
    # Get page with app relationship
    page = db.query(AppDocumentationPage).filter(
        AppDocumentationPage.page_id == page_id
    ).first()

    if not page:
        raise ValueError("Documentation page not found")

    # Verify ownership through app
    if str(page.app.created_by) != str(user_id):
        raise ValueError("You don't have permission to modify this page")

    # Check for slug conflicts if slug is being updated
    if updates.page_slug and updates.page_slug != page.page_slug:
        existing_page = db.query(AppDocumentationPage).filter(
            and_(
                AppDocumentationPage.frontend_app_id == page.frontend_app_id,
                AppDocumentationPage.page_slug == updates.page_slug,
                AppDocumentationPage.page_id != page_id
            )
        ).first()

        if existing_page:
            raise ValueError(f"A page with slug '{updates.page_slug}' already exists for this app")

    # Update fields
    update_data = updates.dict(exclude_unset=True)

    for field, value in update_data.items():
        if field == 'content' and value is not None:
            # Sanitize HTML content
            value = sanitize_html(value)
        setattr(page, field, value)

    page.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(page)

    return page


def delete_documentation_page(
    db: Session,
    page_id: str,
    user_id: str
) -> bool:
    """
    Delete a documentation page.

    Args:
        db: Database session
        page_id: ID of the page to delete
        user_id: ID of the user deleting the page

    Returns:
        True if deleted successfully

    Raises:
        ValueError: If page not found or user doesn't have permission
    """
    page = db.query(AppDocumentationPage).filter(
        AppDocumentationPage.page_id == page_id
    ).first()

    if not page:
        raise ValueError("Documentation page not found")

    # Verify ownership
    if str(page.app.created_by) != str(user_id):
        raise ValueError("You don't have permission to delete this page")

    db.delete(page)
    db.commit()

    return True


def reorder_documentation_pages(
    db: Session,
    frontend_app_id: str,
    user_id: str,
    reorder_data: DocumentationPageReorder
) -> List[AppDocumentationPage]:
    """
    Reorder documentation pages.

    Args:
        db: Database session
        frontend_app_id: ID of the app
        user_id: ID of the user reordering pages
        reorder_data: List of page IDs with new display orders

    Returns:
        List of reordered pages

    Raises:
        ValueError: If validation fails or user doesn't have permission
    """
    # Verify app ownership
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == frontend_app_id
    ).first()

    if not app:
        raise ValueError("App not found")

    if str(app.created_by) != str(user_id):
        raise ValueError("You don't have permission to modify this app")

    # Update display orders
    for order_entry in reorder_data.page_orders:
        page_id = order_entry['page_id']
        new_order = order_entry['display_order']

        page = db.query(AppDocumentationPage).filter(
            and_(
                AppDocumentationPage.page_id == page_id,
                AppDocumentationPage.frontend_app_id == frontend_app_id
            )
        ).first()

        if page:
            page.display_order = new_order
            page.updated_at = datetime.utcnow()

    db.commit()

    # Return updated pages in order
    pages = db.query(AppDocumentationPage).filter(
        AppDocumentationPage.frontend_app_id == frontend_app_id
    ).order_by(AppDocumentationPage.display_order).all()

    return pages


def get_app_documentation_pages(
    db: Session,
    frontend_app_id: str,
    include_unpublished: bool = False
) -> List[AppDocumentationPage]:
    """
    Get all documentation pages for an app.

    Args:
        db: Database session
        frontend_app_id: ID of the app
        include_unpublished: Whether to include unpublished pages

    Returns:
        List of documentation pages ordered by display_order
    """
    query = db.query(AppDocumentationPage).filter(
        AppDocumentationPage.frontend_app_id == frontend_app_id
    )

    if not include_unpublished:
        query = query.filter(AppDocumentationPage.is_published == True)

    pages = query.order_by(AppDocumentationPage.display_order).all()

    return pages


def get_documentation_page_by_slug(
    db: Session,
    frontend_app_id: str,
    page_slug: str,
    include_unpublished: bool = False
) -> Optional[AppDocumentationPage]:
    """
    Get a specific documentation page by slug.

    Args:
        db: Database session
        frontend_app_id: ID of the app
        page_slug: Slug of the page
        include_unpublished: Whether to include unpublished pages

    Returns:
        Documentation page or None if not found
    """
    query = db.query(AppDocumentationPage).filter(
        and_(
            AppDocumentationPage.frontend_app_id == frontend_app_id,
            AppDocumentationPage.page_slug == page_slug
        )
    )

    if not include_unpublished:
        query = query.filter(AppDocumentationPage.is_published == True)

    return query.first()


def get_documentation_page_by_id(
    db: Session,
    page_id: str
) -> Optional[AppDocumentationPage]:
    """
    Get a documentation page by ID.

    Args:
        db: Database session
        page_id: ID of the page

    Returns:
        Documentation page or None if not found
    """
    return db.query(AppDocumentationPage).filter(
        AppDocumentationPage.page_id == page_id
    ).first()

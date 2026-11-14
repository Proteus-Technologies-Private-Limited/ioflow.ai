"""
API endpoints for app documentation pages management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from db.database import get_db
from api.auth import get_current_user
from core.auth_utils import get_current_user_optional
from db.models import User
from schemas.app_documentation_schemas import (
    DocumentationPageCreate,
    DocumentationPageUpdate,
    DocumentationPageResponse,
    DocumentationPageSummary,
    DocumentationPageReorder,
    DocumentationPagesListResponse
)
from services import documentation_service
from db.application_models import FrontendFlowApplication


router = APIRouter(prefix="/api/v1", tags=["Documentation"])


# ============================================================================
# PROTECTED ENDPOINTS - App Owner Only
# ============================================================================

@router.post(
    "/micro-saas-apps/{app_id}/documentation",
    response_model=DocumentationPageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create documentation page",
    description="Create a new documentation page for a micro SaaS app (owner only)"
)
async def create_documentation_page(
    app_id: str,
    page_data: DocumentationPageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new documentation page"""
    import logging
    import traceback
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Creating documentation page for app {app_id}")
        # Use model_dump() for Pydantic v2, fallback to dict() for v1
        try:
            page_data_dict = page_data.model_dump()
        except AttributeError:
            page_data_dict = page_data.dict()
        logger.info(f"Page data: {page_data_dict}")

        page = documentation_service.create_documentation_page(
            db=db,
            frontend_app_id=app_id,
            user_id=str(current_user.user_id),
            page_data=page_data
        )
        return page
    except ValueError as e:
        logger.error(f"ValueError creating documentation page: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Exception creating documentation page: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/micro-saas-apps/{app_id}/documentation",
    response_model=DocumentationPagesListResponse,
    summary="List app documentation pages (owner)",
    description="List all documentation pages for an app including unpublished (owner only)"
)
async def list_app_documentation_pages_owner(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documentation pages for app owner (includes unpublished)"""
    # Verify ownership
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.frontend_app_id == app_id
    ).first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    if str(app.created_by) != str(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to access this app")

    pages = documentation_service.get_app_documentation_pages(
        db=db,
        frontend_app_id=app_id,
        include_unpublished=True  # Owner sees all pages
    )

    return DocumentationPagesListResponse(
        app_id=app_id,
        app_name=app.frontend_app_name,
        total_pages=len(pages),
        pages=[DocumentationPageSummary.from_orm(page) for page in pages]
    )


@router.get(
    "/micro-saas-apps/{app_id}/documentation/{page_id}",
    response_model=DocumentationPageResponse,
    summary="Get documentation page (owner)",
    description="Get a specific documentation page including unpublished (owner only)"
)
async def get_documentation_page_owner(
    app_id: str,
    page_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific documentation page (owner view)"""
    page = documentation_service.get_documentation_page_by_id(db=db, page_id=page_id)

    if not page or page.frontend_app_id != app_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documentation page not found")

    # Verify ownership
    if str(page.app.created_by) != str(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to access this page")

    return page


@router.put(
    "/micro-saas-apps/{app_id}/documentation/{page_id}",
    response_model=DocumentationPageResponse,
    summary="Update documentation page",
    description="Update an existing documentation page (owner only)"
)
async def update_documentation_page(
    app_id: str,
    page_id: str,
    updates: DocumentationPageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a documentation page"""
    try:
        page = documentation_service.update_documentation_page(
            db=db,
            page_id=page_id,
            user_id=str(current_user.user_id),
            updates=updates
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/micro-saas-apps/{app_id}/documentation/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete documentation page",
    description="Delete a documentation page (owner only)"
)
async def delete_documentation_page(
    app_id: str,
    page_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a documentation page"""
    try:
        documentation_service.delete_documentation_page(
            db=db,
            page_id=page_id,
            user_id=str(current_user.user_id)
        )
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch(
    "/micro-saas-apps/{app_id}/documentation/reorder",
    response_model=List[DocumentationPageSummary],
    summary="Reorder documentation pages",
    description="Reorder documentation pages by updating display_order (owner only)"
)
async def reorder_documentation_pages(
    app_id: str,
    reorder_data: DocumentationPageReorder,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reorder documentation pages"""
    try:
        pages = documentation_service.reorder_documentation_pages(
            db=db,
            frontend_app_id=app_id,
            user_id=str(current_user.user_id),
            reorder_data=reorder_data
        )
        return [DocumentationPageSummary.from_orm(page) for page in pages]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# PUBLIC ENDPOINTS - Marketplace Users
# ============================================================================

@router.get(
    "/marketplace/apps/{app_slug}/documentation",
    response_model=List[DocumentationPageSummary],
    summary="List public documentation pages",
    description="List published documentation pages for a marketplace app (public access)"
)
async def list_marketplace_app_documentation(
    app_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """List published documentation pages for marketplace users"""
    # Get app by public_url_slug
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.public_url_slug == app_slug
    ).first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    # Check visibility
    if app.visibility == 'private' and (not current_user or str(app.created_by) != str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This app is private")

    # Get only published pages for public view
    pages = documentation_service.get_app_documentation_pages(
        db=db,
        frontend_app_id=app.frontend_app_id,
        include_unpublished=False
    )

    return [DocumentationPageSummary.from_orm(page) for page in pages]


@router.get(
    "/marketplace/apps/{app_slug}/documentation/{page_slug}",
    response_model=DocumentationPageResponse,
    summary="Get public documentation page",
    description="Get a specific published documentation page by slug (public access)"
)
async def get_marketplace_documentation_page(
    app_slug: str,
    page_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    """Get a specific published documentation page for marketplace users"""
    # Get app by public_url_slug
    app = db.query(FrontendFlowApplication).filter(
        FrontendFlowApplication.public_url_slug == app_slug
    ).first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    # Check visibility
    if app.visibility == 'private' and (not current_user or str(app.created_by) != str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This app is private")

    # Get page by slug
    page = documentation_service.get_documentation_page_by_slug(
        db=db,
        frontend_app_id=app.frontend_app_id,
        page_slug=page_slug,
        include_unpublished=False
    )

    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documentation page not found")

    return page

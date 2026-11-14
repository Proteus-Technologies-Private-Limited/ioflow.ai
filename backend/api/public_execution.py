"""
Public Execution API

Handles public, unauthenticated access to frontend flow applications.
Provides endpoints for viewing and executing flows without IOFlow authentication.
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime
import json

from db.database import get_db
from core.config import settings

# Import models - PostgreSQL Only
from db.models import User, Tenant, Flow
from db.application_models import (
    PublishedApplication, FrontendFlowApplication
)

from services.frontend_app_service import FrontendAppService, AccessDeniedError, RateLimitExceededError
from services.execution_engine import ExecutionEngine
from services.related_flows_service import RelatedFlowsService, RelatedFlowsError
from schemas.micro_saas_schemas import PublicRelatedFlowsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public-apps", tags=["public-execution"])

# Initialize services
frontend_app_service = FrontendAppService()
related_flows_service = RelatedFlowsService()

# Pydantic models for API

class PublicExecutionRequest(BaseModel):
    """Request model for public flow execution"""
    # This will accept any key-value pairs for flow variables
    class Config:
        extra = "allow"  # Allow additional fields
    

class DocumentationPageSummary(BaseModel):
    """Summary of a documentation page for landing page rendering"""
    page_id: str
    title: str
    slug: str
    page_type: Optional[str]
    display_order: int


class PublicApplicationInfo(BaseModel):
    """Public information about a frontend application"""
    frontend_app_name: str
    description: Optional[str]
    public_url_slug: str
    manual_variables: list
    custom_styling: Optional[Dict[str, Any]]
    flow_name: str
    flow_id: Optional[str] = None
    page_definition: Optional[Dict[str, Any]] = None
    documentation_pages: Optional[list] = None


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for X-Forwarded-For header (common with proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in case of multiple IPs
        return forwarded_for.split(",")[0].strip()
    
    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "unknown")


@router.get("/{public_url_slug}/info", response_model=PublicApplicationInfo)
async def get_public_application_info(
    public_url_slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get public information about a frontend application.
    This endpoint does not require authentication but respects access controls.
    """
    try:
        # Get client info
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Get the frontend application
        frontend_app = frontend_app_service.get_frontend_application_by_slug(
            db=db,
            public_url_slug=public_url_slug
        )
        
        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Log the view access
        frontend_app_service.log_access(
            db=db,
            frontend_app_id=frontend_app["frontend_app_id"],
            ip_address=ip_address,
            user_agent=user_agent,
            access_type="view"
        )
        
        # Get the flow's manual trigger configuration
        manual_variables = []
        flow_name = "Unknown Flow"
        
        try:
            flow = None
            
            # For direct frontend apps (published_app_id is None), use flow_id directly
            if frontend_app.get("published_app_id") is None:
                # Direct frontend app - get flow directly using flow_id from frontend app
                frontend_app_record = db.query(FrontendFlowApplication).filter(
                    FrontendFlowApplication.public_url_slug == public_url_slug
                ).first()
                
                if frontend_app_record and frontend_app_record.flow_id:
                    flow = db.query(Flow).filter(Flow.flow_id == frontend_app_record.flow_id).first()
            else:
                # Traditional frontend app - get flow via published application
                published_app = db.query(PublishedApplication).filter(
                    PublishedApplication.published_app_id == frontend_app["published_app_id"]
                ).first()
                
                if published_app:
                    flow = db.query(Flow).filter(Flow.flow_id == published_app.flow_id).first()
            
            if flow:
                flow_name = flow.flow_name
                trigger_config = json.loads(flow.trigger_config) if isinstance(flow.trigger_config, str) else flow.trigger_config
                manual_variables = trigger_config.get("manual_variables", [])
        
        except Exception as e:
            logger.error(f"Error getting manual variables: {str(e)}")
            manual_variables = []
        
        # Get page_definition from the frontend app record
        page_definition = None
        doc_pages_summary = None
        frontend_app_record_for_page = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.public_url_slug == public_url_slug
        ).first()

        if frontend_app_record_for_page:
            raw_page_def = frontend_app_record_for_page.page_definition
            if raw_page_def:
                page_definition = json.loads(raw_page_def) if isinstance(raw_page_def, str) else raw_page_def

            # Get published documentation pages for landing page rendering
            if frontend_app_record_for_page.documentation_pages:
                from db.application_models import AppDocumentationPage
                doc_pages = db.query(AppDocumentationPage).filter(
                    AppDocumentationPage.frontend_app_id == frontend_app_record_for_page.frontend_app_id,
                    AppDocumentationPage.is_published == True
                ).order_by(AppDocumentationPage.display_order).all()
                doc_pages_summary = [
                    {
                        "page_id": p.page_id,
                        "title": p.page_title or p.title,
                        "slug": p.page_slug or p.slug,
                        "page_slug": p.page_slug or p.slug,
                        "page_type": p.page_type,
                        "display_order": p.display_order
                    }
                    for p in doc_pages
                ]

        return PublicApplicationInfo(
            frontend_app_name=frontend_app["frontend_app_name"],
            description=frontend_app.get("description"),
            public_url_slug=public_url_slug,
            manual_variables=manual_variables,
            custom_styling=frontend_app.get("custom_styling", {}),
            flow_name=flow_name,
            flow_id=frontend_app.get("flow_id"),
            page_definition=page_definition,
            documentation_pages=doc_pages_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting public application info for slug '{public_url_slug}': "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application information"
        )


@router.get("/{public_url_slug}/executions")
async def list_public_executions(
    public_url_slug: str,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List execution history for a public application.
    No authentication required. Only returns executions for the specific flow.
    """
    try:
        from db.database import get_tenant_db
        from db.models import FlowExecution, ExecutionStatus, Tenant

        # Get the frontend application
        frontend_app = frontend_app_service.get_frontend_application_by_slug(
            db=db, public_url_slug=public_url_slug
        )
        if not frontend_app:
            raise HTTPException(status_code=404, detail="Application not found")

        # Resolve flow_id — same logic as the /info endpoint
        flow = None
        if frontend_app.get("published_app_id") is None:
            # Direct frontend app - get flow_id from FrontendFlowApplication record
            frontend_app_record = db.query(FrontendFlowApplication).filter(
                FrontendFlowApplication.public_url_slug == public_url_slug
            ).first()
            if frontend_app_record and frontend_app_record.flow_id:
                flow = db.query(Flow).filter(Flow.flow_id == frontend_app_record.flow_id).first()
        else:
            # Traditional frontend app - get flow via published application
            published_app = db.query(PublishedApplication).filter(
                PublishedApplication.published_app_id == frontend_app["published_app_id"]
            ).first()
            if published_app:
                flow = db.query(Flow).filter(Flow.flow_id == published_app.flow_id).first()

        if not flow:
            logger.warning(f"[public-executions] No flow found for {public_url_slug}")
            return {"executions": [], "total": 0}

        flow_id = flow.flow_id

        # Get tenant schema name
        schema_name = "ioflow"
        if flow.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.tenant_id == flow.tenant_id).first()
            if tenant and tenant.schema_name:
                schema_name = tenant.schema_name

        with get_tenant_db(schema_name) as tenant_db:
            query = tenant_db.query(FlowExecution).filter(
                FlowExecution.flow_id == flow_id
            )

            if status_filter and status_filter != 'all':
                try:
                    query = query.filter(FlowExecution.status == ExecutionStatus(status_filter.lower()))
                except ValueError:
                    pass

            total = query.count()
            executions = query.order_by(
                FlowExecution.started_at.desc()
            ).offset(offset).limit(min(limit, 50)).all()

            return {
                "executions": [
                    {
                        "execution_id": ex.execution_id,
                        "flow_id": ex.flow_id,
                        "status": ex.status.value if hasattr(ex.status, 'value') else str(ex.status),
                        "trigger_type": ex.trigger_type,
                        "started_at": ex.started_at.isoformat() if ex.started_at else None,
                        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
                    }
                    for ex in executions
                ],
                "total": total
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing public executions for {public_url_slug}: {str(e)}", exc_info=True)
        return {"executions": [], "total": 0}


class ProxyDropdownRequest(BaseModel):
    """Request model for proxying dropdown API calls"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None


# Simple in-memory rate limiter for proxy-dropdown
_proxy_rate_limit: Dict[str, list] = {}

@router.post("/{public_url_slug}/proxy-dropdown")
async def proxy_dropdown_api(
    public_url_slug: str,
    proxy_request: ProxyDropdownRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Proxy REST API calls for landing page dynamic dropdowns.
    Rate-limited to 10 requests per minute per IP.
    """
    import httpx
    from datetime import datetime, timedelta

    ip = get_client_ip(request)

    # Rate limiting: 10 requests/minute per IP
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=1)
    if ip not in _proxy_rate_limit:
        _proxy_rate_limit[ip] = []
    _proxy_rate_limit[ip] = [t for t in _proxy_rate_limit[ip] if t > cutoff]
    if len(_proxy_rate_limit[ip]) >= 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 10 dropdown requests per minute.")
    _proxy_rate_limit[ip].append(now)

    # Verify the app exists
    frontend_app = frontend_app_service.get_frontend_application_by_slug(db=db, public_url_slug=public_url_slug)
    if not frontend_app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Validate URL - block private IPs
    from urllib.parse import urlparse
    parsed = urlparse(proxy_request.url)
    if not parsed.scheme or parsed.scheme not in ('http', 'https'):
        raise HTTPException(status_code=400, detail="Only http and https URLs are allowed")
    if parsed.hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        raise HTTPException(status_code=400, detail="Local addresses are not allowed")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if proxy_request.method.upper() == "GET":
                resp = await client.get(
                    proxy_request.url,
                    headers=proxy_request.headers or {},
                    params=proxy_request.params or {}
                )
            else:
                resp = await client.post(
                    proxy_request.url,
                    headers=proxy_request.headers or {},
                    params=proxy_request.params or {},
                    json=proxy_request.body
                )
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return {"status_code": resp.status_code, "data": data}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream API timed out")
    except Exception as e:
        logger.error(f"Proxy dropdown error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch from upstream API: {str(e)}")


@router.post("/{public_url_slug}/execute")
async def execute_public_application(
    public_url_slug: str,
    execution_data: Dict[str, Any],  # Accept any JSON data
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Execute a public frontend application.
    This endpoint does not require authentication but respects access controls and rate limits.
    """
    execution_start_time = datetime.now()
    
    try:
        # Get client info
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Get the frontend application
        frontend_app = frontend_app_service.get_frontend_application_by_slug(
            db=db,
            public_url_slug=public_url_slug
        )
        
        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Check if application is active
        frontend_app_record = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app["frontend_app_id"]
        ).first()
        
        if not frontend_app_record or not frontend_app_record.is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application is currently unavailable"
            )
        
        # Check rate limits
        if not frontend_app_service.check_rate_limit(
            db=db,
            frontend_app_id=frontend_app["frontend_app_id"],
            ip_address=ip_address
        ):
            # Log the rate limit exceeded attempt
            frontend_app_service.log_access(
                db=db,
                frontend_app_id=frontend_app["frontend_app_id"],
                ip_address=ip_address,
                user_agent=user_agent,
                access_type="execute",
                execution_success=False,
                error_message="Rate limit exceeded"
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Validate access permissions
        # For now, we'll implement basic access control
        # In a full implementation, you might need to authenticate users for certain access types
        access_permitted = frontend_app_service.validate_access_permission(
            db=db,
            frontend_app=frontend_app,
            ip_address=ip_address,
            user_id=None,  # No authentication required for public access
            tenant_id=None
        )
        
        if not access_permitted:
            # Log the access denied attempt
            frontend_app_service.log_access(
                db=db,
                frontend_app_id=frontend_app["frontend_app_id"],
                ip_address=ip_address,
                user_agent=user_agent,
                access_type="execute",
                execution_success=False,
                error_message="Access denied"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You don't have permission to execute this application."
            )
        
        # Get the flow for execution
        try:
            flow = None
            
            # For direct frontend apps (published_app_id is None), use flow_id directly
            if frontend_app.get("published_app_id") is None:
                # Direct frontend app - get flow directly using flow_id from frontend app
                frontend_app_record = db.query(FrontendFlowApplication).filter(
                    FrontendFlowApplication.public_url_slug == public_url_slug
                ).first()
                
                if frontend_app_record and frontend_app_record.flow_id:
                    flow = db.query(Flow).filter(Flow.flow_id == frontend_app_record.flow_id).first()
            else:
                # Traditional frontend app - get flow via published application
                published_app = db.query(PublishedApplication).filter(
                    PublishedApplication.published_app_id == frontend_app["published_app_id"]
                ).first()
                
                if not published_app:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Published application not found"
                    )
                
                flow = db.query(Flow).filter(Flow.flow_id == published_app.flow_id).first()
            
            if not flow:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Source flow not found"
                )
            
            # TODO: For now, use the manual trigger API to get real execution
            # This is a temporary solution until we integrate the execution engine properly
            
            # Try to execute using the manual trigger API (internal call)
            try:
                logger.info(f"Attempting to execute flow {flow.flow_id} via internal manual trigger API")
                
                # Get a valid user for internal execution
                # Try multiple fallbacks to find an appropriate execution user
                execution_user = None
                
                # First, try to use the flow owner
                if flow.created_by:
                    execution_user = db.query(User).filter(User.user_id == flow.created_by).first()
                
                # If flow owner doesn't exist, try to find an admin in the same tenant
                if not execution_user:
                    logger.warning(f"Flow owner {flow.created_by} not found, looking for tenant admin")
                    execution_user = db.query(User).filter(
                        User.tenant_id == flow.tenant_id,
                        User.role.in_(["INSTANCE_ADMIN", "TENANT_ADMIN"]),
                        User.is_active == True
                    ).first()
                
                # If no tenant admin, try any active admin
                if not execution_user:
                    logger.warning(f"No tenant admin found for tenant {flow.tenant_id}, looking for any admin")
                    execution_user = db.query(User).filter(
                        User.role.in_(["INSTANCE_ADMIN", "TENANT_ADMIN"]),
                        User.is_active == True
                    ).first()
                
                if not execution_user:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="No valid user found to execute this flow"
                    )
                
                logger.info(f"Using execution user: {execution_user.email} (role: {execution_user.role})")
                
                # Execute the flow using internal ASYNCHRONOUS execution
                # This allows WebSocket streaming of progress
                try:
                    from db.database import get_tenant_db
                    from db.models import FlowExecution, ExecutionStatus

                    # Get tenant info - CRITICAL: Use flow's tenant_id to ensure WebSocket receives messages
                    schema_name = "main"  # Default to main schema for now
                    # Use flow's tenant_id instead of execution_user's to ensure WebSocket connection matches
                    tenant_id = flow.tenant_id or "main"

                    logger.info(f"Executing flow {flow.flow_id} for public app {public_url_slug}")
                    logger.info(f"Using tenant_id: {tenant_id} (from flow)")
                    logger.info(f"Execution data: {execution_data}")

                    # Create execution record first
                    execution_id = None
                    with get_tenant_db(schema_name) as tenant_db:
                        execution = FlowExecution(
                            flow_id=flow.flow_id,
                            trigger_type="public",
                            trigger_data={
                                "variables": execution_data,
                                "public_execution": True
                            },
                            status=ExecutionStatus.RUNNING,  # Use RUNNING instead of PENDING
                            execution_data={'public_execution': True}
                        )
                        tenant_db.add(execution)
                        tenant_db.commit()
                        execution_id = execution.execution_id

                    logger.info(f"Created execution record: {execution_id}")

                    # Create execution engine with execution user context
                    # CRITICAL: Use flow's tenant_id to match WebSocket subscription
                    engine = ExecutionEngine(
                        tenant_schema=schema_name,
                        tenant_id=tenant_id,  # This now matches flow.tenant_id
                        user_id=execution_user.user_id
                    )

                    # Prepare trigger data with proper structure
                    trigger_data = {
                        "variables": execution_data,
                        "direct_execution": True,
                        "user_id": execution_user.user_id,
                        "tenant_id": tenant_id,
                        "public_execution": True  # Flag to indicate this is a public execution
                    }

                    # Execute flow in background with proper async handling
                    async def run_flow_execution():
                        """Wrapper to ensure proper async execution"""
                        logger.info(f"🚀 BACKGROUND TASK STARTED for execution {execution_id}")
                        logger.info(f"   Execution tenant_id: {tenant_id}")
                        logger.info(f"   Execution schema: {schema_name}")

                        # CRITICAL: Wait for WebSocket to connect before starting execution
                        # This prevents race condition where execution starts before WebSocket subscribes
                        import asyncio
                        logger.info(f"Waiting 500ms for WebSocket to connect...")
                        await asyncio.sleep(0.5)
                        logger.info(f"Starting execution after WebSocket delay")
                        logger.info(f"Checking WebSocket connections...")
                        from services.websocket_manager import manager
                        stats = manager.get_connection_stats()
                        logger.info(f"WebSocket stats: {stats}")

                        try:
                            logger.info(f"Calling execute_flow_with_id for flow {flow.flow_id}")
                            await engine.execute_flow_with_id(
                                flow_id=flow.flow_id,
                                execution_id=execution_id,
                                trigger_data=trigger_data,
                                trigger_type="public"
                            )
                            logger.info(f"✓ execute_flow_with_id completed for execution {execution_id}")
                        except Exception as e:
                            logger.error(f"✗ Public flow execution failed: {e}", exc_info=True)
                            # Update execution status in database
                            with get_tenant_db(schema_name) as tenant_db:
                                execution = tenant_db.query(FlowExecution).filter(
                                    FlowExecution.execution_id == execution_id
                                ).first()
                                if execution:
                                    execution.status = ExecutionStatus.FAILED
                                    execution.error_message = str(e)
                                    tenant_db.commit()
                                    logger.error(f"Updated execution {execution_id} status to FAILED")

                    # Add to background tasks - this ensures it actually runs!
                    logger.info(f"Adding background task for execution {execution_id}")
                    background_tasks.add_task(run_flow_execution)
                    logger.info(f"✓ Background task added for execution {execution_id}")

                    # Return execution ID immediately for WebSocket connection
                    result = {
                        "success": True,
                        "execution_id": execution_id,
                        "message": "Execution started"
                    }
                
                except Exception as execution_error:
                    logger.error(f"Flow execution failed: {str(execution_error)}")
                    import traceback
                    logger.error(f"Execution traceback: {traceback.format_exc()}")

                    result = {
                        "success": False,
                        "error": f"Flow execution failed: {str(execution_error)}"
                    }

            except Exception as e:
                logger.error(f"Flow execution setup failed: {str(e)}")
                result = {
                    "success": False,
                    "error": f"Flow execution setup failed: {str(e)}"
                }

            execution_success = result.get("success", False)
            execution_time_ms = int((datetime.now() - execution_start_time).total_seconds() * 1000)

            # Log the execution start (async execution)
            frontend_app_service.log_access(
                db=db,
                frontend_app_id=frontend_app["frontend_app_id"],
                ip_address=ip_address,
                user_agent=user_agent,
                access_type="execute",
                execution_success=execution_success,
                execution_time_ms=execution_time_ms,
                error_message=result.get("error") if not execution_success else None
            )

            # Return the result
            # For async execution, return execution_id immediately
            if "execution_id" in result:
                return {
                    "success": True,
                    "execution_id": result["execution_id"],
                    "message": "Execution started - connect to WebSocket for real-time updates"
                }
            elif execution_success:
                # Fallback for synchronous execution (shouldn't happen now)
                return {
                    "success": True,
                    "data": result.get("data"),
                    "execution_time_ms": execution_time_ms,
                    "message": "Execution completed successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Execution failed"),
                    "execution_time_ms": execution_time_ms
                }
                
        except Exception as e:
            execution_time_ms = int((datetime.now() - execution_start_time).total_seconds() * 1000)
            error_message = str(e)
            
            # Log the failed execution
            frontend_app_service.log_access(
                db=db,
                frontend_app_id=frontend_app["frontend_app_id"],
                ip_address=ip_address,
                user_agent=user_agent,
                access_type="execute",
                execution_success=False,
                execution_time_ms=execution_time_ms,
                error_message=error_message
            )
            
            logger.error(f"Flow execution error for public app {public_url_slug}: {error_message}")
            
            return {
                "success": False,
                "error": "Execution failed due to internal error",
                "execution_time_ms": execution_time_ms
            }
        
    except HTTPException:
        raise
    except Exception as e:
        execution_time_ms = int((datetime.now() - execution_start_time).total_seconds() * 1000)
        logger.error(f"Unexpected error in public execution: {str(e)}")
        
        # Try to log the error if we have the frontend app ID
        try:
            if 'frontend_app' in locals() and frontend_app:
                frontend_app_service.log_access(
                    db=db,
                    frontend_app_id=frontend_app["frontend_app_id"],
                    ip_address=ip_address,
                    user_agent=user_agent,
                    access_type="execute",
                    execution_success=False,
                    execution_time_ms=execution_time_ms,
                    error_message=str(e)
                )
        except:
            pass  # Don't let logging errors prevent the response
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during execution"
        )


@router.get("/{public_url_slug}/validate")
async def validate_public_access(
    public_url_slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Validate if public access is allowed for an application.
    This endpoint can be used by embed code to check access before showing the form.
    """
    try:
        # Get client info
        ip_address = get_client_ip(request)
        
        # Get the frontend application
        frontend_app = frontend_app_service.get_frontend_application_by_slug(
            db=db,
            public_url_slug=public_url_slug
        )
        
        if not frontend_app:
            return {
                "valid": False,
                "reason": "Application not found"
            }
        
        # Check if application is active
        frontend_app_record = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.frontend_app_id == frontend_app["frontend_app_id"]
        ).first()
        
        if not frontend_app_record or not frontend_app_record.is_active:
            return {
                "valid": False,
                "reason": "Application is not active"
            }
        
        # Check rate limits
        if not frontend_app_service.check_rate_limit(
            db=db,
            frontend_app_id=frontend_app["frontend_app_id"],
            ip_address=ip_address
        ):
            return {
                "valid": False,
                "reason": "Rate limit exceeded"
            }
        
        # Validate access permissions
        access_permitted = frontend_app_service.validate_access_permission(
            db=db,
            frontend_app=frontend_app,
            ip_address=ip_address,
            user_id=None,
            tenant_id=None
        )
        
        if not access_permitted:
            return {
                "valid": False,
                "reason": "Access denied"
            }
        
        return {
            "valid": True,
            "reason": "Access permitted"
        }
        
    except Exception as e:
        logger.error(f"Error validating public access: {str(e)}")
        return {
            "valid": False,
            "reason": "Validation error"
        }


@router.get("/{public_url_slug}/related-flows", response_model=PublicRelatedFlowsResponse)
async def get_public_related_flows(
    public_url_slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get related flows (prerequisites and follow-ups) for a public application.

    This endpoint does not require authentication and returns information needed
    to display prerequisites before execution and follow-ups after completion.
    """
    try:
        # Get client info for rate limiting/logging
        ip_address = get_client_ip(request)

        # Get the frontend application first to validate it exists
        frontend_app = frontend_app_service.get_frontend_application_by_slug(
            db=db,
            public_url_slug=public_url_slug
        )

        if not frontend_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )

        # Get related flows using the service
        result = related_flows_service.get_public_related_flows_info(
            db=db,
            public_url_slug=public_url_slug
        )

        return result

    except RelatedFlowsError as e:
        logger.error(f"Error getting related flows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting related flows for {public_url_slug}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching related flows"
        )


# Health check endpoint for public applications
@router.get("/health")
async def public_apps_health():
    """Health check endpoint for public applications service"""
    return {
        "status": "healthy",
        "service": "public-applications",
        "timestamp": datetime.now().isoformat()
    }
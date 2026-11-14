from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
import logging
import uvicorn
import os
from pathlib import Path

from core.config import settings
from db.database import init_db, get_db
from db.application_models import ApplicationEvent
from db.documentation_models import AppDocumentationPage  # Register documentation models
from api import auth, applications, flows, flow_design, flow_design_editor, executions, debug_endpoints, oauth2_callback, oauth2_revoke, pricing, billing, usage, seed_applications, tenants, users, api_keys, mcp_bridge, websockets, ai_settings, flow_publishing, frontend_applications, public_execution, google_oauth, polling, collaboration, subscription_preferences, ui_preferences, flow_examples, micro_saas_apps, marketplace, app_documentation, onboarding, hitl, event_wait, tenant_seed_applications
from dev_agent_runtime.api_routes import router as assistant_router
from routes import logs
from services.webhook_handler import router as webhook_router, api_router as event_api_router, handle_api_call_trigger
from services.webhook_handler_simple import simple_api_router
from services.test_endpoint import test_router
from services.scheduler import flow_scheduler
from services.file_watcher import file_watcher_service
from services.polling_service import api_polling_service
from services.email_polling_service import email_polling_service
from services.generic_polling_service import service_polling_service
from services.oauth2_service import OAuth2Service
from services.background_manager import BackgroundServiceManager, set_background_manager
import asyncio
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="IOFlow API",
    description="Integration platform for connecting applications with easy and reliable workflows",
    version="1.0.0"
)

# Custom exception handler to return error fields at root level
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # Check if the detail is already a dict with error structure
    if isinstance(exc.detail, dict) and 'error' in exc.detail:
        # Return the error fields at root level
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    else:
        # Standard error format with fields at root
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": str(exc.detail),
                "type": "http_error",
                "status_code": exc.status_code
            }
        )


# Validation error handler for detailed Pydantic validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with detailed field-level error messages
    """
    errors = exc.errors()

    # Log detailed validation error
    logger.error(f"Validation error on {request.method} {request.url.path}")
    logger.error(f"Request body: {await request.body()}")
    logger.error(f"Validation errors: {errors}")

    # Format errors for user-friendly display
    error_messages = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"]
        error_type = error["type"]

        # Create user-friendly message
        if error_type == "value_error.missing":
            error_messages.append(f"Field '{field}' is required but missing")
        elif error_type == "type_error":
            error_messages.append(f"Field '{field}' has incorrect type: {message}")
        elif "extra" in error_type:
            error_messages.append(f"Unknown field '{field}' - this field is not allowed")
        else:
            error_messages.append(f"Field '{field}': {message}")

    detailed_message = "; ".join(error_messages) if error_messages else "Request validation failed"

    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": f"Validation error: {detailed_message}",
            "type": "validation_error",
            "status_code": 422,
            "details": errors
        }
    )

# OAuth state cleanup task
oauth_cleanup_task = None

# Background service manager
background_manager = None

async def cleanup_oauth_states():
    """Periodically clean up expired OAuth states"""
    while True:
        try:
            from db.database import get_db_context
            with get_db_context() as db:
                count = OAuth2Service.cleanup_expired_states(db)
                if count > 0:
                    logger.info(f"Cleaned up {count} expired OAuth states")
        except Exception as e:
            logger.error(f"Error cleaning up OAuth states: {str(e)}")
        
        # Wait for the configured interval
        await asyncio.sleep(settings.oauth_cleanup_interval_minutes * 60)

# Configure CORS
# Parse allowed_origins from settings or use defaults
allowed_origins = []
if settings.allowed_origins:
    allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
else:
    # Default origins including the domain
    allowed_origins = [
        "http://localhost:7001",
        "http://localhost:3000", 
        "http://localhost:5173",
        "https://localhost:7001",
        "https://127.0.0.1:7001",
        settings.app_url
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")

    logger.info("Patching execution engine for cost tracking...")
    from services.execution_engine_cost_finalization_patch import apply_cost_finalization_patch
    apply_cost_finalization_patch()
    logger.info("Execution engine patched successfully")

    # Generate worker ID (could be from environment variable or config)
    worker_id = os.getenv('WORKER_ID') or f"worker-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting worker with ID: {worker_id}")

    # Initialize and start background service manager
    logger.info("Initializing background service manager...")
    global background_manager
    background_manager = BackgroundServiceManager(worker_id)
    set_background_manager(background_manager)
    await background_manager.start()
    logger.info("Background service manager started successfully")

    # Note: All polling services (api, service, email) are now managed by BackgroundServiceManager
    # with leader election to prevent duplicate executions

    logger.info("Starting OAuth state cleanup task...")
    global oauth_cleanup_task
    oauth_cleanup_task = asyncio.create_task(cleanup_oauth_states())
    logger.info("OAuth state cleanup task started successfully")

    # Discover and register plugins
    logger.info("Discovering plugins...")
    from plugins import discover_plugins
    from plugins.registry import PluginRegistry
    discover_plugins()
    logger.info("Plugin discovery completed")

    # Auto-register plugin-provided routers
    plugin_routers = PluginRegistry.get_routers()
    for plugin_router in plugin_routers:
        app.include_router(plugin_router)
        logger.info(f"Registered plugin router: {getattr(plugin_router, 'prefix', 'unknown')}")
    if plugin_routers:
        logger.info(f"Registered {len(plugin_routers)} plugin routers")

    # Re-initialize webhook verification service with registry verifiers
    from services.webhook_verification import webhook_verification_service, WebhookVerificationService
    webhook_verification_service.__init__()

    # Start database message queue for multi-worker WebSocket support
    logger.info("Starting database message queue...")
    from services.db_message_queue import db_message_queue
    await db_message_queue.start()
    logger.info("Database message queue started successfully")

    # Start HITL escalation scheduler
    logger.info("Starting HITL escalation scheduler...")
    from services.hitl_escalation_scheduler import start_scheduler as start_hitl_scheduler
    asyncio.create_task(start_hitl_scheduler())
    logger.info("HITL escalation scheduler started successfully")

    # Start Event Wait timeout scheduler
    logger.info("Starting Event Wait timeout scheduler...")
    from services.event_wait_scheduler import start_scheduler as start_event_wait_scheduler
    asyncio.create_task(start_event_wait_scheduler())
    logger.info("Event Wait timeout scheduler started successfully")

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping background service manager...")
    global background_manager
    if background_manager:
        await background_manager.stop()
    logger.info("Background service manager stopped")

    # Note: All polling services are now stopped by BackgroundServiceManager

    logger.info("Stopping OAuth state cleanup task...")
    global oauth_cleanup_task
    if oauth_cleanup_task:
        oauth_cleanup_task.cancel()
        try:
            await oauth_cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("OAuth state cleanup task stopped")

    # Stop database message queue
    logger.info("Stopping database message queue...")
    from services.db_message_queue import db_message_queue
    await db_message_queue.stop()
    logger.info("Database message queue stopped")

# Include routers
app.include_router(auth.router)
app.include_router(google_oauth.router)
logger.info(f"Including tenants router: {tenants.router}")
app.include_router(tenants.router)
logger.info(f"Including users router: {users.router}")
app.include_router(users.router)
app.include_router(applications.router)
app.include_router(flows.router)
app.include_router(flow_examples.router)  # Flow Examples API
app.include_router(flow_design.router)
app.include_router(flow_design_editor.router)  # Flow Design Editor API
app.include_router(executions.router)
app.include_router(collaboration.router)
app.include_router(polling.router)
app.include_router(webhook_router)
app.include_router(event_api_router)
app.include_router(test_router)
app.include_router(debug_endpoints.router)
app.include_router(oauth2_callback.router)
app.include_router(oauth2_revoke.router)
app.include_router(pricing.router)
app.include_router(billing.router)
app.include_router(usage.router, prefix="/api/v1/tenant", tags=["usage"])
app.include_router(subscription_preferences.router)
app.include_router(seed_applications.router)
app.include_router(tenant_seed_applications.router)  # A tenant's own seed applications
app.include_router(api_keys.router)
app.include_router(ai_settings.router)
app.include_router(ui_preferences.router)
app.include_router(onboarding.router)
app.include_router(mcp_bridge.router)
app.include_router(websockets.router)
app.include_router(flow_publishing.router)
app.include_router(frontend_applications.router)
app.include_router(micro_saas_apps.router)  # Micro SaaS Apps Management API
app.include_router(marketplace.router)  # Marketplace API for app discovery and subscriptions
app.include_router(app_documentation.router)  # App Documentation Pages API
app.include_router(public_execution.router)
app.include_router(hitl.router)  # Human in the Loop API
app.include_router(event_wait.router)  # Event Wait API
app.include_router(logs.router)

# SMTP configuration and password management
from api.smtp_config import router as smtp_config_router
from api.password_management import router as password_management_router
from api.invitations import router as invitations_router
app.include_router(smtp_config_router)
app.include_router(password_management_router)
app.include_router(invitations_router)

# Direct frontend publishing
from api.direct_frontend_publishing import router as direct_frontend_publishing
from api.flow_agents import router as flow_agents
from api.claude_code_agent import router as claude_code_agent
app.include_router(direct_frontend_publishing, prefix="/api/v1/direct-frontend-publishing", tags=["Direct Frontend Publishing"])
app.include_router(flow_agents, prefix="/api/v1/flow-agents", tags=["Flow Agents"])
app.include_router(claude_code_agent, prefix="/api/v1/claude-code-agent", tags=["Claude Code Agent"])

# Plugin Schemas API
from api.plugin_schemas import router as plugin_schemas_router
app.include_router(plugin_schemas_router)

# IOFlow Assistant - Development Agent Runtime
app.include_router(assistant_router, tags=["IOFlow Assistant"])

# Serve uploaded landing page images
uploads_dir = Path(__file__).parent / "uploads" / "landing-pages"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/landing-pages", StaticFiles(directory=str(uploads_dir)), name="landing-page-uploads")

# Serve static files if they exist
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount static assets
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")
    
    # Mount other static files (like favicon, manifest, etc)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static-files")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "IOFlow API"}

# Root endpoint - redirect to index.html if static files exist
@app.get("/")
async def root():
    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        return FileResponse(str(static_index))
    return {
        "message": "Welcome to IOFlow API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Custom API endpoint handler for /api/custom/* routes
@app.api_route("/api/custom/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def handle_custom_api_endpoint(
    path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle custom API endpoints defined in events"""
    # Check if this path matches any custom API endpoint
    event = db.query(ApplicationEvent).filter(
        ApplicationEvent.api_endpoint == f"/api/custom/{path}",
        ApplicationEvent.event_type == "api_call",
        ApplicationEvent.is_active == True
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Custom endpoint not found")

    # Route to the API call handler with the app_id and event_name
    return await handle_api_call_trigger(
        app_id=event.app_id,
        event_name=event.event_name,
        request=request,
        db=db
    )

# Serve SPA for all other routes (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve the React SPA for all non-API routes"""
    # Explicitly return 404 for non-existent API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # Serve index.html if it exists for non-API routes
    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        return FileResponse(str(static_index))

    # If no static files, return 404
    raise HTTPException(status_code=404, detail="Frontend not built. Run build_complete_distribution.sh first.")

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=7001,
        reload=True
    )
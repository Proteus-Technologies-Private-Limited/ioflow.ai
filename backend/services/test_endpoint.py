from fastapi import APIRouter, Request
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Create a very simple test router
test_router = APIRouter(prefix="/api/v1/test", tags=["test"])

@test_router.post("/events/{app_id}/{event_name}")
async def test_api_call_trigger(
    app_id: str,
    event_name: str,
    request: Request
):
    """Very simple test endpoint without database dependencies."""
    try:
        logger.info(f"Test API call received: app_id={app_id}, event_name={event_name}")
        
        # Get request body
        try:
            if hasattr(request, '_body'):
                body = json.loads(request._body)
            else:
                body = await request.json()
        except Exception as e:
            body = {"error": f"Could not parse body: {str(e)}"}
        
        # Extract API key - prefer standard Bearer token format
        api_key = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # Fallback to x-api-key for backward compatibility
        if not api_key:
            api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        
        return {
            "success": True,
            "message": "Test endpoint working",
            "app_id": app_id,
            "event_name": event_name,
            "body": body,
            "api_key_present": bool(api_key),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Test endpoint failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
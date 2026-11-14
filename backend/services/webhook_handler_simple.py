from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
from typing import Dict, Any
from datetime import datetime
import json

from db.database import get_db

logger = logging.getLogger(__name__)

# Create a simple API router for testing
simple_api_router = APIRouter(prefix="/api/v1/events", tags=["events"])

@simple_api_router.post("/{app_id}/{event_name}")
async def handle_api_call_trigger_simple(
    app_id: str,
    event_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Simple API call trigger handler for testing."""
    try:
        logger.info(f"API call trigger received: app_id={app_id}, event_name={event_name}")
        
        # Get request body
        try:
            if hasattr(request, '_body'):
                body = json.loads(request._body)
            else:
                body = await request.json()
            logger.info(f"Request body parsed successfully: {body}")
        except Exception as e:
            logger.error(f"Failed to parse request body: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        # Extract API key from headers
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if not api_key:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header[7:]
        
        logger.info(f"API key extracted: {'[PRESENT]' if api_key else '[NONE]'}")
        
        # Return success response
        return {
            "success": True,
            "message": f"API call received for {app_id}/{event_name}",
            "received_data": body,
            "api_key_present": bool(api_key),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API call processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
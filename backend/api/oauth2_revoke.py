"""
OAuth2 Token Revocation Handler
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
import json
import logging

from db.database import get_db
from api.auth import get_current_user
from db.application_models import Application, ApplicationSubscription
from utils.crypto_utils import decrypt_credentials, encrypt_credentials

router = APIRouter(prefix="/api/v1/oauth2", tags=["oauth2"])
logger = logging.getLogger(__name__)


@router.post("/revoke/{app_id}")
async def revoke_oauth2_token(
    app_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Revoke OAuth2 tokens for an application"""
    # Get application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if app.auth_type != 'oauth2':
        raise HTTPException(status_code=400, detail="Application does not use OAuth2")
    
    # Get subscription
    subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.app_id == app_id,
        ApplicationSubscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not subscription or not subscription.auth_credentials:
        raise HTTPException(status_code=404, detail="No active connection found")
    
    # Decrypt credentials
    try:
        creds = decrypt_credentials(subscription.auth_credentials)
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to decrypt credentials")
    
    # Get the token to revoke (prefer refresh token, fallback to access token)
    token_to_revoke = creds.get('refresh_token') or creds.get('access_token')
    if not token_to_revoke:
        # No tokens to revoke, just clear the credentials
        creds.pop('access_token', None)
        creds.pop('refresh_token', None)
        creds.pop('expires_at', None)
        subscription.auth_credentials = encrypt_credentials(creds)
        db.commit()
        return {"success": True, "message": "Tokens cleared locally"}
    
    # Provider-specific revocation
    revoked = False
    if app.app_name == "Google Sheets":
        # Google OAuth2 revocation endpoint
        revoke_url = "https://oauth2.googleapis.com/revoke"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    revoke_url,
                    data={"token": token_to_revoke},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully revoked Google OAuth2 token for {app.app_name}")
                    revoked = True
                else:
                    logger.warning(f"Google token revocation returned status {response.status_code}: {response.text}")
                    # Even if revocation fails, we'll clear local tokens
                    
        except Exception as e:
            logger.error(f"Failed to revoke Google OAuth2 token: {str(e)}")
            # Continue to clear local tokens even if revocation fails
    
    # Clear tokens from local storage
    creds.pop('access_token', None)
    creds.pop('refresh_token', None)
    creds.pop('expires_at', None)
    creds.pop('id_token', None)  # Also clear ID token if present
    
    # Keep client credentials but clear tokens
    subscription.auth_credentials = encrypt_credentials(creds)
    db.commit()
    
    return {
        "success": True,
        "message": f"Tokens {'revoked and' if revoked else ''} cleared successfully",
        "revoked_remotely": revoked
    }


@router.post("/force-reconnect/{app_id}")
async def force_reconnect_oauth2(
    app_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Force reconnect by revoking tokens and returning authorization URL"""
    # First revoke existing tokens
    try:
        await revoke_oauth2_token(app_id, db, current_user)
    except HTTPException as e:
        if e.status_code != 404:  # Ignore "no active connection" error
            raise
    
    # Get application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Return info for reconnection
    return {
        "success": True,
        "message": "Tokens revoked. Please reconnect using OAuth2.",
        "next_step": "Use the 'Connect with OAuth2' button to establish a new connection"
    }
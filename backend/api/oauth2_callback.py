"""
OAuth2 Callback Handler for Application Connections
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import httpx
import json
from datetime import datetime, timedelta
from typing import Optional
import logging
from urllib.parse import urlparse

from db.database import get_db
from api.auth import get_current_user_optional
from db.application_models import Application, ApplicationSubscription, OAuthState
from utils.crypto_utils import encrypt_credentials, decrypt_credentials, mask_sensitive_data
from services.oauth2_service import OAuth2Service
from core.config import settings
import secrets
import uuid

router = APIRouter(prefix="/api/v1/oauth2", tags=["oauth2"])
logger = logging.getLogger(__name__)


def get_oauth2_redirect_url(redirect_uri: str, auth_status: str, **params) -> str:
    """Build OAuth2 callback redirect URL"""
    # Extract base URL from redirect_uri
    parsed_uri = urlparse(redirect_uri)
    base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
    
    # Build query parameters
    query_params = [f"auth={auth_status}"]
    for key, value in params.items():
        if value is not None:
            query_params.append(f"{key}={value}")
    
    query_string = "&".join(query_params)
    return f"{base_url}/oauth2/callback?{query_string}"


@router.get("/authorize")
async def initiate_oauth2(
    app_id: str,
    redirect_uri: str = Query(..., description="Frontend URL to redirect after auth"),
    webhook_url: Optional[str] = Query(None, description="Webhook URL for the subscription"),
    use_custom_credentials: bool = Query(False, description="Whether to use custom credentials"),
    client_id: Optional[str] = Query(None, description="Custom client ID"),
    client_secret: Optional[str] = Query(None, description="Custom client secret"),
    subscription_config: Optional[str] = Query(None, description="JSON-encoded subscription config"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Initiate OAuth2 authorization flow"""

    # Get application
    app = db.query(Application).filter(Application.app_id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if app.auth_type != 'oauth2':
        raise HTTPException(status_code=400, detail="Application does not use OAuth2")
    
    auth_config = json.loads(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
    
    logger.info(f"OAuth2 authorize for app {app.app_name} (ID: {app_id})")
    logger.info(f"Auth config type: {type(auth_config)}")
    logger.info(f"Has default_credentials: {'default_credentials' in auth_config}")
    
    # Determine which credentials to use
    oauth_client_id = None
    oauth_client_secret = None
    
    if use_custom_credentials:
        # Use provided custom credentials
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=400,
                detail="Custom client ID and secret are required when use_custom_credentials is true"
            )
        oauth_client_id = client_id
        oauth_client_secret = client_secret
    else:
        # Check for default credentials in app config
        default_creds = auth_config.get('default_credentials', {})
        logger.info(f"Default creds found: {bool(default_creds)}")
        logger.info(f"Default creds has client_id: {bool(default_creds.get('client_id'))}")
        logger.info(f"Default creds has client_secret: {bool(default_creds.get('client_secret'))}")
        
        if default_creds.get('client_id') and default_creds.get('client_secret'):
            oauth_client_id = default_creds['client_id']
            oauth_client_secret = default_creds['client_secret']
            logger.info(f"Using default credentials for {app.app_name}")
        else:
            logger.error(f"No default credentials found for {app.app_name}")
            raise HTTPException(
                status_code=400,
                detail="No OAuth2 credentials available. Please provide custom credentials or configure default credentials."
            )
    
    # Check if PKCE is required
    use_pkce = auth_config.get('pkce_required', False)
    
    # Parse subscription config if provided
    parsed_subscription_config = {}
    if subscription_config:
        try:
            parsed_subscription_config = json.loads(subscription_config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid subscription_config JSON")
    
    # Prepare temporary credentials to store in OAuth state
    temp_creds = {
        'client_id': oauth_client_id,
        'client_secret': oauth_client_secret,
        'using_default_credentials': not use_custom_credentials
    }
    
    # Create OAuth state in database
    oauth_state = OAuth2Service.create_oauth_state(
        db=db,
        app_id=app_id,
        redirect_uri=redirect_uri,
        user_id=current_user.user_id if current_user else None,
        tenant_id=current_user.tenant_id if current_user else None,
        provider_params=auth_config.get('authorization_params') or {},
        use_pkce=use_pkce,
        temp_credentials=temp_creds,
        webhook_url=webhook_url,
        subscription_config=parsed_subscription_config
    )
    
    try:
        # Build authorization URL
        authorization_url = OAuth2Service.build_authorization_url(
            app=app,
            state_token=oauth_state.state_token,
            client_id=oauth_client_id,
            code_verifier=oauth_state.code_verifier,
            provider_params=auth_config.get('authorization_params') or {}
        )
        
        return {
            "authorization_url": authorization_url,
            "use_popup": settings.oauth_popup_enabled
        }
    except Exception as e:
        # Clean up state on error
        logger.error(f"Failed to build authorization URL: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.delete(oauth_state)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def oauth2_callback(
    code: str = Query(..., description="Authorization code from OAuth2 provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth2 provider"),
    error_description: Optional[str] = Query(None, description="Error description from OAuth2 provider"),
    db: Session = Depends(get_db)
):
    """Handle OAuth2 callback"""
    # Handle OAuth2 errors
    if error:
        logger.error(f"OAuth2 callback error: {error} - {error_description}")
        # Try to get state data for redirect
        oauth_state = OAuth2Service.validate_state(db, state) if state else None
        redirect_uri = oauth_state.redirect_uri if oauth_state else "/applications"
        
        # Clean up state if found
        if oauth_state:
            db.delete(oauth_state)
            db.commit()
        
        return RedirectResponse(url=get_oauth2_redirect_url(redirect_uri, "error", error=error, description=error_description))
    
    # Validate state
    oauth_state = OAuth2Service.validate_state(db, state)
    if not oauth_state:
        return RedirectResponse(url="/oauth2/callback?auth=error&error=invalid_state")
    
    # Get application
    app = db.query(Application).filter(Application.app_id == oauth_state.app_id).first()
    if not app:
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "error", error="app_not_found"))
    
    # Get temp credentials from oauth state
    temp_creds = oauth_state.temp_credentials
    if settings.database_url.startswith("sqlite") and isinstance(temp_creds, str):
        temp_creds = json.loads(temp_creds)
    
    if not temp_creds or not temp_creds.get('client_id') or not temp_creds.get('client_secret'):
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "error", error="missing_credentials"))
    
    auth_config = json.loads(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
    token_url = auth_config.get('token_url')
    
    if not token_url:
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "error", error="token_url_not_configured"))
    
    try:
        # Build token request data
        token_data = OAuth2Service.build_token_request_data(
            app=app,
            code=code,
            oauth_state=oauth_state,
            client_id=temp_creds['client_id'],
            client_secret=temp_creds['client_secret']
        )
        
        # Get headers
        headers = OAuth2Service.get_authorization_headers(
            auth_config,
            temp_creds['client_id'],
            temp_creds['client_secret']
        )
        
        # Remove credentials from body if using basic auth
        if OAuth2Service.should_remove_credentials_from_body(auth_config):
            token_data.pop('client_id', None)
            token_data.pop('client_secret', None)
        
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=token_data,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            tokens = response.json()
        
        # Log the token response for debugging
        logger.info(f"Token response from {app.app_name}: {mask_sensitive_data(tokens)}")
        logger.info(f"Refresh token in response: {'refresh_token' in tokens}")
        
        # Special handling for Google - log if refresh token is missing
        google_apps = ["Google Sheets", "Google Tasks", "Gmail", "Google Calendar", "Google Drive"]
        if app.app_name in google_apps and 'refresh_token' not in tokens:
            logger.warning(f"{app.app_name} did not return a refresh token!")
            logger.warning("This usually means the app was previously authorized.")
            logger.warning("User should revoke access at https://myaccount.google.com/permissions and try again.")
        
        # Prepare credentials with tokens
        final_creds = {
            'client_id': temp_creds['client_id'],
            'client_secret': temp_creds['client_secret'],
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'token_type': tokens.get('token_type', 'Bearer')
        }
        
        # Handle token type mapping if configured
        # Some OAuth providers (like Slack) return non-standard token types
        token_type_mapping = auth_config.get('token_type_mapping', {})
        if token_type_mapping and final_creds['token_type'] in token_type_mapping:
            original_type = final_creds['token_type']
            mapped_type = token_type_mapping[original_type]
            logger.info(f"Mapping token_type '{original_type}' to '{mapped_type}' based on auth_config")
            final_creds['token_type'] = mapped_type
        
        # Calculate expiration
        expires_in = tokens.get('expires_in')
        if expires_in:
            final_creds['expires_at'] = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
        
        # Store additional token data (like id_token for OpenID Connect)
        if tokens.get('id_token'):
            final_creds['id_token'] = tokens['id_token']
        
        # Now create or update the subscription
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == oauth_state.app_id,
            ApplicationSubscription.tenant_id == oauth_state.tenant_id
        ).first()
        
        if subscription:
            # Update existing subscription with OAuth tokens
            subscription.auth_credentials = encrypt_credentials(final_creds)
            logger.info(f"Updated existing subscription {subscription.subscription_id} with OAuth tokens")
        else:
            # Create new subscription with OAuth tokens
            # Get subscription config from oauth state
            sub_config = oauth_state.subscription_config
            if settings.database_url.startswith("sqlite") and isinstance(sub_config, str):
                sub_config = json.loads(sub_config) if sub_config else {}
            
            # Generate API key for the subscription
            invocation_api_key = f"ioflow_{secrets.token_urlsafe(32)}"
            
            # For SQLite, ensure subscription_config is JSON string
            config_value = sub_config or {}
            if settings.database_url.startswith("sqlite"):
                config_value = json.dumps(config_value)
            
            subscription = ApplicationSubscription(
                subscription_id=str(uuid.uuid4()),  # Explicitly set for SQLite
                tenant_id=oauth_state.tenant_id,
                app_id=oauth_state.app_id,
                auth_credentials=encrypt_credentials(final_creds),
                subscription_config=config_value,
                webhook_url=oauth_state.webhook_url or '',
                invocation_api_key=invocation_api_key,
                api_key_created_at=datetime.utcnow(),
                status='active'
            )
            db.add(subscription)
            logger.info(f"Created new subscription for app {app.app_name} with OAuth tokens")
        
        db.commit()
        
        # Clean up OAuth state
        db.delete(oauth_state)
        db.commit()
        
        # Redirect back to frontend OAuth2 callback page
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "success", app=app.app_name))
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OAuth2 token exchange failed with status {e.response.status_code}: {e.response.text}")
        logger.error(f"Token URL: {token_url}")
        logger.error(f"Token request data: {mask_sensitive_data(token_data)}")
        logger.error(f"Headers: {mask_sensitive_data(dict(headers))}")
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "error", error="token_exchange_failed"))
    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Try to clean up OAuth state on error
        try:
            if oauth_state:
                db.delete(oauth_state)
                db.commit()
        except:
            pass
            
        # For debugging, return more detailed error
        # raise HTTPException(status_code=500, detail=f"OAuth callback error: {str(e)}")
        
        return RedirectResponse(url=get_oauth2_redirect_url(oauth_state.redirect_uri, "error", error="token_exchange_failed"))


@router.get("/status/{app_id}")
async def get_oauth2_status(
    app_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Check OAuth2 connection status for an application"""
    # Get subscription
    subscription = None
    if current_user:
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.tenant_id == current_user.tenant_id
        ).first()
    
    if not subscription:
        return {"connected": False, "has_credentials": False}
    
    if not subscription.auth_credentials:
        return {"connected": False, "has_credentials": False}
    
    # Check if we have tokens
    try:
        creds = decrypt_credentials(subscription.auth_credentials)
        has_access_token = bool(creds.get('access_token'))
        has_refresh_token = bool(creds.get('refresh_token'))
        
        # Check if token is expired
        token_expired = False
        if has_access_token and creds.get('expires_at'):
            token_expired = datetime.utcnow().timestamp() > creds['expires_at']
        
        return {
            "connected": has_access_token or has_refresh_token,
            "has_credentials": bool(creds.get('client_id') and creds.get('client_secret')),
            "has_access_token": has_access_token,
            "has_refresh_token": has_refresh_token,
            "token_expired": token_expired
        }
    except Exception as e:
        logger.error(f"Error checking OAuth2 status: {str(e)}")
        return {"connected": False, "has_credentials": False, "error": str(e)}
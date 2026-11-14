"""
OAuth2 Token Management Service
"""
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import base64
from sqlalchemy.orm import Session

from db.database import get_db
from db.application_models import ApplicationSubscription
from utils.crypto_utils import encrypt_credentials, decrypt_credentials, mask_sensitive_data

logger = logging.getLogger(__name__)


class OAuth2TokenManager:
    """Manages OAuth2 tokens with automatic refresh"""
    
    def __init__(self):
        self.token_cache = {}  # In-memory cache for tokens
        self.lock = asyncio.Lock()
    
    async def get_valid_token(
        self, 
        subscription_id: str,
        auth_config: Dict[str, Any],
        current_credentials: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """
        Get a valid OAuth2 token, refreshing if necessary
        
        Args:
            subscription_id: The subscription ID
            auth_config: The application's auth configuration
            current_credentials: Current decrypted credentials
            db: Database session
            
        Returns:
            Updated credentials with valid access token
        """
        async with self.lock:
            # Check if token is still valid
            if self._is_token_valid(current_credentials):
                logger.debug(f"Token for subscription {subscription_id} is still valid")
                return current_credentials
            
            # Token needs refresh
            logger.info(f"Token for subscription {subscription_id} needs refresh")
            
            # Get new token
            refresh_token = current_credentials.get('refresh_token')
            logger.debug(f"Refresh token available: {bool(refresh_token)}, length: {len(refresh_token) if refresh_token else 0}")
            
            new_token_data = await self._request_new_token(
                auth_config=auth_config,
                client_id=current_credentials.get('client_id'),
                client_secret=current_credentials.get('client_secret'),
                scope=current_credentials.get('scope') or auth_config.get('scope'),
                refresh_token=refresh_token,
                credentials=current_credentials
            )
            
            if not new_token_data:
                if not current_credentials.get('refresh_token'):
                    if self._uses_client_credentials(auth_config):
                        # client_credentials apps (e.g. Shopify, Flipkart) never get a
                        # refresh token: a failure here is the token request itself.
                        logger.error(f"client_credentials token request failed for subscription {subscription_id}")
                        raise ValueError(
                            "Failed to obtain an OAuth2 access token with the client_credentials grant. "
                            "Check the connection's client ID/secret and the fields the token URL needs.")
                    logger.error(f"No refresh token available for subscription {subscription_id}")
                    raise ValueError("OAuth2 refresh token missing. Please disconnect and reconnect the application to obtain a new refresh token.")
                else:
                    logger.error(f"Token refresh failed for subscription {subscription_id}")
                    raise ValueError("Failed to refresh OAuth2 token. The refresh token may have been revoked. Please reconnect the application.")
            
            # Update credentials
            updated_credentials = current_credentials.copy()
            updated_credentials.update({
                'access_token': new_token_data['access_token'],
                'token_type': new_token_data.get('token_type', 'Bearer'),
                'expires_at': new_token_data.get('expires_at'),
                'refresh_token': new_token_data.get('refresh_token') or current_credentials.get('refresh_token')
            })
            
            # Save updated credentials back to database
            await self._save_updated_credentials(subscription_id, updated_credentials, db)
            
            return updated_credentials
    
    @staticmethod
    def _uses_client_credentials(auth_config: Dict[str, Any]) -> bool:
        """True when the app obtains tokens with the client_credentials grant."""
        if not isinstance(auth_config, dict):
            return False
        grant = auth_config.get('grant_type')
        grants = auth_config.get('grant_types') or []
        token_request = auth_config.get('token_request') or {}
        extra = token_request.get('extra_params') if isinstance(token_request, dict) else None
        if isinstance(extra, dict) and extra.get('grant_type') == 'client_credentials':
            return True
        return grant == 'client_credentials' or (isinstance(grants, list) and grants == ['client_credentials'])

    def _is_token_valid(self, credentials: Dict[str, Any]) -> bool:
        """Check if the current token is still valid"""
        if not credentials.get('access_token'):
            return False
        
        expires_at = credentials.get('expires_at')
        if not expires_at:
            # If no expiration, assume token is valid (some APIs don't provide expiration)
            return True
        
        # Check if token expires in next 5 minutes (buffer time)
        expiry_time = datetime.fromtimestamp(expires_at)
        buffer_time = datetime.utcnow() + timedelta(minutes=5)
        
        return expiry_time > buffer_time
    
    async def _request_new_token(
        self,
        auth_config: Dict[str, Any],
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        refresh_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Request a new access token using refresh token or client credentials flow.

        ``auth_config`` options (all optional, defaults = the historical behaviour):
          token_url      may hold {{auth.<field>}} placeholders rendered from
                         ``credentials`` (per-connection hosts, e.g. a Shopify shop).
          auth_method    "basic" sends client_id:client_secret as HTTP Basic.
          token_request  {"method": "GET"|"POST" (POST), "params_in": "body"|"query"
                         (body), "extra_params": {...} (always merged)}.
        Raises ValueError when token_url needs a credential field that is missing.
        """
        token_url = auth_config.get('token_url')
        if not token_url:
            logger.error("No token URL configured for OAuth2")
            return None

        # Per-connection token URL, e.g. https://{{auth.shop_domain}}/admin/oauth/access_token
        from services.jinja_templating import render_auth_placeholders, has_auth_placeholders
        if has_auth_placeholders(token_url):
            token_url = render_auth_placeholders(token_url, credentials or {}, "The OAuth2 token_url")
            logger.info(f"Rendered per-connection token_url: {token_url}")

        token_request = auth_config.get('token_request') or {}
        if not isinstance(token_request, dict):
            logger.warning(f"Ignoring auth_config.token_request: expected an object, got {type(token_request).__name__}")
            token_request = {}
        request_method = str(token_request.get('method') or 'POST').upper()
        if request_method not in ('GET', 'POST'):
            logger.warning(f"Unsupported token_request.method '{request_method}', using POST")
            request_method = 'POST'
        params_in = str(token_request.get('params_in') or 'body').lower()
        if params_in not in ('body', 'query'):
            logger.warning(f"Unsupported token_request.params_in '{params_in}', using body")
            params_in = 'body'
        if request_method == 'GET':
            params_in = 'query'  # a GET has no body
        extra_params = token_request.get('extra_params') or {}
        if not isinstance(extra_params, dict):
            logger.warning(f"Ignoring token_request.extra_params: expected an object, got {type(extra_params).__name__}")
            extra_params = {}
        
        # Prepare request - use refresh_token if available (for services like Google)
        if refresh_token and isinstance(refresh_token, str) and len(refresh_token) > 1:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': client_id,
                'client_secret': client_secret
            }
        else:
            # Fallback to client credentials for services that support it
            data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
        
        if scope and not refresh_token:  # Don't send scope with refresh_token grant
            data['scope'] = scope

        # extra_params are always sent (e.g. Flipkart {"scope": "Seller_Api"})
        if extra_params:
            data.update({k: v for k, v in extra_params.items() if v is not None})
        
        headers = {}
        if params_in == 'body':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        # Some APIs prefer client credentials in Authorization header
        if auth_config.get('auth_method') == 'basic':
            basic_credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(basic_credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
            # Remove from body if using basic auth
            data.pop('client_id', None)
            data.pop('client_secret', None)
        
        try:
            logger.info(f"Requesting new OAuth2 token: {request_method} {token_url} (params in {params_in})")
            logger.debug(f"Token request data (masked): {mask_sensitive_data(data)}")
            
            async with httpx.AsyncClient() as client:
                if params_in == 'query':
                    response = await client.request(
                        request_method,
                        token_url,
                        params=data,
                        headers=headers,
                        timeout=30.0
                    )
                else:
                    response = await client.post(
                        token_url,
                        data=data,
                        headers=headers,
                        timeout=30.0
                    )
                
                response.raise_for_status()
                token_data = response.json()

                if not isinstance(token_data, dict) or not token_data.get('access_token'):
                    logger.error(f"OAuth2 token response from {token_url} has no access_token: "
                                 f"{mask_sensitive_data(token_data) if isinstance(token_data, dict) else str(token_data)[:200]}")
                    return None
                
                # Calculate expiration timestamp
                expires_in = token_data.get('expires_in')
                if expires_in:
                    try:
                        token_data['expires_at'] = int((datetime.utcnow() + timedelta(seconds=int(float(expires_in)))).timestamp())
                    except (TypeError, ValueError):
                        logger.warning(f"Ignoring non-numeric expires_in in token response: {expires_in!r}")
                
                logger.info("Successfully obtained new OAuth2 token")
                return token_data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth2 token request failed with status {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"OAuth2 token request failed: {str(e)}")
            return None
    
    async def _save_updated_credentials(
        self,
        subscription_id: str,
        updated_credentials: Dict[str, Any],
        db: Session
    ):
        """Save updated credentials back to the database"""
        try:
            # Get subscription
            subscription = db.query(ApplicationSubscription).filter(
                ApplicationSubscription.subscription_id == subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription {subscription_id} not found")
                return
            
            # Merge onto what is stored so connection fields the caller did not
            # carry (shop_domain, endpoint, seller_id, marketplace_id, ...) survive
            # a token refresh; the refreshed token fields win.
            merged_credentials = {}
            if subscription.auth_credentials:
                try:
                    stored = decrypt_credentials(subscription.auth_credentials)
                    if isinstance(stored, dict):
                        merged_credentials.update(stored)
                except Exception as decrypt_error:
                    logger.warning(f"Could not read stored credentials for subscription {subscription_id} "
                                   f"before saving the refreshed token; saving the refreshed set only: {decrypt_error}")
            merged_credentials.update(updated_credentials)

            # Encrypt and save
            encrypted_credentials = encrypt_credentials(merged_credentials)
            subscription.auth_credentials = encrypted_credentials
            db.commit()
            
            logger.info(f"Updated OAuth2 credentials for subscription {subscription_id}")
            
        except Exception as e:
            logger.error(f"Failed to save updated OAuth2 credentials: {str(e)}")
            db.rollback()


# Global instance
oauth2_manager = OAuth2TokenManager()


async def ensure_valid_oauth2_token(
    subscription_id: str,
    auth_config: Dict[str, Any],
    credentials: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """
    Ensure OAuth2 credentials have a valid access token
    
    This is the main entry point for OAuth2 token management
    """
    return await oauth2_manager.get_valid_token(
        subscription_id=subscription_id,
        auth_config=auth_config,
        current_credentials=credentials,
        db=db
    )
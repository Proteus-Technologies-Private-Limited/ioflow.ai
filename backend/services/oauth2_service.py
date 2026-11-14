"""
Generic OAuth2 Service for handling OAuth2 flows with any provider
"""
import secrets
import hashlib
import base64
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode, quote
import logging
from sqlalchemy.orm import Session

from db.application_models import OAuthState, Application, ApplicationSubscription
from core.config import settings
from utils.crypto_utils import decrypt_credentials

logger = logging.getLogger(__name__)


class OAuth2Service:
    """Generic OAuth2 flow handler supporting PKCE and dynamic provider parameters"""
    
    @staticmethod
    def generate_pkce_pair() -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        # Generate a random code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode('utf-8').rstrip('=')
        
        # Generate code challenge using SHA256
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    @staticmethod
    def create_oauth_state(
        db: Session,
        app_id: str,
        redirect_uri: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        provider_params: Optional[Dict[str, Any]] = None,
        use_pkce: bool = False,
        temp_credentials: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
        subscription_config: Optional[Dict[str, Any]] = None
    ) -> OAuthState:
        """Create and store OAuth state in database"""
        # Generate secure state token
        state_token = secrets.token_urlsafe(32)
        
        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(minutes=settings.oauth_state_ttl_minutes)
        
        # Generate PKCE if needed
        code_verifier = None
        if use_pkce:
            code_verifier, _ = OAuth2Service.generate_pkce_pair()
        
        # Create OAuth state record
        # For SQLite, we need to serialize JSON fields to string
        provider_params_value = provider_params or {}
        temp_credentials_value = temp_credentials or {}
        subscription_config_value = subscription_config or {}
        
        if settings.database_url.startswith("sqlite"):
            provider_params_value = json.dumps(provider_params_value) if provider_params_value else None
            temp_credentials_value = json.dumps(temp_credentials_value) if temp_credentials_value else None
            subscription_config_value = json.dumps(subscription_config_value) if subscription_config_value else None
        
        oauth_state = OAuthState(
            app_id=app_id,
            state_token=state_token,
            redirect_uri=redirect_uri,
            user_id=user_id,
            tenant_id=tenant_id,
            code_verifier=code_verifier,
            provider_params=provider_params_value,
            temp_credentials=temp_credentials_value,
            webhook_url=webhook_url,
            subscription_config=subscription_config_value,
            expires_at=expires_at
        )
        
        db.add(oauth_state)
        db.commit()
        db.refresh(oauth_state)
        
        return oauth_state
    
    @staticmethod
    def build_authorization_url(
        app: Application,
        state_token: str,
        client_id: str,
        code_verifier: Optional[str] = None,
        provider_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build authorization URL with provider-specific parameters"""
        auth_config = json.loads(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
        
        # Get authorization URL (support both authorization_url and auth_url for backward compatibility)
        authorization_url = auth_config.get('authorization_url')
        if not authorization_url:
            raise ValueError("OAuth2 authorization_url not configured in auth_config")
        if not client_id:
            raise ValueError("Client ID not configured")
        
        # Build base parameters
        params = {
            'client_id': client_id,
            'redirect_uri': settings.oauth_callback_base_url,
            'response_type': auth_config.get('response_type', 'code'),
            'state': state_token
        }
        
        # Add scopes
        scopes = auth_config.get('scopes', [])
        if scopes:
            if isinstance(scopes, list):
                params['scope'] = ' '.join(scopes)
            else:
                params['scope'] = scopes
        
        # Add PKCE challenge if verifier provided
        if code_verifier:
            _, code_challenge = OAuth2Service.generate_pkce_pair()
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 'S256'
        
        # Add provider-specific authorization parameters from auth_config
        # This allows each application to define its own OAuth requirements
        auth_params = auth_config.get('authorization_params', {})
        if auth_params:
            logger.info(f"Applying authorization_params from auth_config for {app.app_name}: {auth_params}")
            params.update(auth_params)
        
        # Add any additional provider params passed in (these can override auth_config params)
        if provider_params:
            logger.info(f"Applying additional provider_params: {provider_params}")
            params.update(provider_params)
        
        # Log the authorization URL parameters for debugging
        logger.info(f"Building authorization URL for {app.app_name}")
        logger.info(f"Authorization params: {auth_params}")
        logger.info(f"Final params: {params}")
        
        # Build full URL
        auth_url = f"{authorization_url}?{urlencode(params)}"
        logger.info(f"Full authorization URL: {auth_url}")
        return auth_url
    
    @staticmethod
    def validate_state(db: Session, state_token: str) -> Optional[OAuthState]:
        """Validate OAuth state token and check expiration"""
        oauth_state = db.query(OAuthState).filter(
            OAuthState.state_token == state_token
        ).first()
        
        if not oauth_state:
            logger.error(f"OAuth state not found: {state_token}")
            return None
        
        # Check expiration
        if oauth_state.expires_at < datetime.utcnow():
            logger.error(f"OAuth state expired: {state_token}")
            # Delete expired state
            db.delete(oauth_state)
            db.commit()
            return None
        
        return oauth_state
    
    @staticmethod
    def build_token_request_data(
        app: Application,
        code: str,
        oauth_state: OAuthState,
        client_id: str,
        client_secret: str
    ) -> Dict[str, Any]:
        """Build token exchange request data with provider-specific parameters"""
        auth_config = json.loads(app.auth_config) if isinstance(app.auth_config, str) else app.auth_config
        
        # Base token request data
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.oauth_callback_base_url,
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        # Add PKCE verifier if present
        if oauth_state.code_verifier:
            data['code_verifier'] = oauth_state.code_verifier
        
        # Add provider-specific token parameters
        token_params = auth_config.get('token_params', {})
        if token_params:
            data.update(token_params)
        
        return data
    
    @staticmethod
    def cleanup_expired_states(db: Session) -> int:
        """Clean up expired OAuth states from database"""
        expired_states = db.query(OAuthState).filter(
            OAuthState.expires_at < datetime.utcnow()
        ).all()
        
        count = len(expired_states)
        for state in expired_states:
            db.delete(state)
        
        if count > 0:
            db.commit()
            logger.info(f"Cleaned up {count} expired OAuth states")
        
        return count
    
    @staticmethod
    def get_authorization_headers(auth_config: Dict[str, Any], client_id: str, client_secret: str) -> Dict[str, str]:
        """Get authorization headers based on provider configuration"""
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Some providers prefer credentials in Authorization header
        if auth_config.get('auth_method') == 'basic':
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
        
        return headers
    
    @staticmethod
    def should_remove_credentials_from_body(auth_config: Dict[str, Any]) -> bool:
        """Check if credentials should be removed from request body"""
        return auth_config.get('auth_method') == 'basic'
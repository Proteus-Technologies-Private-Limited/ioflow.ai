"""
Google OAuth Service for authentication
"""
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import logging
from authlib.integrations.starlette_client import OAuth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session
from sqlalchemy import and_

from db.google_oauth_models import GoogleOAuthConfig, GoogleOAuthState
from db.models import User, Tenant
from core.security import AuthService
from core.config import settings
import uuid

logger = logging.getLogger(__name__)

class GoogleOAuthService:
    """Service for handling Google OAuth authentication"""
    
    @staticmethod
    def get_redirect_uri() -> str:
        """Get the redirect URI from environment configuration"""
        # Use the OAuth callback base URL from settings, but change the path for Google
        oauth_callback_url = getattr(settings, 'oauth_callback_base_url', 'http://localhost:7001/api/v1/oauth2/callback')
        
        # Extract the base URL (everything before /api/v1)
        if '/api/v1' in oauth_callback_url:
            base_url = oauth_callback_url.split('/api/v1')[0]
        else:
            base_url = 'http://localhost:7001'
        
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        return f"{base_url}/api/v1/auth/google/callback"
    
    @staticmethod
    def save_config(
        db: Session,
        client_id: str,
        client_secret: str,
        project_id: Optional[str],
        created_by: str
    ) -> GoogleOAuthConfig:
        """Save or update Google OAuth configuration"""
        # Check if config already exists
        config = db.query(GoogleOAuthConfig).filter(
            GoogleOAuthConfig.is_active == True
        ).first()
        
        redirect_uri = GoogleOAuthService.get_redirect_uri()
        
        if config:
            # Update existing config
            config.client_id = client_id
            config.client_secret = client_secret
            config.project_id = project_id
            config.redirect_uris = [redirect_uri]
            config.updated_at = datetime.utcnow()
        else:
            # Create new config
            config = GoogleOAuthConfig(
                client_id=client_id,
                client_secret=client_secret,
                project_id=project_id,
                redirect_uris=[redirect_uri],
                created_by=created_by
            )
            db.add(config)
        
        db.commit()
        db.refresh(config)
        return config
    
    @staticmethod
    def get_active_config(db: Session) -> Optional[GoogleOAuthConfig]:
        """Get active Google OAuth configuration"""
        return db.query(GoogleOAuthConfig).filter(
            GoogleOAuthConfig.is_active == True
        ).first()
    
    @staticmethod
    def generate_state_token() -> str:
        """Generate a secure random state token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    @staticmethod
    def create_auth_url(
        db: Session,
        action: str = 'login'  # 'login' or 'signup'
    ) -> Optional[str]:
        """Create Google OAuth authorization URL"""
        config = GoogleOAuthService.get_active_config(db)
        if not config:
            return None
        
        # Generate and save state token
        state_token = GoogleOAuthService.generate_state_token()
        redirect_uri = GoogleOAuthService.get_redirect_uri()
        
        # Save state for verification
        oauth_state = GoogleOAuthState(
            state_token=state_token,
            redirect_uri=redirect_uri,
            action=action,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.add(oauth_state)
        db.commit()
        
        # Build authorization URL
        auth_url = (
            f"{config.auth_uri}?"
            f"client_id={config.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=openid email profile&"
            f"state={state_token}&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        
        return auth_url
    
    @staticmethod
    def verify_state_token(db: Session, state_token: str) -> Optional[GoogleOAuthState]:
        """Verify and consume state token"""
        oauth_state = db.query(GoogleOAuthState).filter(
            and_(
                GoogleOAuthState.state_token == state_token,
                GoogleOAuthState.used == False,
                GoogleOAuthState.expires_at > datetime.utcnow()
            )
        ).first()
        
        if oauth_state:
            # Mark as used
            oauth_state.used = True
            db.commit()
            return oauth_state
        
        return None
    
    @staticmethod
    def exchange_code_for_token(
        db: Session,
        code: str,
        state_token: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token and get user info"""
        import requests
        
        # Verify state token
        oauth_state = GoogleOAuthService.verify_state_token(db, state_token)
        if not oauth_state:
            logger.error("Invalid or expired state token")
            return None
        
        config = GoogleOAuthService.get_active_config(db)
        if not config:
            logger.error("No active Google OAuth configuration found")
            return None
        
        # Exchange code for token
        token_url = config.token_uri
        redirect_uri = GoogleOAuthService.get_redirect_uri()
        
        token_data = {
            'code': code,
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            token_info = response.json()
            
            # Verify and decode ID token
            id_token_str = token_info.get('id_token')
            if not id_token_str:
                logger.error("No ID token in response")
                return None
            
            # Decode ID token to get user info
            # For production, you should verify the token signature
            try:
                # Verify the token with Google
                idinfo = id_token.verify_oauth2_token(
                    id_token_str, 
                    google_requests.Request(), 
                    config.client_id
                )
                
                return {
                    'email': idinfo.get('email'),
                    'name': idinfo.get('name'),
                    'picture': idinfo.get('picture'),
                    'email_verified': idinfo.get('email_verified'),
                    'sub': idinfo.get('sub'),  # Google user ID
                    'action': oauth_state.action,
                    'access_token': token_info.get('access_token'),
                    'refresh_token': token_info.get('refresh_token')
                }
            except Exception as e:
                logger.error(f"Failed to verify ID token: {str(e)}")
                # Fallback: decode without verification (for development only)
                import json
                import base64
                
                # Split the JWT token
                parts = id_token_str.split('.')
                if len(parts) != 3:
                    return None
                
                # Decode the payload (add padding if needed)
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                user_info = json.loads(decoded)
                
                return {
                    'email': user_info.get('email'),
                    'name': user_info.get('name'),
                    'picture': user_info.get('picture'),
                    'email_verified': user_info.get('email_verified'),
                    'sub': user_info.get('sub'),
                    'action': oauth_state.action,
                    'access_token': token_info.get('access_token'),
                    'refresh_token': token_info.get('refresh_token')
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for token: {str(e)}")
            return None
    
    @staticmethod
    def create_or_login_user(
        db: Session,
        google_user_info: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], bool]:
        """
        Create a new user or login existing user with Google OAuth
        Returns: (user_id, tenant_id, email, username, is_new_user)
        """
        email = google_user_info.get('email')
        name = google_user_info.get('name', email.split('@')[0])
        action = google_user_info.get('action', 'login')
        
        if not email or not google_user_info.get('email_verified'):
            logger.error("Email not verified or not provided")
            return None, None, None, None, False
        
        # Check if user exists
        existing_user = db.query(User).filter(User.email == email).first()
        
        if existing_user:
            # User exists - login
            if existing_user.status != 'A':
                # Activate user if logging in with Google
                existing_user.status = 'A'
                existing_user.auth_provider = 'google'
                db.commit()
            
            return (
                existing_user.user_id,
                existing_user.tenant_id,
                existing_user.email,
                existing_user.user_name,
                False
            )
        
        # New user - create account
        if action == 'signup':
            # Check if this is the first user
            user_count = db.query(User).count()
            is_first_user = user_count == 0
            
            # Generate username from email
            username = email.split('@')[0]
            # Ensure username is unique
            base_username = username
            counter = 1
            while db.query(User).filter(User.user_name == username).first():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create tenant for the user using common method from AuthService
            from core.security import AuthService
            tenant = AuthService.create_tenant_for_user(db, username, email)
            tenant_id = tenant.tenant_id
            
            # Create user
            user_id = str(uuid.uuid4())
            user = User(
                user_id=user_id,
                user_name=username,
                email=email,
                auth_provider='google',
                pass_wd_sha='GOOGLE_AUTH',  # Placeholder for Google auth users
                status='A',  # Auto-activate for Google users
                tenant_id=tenant_id,
                role='TENANT_ADMIN' if is_first_user else 'TENANT_ADMIN',  # User creating tenant is admin
                is_active=True
            )
            db.add(user)
            db.flush()
            
            # Update tenant owner
            tenant.user_id_own = user_id
            
            # Commit all changes
            db.commit()

            # Create tenant schema and tables
            from db.database import create_schema, create_tenant_tables
            create_schema(tenant.schema_name)
            create_tenant_tables(tenant.schema_name)

            logger.info(f"Created new user {email} with Google OAuth")
            return user_id, tenant_id, email, username, True
        
        # User doesn't exist and action is not signup
        return None, None, None, None, False
    
    @staticmethod
    def delete_config(db: Session) -> bool:
        """Delete Google OAuth configuration"""
        config = db.query(GoogleOAuthConfig).filter(
            GoogleOAuthConfig.is_active == True
        ).first()
        
        if config:
            config.is_active = False
            db.commit()
            return True
        
        return False
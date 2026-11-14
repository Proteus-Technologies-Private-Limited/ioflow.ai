"""
Google OAuth API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta
from pydantic import BaseModel
import logging

from db.database import get_db
from core.google_oauth_service import GoogleOAuthService
from core.security import AuthService
from core.config import settings
from core.auth_utils import get_current_user_required
from db.models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/google", tags=["google-oauth"])

class GoogleOAuthConfigRequest(BaseModel):
    client_id: str
    client_secret: str
    project_id: Optional[str] = None

class GoogleOAuthConfigResponse(BaseModel):
    client_id: str
    project_id: Optional[str]
    redirect_uri: str
    is_configured: bool

class GoogleAuthURLResponse(BaseModel):
    auth_url: str

@router.post("/config")
async def configure_google_oauth(
    config: GoogleOAuthConfigRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Configure Google OAuth settings (Instance Admin only)"""
    # Check if user is instance admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can configure Google OAuth"
        )
    
    try:
        saved_config = GoogleOAuthService.save_config(
            db=db,
            client_id=config.client_id,
            client_secret=config.client_secret,
            project_id=config.project_id,
            created_by=current_user.user_id
        )
        
        return {
            "message": "Google OAuth configuration saved successfully",
            "redirect_uri": GoogleOAuthService.get_redirect_uri()
        }
    except Exception as e:
        logger.error(f"Failed to save Google OAuth config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save configuration"
        )

@router.get("/config", response_model=GoogleOAuthConfigResponse)
async def get_google_oauth_config(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Get Google OAuth configuration (Instance Admin only)"""
    # Check if user is instance admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can view Google OAuth configuration"
        )
    
    config = GoogleOAuthService.get_active_config(db)
    
    return GoogleOAuthConfigResponse(
        client_id=config.client_id if config else "",
        project_id=config.project_id if config else None,
        redirect_uri=GoogleOAuthService.get_redirect_uri(),
        is_configured=config is not None
    )

@router.delete("/config")
async def delete_google_oauth_config(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Delete Google OAuth configuration (Instance Admin only)"""
    # Check if user is instance admin
    if current_user.role != UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instance admins can delete Google OAuth configuration"
        )
    
    success = GoogleOAuthService.delete_config(db)
    
    if success:
        return {"message": "Google OAuth configuration deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active configuration found"
        )

@router.get("/login", response_model=GoogleAuthURLResponse)
async def google_login(db: Session = Depends(get_db)):
    """Get Google OAuth login URL"""
    auth_url = GoogleOAuthService.create_auth_url(db, action='login')
    
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Please contact your administrator."
        )
    
    return GoogleAuthURLResponse(auth_url=auth_url)

@router.get("/signup", response_model=GoogleAuthURLResponse)
async def google_signup(db: Session = Depends(get_db)):
    """Get Google OAuth signup URL"""
    auth_url = GoogleOAuthService.create_auth_url(db, action='signup')
    
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Please contact your administrator."
        )
    
    return GoogleAuthURLResponse(auth_url=auth_url)

@router.get("/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for security"),
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for token and get user info
        user_info = GoogleOAuthService.exchange_code_for_token(db, code, state)
        
        if not user_info:
            # Redirect to login with error
            return RedirectResponse(url="/login?error=oauth_failed&message=Failed_to_authenticate_with_Google")
        
        # Create or login user
        user_id, tenant_id, email, username, is_new_user = GoogleOAuthService.create_or_login_user(
            db, user_info
        )
        
        if not user_id:
            # User doesn't exist and action was login (not signup)
            action = user_info.get('action', 'login')
            if action == 'login':
                return RedirectResponse(url="/login?error=user_not_found&message=Please_sign_up_first")
            else:
                return RedirectResponse(url="/register?error=signup_failed&message=Failed_to_create_account")
        
        # Get user details
        user = db.query(User).filter(User.user_id == user_id).first()
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = AuthService.create_access_token(
            data={"sub": user_id, "tenant_id": tenant_id, "email": email},
            expires_delta=access_token_expires
        )
        
        # Get tenant name
        tenant_name = AuthService.get_tenant_info(db, tenant_id)
        
        # Redirect to frontend with token
        # The frontend will handle storing the token and redirecting to dashboard
        redirect_url = f"/auth/callback?token={access_token}&user_id={user_id}&tenant_id={tenant_id}&tenant_name={tenant_name}&username={username}&role={user.role.value}&is_new={is_new_user}"
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {str(e)}")
        # Determine if this was a signup or login attempt
        if "signup" in str(state).lower():
            return RedirectResponse(url="/register?error=oauth_error&message=Failed_to_create_account_Please_try_again")
        else:
            return RedirectResponse(url="/login?error=oauth_error&message=Authentication_failed_Please_try_again")

@router.get("/status")
async def google_oauth_status(db: Session = Depends(get_db)):
    """Check if Google OAuth is configured"""
    config = GoogleOAuthService.get_active_config(db)
    
    return {
        "is_configured": config is not None,
        "redirect_uri": GoogleOAuthService.get_redirect_uri()  # Always return the redirect URI
    }
"""
Password management API endpoints for forgot password and change password
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import secrets
import logging

from db.database import get_db
try:
    from db.models import User
except ImportError:
    from db.models import User
from core.auth_utils import get_current_user_required
get_current_user = get_current_user_required  # Alias for consistency
from services.email_service import EmailService
from core.config import settings
from core.security import AuthService  # Use the same AuthService for consistency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/password", tags=["password-management"])

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class PasswordResponse(BaseModel):
    message: str
    success: bool

@router.post("/forgot", response_model=PasswordResponse)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request a password reset link"""
    try:
        # First check if SMTP is configured
        email_service = EmailService(db)
        
        # Check for valid SMTP configuration for default tenant
        # We need to check for the user's tenant, but since we don't know it yet, check default
        user = db.query(User).filter(User.email == request_data.email).first()
        
        if not user:
            # Don't reveal if email exists or not for security
            return PasswordResponse(
                message="If an account exists with this email, a password reset link has been sent.",
                success=True
            )
        
        # Check SMTP configuration for user's tenant
        smtp_config = email_service.get_smtp_config(user.tenant_id)
        if not smtp_config:
            logger.error(f"No SMTP configuration found for tenant {user.tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not configured. Please contact your administrator."
            )
        
        # Validate SMTP configuration has real credentials (not placeholder)
        if (smtp_config.smtp_username == "your-email@gmail.com" or 
            smtp_config.smtp_password == "your-app-password" or
            smtp_config.smtp_username == "use-your-mailtrap-username"):
            logger.error(f"SMTP configuration has placeholder credentials for tenant {user.tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not properly configured. Please contact your administrator."
            )
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        
        # Update user with reset token
        user.reset_token = reset_token
        user.reset_token_expires = reset_token_expires
        db.commit()
        
        # Generate reset link
        # Get the base URL from the request
        base_url = str(request.base_url).rstrip('/')
        reset_link = f"{base_url}/reset-password?token={reset_token}"
        
        # Send reset email
        email_sent = email_service.send_password_reset_email(
            tenant_id=user.tenant_id,
            to_email=user.email,
            user_name=user.user_name,
            reset_link=reset_link
        )
        
        if not email_sent:
            logger.error(f"Failed to send password reset email to {user.email}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to send password reset email. Please try again later."
            )
        else:
            logger.info(f"Password reset email sent to {user.email}")
        
        return PasswordResponse(
            message="Password reset link has been sent to your email address.",
            success=True
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (including our SMTP config errors)
        raise
    except Exception as e:
        logger.error(f"Error in forgot password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )

@router.post("/reset", response_model=PasswordResponse)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using the reset token"""
    try:
        # Find user by reset token
        user = db.query(User).filter(
            User.reset_token == request_data.token
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Check if token is expired
        if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
            # Clear expired token
            user.reset_token = None
            user.reset_token_expires = None
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new one."
            )
        
        # Validate password strength
        if len(request_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Update password using the same hashing method as the auth system
        user.pass_wd_sha = AuthService.get_password_hash(request_data.new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        
        # Send confirmation email
        email_service = EmailService(db)
        email_service.send_password_changed_email(
            tenant_id=user.tenant_id,
            to_email=user.email,
            user_name=user.user_name
        )
        
        logger.info(f"Password reset successfully for user {user.email}")
        
        return PasswordResponse(
            message="Password has been reset successfully. You can now login with your new password.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting your password"
        )

@router.post("/change", response_model=PasswordResponse)
async def change_password(
    request_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Change password for authenticated user"""
    try:
        # Verify current password using AuthService
        if not AuthService.verify_password(request_data.current_password, current_user.pass_wd_sha):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Check if new password is same as current
        if request_data.current_password == request_data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Validate password strength
        if len(request_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Update password using the same hashing method as the auth system
        current_user.pass_wd_sha = AuthService.get_password_hash(request_data.new_password)
        db.commit()
        
        # Send confirmation email
        email_service = EmailService(db)
        email_service.send_password_changed_email(
            tenant_id=current_user.tenant_id,
            to_email=current_user.email,
            user_name=current_user.user_name
        )
        
        logger.info(f"Password changed successfully for user {current_user.email}")
        
        return PasswordResponse(
            message="Password has been changed successfully.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in change password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while changing your password"
        )

@router.get("/validate-reset-token")
async def validate_reset_token(
    token: str,
    db: Session = Depends(get_db)
):
    """Validate if a reset token is valid and not expired"""
    try:
        # Find user by reset token
        user = db.query(User).filter(
            User.reset_token == token
        ).first()
        
        if not user:
            return {
                "valid": False,
                "message": "Invalid reset token"
            }
        
        # Check if token is expired
        if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
            return {
                "valid": False,
                "message": "Reset token has expired"
            }
        
        return {
            "valid": True,
            "message": "Token is valid",
            "email": user.email
        }
        
    except Exception as e:
        logger.error(f"Error validating reset token: {str(e)}")
        return {
            "valid": False,
            "message": "Error validating token"
        }
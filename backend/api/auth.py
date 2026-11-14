from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import logging
import os

from db.database import get_db
from core.security import AuthService, AuthError, DatabaseError
from core.config import settings
from core.auth_utils import get_current_user_required, get_current_user_optional, authenticate_jwt_token, authenticate_api_key
from utils.email_service import EmailService
from db.models import User

# Debug will be done in the endpoint instead of at import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(..., min_length=8, max_length=72, description="Password must be between 8 and 72 characters")
    organization: Optional[str] = None  # For first user only
    tenant_id: Optional[str] = None     # For subsequent users

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72)

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    tenant_id: str
    tenant_name: str
    username: str
    role: str

class ActivateAccount(BaseModel):
    email: EmailStr
    activation_code: str

class ResetPassword(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8, max_length=72, description="Password must be between 8 and 72 characters")
    reset_code: str

class Message(BaseModel):
    message: str

# Legacy dependencies for backward compatibility - these now use the enhanced auth
get_current_user = get_current_user_required

@router.post("/register")
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user and send activation email."""
    logger.info(f"Registration attempt for email: {user_data.email}")
    try:
        # Check if this is the first user in the system
        user_count = db.query(User).count()
        is_first_user = user_count == 0
        
        # Validate registration data
        if is_first_user:
            # First user must provide organization name
            if not user_data.organization:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization name is required for the first user"
                )
            tenant_id = None  # Will be created
            organization = user_data.organization
        else:
            # Subsequent users can provide tenant_id or have one auto-created
            if user_data.tenant_id:
                # Verify tenant exists if provided
                from db.models import Tenant
                tenant = db.query(Tenant).filter(Tenant.tenant_id == user_data.tenant_id).first()
                if not tenant:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid tenant ID. Please contact your administrator."
                    )

                tenant_id = tenant.tenant_id
                organization = tenant.tenant_name
            else:
                # Auto-create tenant for user if not provided
                tenant_id = None  # Will be created
                # Use provided organization name or fallback to username's organization
                if user_data.organization:
                    organization = user_data.organization
                else:
                    organization = f"{user_data.username}'s organization"
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        is_reregistration = False
        if existing_user:
            # Check activation status
            is_activated = existing_user.status == 'A'
            is_inactive = existing_user.status == 'N'
            logger.info(f"User exists with status: {existing_user.status}")

            if is_activated:
                logger.info(f"User {user_data.email} already activated, returning login message")
                return {
                    "message": "This email is already registered and activated. You can login using your email and password.",
                    "status": "activated",
                    "action": "login",
                    "loginUrl": "/login"
                }
            elif is_inactive:
                # User exists but not activated, will resend activation code
                is_reregistration = True
                logger.info(f"User {user_data.email} exists but not activated, will resend activation code")

        logger.info("Calling register_user")
        user_id, created_tenant_id, activation_code = AuthService.register_user(
            db=db,
            email=user_data.email,
            username=user_data.username,
            password=user_data.password,
            organization=organization,
            tenant_id=tenant_id,
            is_first_user=is_first_user
        )
        
        # Send activation email
        try:
            email_service = EmailService()
            email_service.send_activation_email(user_data.email, activation_code)

            # Return appropriate message based on new or re-registration
            if is_reregistration:
                message = "A new activation code has been sent to your email. Please enter the code to activate your account."
            else:
                message = "Registration successful. Please check your email for the activation code."

            return {
                "message": message,
                "status": "registered",
                "action": "activate",
                "email": user_data.email,
                "activation_code": activation_code  # Include for development
            }
        except Exception as e:
            # Log the error but still return success since user was created
            logger.error(f"Failed to send activation email to {user_data.email}: {str(e)}")

            # Return appropriate message based on new or re-registration
            if is_reregistration:
                message = "A new activation code has been generated. Email service not configured - activation code shown below."
            else:
                message = "Registration successful. Email service not configured - activation code shown below."

            return {
                "message": message,
                "status": "registered",
                "action": "activate",
                "email": user_data.email,
                "activation_code": activation_code  # Show code since email failed
            }
    
    except HTTPException:
        # Re-raise HTTPExceptions as they are (they already have proper status codes and messages)
        raise
    except AuthError as e:
        print(f"\n=== AUTH ERROR IN REGISTER ===")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        print(f"This causes 400 Bad Request")
        logger.error(f"AuthError in register: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        print(f"\n=== DATABASE ERROR IN REGISTER ===")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        logger.error(f"DatabaseError in register: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred")
    except Exception as e:
        print(f"\n=== UNEXPECTED ERROR IN REGISTER ===")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        logger.error(f"Unexpected error in register: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login with email and password."""
    try:
        logger.info(f"Login attempt received for: {form_data.username}")
        
        user_id, tenant_id, email, username = AuthService.authenticate_user(
            db=db,
            email=form_data.username,  # OAuth2PasswordRequestForm uses 'username' field
            password=form_data.password
        )
        
        logger.info(f"Authentication result: user_id={user_id}, tenant_id={tenant_id}, email={email}, username={username}")
        
        if not user_id:
            logger.warning(f"Authentication failed for {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user details
        user_data = AuthService.get_user_by_email(db, email)
        if user_data and user_data.get('status') != 'A':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account not activated. Please check your email for activation code."
            )
        
        # Get tenant name
        tenant_name = AuthService.get_tenant_info(db, tenant_id)
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = AuthService.create_access_token(
            data={"sub": user_id, "tenant_id": tenant_id, "email": email},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "username": username,
            "role": user_data['role']
        }
    
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.get("/twasta-config")
async def twasta_config():
    """Public config for the 'Authenticate with Twasta' login button: where to
    send the user for the twasta-side authorize redirect. No secrets here."""
    twasta_url = (settings.twasta_url or "").rstrip("/")
    return {
        "enabled": bool(twasta_url),
        "authorize_url": f"{twasta_url}/api/auth/runtime-authorize" if twasta_url else None,
    }


class TwastaExchangeRequest(BaseModel):
    twasta_token: str


@router.post("/twasta-exchange", response_model=Token)
async def twasta_exchange(req: TwastaExchangeRequest, db: Session = Depends(get_db)):
    """'Authenticate with Twasta' SSO: exchange a twasta.ai access token for an
    IOFlow session.

    The twasta token is verified server-side via twasta's introspection
    endpoint (POST {twasta_url}/api/auth/verify-token). On first login the
    user's twasta tenant is auto-provisioned as an IOFlow tenant (mapped via
    tenants.twasta_tenant_id) and the user is auto-created in it; subsequent
    logins reuse the mapped tenant/user. Returns the same Token shape as
    /login so the frontend can store it identically.
    """
    import httpx
    import uuid as _uuid
    import secrets as _secrets
    from db.models import Tenant, UserRole

    # 1. Verify the twasta token via introspection (never trust the client).
    verify_url = settings.twasta_url.rstrip("/") + "/api/auth/verify-token"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(verify_url, json={"token": req.twasta_token})
            resp.raise_for_status()
            info = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Twasta verify-token call failed ({verify_url}): {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the Twasta server to verify the token",
        )

    if not info.get("valid") or not info.get("email") or not info.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Twasta token",
        )

    twasta_tenant_id = info["tenant_id"]
    email = info["email"]
    username = info.get("user_name") or email.split("@")[0]
    twasta_tenant_name = (info.get("tenant_name") or "").strip()

    try:
        created_tenant = None

        # 2. Existing user (by email) wins — log them into their own tenant.
        user = db.query(User).filter(User.email == email).first()
        if user:
            tenant = db.query(Tenant).filter(Tenant.tenant_id == user.tenant_id).first()
            if tenant and not tenant.twasta_tenant_id:
                # Link the tenant to twasta if no other tenant claimed it yet.
                already = db.query(Tenant).filter(
                    Tenant.twasta_tenant_id == twasta_tenant_id
                ).first()
                if not already:
                    tenant.twasta_tenant_id = twasta_tenant_id
            # Twasta verified the email — activate pending accounts.
            if user.status != 'A' or not user.is_active:
                user.status = 'A'
                user.is_active = True
                user.activation_code = None
        else:
            # 3. Resolve the IOFlow tenant mapped to the twasta tenant.
            tenant = db.query(Tenant).filter(
                Tenant.twasta_tenant_id == twasta_tenant_id
            ).first()
            if not tenant:
                tenant = AuthService.create_tenant_for_user(
                    db, username=username, email=email,
                    organization=twasta_tenant_name or None,
                )
                tenant.twasta_tenant_id = twasta_tenant_id
                created_tenant = tenant

            # 4. Create the user in that tenant. First user of a freshly
            # provisioned tenant becomes its admin; later users join as
            # flow designers. Random password — login is via twasta only.
            user = User(
                user_id=str(_uuid.uuid4()),
                user_name=username,
                email=email,
                auth_provider='twasta',
                pass_wd_sha=AuthService.get_password_hash(_secrets.token_urlsafe(32)),
                status='A',
                acct_lock='N',
                activation_code=None,
                tenant_id=tenant.tenant_id,
                role=UserRole.TENANT_ADMIN if created_tenant else UserRole.FLOW_DESIGNER,
                is_active=True,
            )
            db.add(user)
            if created_tenant is not None:
                created_tenant.user_id_own = user.user_id

        user.last_login_at = datetime.utcnow()
        db.commit()

        # 5. Provision the tenant schema AFTER commit (mirrors register_user).
        if created_tenant is not None:
            from db.database import create_schema, create_tenant_tables
            create_schema(created_tenant.schema_name)
            create_tenant_tables(created_tenant.schema_name)

        # 6. Mint an IOFlow session token (same shape as /login).
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = AuthService.create_access_token(
            data={"sub": user.user_id, "tenant_id": user.tenant_id, "email": user.email},
            expires_delta=access_token_expires,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.tenant_name if tenant else "",
            "username": user.user_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"twasta-exchange failed for {email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twasta sign-in failed due to a server error",
        )


@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh the access token for an authenticated user."""
    try:
        # Create new access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = AuthService.create_access_token(
            data={
                "sub": current_user.user_id, 
                "tenant_id": current_user.tenant_id, 
                "email": current_user.email
            },
            expires_delta=access_token_expires
        )
        
        # Get tenant name
        tenant_name = AuthService.get_tenant_info(db, current_user.tenant_id)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": current_user.user_id,
            "tenant_id": current_user.tenant_id,
            "tenant_name": tenant_name,
            "username": current_user.user_name,
            "role": current_user.role.value
        }
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to refresh token")

@router.post("/activate", response_model=Message)
async def activate_account(activation_data: ActivateAccount, db: Session = Depends(get_db)):
    """Activate user account with activation code."""
    try:
        logger.info(f"Activation attempt for email: {activation_data.email}")

        # Check user before activation
        user_before = db.query(User).filter(User.email == activation_data.email).first()
        if user_before:
            logger.info(f"User before activation - status: {user_before.status}, is_active: {user_before.is_active}, activation_code: {user_before.activation_code}")

            # If account is already activated, treat as success so reused links don't error.
            if user_before.is_active and user_before.status == 'A':
                return {"message": "Account is already activated. You can login."}

        success = AuthService.activate_user(
            db=db,
            email=activation_data.email,
            activation_code=activation_data.activation_code
        )

        # Check user after activation
        user_after = db.query(User).filter(User.email == activation_data.email).first()
        if user_after:
            logger.info(f"User after activation - status: {user_after.status}, is_active: {user_after.is_active}")

        if success:
            return {"message": "Account activated successfully. You can now login."}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid activation code")

    except AuthError as e:
        logger.error(f"Activation AuthError for {activation_data.email}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Activation DatabaseError for {activation_data.email}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred")

@router.post("/forgot-password", response_model=Message)
async def forgot_password(email: EmailStr, db: Session = Depends(get_db)):
    """Send password reset code to email."""
    try:
        user = AuthService.get_user_by_email(db, email)
        if not user:
            # Don't reveal if email exists
            return {"message": "If the email exists, a reset code has been sent."}
        
        # Generate and save reset code (reusing activation_code field)
        reset_code = AuthService.generate_activation_code()
        user_obj = db.query(User).filter(User.email == email).first()
        user_obj.activation_code = reset_code
        db.commit()
        
        # Send reset email
        email_service = EmailService()
        email_service.send_password_reset_email(email, reset_code)
        
        return {"message": "If the email exists, a reset code has been sent."}
    
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred")

@router.post("/reset-password", response_model=Message)
async def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """Reset password with reset code."""
    try:
        user = db.query(User).filter(User.email == reset_data.email).first()
        if not user or user.activation_code != reset_data.reset_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset code")
        
        # Update password
        success = AuthService.update_password(db, reset_data.email, reset_data.new_password)
        
        if success:
            # Clear the reset code
            user.activation_code = None
            db.commit()
            return {"message": "Password reset successfully."}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to reset password")
    
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred")

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "username": current_user.user_name,
        "role": current_user.role.value if current_user.role else None,
        "tenant": {
            "tenant_id": current_user.tenant.tenant_id,
            "tenant_name": current_user.tenant.tenant_name,
            "schema_name": current_user.tenant.schema_name
        } if current_user.tenant else None
    }

@router.post("/logout", response_model=Message)
async def logout(current_user: User = Depends(get_current_user)):
    """Logout current user."""
    # In a stateless JWT system, logout is handled client-side by removing the token
    # Here we can add any server-side cleanup if needed
    return {"message": "Logged out successfully"}


async def get_current_user_ws(token: str, db: Session) -> Optional[User]:
    """
    Authenticate user for WebSocket connections.
    Supports both JWT tokens and API keys.
    """
    if not token:
        return None
    
    # Check if it's an API key
    if token.startswith("ioflow_"):
        return await authenticate_api_key(token, db)
    else:
        # Assume it's a JWT token
        return await authenticate_jwt_token(token, db)
"""
User Invitation API endpoints.
Allows admins to invite users to their organization/tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import logging
import secrets
import uuid

from db.database import get_db
from db.models import User, UserRole, Tenant, UserInvitation, InvitationStatus
from api.auth import get_current_user
from utils.email_service import EmailService
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])

# Default invitation expiry in days
DEFAULT_INVITATION_EXPIRY_DAYS = 7


# Pydantic models
class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "FLOW_DESIGNER"
    message: Optional[str] = None
    expiry_days: Optional[int] = DEFAULT_INVITATION_EXPIRY_DAYS


class InvitationResponse(BaseModel):
    invitation_id: str
    email: str
    role: str
    status: str
    tenant_id: str
    tenant_name: Optional[str] = None
    invited_by: str
    inviter_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    message: Optional[str] = None
    invitation_link: Optional[str] = None

    class Config:
        from_attributes = True


class InvitationAccept(BaseModel):
    token: str
    username: str
    password: str


class BulkInvitationCreate(BaseModel):
    emails: List[EmailStr]
    role: str = "FLOW_DESIGNER"
    message: Optional[str] = None
    expiry_days: Optional[int] = DEFAULT_INVITATION_EXPIRY_DAYS


class InvitationValidation(BaseModel):
    valid: bool
    email: Optional[str] = None
    tenant_name: Optional[str] = None
    role: Optional[str] = None
    inviter_name: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


def check_invitation_permission(current_user: User) -> None:
    """Check if current user can manage invitations"""
    if current_user.role not in [UserRole.INSTANCE_ADMIN, UserRole.TENANT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage invitations"
        )


def generate_invitation_token() -> str:
    """Generate a secure invitation token"""
    return secrets.token_urlsafe(32)


def get_invitation_link(token: str) -> str:
    """Generate the invitation acceptance link"""
    base_url = (
        settings.frontend_url
        or settings.server_url
        or settings.base_url
        or settings.app_url
    )
    return f"{base_url}/accept-invitation?token={token}"


@router.post("/", response_model=InvitationResponse)
async def create_invitation(
    invitation_data: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user invitation.
    Sends an email to the invited user with a link to accept.
    """
    check_invitation_permission(current_user)

    # Validate role
    try:
        role_enum = UserRole(invitation_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {invitation_data.role}"
        )

    # Tenant admin cannot invite instance admins
    if current_user.role == UserRole.TENANT_ADMIN and role_enum == UserRole.INSTANCE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admins cannot invite instance administrators"
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == invitation_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )

    # Check for existing pending invitation
    existing_invitation = db.query(UserInvitation).filter(
        UserInvitation.email == invitation_data.email,
        UserInvitation.tenant_id == current_user.tenant_id,
        UserInvitation.status == InvitationStatus.PENDING
    ).first()

    if existing_invitation:
        # Check if expired
        if existing_invitation.expires_at < datetime.utcnow():
            # Mark as expired and allow new invitation
            existing_invitation.status = InvitationStatus.EXPIRED
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A pending invitation already exists for this email. Cancel it first or wait for it to expire."
            )

    # Create invitation
    invitation_token = generate_invitation_token()
    expiry_days = invitation_data.expiry_days or DEFAULT_INVITATION_EXPIRY_DAYS
    expires_at = datetime.utcnow() + timedelta(days=expiry_days)

    invitation = UserInvitation(
        invitation_id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        email=invitation_data.email,
        invited_by=current_user.user_id,
        invitation_token=invitation_token,
        role=role_enum,
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
        message=invitation_data.message
    )

    try:
        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        # Get tenant name for email
        tenant = db.query(Tenant).filter(Tenant.tenant_id == current_user.tenant_id).first()
        tenant_name = tenant.tenant_name if tenant else "IOFlow"

        # Send invitation email
        try:
            email_service = EmailService()
            invitation_link = get_invitation_link(invitation_token)
            email_service.send_invitation_email(
                email=invitation_data.email,
                inviter_name=current_user.user_name,
                tenant_name=tenant_name,
                invitation_link=invitation_link
            )
        except Exception as e:
            logger.warning(f"Failed to send invitation email: {str(e)}")
            # Continue even if email fails - invitation is still created

        return InvitationResponse(
            invitation_id=invitation.invitation_id,
            email=invitation.email,
            role=invitation.role.value,
            status=invitation.status.value,
            tenant_id=invitation.tenant_id,
            tenant_name=tenant_name,
            invited_by=invitation.invited_by,
            inviter_name=current_user.user_name,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
            message=invitation.message,
            invitation_link=get_invitation_link(invitation_token)
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating invitation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create invitation"
        )


@router.post("/bulk", response_model=List[InvitationResponse])
async def create_bulk_invitations(
    invitation_data: BulkInvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create multiple invitations at once"""
    check_invitation_permission(current_user)

    results = []
    for email in invitation_data.emails:
        try:
            single_invitation = InvitationCreate(
                email=email,
                role=invitation_data.role,
                message=invitation_data.message,
                expiry_days=invitation_data.expiry_days
            )
            result = await create_invitation(single_invitation, current_user, db)
            results.append(result)
        except HTTPException as e:
            # Log but continue with other emails
            logger.warning(f"Failed to invite {email}: {e.detail}")

    return results


@router.get("/", response_model=List[InvitationResponse])
async def list_invitations(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all invitations for the current tenant"""
    check_invitation_permission(current_user)

    query = db.query(UserInvitation).filter(
        UserInvitation.tenant_id == current_user.tenant_id
    )

    if status_filter:
        try:
            status_enum = InvitationStatus(status_filter)
            query = query.filter(UserInvitation.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )

    # Update expired invitations
    now = datetime.utcnow()
    db.query(UserInvitation).filter(
        UserInvitation.status == InvitationStatus.PENDING,
        UserInvitation.expires_at < now
    ).update({"status": InvitationStatus.EXPIRED})
    db.commit()

    invitations = query.order_by(UserInvitation.created_at.desc()).all()

    # Get tenant name
    tenant = db.query(Tenant).filter(Tenant.tenant_id == current_user.tenant_id).first()
    tenant_name = tenant.tenant_name if tenant else None

    results = []
    for inv in invitations:
        inviter = db.query(User).filter(User.user_id == inv.invited_by).first()
        results.append(InvitationResponse(
            invitation_id=inv.invitation_id,
            email=inv.email,
            role=inv.role.value,
            status=inv.status.value,
            tenant_id=inv.tenant_id,
            tenant_name=tenant_name,
            invited_by=inv.invited_by,
            inviter_name=inviter.user_name if inviter else None,
            created_at=inv.created_at,
            expires_at=inv.expires_at,
            accepted_at=inv.accepted_at,
            message=inv.message,
            invitation_link=get_invitation_link(inv.invitation_token) if inv.status == InvitationStatus.PENDING else None
        ))

    return results


@router.get("/validate/{token}", response_model=InvitationValidation)
async def validate_invitation(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Validate an invitation token without accepting it.
    This is a public endpoint for the invitation acceptance page.
    """
    invitation = db.query(UserInvitation).filter(
        UserInvitation.invitation_token == token
    ).first()

    if not invitation:
        return InvitationValidation(
            valid=False,
            error="Invalid invitation token"
        )

    if invitation.status != InvitationStatus.PENDING:
        return InvitationValidation(
            valid=False,
            error=f"This invitation has been {invitation.status.value}"
        )

    if invitation.expires_at < datetime.utcnow():
        # Mark as expired
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        return InvitationValidation(
            valid=False,
            error="This invitation has expired"
        )

    # Get additional info
    tenant = db.query(Tenant).filter(Tenant.tenant_id == invitation.tenant_id).first()
    inviter = db.query(User).filter(User.user_id == invitation.invited_by).first()

    return InvitationValidation(
        valid=True,
        email=invitation.email,
        tenant_name=tenant.tenant_name if tenant else None,
        role=invitation.role.value,
        inviter_name=inviter.user_name if inviter else None,
        message=invitation.message
    )


@router.post("/accept")
async def accept_invitation(
    acceptance_data: InvitationAccept,
    db: Session = Depends(get_db)
):
    """
    Accept an invitation and create a new user account.
    This is a public endpoint.
    """
    # Find the invitation
    invitation = db.query(UserInvitation).filter(
        UserInvitation.invitation_token == acceptance_data.token
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token"
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This invitation has been {invitation.status.value}"
        )

    if invitation.expires_at < datetime.utcnow():
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired"
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == invitation.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )

    # Validate password
    if len(acceptance_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    if len(acceptance_data.password) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot exceed 72 characters"
        )

    try:
        # Create the user
        from core.security import AuthService

        # Hash the password
        password_hash = AuthService.hash_password(acceptance_data.password)

        new_user = User(
            user_id=str(uuid.uuid4()),
            user_name=acceptance_data.username,
            email=invitation.email,
            pass_wd_sha=password_hash,
            tenant_id=invitation.tenant_id,
            role=invitation.role,
            status='A',  # Already activated since invited
            is_active=True
        )

        db.add(new_user)

        # Update invitation status
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = datetime.utcnow()

        db.commit()

        # Get tenant info for response
        tenant = db.query(Tenant).filter(Tenant.tenant_id == invitation.tenant_id).first()

        return {
            "message": "Invitation accepted successfully. You can now login.",
            "email": invitation.email,
            "tenant_name": tenant.tenant_name if tenant else None,
            "role": invitation.role.value
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error accepting invitation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


@router.post("/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend an invitation email"""
    check_invitation_permission(current_user)

    invitation = db.query(UserInvitation).filter(
        UserInvitation.invitation_id == invitation_id,
        UserInvitation.tenant_id == current_user.tenant_id
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resend invitation that is {invitation.status.value}"
        )

    # Extend expiry if needed
    if invitation.expires_at < datetime.utcnow():
        invitation.expires_at = datetime.utcnow() + timedelta(days=DEFAULT_INVITATION_EXPIRY_DAYS)
        db.commit()

    # Get tenant name
    tenant = db.query(Tenant).filter(Tenant.tenant_id == current_user.tenant_id).first()
    tenant_name = tenant.tenant_name if tenant else "IOFlow"

    # Resend email
    try:
        email_service = EmailService()
        invitation_link = get_invitation_link(invitation.invitation_token)
        email_service.send_invitation_email(
            email=invitation.email,
            inviter_name=current_user.user_name,
            tenant_name=tenant_name,
            invitation_link=invitation_link
        )
        return {"message": "Invitation resent successfully"}
    except Exception as e:
        logger.error(f"Failed to resend invitation email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation email"
        )


@router.delete("/{invitation_id}")
async def cancel_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a pending invitation"""
    check_invitation_permission(current_user)

    invitation = db.query(UserInvitation).filter(
        UserInvitation.invitation_id == invitation_id,
        UserInvitation.tenant_id == current_user.tenant_id
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel invitation that is {invitation.status.value}"
        )

    invitation.status = InvitationStatus.CANCELLED
    db.commit()

    return {"message": "Invitation cancelled successfully"}

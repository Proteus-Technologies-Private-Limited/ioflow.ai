"""
SMTP Configuration API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr
from db.database import get_db
try:
    from db.models import SMTPConfiguration, User, UserRole
except ImportError:
    from db.models import SMTPConfiguration, User, UserRole
from core.auth_utils import get_current_user_required
get_current_user = get_current_user_required  # Alias for consistency
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/smtp-config", tags=["smtp-config"])

class SMTPConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from_email: EmailStr
    smtp_from_name: str = "IOFlow"
    use_tls: bool = True
    use_ssl: bool = False
    is_active: bool = True

class SMTPConfigResponse(BaseModel):
    id: str
    tenant_id: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_from_email: str
    smtp_from_name: str
    use_tls: bool
    use_ssl: bool
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class TestEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str = "Test Email from IOFlow"
    body: str = "This is a test email to verify SMTP configuration."

def check_admin_permission(current_user: User):
    """Check if user has admin permissions"""
    if current_user.role not in [UserRole.INSTANCE_ADMIN, UserRole.TENANT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage SMTP configuration"
        )

@router.get("", response_model=Optional[SMTPConfigResponse])
async def get_smtp_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Get SMTP configuration for the current tenant"""
    check_admin_permission(current_user)
    
    config = db.query(SMTPConfiguration).filter_by(
        tenant_id=current_user.tenant_id
    ).first()
    
    if not config:
        return None
    
    # Don't return the actual password
    response = SMTPConfigResponse(
        id=config.id,
        tenant_id=config.tenant_id,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_username=config.smtp_username,
        smtp_from_email=config.smtp_from_email,
        smtp_from_name=config.smtp_from_name,
        use_tls=config.use_tls,
        use_ssl=config.use_ssl,
        is_active=config.is_active,
        created_at=str(config.created_at) if config.created_at else None,
        updated_at=str(config.updated_at) if config.updated_at else None
    )
    
    return response

@router.post("", response_model=SMTPConfigResponse)
async def create_or_update_smtp_config(
    config_data: SMTPConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Create or update SMTP configuration for the current tenant"""
    check_admin_permission(current_user)
    
    # Check if configuration already exists
    existing_config = db.query(SMTPConfiguration).filter_by(
        tenant_id=current_user.tenant_id
    ).first()
    
    if existing_config:
        # Update existing configuration
        existing_config.smtp_host = config_data.smtp_host
        existing_config.smtp_port = config_data.smtp_port
        existing_config.smtp_username = config_data.smtp_username
        existing_config.smtp_password = config_data.smtp_password
        existing_config.smtp_from_email = config_data.smtp_from_email
        existing_config.smtp_from_name = config_data.smtp_from_name
        existing_config.use_tls = config_data.use_tls
        existing_config.use_ssl = config_data.use_ssl
        existing_config.is_active = config_data.is_active
        
        db.commit()
        db.refresh(existing_config)
        
        logger.info(f"Updated SMTP configuration for tenant {current_user.tenant_id}")
        
        return SMTPConfigResponse(
            id=existing_config.id,
            tenant_id=existing_config.tenant_id,
            smtp_host=existing_config.smtp_host,
            smtp_port=existing_config.smtp_port,
            smtp_username=existing_config.smtp_username,
            smtp_from_email=existing_config.smtp_from_email,
            smtp_from_name=existing_config.smtp_from_name,
            use_tls=existing_config.use_tls,
            use_ssl=existing_config.use_ssl,
            is_active=existing_config.is_active,
            created_at=str(existing_config.created_at) if existing_config.created_at else None,
            updated_at=str(existing_config.updated_at) if existing_config.updated_at else None
        )
    else:
        # Create new configuration
        new_config = SMTPConfiguration(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            smtp_host=config_data.smtp_host,
            smtp_port=config_data.smtp_port,
            smtp_username=config_data.smtp_username,
            smtp_password=config_data.smtp_password,
            smtp_from_email=config_data.smtp_from_email,
            smtp_from_name=config_data.smtp_from_name,
            use_tls=config_data.use_tls,
            use_ssl=config_data.use_ssl,
            is_active=config_data.is_active
        )
        
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        
        logger.info(f"Created SMTP configuration for tenant {current_user.tenant_id}")
        
        return SMTPConfigResponse(
            id=new_config.id,
            tenant_id=new_config.tenant_id,
            smtp_host=new_config.smtp_host,
            smtp_port=new_config.smtp_port,
            smtp_username=new_config.smtp_username,
            smtp_from_email=new_config.smtp_from_email,
            smtp_from_name=new_config.smtp_from_name,
            use_tls=new_config.use_tls,
            use_ssl=new_config.use_ssl,
            is_active=new_config.is_active,
            created_at=str(new_config.created_at) if new_config.created_at else None,
            updated_at=str(new_config.updated_at) if new_config.updated_at else None
        )

@router.delete("")
async def delete_smtp_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Delete SMTP configuration for the current tenant"""
    check_admin_permission(current_user)
    
    config = db.query(SMTPConfiguration).filter_by(
        tenant_id=current_user.tenant_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMTP configuration not found"
        )
    
    db.delete(config)
    db.commit()
    
    logger.info(f"Deleted SMTP configuration for tenant {current_user.tenant_id}")
    
    return {"message": "SMTP configuration deleted successfully"}

@router.post("/test")
async def test_smtp_config(
    test_data: TestEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """Test SMTP configuration by sending a test email"""
    check_admin_permission(current_user)
    
    from services.email_service import EmailService
    
    email_service = EmailService(db)
    
    # Check if SMTP is configured
    config = email_service.get_smtp_config(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP configuration not found. Please configure SMTP settings first."
        )
    
    # Prepare HTML body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .success {{ color: #4CAF50; }}
        </style>
    </head>
    <body>
        <h2 class="success">SMTP Configuration Test Successful!</h2>
        <p>{test_data.body}</p>
        <hr>
        <p>This email was sent from IOFlow using the following configuration:</p>
        <ul>
            <li>SMTP Host: {config.smtp_host}</li>
            <li>SMTP Port: {config.smtp_port}</li>
            <li>From Email: {config.smtp_from_email}</li>
            <li>TLS: {'Enabled' if config.use_tls else 'Disabled'}</li>
            <li>SSL: {'Enabled' if config.use_ssl else 'Disabled'}</li>
        </ul>
    </body>
    </html>
    """
    
    # Send test email
    success = email_service.send_email(
        tenant_id=current_user.tenant_id,
        to_email=test_data.to_email,
        subject=test_data.subject,
        body_html=html_body,
        body_text=test_data.body
    )
    
    if success:
        return {"message": f"Test email sent successfully to {test_data.to_email}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email. Please check your SMTP configuration and try again."
        )
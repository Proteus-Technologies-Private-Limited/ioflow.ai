import os
from typing import Optional
from postmarker.core import PostmarkClient
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging

from core.config import settings

logger = logging.getLogger(__name__)

def _get_public_base_url() -> str:
    """Resolve the public-facing base URL for links embedded in emails.

    Prefers explicit frontend_url, then server_url / base_url, falling back
    to app_url so a localhost default doesn't leak into outbound mail.
    """
    return (
        settings.frontend_url
        or settings.server_url
        or settings.base_url
        or settings.app_url
    )


class EmailService:
    """Email service for sending transactional emails."""

    def __init__(self):
        self.from_email = settings.from_email
        self.postmark_api_key = settings.postmark_api_key

        # Check if we're in development mode (no email configuration)
        self.development_mode = False

        # Use Postmark if API key is available, otherwise fall back to SMTP
        if self.postmark_api_key:
            self.client = PostmarkClient(server_token=self.postmark_api_key)
            self.use_postmark = True
        else:
            self.use_postmark = False
            # Fall back to SMTP configuration from settings (loaded from .env)
            self.smtp_server = settings.mail_server or ''
            self.smtp_port = 587
            self.smtp_username = settings.email_user or ''
            self.smtp_password = settings.email_pass or ''

            # If no email configuration is available, use development mode
            if not self.smtp_server or not self.smtp_username:
                self.development_mode = True
                logger.warning("No email configuration found. Running in development mode - emails will be logged to console.")
            else:
                logger.info(f"SMTP configured: server={self.smtp_server}, user={self.smtp_username[:20]}...")
    
    def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None):
        """Send an email using configured service."""
        try:
            if self.development_mode:
                self._log_email(to_email, subject, body)
            elif self.use_postmark:
                self._send_postmark_email(to_email, subject, body, html_body)
            else:
                self._send_smtp_email(to_email, subject, body, html_body)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise
    
    def _log_email(self, to_email: str, subject: str, body: str):
        """Log email to console in development mode."""
        logger.info("="*60)
        logger.info("EMAIL SENT (Development Mode)")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info("-"*60)
        logger.info(body)
        logger.info("="*60)
        print("\n" + "="*60)
        print("EMAIL SENT (Development Mode)")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("-"*60)
        print(body)
        print("="*60 + "\n")
    
    def _send_postmark_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None):
        """Send email using Postmark."""
        email_data = {
            "From": self.from_email,
            "To": to_email,
            "Subject": subject,
            "TextBody": body
        }
        
        if html_body:
            email_data["HtmlBody"] = html_body
        
        self.client.emails.send(**email_data)
    
    def _send_smtp_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None):
        """Send email using SMTP."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = to_email
        
        # Add text part
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
    
    def send_activation_email(self, email: str, activation_code: str):
        """Send account activation email."""
        subject = "Activate Your IOFlow Account"
        base_url = _get_public_base_url()
        activation_link = f"{base_url}/activate?email={email}&code={activation_code}"

        body = f"""
Dear User,

Thank you for registering with IOFlow. Please use the following activation code to activate your account:

Activation Code: {activation_code}

Or visit: {activation_link}

This code will expire in 24 hours.

Best regards,
The IOFlow Team
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5aa0;">Welcome to IOFlow!</h2>
        <p>Thank you for registering. Please use the following activation code to activate your account:</p>
        
        <div style="background-color: #f4f4f4; padding: 15px; margin: 20px 0; text-align: center; border-radius: 5px;">
            <h3 style="margin: 0; color: #2c5aa0;">{activation_code}</h3>
        </div>
        
        <p>Or click the button below to activate your account:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{activation_link}"
               style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Activate Account
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">This code will expire in 24 hours.</p>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        
        <p style="color: #666; font-size: 12px;">
            If you didn't create an account with IOFlow, please ignore this email.
        </p>
    </div>
</body>
</html>
"""
        
        self.send_email(email, subject, body, html_body)
    
    def send_password_reset_email(self, email: str, reset_code: str):
        """Send password reset email."""
        subject = "Reset Your IOFlow Password"
        base_url = _get_public_base_url()
        reset_link = f"{base_url}/reset-password?email={email}&code={reset_code}"

        body = f"""
Dear User,

We received a request to reset your password. Please use the following code to reset your password:

Reset Code: {reset_code}

Or visit: {reset_link}

This code will expire in 1 hour. If you didn't request this, please ignore this email.

Best regards,
The IOFlow Team
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5aa0;">Password Reset Request</h2>
        <p>We received a request to reset your password. Please use the following code:</p>
        
        <div style="background-color: #f4f4f4; padding: 15px; margin: 20px 0; text-align: center; border-radius: 5px;">
            <h3 style="margin: 0; color: #2c5aa0;">{reset_code}</h3>
        </div>
        
        <p>Or click the button below to reset your password:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}"
               style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Reset Password
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">This code will expire in 1 hour.</p>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        
        <p style="color: #666; font-size: 12px;">
            If you didn't request a password reset, please ignore this email and your password will remain unchanged.
        </p>
    </div>
</body>
</html>
"""
        
        self.send_email(email, subject, body, html_body)
    
    def send_invitation_email(self, email: str, inviter_name: str, tenant_name: str, invitation_link: str):
        """Send invitation email to join a tenant."""
        subject = f"Invitation to join {tenant_name} on IOFlow"
        
        body = f"""
Dear User,

{inviter_name} has invited you to join {tenant_name} on IOFlow.

Click the following link to accept the invitation:
{invitation_link}

This invitation will expire in 7 days.

Best regards,
The IOFlow Team
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c5aa0;">You're Invited!</h2>
        <p><strong>{inviter_name}</strong> has invited you to join <strong>{tenant_name}</strong> on IOFlow.</p>
        
        <p>IOFlow is a powerful integration platform that allows you to connect different applications and automate workflows.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{invitation_link}" 
               style="background-color: #2c5aa0; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Accept Invitation
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">This invitation will expire in 7 days.</p>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        
        <p style="color: #666; font-size: 12px;">
            If you don't know {inviter_name} or didn't expect this invitation, please ignore this email.
        </p>
    </div>
</body>
</html>
"""
        
        self.send_email(email, subject, body, html_body)
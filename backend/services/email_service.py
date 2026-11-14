"""
Email service for sending emails using configured SMTP settings
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from sqlalchemy.orm import Session
try:
    from db.models import SMTPConfiguration
except ImportError:
    from db.models import SMTPConfiguration
import os
from jinja2 import Template

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, db: Session):
        self.db = db
        
    def get_smtp_config(self, tenant_id: str) -> Optional[SMTPConfiguration]:
        """Get SMTP configuration for a tenant"""
        return self.db.query(SMTPConfiguration).filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).first()
    
    def send_email(
        self,
        tenant_id: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """Send an email using tenant's SMTP configuration"""
        try:
            # Get SMTP configuration
            smtp_config = self.get_smtp_config(tenant_id)
            if not smtp_config:
                logger.error(f"No active SMTP configuration found for tenant {tenant_id}")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{smtp_config.smtp_from_name} <{smtp_config.smtp_from_email}>"
            msg['To'] = to_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            if bcc_emails:
                msg['Bcc'] = ', '.join(bcc_emails)
            
            # Add text and HTML parts
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)
            
            # Send email
            if smtp_config.use_ssl:
                server = smtplib.SMTP_SSL(smtp_config.smtp_host, smtp_config.smtp_port)
            else:
                server = smtplib.SMTP(smtp_config.smtp_host, smtp_config.smtp_port)
                if smtp_config.use_tls:
                    server.starttls()
            
            server.login(smtp_config.smtp_username, smtp_config.smtp_password)
            
            # Prepare recipients
            recipients = [to_email]
            if cc_emails:
                recipients.extend(cc_emails)
            if bcc_emails:
                recipients.extend(bcc_emails)
            
            server.send_message(msg, smtp_config.smtp_from_email, recipients)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_password_reset_email(
        self,
        tenant_id: str,
        to_email: str,
        user_name: str,
        reset_link: str
    ) -> bool:
        """Send password reset email"""
        subject = "Password Reset Request - IOFlow"
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
                .content { background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }
                .button { display: inline-block; padding: 12px 24px; background-color: #4CAF50; 
                         color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
                .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>IOFlow Password Reset</h1>
                </div>
                <div class="content">
                    <h2>Hello {{ user_name }},</h2>
                    <p>We received a request to reset your password for your IOFlow account.</p>
                    <p>Click the button below to reset your password:</p>
                    <p style="text-align: center;">
                        <a href="{{ reset_link }}" class="button">Reset Password</a>
                    </p>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #f0f0f0; padding: 10px;">
                        {{ reset_link }}
                    </p>
                    <p><strong>This link will expire in 1 hour for security reasons.</strong></p>
                    <p>If you didn't request a password reset, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2024 IOFlow. All rights reserved.</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_template = """
        Hello {{ user_name }},
        
        We received a request to reset your password for your IOFlow account.
        
        Click the following link to reset your password:
        {{ reset_link }}
        
        This link will expire in 1 hour for security reasons.
        
        If you didn't request a password reset, please ignore this email.
        
        Best regards,
        IOFlow Team
        """
        
        # Render templates
        html_body = Template(html_template).render(user_name=user_name, reset_link=reset_link)
        text_body = Template(text_template).render(user_name=user_name, reset_link=reset_link)
        
        return self.send_email(
            tenant_id=tenant_id,
            to_email=to_email,
            subject=subject,
            body_html=html_body,
            body_text=text_body
        )
    
    def send_user_invitation_email(
        self,
        tenant_id: str,
        to_email: str,
        user_name: str,
        invitation_link: str,
        invited_by: str
    ) -> bool:
        """Send user invitation email"""
        subject = "You're Invited to Join IOFlow"
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
                .content { background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }
                .button { display: inline-block; padding: 12px 24px; background-color: #4CAF50; 
                         color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
                .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to IOFlow</h1>
                </div>
                <div class="content">
                    <h2>Hello {{ user_name }},</h2>
                    <p>{{ invited_by }} has invited you to join IOFlow, a powerful workflow automation platform.</p>
                    <p>Click the button below to accept the invitation and set up your account:</p>
                    <p style="text-align: center;">
                        <a href="{{ invitation_link }}" class="button">Accept Invitation</a>
                    </p>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #f0f0f0; padding: 10px;">
                        {{ invitation_link }}
                    </p>
                    <p><strong>This invitation link will expire in 7 days.</strong></p>
                    <h3>What is IOFlow?</h3>
                    <p>IOFlow is a comprehensive workflow automation platform that helps you:</p>
                    <ul>
                        <li>Design and execute complex workflows</li>
                        <li>Integrate with multiple services and APIs</li>
                        <li>Monitor and manage your automation processes</li>
                        <li>Collaborate with your team efficiently</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>© 2024 IOFlow. All rights reserved.</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_template = """
        Hello {{ user_name }},
        
        {{ invited_by }} has invited you to join IOFlow, a powerful workflow automation platform.
        
        Click the following link to accept the invitation and set up your account:
        {{ invitation_link }}
        
        This invitation link will expire in 7 days.
        
        What is IOFlow?
        IOFlow is a comprehensive workflow automation platform that helps you:
        - Design and execute complex workflows
        - Integrate with multiple services and APIs
        - Monitor and manage your automation processes
        - Collaborate with your team efficiently
        
        Best regards,
        IOFlow Team
        """
        
        # Render templates
        html_body = Template(html_template).render(
            user_name=user_name,
            invitation_link=invitation_link,
            invited_by=invited_by
        )
        text_body = Template(text_template).render(
            user_name=user_name,
            invitation_link=invitation_link,
            invited_by=invited_by
        )
        
        return self.send_email(
            tenant_id=tenant_id,
            to_email=to_email,
            subject=subject,
            body_html=html_body,
            body_text=text_body
        )
    
    def send_password_changed_email(
        self,
        tenant_id: str,
        to_email: str,
        user_name: str
    ) -> bool:
        """Send password changed notification email"""
        subject = "Your IOFlow Password Has Been Changed"
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
                .content { background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }
                .warning { background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; 
                          border-radius: 4px; margin: 20px 0; }
                .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Changed Successfully</h1>
                </div>
                <div class="content">
                    <h2>Hello {{ user_name }},</h2>
                    <p>Your IOFlow account password has been successfully changed.</p>
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong>
                        <p>If you did not make this change, please contact your administrator immediately 
                        and reset your password as soon as possible.</p>
                    </div>
                    <p>For security reasons, you may need to sign in again on all your devices.</p>
                    <h3>Security Tips:</h3>
                    <ul>
                        <li>Use a strong, unique password</li>
                        <li>Never share your password with anyone</li>
                        <li>Enable two-factor authentication if available</li>
                        <li>Regularly update your password</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>© 2024 IOFlow. All rights reserved.</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_template = """
        Hello {{ user_name }},
        
        Your IOFlow account password has been successfully changed.
        
        ⚠️ Security Notice:
        If you did not make this change, please contact your administrator immediately 
        and reset your password as soon as possible.
        
        For security reasons, you may need to sign in again on all your devices.
        
        Security Tips:
        - Use a strong, unique password
        - Never share your password with anyone
        - Enable two-factor authentication if available
        - Regularly update your password
        
        Best regards,
        IOFlow Team
        """
        
        # Render templates
        html_body = Template(html_template).render(user_name=user_name)
        text_body = Template(text_template).render(user_name=user_name)

        return self.send_email(
            tenant_id=tenant_id,
            to_email=to_email,
            subject=subject,
            body_html=html_body,
            body_text=text_body
        )

    def send_hitl_task_notification(
        self,
        tenant_id: str,
        to_email: str,
        user_name: str,
        task_title: str,
        task_type: str,
        flow_name: str,
        priority: str,
        action_url: str,
        task_token: str = None
    ) -> bool:
        """Send HITL task notification email to an assigned user."""
        type_labels = {
            'review': 'Review',
            'edit': 'Edit & Submit',
            'approve_reject': 'Approve or Reject',
        }
        type_label = type_labels.get(task_type, task_type.title())
        priority_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545',
        }
        priority_color = priority_colors.get(priority, '#ffc107')

        subject = f"[IOFlow] Action Required: {task_title}"

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #7c3aed; color: white; padding: 20px; text-align: center; }
                .content { background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }
                .task-info { background-color: #fff; border: 1px solid #e5e7eb; padding: 15px;
                            border-radius: 4px; margin: 20px 0; }
                .task-info table { width: 100%; }
                .task-info td { padding: 8px 0; }
                .task-info td:first-child { font-weight: bold; width: 120px; color: #666; }
                .priority-badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
                                 color: white; font-size: 12px; font-weight: bold; }
                .btn { display: inline-block; padding: 12px 24px; border-radius: 6px;
                      text-decoration: none; font-weight: bold; margin: 5px; }
                .btn-primary { background-color: #7c3aed; color: white; }
                .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Action Required</h1>
                </div>
                <div class="content">
                    <h2>Hello {{ user_name }},</h2>
                    <p>A task requires your attention in IOFlow.</p>
                    <div class="task-info">
                        <table>
                            <tr><td>Task</td><td>{{ task_title }}</td></tr>
                            <tr><td>Type</td><td>{{ type_label }}</td></tr>
                            <tr><td>Flow</td><td>{{ flow_name }}</td></tr>
                            <tr><td>Priority</td><td>
                                <span class="priority-badge" style="background-color: {{ priority_color }}">
                                    {{ priority }}
                                </span>
                            </td></tr>
                        </table>
                    </div>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{ action_url }}" class="btn btn-primary">Open Task</a>
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; 2024 IOFlow. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_template = """
        Hello {{ user_name }},

        A task requires your attention in IOFlow.

        Task: {{ task_title }}
        Type: {{ type_label }}
        Flow: {{ flow_name }}
        Priority: {{ priority }}

        Open the task: {{ action_url }}

        Best regards,
        IOFlow Team
        """

        html_body = Template(html_template).render(
            user_name=user_name,
            task_title=task_title,
            type_label=type_label,
            flow_name=flow_name,
            priority=priority,
            priority_color=priority_color,
            action_url=action_url,
        )
        text_body = Template(text_template).render(
            user_name=user_name,
            task_title=task_title,
            type_label=type_label,
            flow_name=flow_name,
            priority=priority,
            action_url=action_url,
        )

        return self.send_email(
            tenant_id=tenant_id,
            to_email=to_email,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
        )
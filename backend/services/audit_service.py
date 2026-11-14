"""
Audit logging service for tracking user actions and security events
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
import json
import uuid

from db.models import User, Base
from core.config import settings

logger = logging.getLogger(__name__)

# Audit log model
class AuditLog(Base):
    __tablename__ = 'audit_logs'
    __table_args__ = {'schema': 'ioflow'}
    
    audit_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(String(36), nullable=True)  # Null for system events
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    tenant_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default='success')  # success, failure, error
    error_message = Column(Text, nullable=True)

class AuditService:
    """Service for logging and managing audit trails"""
    
    # Action types
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTER = "user.register"
    USER_ACTIVATE = "user.activate"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"
    USER_STATUS_CHANGE = "user.status_change"
    
    TENANT_CREATE = "tenant.create"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"
    
    APP_CREATE = "app.create"
    APP_UPDATE = "app.update"
    APP_DELETE = "app.delete"
    APP_AUTH_UPDATE = "app.auth_update"
    
    FLOW_CREATE = "flow.create"
    FLOW_UPDATE = "flow.update"
    FLOW_DELETE = "flow.delete"
    FLOW_EXECUTE = "flow.execute"
    
    PERMISSION_DENIED = "permission.denied"
    TENANT_ACCESS_DENIED = "tenant.access_denied"
    
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        resource_type: str,
        user: Optional[User] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """Log an audit entry"""
        try:
            audit_entry = AuditLog(
                user_id=user.user_id if user else None,
                user_email=user.email if user else None,
                user_role=user.role.value if user and user.role else None,
                tenant_id=user.tenant_id if user else None,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message
            )
            
            db.add(audit_entry)
            db.commit()
            
            # Also log to application logger
            log_message = f"AUDIT: {action} by {user.email if user else 'system'} on {resource_type}"
            if resource_id:
                log_message += f" [{resource_id}]"
            if status != "success":
                log_message += f" - {status}: {error_message}"
            
            if status == "success":
                logger.info(log_message)
            else:
                logger.warning(log_message)
                
        except Exception as e:
            logger.error(f"Failed to write audit log: {str(e)}")
            # Don't raise - audit logging should not break the application
    
    @staticmethod
    def log_login(db: Session, user: User, ip_address: str = None, user_agent: str = None, success: bool = True):
        """Log user login attempt"""
        AuditService.log_action(
            db=db,
            action=AuditService.USER_LOGIN,
            resource_type="user",
            user=user if success else None,
            resource_id=user.user_id,
            details={"email": user.email},
            ip_address=ip_address,
            user_agent=user_agent,
            status="success" if success else "failure",
            error_message=None if success else "Invalid credentials"
        )
    
    @staticmethod
    def log_permission_denied(
        db: Session, 
        user: User, 
        resource_type: str, 
        action: str,
        resource_id: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Log permission denied events"""
        AuditService.log_action(
            db=db,
            action=AuditService.PERMISSION_DENIED,
            resource_type=resource_type,
            user=user,
            resource_id=resource_id,
            details={
                "attempted_action": action,
                "user_role": user.role.value if user.role else None
            },
            ip_address=ip_address,
            user_agent=user_agent,
            status="failure",
            error_message=f"Permission denied for {action} on {resource_type}"
        )
    
    @staticmethod
    def log_role_change(
        db: Session,
        changed_by: User,
        target_user: User,
        old_role: str,
        new_role: str,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Log user role changes"""
        AuditService.log_action(
            db=db,
            action=AuditService.USER_ROLE_CHANGE,
            resource_type="user",
            user=changed_by,
            resource_id=target_user.user_id,
            details={
                "target_user_email": target_user.email,
                "old_role": old_role,
                "new_role": new_role
            },
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def get_user_activity(
        db: Session,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Get audit logs for a specific user"""
        logs = db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "audit_id": log.audit_id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": json.loads(log.details) if log.details else None,
                "status": log.status,
                "error_message": log.error_message
            }
            for log in logs
        ]
    
    @staticmethod
    def get_tenant_activity(
        db: Session,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Get audit logs for a specific tenant"""
        logs = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "audit_id": log.audit_id,
                "timestamp": log.timestamp.isoformat(),
                "user_email": log.user_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": json.loads(log.details) if log.details else None,
                "status": log.status,
                "error_message": log.error_message
            }
            for log in logs
        ]
    
    @staticmethod
    def get_security_events(
        db: Session,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """Get security-related audit logs (failures, permission denials)"""
        logs = db.query(AuditLog).filter(
            AuditLog.status != 'success'
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "audit_id": log.audit_id,
                "timestamp": log.timestamp.isoformat(),
                "user_email": log.user_email,
                "tenant_id": log.tenant_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": json.loads(log.details) if log.details else None,
                "status": log.status,
                "error_message": log.error_message,
                "ip_address": log.ip_address
            }
            for log in logs
        ]

# Create audit service instance
audit_service = AuditService()
"""
HITL Notification Service - Sends notifications to assigned users via WebSocket and email.
"""
import logging
from datetime import datetime
from typing import List

from db.models import HITLTask, HITLTaskAssignment, HITLUserRole, User
from db.database import get_tenant_db
from services.websocket_manager import manager as ws_manager
from services.email_service import EmailService
from core.config import settings

logger = logging.getLogger(__name__)


class HITLNotificationService:
    """Handles sending notifications to HITL task assignees."""

    def _resolve_assignee_users(self, task_id: str, tenant_id: str, db) -> List[User]:
        """Resolve all assignments to actual user records."""
        assignments = db.query(HITLTaskAssignment).filter(
            HITLTaskAssignment.task_id == task_id
        ).all()

        user_ids = set()
        for assignment in assignments:
            if assignment.assignee_type == 'user':
                user_ids.add(assignment.assignee_id)
            elif assignment.assignee_type == 'hitl_role':
                # Expand role to users
                role_users = db.query(HITLUserRole).filter(
                    HITLUserRole.hitl_role_id == assignment.assignee_id,
                    HITLUserRole.tenant_id == tenant_id,
                ).all()
                for ru in role_users:
                    user_ids.add(ru.user_id)

        if not user_ids:
            return []

        users = db.query(User).filter(User.user_id.in_(list(user_ids))).all()
        return users

    async def notify_assignees(self, task_id: str, tenant_id: str, schema_name: str):
        """Send notifications to all users assigned to a HITL task."""
        with get_tenant_db(schema_name) as db:
            task = db.query(HITLTask).filter(HITLTask.task_id == task_id).first()
            if not task:
                logger.warning(f"HITL task {task_id} not found for notification")
                return

            users = self._resolve_assignee_users(task_id, tenant_id, db)
            if not users:
                logger.warning(f"No users found for HITL task {task_id}")
                return

            flow_name = ''
            if task.task_metadata:
                flow_name = task.task_metadata.get('flow_name', '')

            action_url = f"{settings.frontend_url}/tasks" if hasattr(settings, 'frontend_url') else '/tasks'

            # Send WebSocket notifications
            for user in users:
                try:
                    await ws_manager.send_to_user(
                        user_id=user.user_id,
                        tenant_id=tenant_id,
                        message={
                            'type': 'hitl_task_created',
                            'task_id': task.task_id,
                            'task_type': task.task_type,
                            'title': task.title,
                            'priority': task.priority,
                            'flow_name': flow_name,
                            'timestamp': datetime.utcnow().isoformat(),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to send WebSocket notification to user {user.user_id}: {e}")

            # Send email notifications
            try:
                email_service = EmailService()
                for user in users:
                    try:
                        email_service.send_hitl_task_notification(
                            tenant_id=tenant_id,
                            to_email=user.email,
                            user_name=user.user_name,
                            task_title=task.title,
                            task_type=task.task_type,
                            flow_name=flow_name,
                            priority=task.priority,
                            action_url=action_url,
                            task_token=task.task_token,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send email notification to {user.email}: {e}")
            except Exception as e:
                logger.warning(f"Failed to initialize email service for HITL notifications: {e}")

            # Update notified_at on assignments
            now = datetime.utcnow()
            assignments = db.query(HITLTaskAssignment).filter(
                HITLTaskAssignment.task_id == task_id
            ).all()
            for assignment in assignments:
                assignment.notified_at = now
            db.commit()

            logger.info(f"Sent HITL notifications for task {task_id} to {len(users)} user(s)")


# Singleton instance
hitl_notification_service = HITLNotificationService()

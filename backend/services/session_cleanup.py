"""
Session Cleanup Service - Background task for cleaning up expired sessions.

Provides periodic cleanup of:
- Expired chat sessions
- Expired node session states
- Stale ADK sessions in memory

This service can be called periodically or on-demand to maintain
database hygiene and free up resources.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from services.node_session_service import (
    get_chat_session_service,
    get_node_session_service,
    DEFAULT_SESSION_TTL_HOURS
)

logger = logging.getLogger(__name__)

# Track last cleanup time per tenant
_last_cleanup: Dict[str, datetime] = {}

# Minimum interval between automatic cleanups (in seconds)
MIN_CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour


class SessionCleanupService:
    """
    Service for cleaning up expired sessions.

    Handles cleanup of both chat sessions and node session states,
    as well as in-memory ADK sessions that are no longer needed.
    """

    def __init__(self, db_session_factory=None):
        """
        Initialize the cleanup service.

        Args:
            db_session_factory: Optional database session factory.
                               If not provided, will use default tenant_db.
        """
        self.chat_session_service = get_chat_session_service(db_session_factory)
        self.node_session_service = get_node_session_service(db_session_factory)

    def cleanup_expired_sessions(
        self,
        tenant_id: str,
        schema_name: Optional[str] = None,
        max_age_hours: int = DEFAULT_SESSION_TTL_HOURS,
        force: bool = False
    ) -> Dict[str, int]:
        """
        Clean up expired sessions for a tenant.

        Args:
            tenant_id: The tenant ID to clean up sessions for
            schema_name: Optional schema name for multi-tenant database
            max_age_hours: Maximum age in hours before a session is expired
            force: If True, bypass the minimum cleanup interval check

        Returns:
            Dict with cleanup counts:
                - chat_sessions: Number of expired chat sessions cleaned up
                - node_sessions: Number of expired node sessions cleaned up
        """
        global _last_cleanup

        # Check if we should skip cleanup based on interval
        if not force:
            last_cleanup = _last_cleanup.get(tenant_id)
            if last_cleanup:
                elapsed = (datetime.utcnow() - last_cleanup).total_seconds()
                if elapsed < MIN_CLEANUP_INTERVAL_SECONDS:
                    logger.debug(
                        f"Skipping cleanup for tenant {tenant_id}, "
                        f"last cleanup was {elapsed:.0f}s ago"
                    )
                    return {'chat_sessions': 0, 'node_sessions': 0, 'skipped': True}

        try:
            # Clean up expired chat sessions (this also cleans associated node sessions)
            chat_count = self.chat_session_service.cleanup_expired_sessions(
                tenant_id=tenant_id,
                schema_name=schema_name
            )

            # Also clean up any orphaned node sessions
            node_count = self.node_session_service.cleanup_expired_sessions(
                tenant_id=tenant_id,
                max_age_hours=max_age_hours,
                schema_name=schema_name
            )

            # Update last cleanup time
            _last_cleanup[tenant_id] = datetime.utcnow()

            if chat_count > 0 or node_count > 0:
                logger.info(
                    f"Cleaned up {chat_count} chat sessions and "
                    f"{node_count} node sessions for tenant {tenant_id}"
                )

            return {
                'chat_sessions': chat_count,
                'node_sessions': node_count,
                'skipped': False
            }

        except Exception as e:
            logger.error(f"Error during session cleanup for tenant {tenant_id}: {e}", exc_info=True)
            return {'chat_sessions': 0, 'node_sessions': 0, 'error': str(e)}

    def cleanup_all_tenants(
        self,
        schema_name: Optional[str] = None,
        max_age_hours: int = DEFAULT_SESSION_TTL_HOURS
    ) -> Dict[str, Any]:
        """
        Clean up expired sessions for all tenants.

        This is typically called by a background task or cron job.

        Args:
            schema_name: Optional schema name for multi-tenant database
            max_age_hours: Maximum age in hours before a session is expired

        Returns:
            Dict with aggregate cleanup results
        """
        from db.models import ChatSession

        try:
            # Get all unique tenant IDs with sessions
            with self.chat_session_service.db_session_factory(schema_name) as db:
                tenant_ids = db.query(ChatSession.tenant_id).distinct().all()
                tenant_ids = [t[0] for t in tenant_ids]

            total_chat = 0
            total_node = 0
            errors = []

            for tenant_id in tenant_ids:
                result = self.cleanup_expired_sessions(
                    tenant_id=tenant_id,
                    schema_name=schema_name,
                    max_age_hours=max_age_hours,
                    force=True  # Force cleanup for all tenants task
                )
                if 'error' in result:
                    errors.append({'tenant_id': tenant_id, 'error': result['error']})
                else:
                    total_chat += result.get('chat_sessions', 0)
                    total_node += result.get('node_sessions', 0)

            logger.info(
                f"All-tenant cleanup complete: {total_chat} chat sessions, "
                f"{total_node} node sessions, {len(errors)} errors"
            )

            return {
                'total_chat_sessions': total_chat,
                'total_node_sessions': total_node,
                'tenants_processed': len(tenant_ids),
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error during all-tenant cleanup: {e}", exc_info=True)
            return {'error': str(e)}

    def cleanup_adk_sessions(self) -> int:
        """
        Clean up stale ADK sessions from memory.

        This removes ADK sessions that are no longer associated with
        active chat sessions.

        Returns:
            Number of ADK sessions cleaned up
        """
        try:
            from services.flow_agent_executor import SESSION_SERVICE

            if SESSION_SERVICE is None:
                logger.warning("ADK SESSION_SERVICE not available")
                return 0

            # Note: The InMemorySessionService doesn't expose a way to
            # list or iterate sessions. ADK sessions are typically cleaned
            # up when the chat session ends via the ChatSessionService.
            # This method is a placeholder for future cleanup logic if
            # ADK provides better session management APIs.

            logger.debug("ADK session cleanup - no action needed (managed by ADK)")
            return 0

        except Exception as e:
            logger.error(f"Error during ADK session cleanup: {e}", exc_info=True)
            return 0


# Singleton instance
_cleanup_service: Optional[SessionCleanupService] = None


def get_cleanup_service(db_session_factory=None) -> SessionCleanupService:
    """Get the global SessionCleanupService instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = SessionCleanupService(db_session_factory)
    return _cleanup_service


async def run_periodic_cleanup(
    interval_seconds: int = 3600,
    max_age_hours: int = DEFAULT_SESSION_TTL_HOURS
):
    """
    Run periodic cleanup in the background.

    This is an async task that can be started at application startup
    to periodically clean up expired sessions.

    Args:
        interval_seconds: Interval between cleanup runs (default: 1 hour)
        max_age_hours: Maximum age in hours before a session is expired
    """
    cleanup_service = get_cleanup_service()

    logger.info(
        f"Starting periodic session cleanup (interval: {interval_seconds}s, "
        f"max_age: {max_age_hours}h)"
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            result = cleanup_service.cleanup_all_tenants(
                max_age_hours=max_age_hours
            )

            if 'error' not in result:
                logger.info(
                    f"Periodic cleanup completed: "
                    f"{result.get('total_chat_sessions', 0)} chat sessions, "
                    f"{result.get('total_node_sessions', 0)} node sessions"
                )

        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
            # Continue running despite errors
            continue

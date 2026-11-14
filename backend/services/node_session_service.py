"""
Node Session Service - Generic session management for stateful nodes.

Provides a database-backed, multi-worker safe session management system
that any node type can use for maintaining state across flow executions.

Primary use case: AI Agent nodes maintaining conversation continuity
across multiple flow invocations within a chat session.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

logger = logging.getLogger(__name__)

# Default session TTL in hours
DEFAULT_SESSION_TTL_HOURS = 24


class NodeSessionService:
    """
    Generic service for managing node session state.
    Multi-worker safe through database-backed storage.

    This service provides a reusable pattern for any node type that needs
    to maintain persistent state across flow executions.

    For AI Agent nodes: Maps (node_id, chat_session_id) -> agent_session_id
    """

    def __init__(self, db_session_factory):
        """
        Initialize the service with a database session factory.

        Args:
            db_session_factory: Callable that returns a database session context manager
        """
        self.db_session_factory = db_session_factory

    def get_or_create_session(
        self,
        node_id: str,
        chat_session_id: str,
        tenant_id: str,
        node_type: str,
        user_id: Optional[str] = None,
        flow_id: Optional[str] = None,
        schema_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get existing session or create a new one.

        Args:
            node_id: The ID of the node in the flow
            chat_session_id: The chat session ID
            tenant_id: The tenant ID
            node_type: Type of node (e.g., 'agent')
            user_id: Optional user ID
            flow_id: Optional flow ID
            schema_name: Optional schema name for multi-tenant DB

        Returns:
            Dict with:
                - id: Session record ID
                - agent_session_id: ADK session ID (if exists)
                - is_new: Whether this is a new session
                - session_data: Any additional session data
                - invocation_count: Number of times this session was invoked
        """
        from db.models import NodeSessionState

        try:
            with self.db_session_factory(schema_name) as db:
                # Look for existing session
                existing = db.query(NodeSessionState).filter(
                    and_(
                        NodeSessionState.node_id == node_id,
                        NodeSessionState.chat_session_id == chat_session_id,
                        NodeSessionState.tenant_id == tenant_id,
                        NodeSessionState.is_active == True
                    )
                ).first()

                if existing:
                    # Update last invocation time and increment count
                    existing.last_invocation_at = datetime.utcnow()
                    existing.invocation_count = (existing.invocation_count or 0) + 1
                    db.commit()

                    logger.info(f"Found existing node session for node={node_id}, chat_session={chat_session_id[:8]}...")

                    return {
                        'id': existing.id,
                        'agent_session_id': existing.agent_session_id,
                        'is_new': False,
                        'session_data': existing.session_data,
                        'invocation_count': existing.invocation_count
                    }

                # Create new session
                new_session = NodeSessionState(
                    id=str(uuid.uuid4()),
                    node_id=node_id,
                    chat_session_id=chat_session_id,
                    tenant_id=tenant_id,
                    node_type=node_type,
                    user_id=user_id,
                    flow_id=flow_id,
                    invocation_count=1,
                    is_active=True
                )
                db.add(new_session)
                db.commit()

                logger.info(f"Created new node session for node={node_id}, chat_session={chat_session_id[:8]}...")

                return {
                    'id': new_session.id,
                    'agent_session_id': None,
                    'is_new': True,
                    'session_data': None,
                    'invocation_count': 1
                }

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {e}", exc_info=True)
            raise

    def update_session(
        self,
        node_id: str,
        chat_session_id: str,
        tenant_id: str,
        agent_session_id: Optional[str] = None,
        session_data: Optional[Dict[str, Any]] = None,
        schema_name: Optional[str] = None
    ) -> bool:
        """
        Update session with new data.

        Args:
            node_id: The node ID
            chat_session_id: The chat session ID
            tenant_id: The tenant ID
            agent_session_id: Optional ADK session ID to store
            session_data: Optional additional data to store
            schema_name: Optional schema name

        Returns:
            True if update was successful, False otherwise
        """
        from db.models import NodeSessionState

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(NodeSessionState).filter(
                    and_(
                        NodeSessionState.node_id == node_id,
                        NodeSessionState.chat_session_id == chat_session_id,
                        NodeSessionState.tenant_id == tenant_id,
                        NodeSessionState.is_active == True
                    )
                ).first()

                if not session:
                    logger.warning(f"No session found to update for node={node_id}, chat_session={chat_session_id[:8]}...")
                    return False

                if agent_session_id is not None:
                    session.agent_session_id = agent_session_id

                if session_data is not None:
                    session.session_data = session_data

                session.last_invocation_at = datetime.utcnow()
                db.commit()

                logger.info(f"Updated node session for node={node_id}, agent_session={agent_session_id}")
                return True

        except Exception as e:
            logger.error(f"Error in update_session: {e}", exc_info=True)
            return False

    def get_session(
        self,
        node_id: str,
        chat_session_id: str,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get session if it exists.

        Returns:
            Dict with session data or None if not found
        """
        from db.models import NodeSessionState

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(NodeSessionState).filter(
                    and_(
                        NodeSessionState.node_id == node_id,
                        NodeSessionState.chat_session_id == chat_session_id,
                        NodeSessionState.tenant_id == tenant_id,
                        NodeSessionState.is_active == True
                    )
                ).first()

                if not session:
                    return None

                return {
                    'id': session.id,
                    'agent_session_id': session.agent_session_id,
                    'session_data': session.session_data,
                    'invocation_count': session.invocation_count,
                    'first_invocation_at': session.first_invocation_at,
                    'last_invocation_at': session.last_invocation_at
                }

        except Exception as e:
            logger.error(f"Error in get_session: {e}", exc_info=True)
            return None

    def end_session(
        self,
        node_id: str,
        chat_session_id: str,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> bool:
        """
        Mark a session as inactive.

        Returns:
            True if session was ended, False otherwise
        """
        from db.models import NodeSessionState

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(NodeSessionState).filter(
                    and_(
                        NodeSessionState.node_id == node_id,
                        NodeSessionState.chat_session_id == chat_session_id,
                        NodeSessionState.tenant_id == tenant_id,
                        NodeSessionState.is_active == True
                    )
                ).first()

                if not session:
                    return False

                session.is_active = False
                db.commit()

                logger.info(f"Ended node session for node={node_id}, chat_session={chat_session_id[:8]}...")
                return True

        except Exception as e:
            logger.error(f"Error in end_session: {e}", exc_info=True)
            return False

    def cleanup_expired_sessions(
        self,
        tenant_id: str,
        max_age_hours: int = DEFAULT_SESSION_TTL_HOURS,
        schema_name: Optional[str] = None
    ) -> int:
        """
        Remove expired sessions.

        Args:
            tenant_id: The tenant ID
            max_age_hours: Maximum age in hours before a session is considered expired
            schema_name: Optional schema name

        Returns:
            Count of deleted sessions
        """
        from db.models import NodeSessionState

        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            with self.db_session_factory(schema_name) as db:
                expired_sessions = db.query(NodeSessionState).filter(
                    and_(
                        NodeSessionState.tenant_id == tenant_id,
                        NodeSessionState.last_invocation_at < cutoff_time
                    )
                ).all()

                count = len(expired_sessions)
                for session in expired_sessions:
                    db.delete(session)

                db.commit()

                if count > 0:
                    logger.info(f"Cleaned up {count} expired node sessions for tenant={tenant_id}")

                return count

        except Exception as e:
            logger.error(f"Error in cleanup_expired_sessions: {e}", exc_info=True)
            return 0


class ChatSessionService:
    """
    Manages chat sessions for flows with chat_input triggers.

    A chat session represents a conversation with a flow that can span
    multiple flow executions. Each execution within a chat session
    can maintain state for individual nodes (like AI Agents).
    """

    def __init__(self, db_session_factory):
        """
        Initialize the service with a database session factory.

        Args:
            db_session_factory: Callable that returns a database session context manager
        """
        self.db_session_factory = db_session_factory
        self.node_session_service = NodeSessionService(db_session_factory)

    def create_session(
        self,
        tenant_id: str,
        flow_id: str,
        user_id: str,
        ttl_hours: int = DEFAULT_SESSION_TTL_HOURS,
        schema_name: Optional[str] = None
    ) -> str:
        """
        Create a new chat session.

        Args:
            tenant_id: The tenant ID
            flow_id: The flow ID
            user_id: The user ID
            ttl_hours: Time-to-live in hours (default 24)
            schema_name: Optional schema name

        Returns:
            The new session ID
        """
        from db.models import ChatSession

        try:
            session_id = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

            with self.db_session_factory(schema_name) as db:
                new_session = ChatSession(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    flow_id=flow_id,
                    user_id=user_id,
                    status='active',
                    message_count=0,
                    expires_at=expires_at
                )
                db.add(new_session)
                db.commit()

                logger.info(f"Created new chat session: {session_id[:8]}... for flow={flow_id[:8]}...")
                return session_id

        except Exception as e:
            logger.error(f"Error creating chat session: {e}", exc_info=True)
            raise

    def get_session(
        self,
        session_id: str,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get chat session metadata.

        Returns:
            Dict with session data or None if not found
        """
        from db.models import ChatSession

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(ChatSession).filter(
                    and_(
                        ChatSession.session_id == session_id,
                        ChatSession.tenant_id == tenant_id
                    )
                ).first()

                if not session:
                    return None

                # Check if expired
                if session.expires_at and session.expires_at < datetime.utcnow():
                    session.status = 'expired'
                    db.commit()

                return {
                    'session_id': session.session_id,
                    'flow_id': session.flow_id,
                    'user_id': session.user_id,
                    'status': session.status,
                    'created_at': session.created_at,
                    'last_message_at': session.last_message_at,
                    'message_count': session.message_count,
                    'expires_at': session.expires_at
                }

        except Exception as e:
            logger.error(f"Error getting chat session: {e}", exc_info=True)
            return None

    def update_session_activity(
        self,
        session_id: str,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> bool:
        """
        Update last_message_at and increment message_count.

        Returns:
            True if update was successful
        """
        from db.models import ChatSession

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(ChatSession).filter(
                    and_(
                        ChatSession.session_id == session_id,
                        ChatSession.tenant_id == tenant_id,
                        ChatSession.status == 'active'
                    )
                ).first()

                if not session:
                    logger.warning(f"Chat session not found or not active: {session_id[:8]}...")
                    return False

                # Check if expired
                if session.expires_at and session.expires_at < datetime.utcnow():
                    session.status = 'expired'
                    db.commit()
                    logger.warning(f"Chat session expired: {session_id[:8]}...")
                    return False

                session.last_message_at = datetime.utcnow()
                session.message_count = (session.message_count or 0) + 1
                db.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating chat session activity: {e}", exc_info=True)
            return False

    def end_session(
        self,
        session_id: str,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> bool:
        """
        End a chat session and cleanup all associated node sessions.

        Returns:
            True if session was ended successfully
        """
        from db.models import ChatSession, NodeSessionState

        try:
            with self.db_session_factory(schema_name) as db:
                session = db.query(ChatSession).filter(
                    and_(
                        ChatSession.session_id == session_id,
                        ChatSession.tenant_id == tenant_id
                    )
                ).first()

                if not session:
                    logger.warning(f"Chat session not found: {session_id[:8]}...")
                    return False

                # Mark chat session as ended
                session.status = 'ended'

                # Delete all associated node sessions
                deleted_count = db.query(NodeSessionState).filter(
                    NodeSessionState.chat_session_id == session_id
                ).delete()

                db.commit()

                logger.info(f"Ended chat session {session_id[:8]}..., cleaned up {deleted_count} node sessions")
                return True

        except Exception as e:
            logger.error(f"Error ending chat session: {e}", exc_info=True)
            return False

    def cleanup_expired_sessions(
        self,
        tenant_id: str,
        schema_name: Optional[str] = None
    ) -> int:
        """
        Cleanup expired chat sessions and their associated node sessions.

        Returns:
            Count of deleted chat sessions
        """
        from db.models import ChatSession, NodeSessionState

        try:
            now = datetime.utcnow()

            with self.db_session_factory(schema_name) as db:
                # Find expired sessions
                expired_sessions = db.query(ChatSession).filter(
                    and_(
                        ChatSession.tenant_id == tenant_id,
                        ChatSession.status == 'active',
                        ChatSession.expires_at < now
                    )
                ).all()

                count = 0
                for session in expired_sessions:
                    # Delete associated node sessions
                    db.query(NodeSessionState).filter(
                        NodeSessionState.chat_session_id == session.session_id
                    ).delete()

                    # Mark as expired
                    session.status = 'expired'
                    count += 1

                db.commit()

                if count > 0:
                    logger.info(f"Cleaned up {count} expired chat sessions for tenant={tenant_id}")

                return count

        except Exception as e:
            logger.error(f"Error cleaning up expired chat sessions: {e}", exc_info=True)
            return 0


# Singleton instances for global access
_node_session_service: Optional[NodeSessionService] = None
_chat_session_service: Optional[ChatSessionService] = None


def _default_db_session_factory(schema_name=None):
    """Default database session factory using get_db_context."""
    from db.database import get_db_context
    return get_db_context()


def get_node_session_service(db_session_factory=None) -> NodeSessionService:
    """Get the global NodeSessionService instance."""
    global _node_session_service
    if _node_session_service is None:
        if db_session_factory is None:
            db_session_factory = _default_db_session_factory
        _node_session_service = NodeSessionService(db_session_factory)
    return _node_session_service


def get_chat_session_service(db_session_factory=None) -> ChatSessionService:
    """Get the global ChatSessionService instance."""
    global _chat_session_service
    if _chat_session_service is None:
        if db_session_factory is None:
            db_session_factory = _default_db_session_factory
        _chat_session_service = ChatSessionService(db_session_factory)
    return _chat_session_service

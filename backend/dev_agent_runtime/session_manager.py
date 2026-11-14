"""
Session Manager for Agent Executions

Manages execution sessions, tracking their state and messages.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session execution status"""
    CREATED = "created"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class AgentMessage:
    """Represents a message in the agent conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSession:
    """Represents an agent execution session"""
    session_id: str
    agent_id: str
    model: str
    status: SessionStatus
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: List[AgentMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def add_message(self, role: str, content: str, **metadata):
        """Add a message to the session"""
        message = AgentMessage(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def set_status(self, status: SessionStatus):
        """Update session status"""
        self.status = status
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in self.messages
            ],
            "metadata": self.metadata,
            "error": self.error
        }


class SessionManager:
    """
    Manages agent execution sessions
    """

    def __init__(self):
        self.sessions: Dict[str, ExecutionSession] = {}
        self.active_tasks: Dict[str, Any] = {}  # Maps session_id to asyncio tasks
        # Track user-agent sessions for conversation persistence
        self.user_agent_sessions: Dict[str, str] = {}  # Maps "user_id:agent_id" to session_id

    def create_session(
        self,
        session_id: Optional[str] = None,
        agent_id: str = "",
        model: str = ""
    ) -> ExecutionSession:
        """Create a new execution session"""
        if not session_id:
            session_id = str(uuid.uuid4())

        session = ExecutionSession(
            session_id=session_id,
            agent_id=agent_id,
            model=model,
            status=SessionStatus.CREATED
        )

        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} for agent {agent_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ExecutionSession]:
        """Get a session by ID"""
        return self.sessions.get(session_id)

    def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """Update the status of a session"""
        session = self.get_session(session_id)
        if session:
            session.set_status(status)
            logger.info(f"Updated session {session_id} status to {status.value}")
            return True
        return False

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **metadata
    ) -> Optional[AgentMessage]:
        """Add a message to a session"""
        session = self.get_session(session_id)
        if session:
            message = session.add_message(role, content, **metadata)
            logger.debug(f"Added {role} message to session {session_id}")
            return message
        return None

    def set_session_error(self, session_id: str, error: str):
        """Set error message for a session"""
        session = self.get_session(session_id)
        if session:
            session.error = error
            session.set_status(SessionStatus.ERROR)
            logger.error(f"Session {session_id} error: {error}")

    def complete_session(self, session_id: str):
        """Mark a session as completed"""
        self.update_session_status(session_id, SessionStatus.COMPLETED)

    def cancel_session(self, session_id: str):
        """Mark a session as cancelled"""
        self.update_session_status(session_id, SessionStatus.CANCELLED)

    def get_active_sessions(self) -> List[ExecutionSession]:
        """Get all active sessions"""
        return [
            session for session in self.sessions.values()
            if session.status in [SessionStatus.CREATED, SessionStatus.RUNNING, SessionStatus.STREAMING]
        ]

    def cleanup_old_sessions(self, hours: int = 24):
        """Remove sessions older than specified hours"""
        cutoff = datetime.now()
        sessions_to_remove = []

        for session_id, session in self.sessions.items():
            age = (cutoff - session.created_at).total_seconds() / 3600
            if age > hours and session.status in [SessionStatus.COMPLETED, SessionStatus.CANCELLED, SessionStatus.ERROR]:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            logger.info(f"Cleaned up old session {session_id}")

        return len(sessions_to_remove)

    def register_task(self, session_id: str, task: Any):
        """Register an asyncio task for a session"""
        self.active_tasks[session_id] = task

    def get_task(self, session_id: str) -> Any:
        """Get the asyncio task for a session"""
        return self.active_tasks.get(session_id)

    def unregister_task(self, session_id: str):
        """Remove a task registration"""
        if session_id in self.active_tasks:
            del self.active_tasks[session_id]

    def get_session_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session history"""
        sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.created_at,
            reverse=True
        )[:limit]

        return [session.to_dict() for session in sessions]

    def get_user_agent_session(self, user_id: str, agent_id: str) -> Optional[ExecutionSession]:
        """
        Get existing session for user-agent combination if it exists.
        """
        session_key = f"{user_id}:{agent_id}"

        if session_key in self.user_agent_sessions:
            session_id = self.user_agent_sessions[session_key]
            session = self.get_session(session_id)
            if session and session.status in [SessionStatus.CREATED, SessionStatus.RUNNING]:
                return session

        return None

    def get_or_create_user_agent_session(
        self,
        user_id: str,
        agent_id: str,
        model: str = "",
        force_new: bool = False
    ) -> ExecutionSession:
        """
        Get existing session for user-agent combination or create new one.
        This enables conversation persistence across multiple prompts.
        """
        session_key = f"{user_id}:{agent_id}"

        # If force_new is True, clear existing session
        if force_new and session_key in self.user_agent_sessions:
            old_session_id = self.user_agent_sessions[session_key]
            if old_session_id in self.sessions:
                # Mark old session as completed
                self.complete_session(old_session_id)
            del self.user_agent_sessions[session_key]

        # Check if we have an existing active session for this user-agent pair
        if session_key in self.user_agent_sessions:
            session_id = self.user_agent_sessions[session_key]
            session = self.get_session(session_id)

            # If session exists and is still active, return it
            if session and session.status in [SessionStatus.CREATED, SessionStatus.RUNNING, SessionStatus.COMPLETED]:
                logger.info(f"Reusing existing session {session_id} for user {user_id} and agent {agent_id}")
                # Reset status to RUNNING for continued conversation
                if session.status == SessionStatus.COMPLETED:
                    session.set_status(SessionStatus.RUNNING)
                return session

        # Create new session
        session_id = f"{user_id}_{agent_id}_{uuid.uuid4().hex[:8]}"
        session = self.create_session(
            session_id=session_id,
            agent_id=agent_id,
            model=model
        )

        # Track this session for the user-agent pair
        self.user_agent_sessions[session_key] = session_id
        logger.info(f"Created new persistent session {session_id} for user {user_id} and agent {agent_id}")

        return session

    def clear_user_agent_session(self, user_id: str, agent_id: str) -> bool:
        """
        Clear the conversation history for a specific user-agent combination
        """
        session_key = f"{user_id}:{agent_id}"

        if session_key in self.user_agent_sessions:
            session_id = self.user_agent_sessions[session_key]

            # Mark session as completed
            if session_id in self.sessions:
                self.complete_session(session_id)

            # Remove the mapping
            del self.user_agent_sessions[session_key]
            logger.info(f"Cleared session for user {user_id} and agent {agent_id}")
            return True

        return False
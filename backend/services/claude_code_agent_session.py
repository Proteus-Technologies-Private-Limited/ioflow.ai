"""
In-memory session model for Claude Code agent conversations in IOFlow.

Sessions are stored in-process with a configurable TTL (default 30 minutes).
No persistence -- restarting the server clears all sessions.
Adapted from twasta.ai's agent session implementation.
"""
import asyncio
import secrets
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ClaudeCodeAgentSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    working_dir: str = ""
    claude_session_id: str | None = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    # Shared secret between this session and its CLI's permission hook, so only
    # that hook can answer /permission/{session_id} (the session id alone is
    # not a credential).
    hook_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)

    # Runtime-only fields for cancel support
    _active_process: asyncio.subprocess.Process | None = field(
        default=None, repr=False, compare=False,
    )
    _streaming_task: asyncio.Task | None = field(
        default=None, repr=False, compare=False,
    )

    # Runtime-only fields for interactive permission handling
    _websocket: object | None = field(
        default=None, repr=False, compare=False,
    )
    _pending_permission: dict | None = field(
        default=None, repr=False, compare=False,
    )

    def is_expired(self, ttl_seconds: int = 1800) -> bool:
        return time.time() - self.last_accessed > ttl_seconds

    def touch(self):
        self.last_accessed = time.time()


class ClaudeCodeAgentSessionStore:
    """In-memory session store with TTL cleanup."""

    def __init__(self):
        self._sessions: dict[str, ClaudeCodeAgentSession] = {}

    def create(
        self,
        user_id: str = "",
        tenant_id: str = "",
        agent_id: str = "",
        working_dir: str = "",
    ) -> ClaudeCodeAgentSession:
        session = ClaudeCodeAgentSession(
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            working_dir=working_dir,
        )
        self._sessions[session.id] = session
        self._cleanup()
        return session

    def get(self, session_id: str) -> ClaudeCodeAgentSession | None:
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            session.touch()
            return session
        if session:
            del self._sessions[session_id]
        return None

    def delete(self, session_id: str):
        self._sessions.pop(session_id, None)

    def _cleanup(self):
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]


# Global session store
claude_code_session_store = ClaudeCodeAgentSessionStore()

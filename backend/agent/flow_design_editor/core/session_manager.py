"""
Session Manager for Flow Designer V2

Manages flow design sessions with state persistence, checkpointing,
and incremental building capabilities.
"""

import json
import uuid
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import redis
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class FlowNode:
    """Represents a node in the flow"""
    id: str
    type: str
    position: Dict[str, int]
    data: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return asdict(self)


@dataclass
class FlowEdge:
    """Represents an edge in the flow"""
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class FlowSession:
    """Represents a flow design session"""
    session_id: str
    name: str
    description: str
    status: SessionStatus
    nodes: List[FlowNode] = field(default_factory=list)
    edges: List[FlowEdge] = field(default_factory=list)
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None

    def to_dict(self):
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "trigger_config": self.trigger_config,
            "metadata": self.metadata,
            "checkpoints": self.checkpoints,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FlowSession':
        """Create session from dictionary"""
        session = cls(
            session_id=data["session_id"],
            name=data["name"],
            description=data["description"],
            status=SessionStatus(data["status"]),
            trigger_config=data.get("trigger_config", {}),
            metadata=data.get("metadata", {}),
            checkpoints=data.get("checkpoints", []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            expires_at=data.get("expires_at")
        )

        # Reconstruct nodes
        for node_data in data.get("nodes", []):
            session.nodes.append(FlowNode(**node_data))

        # Reconstruct edges
        for edge_data in data.get("edges", []):
            session.edges.append(FlowEdge(**edge_data))

        return session


class SessionManager:
    """
    Manages flow design sessions with Redis backend for persistence
    and fast access across multiple agent invocations.
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379,
                 redis_db: int = 1, use_redis: bool = False):
        """
        Initialize session manager.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            use_redis: Whether to use Redis (if False, uses SQLite storage)
        """
        self.use_redis = use_redis
        self.use_sqlite = False
        self.sessions: Dict[str, FlowSession] = {}  # In-memory fallback
        self.sqlite_conn = None

        if use_redis:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Connected to Redis for session management")
            except Exception as e:
                logger.warning(f"Redis connection failed, falling back to SQLite: {e}")
                self.use_redis = False
                self.redis_client = None
                # Fallback to SQLite
                self._init_sqlite()
        else:
            self.redis_client = None
            # Use SQLite for multi-worker persistence
            self._init_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite storage for sessions."""
        try:
            # Use backend/flow_sessions.db for session storage
            db_path = Path(__file__).resolve().parents[3] / "backend" / "flow_sessions.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)

            self.sqlite_conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self.sqlite_conn.commit()
            self.use_sqlite = True
            logger.info(f"Using SQLite session storage at {db_path}")
        except Exception as e:
            logger.error(f"SQLite initialization failed, using in-memory storage: {e}")
            self.use_sqlite = False
            self.sqlite_conn = None

    def create_session(self, name: str, description: str = "",
                      ttl_minutes: int = 30) -> str:
        """
        Create a new flow design session.

        Args:
            name: Session name
            description: Session description
            ttl_minutes: Time-to-live in minutes

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        expires_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()

        session = FlowSession(
            session_id=session_id,
            name=name,
            description=description,
            status=SessionStatus.ACTIVE,
            expires_at=expires_at
        )

        self._save_session(session)
        logger.info(f"Created new session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[FlowSession]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session ID

        Returns:
            FlowSession or None if not found
        """
        if self.use_redis and self.redis_client:
            key = f"flow_session:{session_id}"
            data = self.redis_client.get(key)
            if data:
                session = FlowSession.from_dict(json.loads(data))
                # Check expiration
                if session.expires_at and datetime.fromisoformat(session.expires_at) < datetime.utcnow():
                    session.status = SessionStatus.EXPIRED
                    self._save_session(session)
                return session
        else:
            session = self.sessions.get(session_id)
            if session:
                # Check expiration
                if session.expires_at and datetime.fromisoformat(session.expires_at) < datetime.utcnow():
                    session.status = SessionStatus.EXPIRED
                return session

        return None

    def update_session(self, session: FlowSession) -> bool:
        """
        Update an existing session.

        Args:
            session: Updated session object

        Returns:
            Success status
        """
        session.updated_at = datetime.utcnow().isoformat()
        return self._save_session(session)

    def add_node(self, session_id: str, node_type: str,
                 position: Dict[str, int], data: Dict[str, Any]) -> Optional[str]:
        """
        Add a node to the session.

        Args:
            session_id: Session ID
            node_type: Type of node
            position: Node position
            data: Node data

        Returns:
            Node ID or None if session not found
        """
        session = self.get_session(session_id)
        if not session or session.status != SessionStatus.ACTIVE:
            return None

        node_id = f"{node_type}_{len(session.nodes) + 1}"
        node = FlowNode(
            id=node_id,
            type=node_type,
            position=position,
            data=data
        )

        session.nodes.append(node)
        self.update_session(session)

        logger.info(f"Added node {node_id} to session {session_id}")
        return node_id

    def add_edge(self, session_id: str, source: str, target: str,
                 source_handle: Optional[str] = None,
                 target_handle: Optional[str] = None) -> Optional[str]:
        """
        Add an edge to the session.

        Args:
            session_id: Session ID
            source: Source node ID
            target: Target node ID
            source_handle: Source handle name
            target_handle: Target handle name

        Returns:
            Edge ID or None if session not found
        """
        session = self.get_session(session_id)
        if not session or session.status != SessionStatus.ACTIVE:
            return None

        # Validate nodes exist
        node_ids = {node.id for node in session.nodes}
        if source not in node_ids or target not in node_ids:
            logger.warning(f"Invalid edge: nodes {source} or {target} not found")
            return None

        edge_id = f"e{len(session.edges) + 1}"
        edge = FlowEdge(
            id=edge_id,
            source=source,
            target=target,
            sourceHandle=source_handle,
            targetHandle=target_handle
        )

        session.edges.append(edge)
        self.update_session(session)

        logger.info(f"Added edge {edge_id} to session {session_id}")
        return edge_id

    def create_checkpoint(self, session_id: str, label: str = "") -> Optional[str]:
        """
        Create a checkpoint for the session.

        Args:
            session_id: Session ID
            label: Optional checkpoint label

        Returns:
            Checkpoint ID or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        checkpoint_id = f"cp_{len(session.checkpoints)}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        if label:
            checkpoint_id += f"_{label}"

        # Store checkpoint separately
        checkpoint_data = session.to_dict()
        if self.use_redis and self.redis_client:
            checkpoint_key = f"flow_checkpoint:{session_id}:{checkpoint_id}"
            self.redis_client.set(
                checkpoint_key,
                json.dumps(checkpoint_data),
                ex=86400  # 24 hour TTL for checkpoints
            )
        else:
            # In-memory storage
            if not hasattr(self, 'checkpoints'):
                self.checkpoints = {}
            self.checkpoints[f"{session_id}:{checkpoint_id}"] = checkpoint_data

        session.checkpoints.append(checkpoint_id)
        self.update_session(session)

        logger.info(f"Created checkpoint {checkpoint_id} for session {session_id}")
        return checkpoint_id

    def restore_checkpoint(self, session_id: str, checkpoint_id: str) -> bool:
        """
        Restore session from a checkpoint.

        Args:
            session_id: Session ID
            checkpoint_id: Checkpoint ID

        Returns:
            Success status
        """
        if self.use_redis and self.redis_client:
            checkpoint_key = f"flow_checkpoint:{session_id}:{checkpoint_id}"
            data = self.redis_client.get(checkpoint_key)
            if data:
                session = FlowSession.from_dict(json.loads(data))
                session.status = SessionStatus.ACTIVE  # Reactivate
                session.updated_at = datetime.utcnow().isoformat()
                self._save_session(session)
                logger.info(f"Restored session {session_id} from checkpoint {checkpoint_id}")
                return True
        else:
            checkpoint_data = getattr(self, 'checkpoints', {}).get(f"{session_id}:{checkpoint_id}")
            if checkpoint_data:
                session = FlowSession.from_dict(checkpoint_data)
                session.status = SessionStatus.ACTIVE
                session.updated_at = datetime.utcnow().isoformat()
                self.sessions[session_id] = session
                logger.info(f"Restored session {session_id} from checkpoint {checkpoint_id}")
                return True

        logger.warning(f"Checkpoint {checkpoint_id} not found for session {session_id}")
        return False

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current state of a session.

        Args:
            session_id: Session ID

        Returns:
            Session state dictionary or None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "name": session.name,
            "status": session.status.value,
            "nodes_count": len(session.nodes),
            "edges_count": len(session.edges),
            "checkpoints_count": len(session.checkpoints),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "expires_at": session.expires_at,
            "has_trigger": any(node.type == "trigger" for node in session.nodes),
            "current_structure": {
                "nodes": [{"id": n.id, "type": n.type} for n in session.nodes],
                "edges": [{"source": e.source, "target": e.target} for e in session.edges]
            }
        }

    def complete_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Complete a session and generate final flow JSON.

        Args:
            session_id: Session ID

        Returns:
            Complete flow JSON or None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session.status = SessionStatus.COMPLETED
        self.update_session(session)

        # Generate flow JSON
        flow_json = {
            "version": "1.0",
            "export_timestamp": datetime.utcnow().isoformat(),
            "flow": {
                "flow_name": session.name,
                "description": session.description,
                "category": "",
                "trigger_config": session.trigger_config,
                "flow_definition": {
                    "nodes": [node.to_dict() for node in session.nodes],
                    "edges": [edge.to_dict() for edge in session.edges]
                },
                "is_synchronous": session.metadata.get("is_synchronous", False),
                "sync_timeout": session.metadata.get("sync_timeout", 60)
            },
            "metadata": {
                "session_id": session.session_id,
                "checkpoints": session.checkpoints,
                "created_at": session.created_at,
                "completed_at": datetime.utcnow().isoformat()
            }
        }

        logger.info(f"Completed session {session_id}")
        return flow_json

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned
        """
        count = 0

        if self.use_redis and self.redis_client:
            # Redis cleanup
            pattern = "flow_session:*"
            for key in self.redis_client.scan_iter(match=pattern):
                data = self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get("expires_at"):
                        if datetime.fromisoformat(session_data["expires_at"]) < datetime.utcnow():
                            self.redis_client.delete(key)
                            count += 1
        else:
            # In-memory cleanup
            expired = []
            for session_id, session in self.sessions.items():
                if session.expires_at and datetime.fromisoformat(session.expires_at) < datetime.utcnow():
                    expired.append(session_id)

            for session_id in expired:
                del self.sessions[session_id]
                count += 1

        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")

        return count

    def _save_session(self, session: FlowSession) -> bool:
        """
        Save session to storage.

        Args:
            session: Session to save

        Returns:
            Success status
        """
        try:
            if self.use_redis and self.redis_client:
                key = f"flow_session:{session.session_id}"
                ttl = None
                if session.expires_at:
                    expires = datetime.fromisoformat(session.expires_at)
                    ttl_seconds = int((expires - datetime.utcnow()).total_seconds())
                    if ttl_seconds > 0:
                        ttl = ttl_seconds

                self.redis_client.set(
                    key,
                    json.dumps(session.to_dict()),
                    ex=ttl
                )
            else:
                self.sessions[session.session_id] = session

            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False


# Singleton instance for global access
_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """Get or create the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        # Check if Redis is available
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=1)
            r.ping()
            use_redis = True
        except:
            use_redis = False

        _session_manager = SessionManager(use_redis=use_redis)

    return _session_manager
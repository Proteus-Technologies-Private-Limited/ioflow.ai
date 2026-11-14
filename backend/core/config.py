from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # Application
    app_name: str = "IOFlow"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:7001"
    server_url: str = "http://localhost:7001"  # Public-facing server URL
    base_url: str = "http://localhost:7001"    # Alias for server_url for compatibility
    frontend_url: Optional[str] = None  # Frontend URL for collaboration links, defaults to server_url
    environment: str = "production"  # development, production
    allowed_origins: str = ""  # Comma-separated list of allowed origins
    
    # Database - PostgreSQL Only
    database_url: str = "postgresql://localhost:5432/ioflow"
    redis_url: str = "redis://localhost:6379"
    # Separate TimescaleDB database dedicated to MQTT time-series data
    mqtt_timeseries_database_url: Optional[str] = None

    # Connection pool per tenant schema (PostgreSQL). Keep
    # (pool_size + max_overflow) * active_schemas + main pool (10+20)
    # below the server's max_connections (default 100).
    tenant_db_pool_size: int = 10
    tenant_db_max_overflow: int = 20

    # Skip publishing execution WebSocket events when no client on this worker
    # is subscribed to that execution. Only valid while the server runs a
    # single worker (run.py caps workers at 1); with multiple workers the
    # subscriber may be connected to another process, so set this to False.
    ws_skip_unwatched_publish: bool = True

    # Transport for execution WebSocket events between publisher and
    # subscribers: "auto" uses Redis pub/sub when redis_url responds at
    # startup and falls back to the database queue otherwise;
    # "redis" / "database" force a backend ("redis" still falls back with an
    # error logged so the server stays functional).
    ws_message_queue_backend: str = "auto"

    # MQTT trigger dispatch (operator ceilings — user/flow settings can never
    # exceed these). Queue sits between paho's network threads and flow
    # execution; the worker pool is the global cap on concurrent
    # MQTT-triggered executions.
    mqtt_dispatch_queue_size: int = 1000
    mqtt_worker_pool_size: int = 20
    # What to do when the dispatch queue is full:
    # "drop_oldest" — discard the stalest queued execution (stay realtime),
    # "drop_newest" — discard the incoming one,
    # "block" — stall paho's network thread so the broker's QoS 1 in-flight
    #           window absorbs the burst (no data loss, backpressure to broker).
    mqtt_overflow_policy: str = "drop_oldest"

    # Operator cap on flow execution log verbosity. Unset = flows choose their
    # own level (flow_definition.settings.execution_log_level, default "full").
    # Set to "node_summary" or "errors_only" to force at most that much
    # logging on every flow.
    flow_log_min_level: Optional[str] = None

    # Cache for flow definition reads in the execution hot path.
    # Invalidation is automatic on any ORM write to a flow (SQLAlchemy commit
    # hooks); the TTL is only a backstop for out-of-band edits (direct SQL).
    # Backend: "auto" uses Redis (redis_url) when reachable — shared across
    # worker processes, so invalidation is cluster-wide — and falls back to an
    # in-process memory cache otherwise; "redis" / "memory" force a backend.
    # The memory backend is per-process: correct for the current single-worker
    # server; with multiple processes it relies on the TTL to converge.
    flow_cache_enabled: bool = True
    flow_cache_backend: str = "auto"
    flow_cache_ttl_seconds: int = 300
    flow_cache_max_entries: int = 1000  # memory backend only (Redis uses TTL)
    
    
    # Security
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60  # 1 hour
    encryption_key: Optional[str] = None
    
    # JWT Settings (for backward compatibility)
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_delta: int = 720  # minutes
    
    # OAuth2 Settings
    oauth_callback_base_url: str = "http://localhost:7001/api/v1/oauth2/callback"
    oauth_state_ttl_minutes: int = 15  # OAuth state expiration time
    oauth_popup_enabled: bool = True  # Whether to use popup for OAuth flow
    oauth_cleanup_interval_minutes: int = 60  # How often to clean expired states
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # Twasta SSO ("Authenticate with Twasta"): base URL of the twasta.ai
    # backend used to verify twasta access tokens (POST /api/auth/verify-token).
    twasta_url: str = "http://localhost:7077"
    
    # Email (from twasta)
    postmark_api_key: Optional[str] = None
    from_email: str = os.environ.get("FROM_EMAIL", "noreply@ioflow.com")

    # SMTP Configuration for activation emails
    mail_server: Optional[str] = None
    email_user: Optional[str] = None
    email_pass: Optional[str] = None
    
    # AWS (optional)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    # Flow Design
    flow_design_model: Optional[str] = None
    
    # Agent Model
    agent_model: Optional[str] = None

    # Claude Code Agent Settings
    claude_code_path: str = ""  # Path to claude CLI binary, empty = auto-detect
    claude_code_model: Optional[str] = None  # Model override for Claude Code
    claude_code_max_budget_usd: float = 2.0  # Cost cap per execution
    
    # Razorpay Settings
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    
    class Config:
        # Get the backend directory path dynamically
        backend_dir = Path(__file__).parent.parent
        env_file = str(backend_dir / ".env")
        case_sensitive = False

settings = Settings()
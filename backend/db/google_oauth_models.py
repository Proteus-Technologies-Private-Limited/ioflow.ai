"""
Google OAuth Configuration Models - PostgreSQL and SQLite
"""
from sqlalchemy import Column, String, Boolean, TIMESTAMP
from sqlalchemy.sql import func
import uuid

from .models import Base
from .db_compat import JSONB, get_schema_dict


class GoogleOAuthConfig(Base):
    """
    Stores Google OAuth configuration for the instance.
    Only instance admins can configure this.
    """
    __tablename__ = 'google_oauth_config'
    __table_args__ = get_schema_dict()

    config_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(500), nullable=False)
    client_secret = Column(String(500), nullable=False)
    project_id = Column(String(200))
    auth_uri = Column(String(500), default='https://accounts.google.com/o/oauth2/auth')
    token_uri = Column(String(500), default='https://oauth2.googleapis.com/token')
    auth_provider_x509_cert_url = Column(String(500), default='https://www.googleapis.com/oauth2/v1/certs')
    redirect_uris = Column(JSONB)
    javascript_origins = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(String(36))


class GoogleOAuthState(Base):
    """
    Stores temporary OAuth state tokens for security during the OAuth flow
    """
    __tablename__ = 'google_oauth_states'
    __table_args__ = get_schema_dict()

    state_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state_token = Column(String(500), unique=True, nullable=False)
    redirect_uri = Column(String(500), nullable=False)
    action = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    expires_at = Column(TIMESTAMP, nullable=False)
    used = Column(Boolean, default=False)

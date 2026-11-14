"""
Authentication credential validation schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from enum import Enum

class AuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN_EXCHANGE = "token_exchange"
    CUSTOM = "custom"

class ApiKeyCredentials(BaseModel):
    """API Key authentication credentials"""
    api_key: str = Field(..., min_length=1, description="API key value")
    header_name: Optional[str] = Field("Authorization", description="Header name for API key")
    header_prefix: Optional[str] = Field("Bearer", description="Prefix for API key in header")
    
    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "sk-1234567890abcdef",
                "header_name": "Authorization",
                "header_prefix": "Bearer"
            }
        }

class BasicAuthCredentials(BaseModel):
    """Basic authentication credentials"""
    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "user@example.com",
                "password": "secure_password"
            }
        }

class TokenExchangeCredentials(BaseModel):
    """Token exchange authentication credentials"""
    username: str = Field(..., min_length=1, description="Username/Email/Mobile")
    password: str = Field(..., min_length=1, description="Password")
    handle_type: Optional[str] = Field("email", description="Type of handle: email, mobile, username")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "user@example.com",
                "password": "secure_password",
                "handle_type": "email"
            }
        }

class OAuth2UserCredentials(BaseModel):
    """OAuth2 credentials that users provide (only client_id and client_secret)"""
    client_id: str = Field(..., min_length=1, description="OAuth2 client ID")
    client_secret: str = Field(..., min_length=1, description="OAuth2 client secret")
    
    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "your-client-id",
                "client_secret": "your-client-secret"
            }
        }
    
    @validator('client_id')
    def validate_client_id(cls, v):
        """Validate OAuth2 client ID format"""
        # Check for common invalid patterns
        if '@' in v:
            raise ValueError(
                "Invalid OAuth2 Client ID. This appears to be an email address. "
                "OAuth2 requires application credentials from your provider's developer console, "
                "not your personal login credentials."
            )
        
        # Check for specific provider patterns
        if 'google' in v.lower() or 'sheets' in v.lower():
            # Google OAuth2 client IDs have a specific format
            if not v.endswith('.apps.googleusercontent.com') and '.' in v:
                raise ValueError(
                    "Invalid Google OAuth2 Client ID format. "
                    "Google Client IDs should look like: 123456789-abc.apps.googleusercontent.com. "
                    "Please create OAuth2 credentials at https://console.cloud.google.com/apis/credentials"
                )
        
        return v
    
    @validator('client_secret')
    def validate_client_secret(cls, v, values):
        """Validate OAuth2 client secret"""
        # Check if it looks like a password attempt
        if len(v) < 20 and any(char in v for char in ['@', '!', '#', '$']):
            raise ValueError(
                "Invalid OAuth2 Client Secret. This appears to be a personal password. "
                "OAuth2 requires application credentials from your provider's developer console."
            )
        
        # For Google, secrets usually start with GOCSPX-
        client_id = values.get('client_id', '')
        if '.apps.googleusercontent.com' in client_id and not v.startswith('GOCSPX-'):
            raise ValueError(
                "Invalid Google OAuth2 Client Secret format. "
                "Google Client Secrets typically start with 'GOCSPX-'. "
                "Please check your credentials from Google Cloud Console."
            )
        
        return v

class OAuth2Credentials(OAuth2UserCredentials):
    """Full OAuth2 authentication credentials (includes runtime fields)"""
    token_url: Optional[str] = Field(None, description="Token endpoint URL")
    scope: Optional[str] = Field(None, description="OAuth2 scope")
    access_token: Optional[str] = Field(None, description="Current access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: Optional[str] = Field("Bearer", description="Token type")
    expires_at: Optional[int] = Field(None, description="Token expiration timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "your-client-id",
                "client_secret": "your-client-secret",
                "token_url": "https://api.example.com/oauth/token",
                "scope": "read write"
            }
        }

class CustomAuthCredentials(BaseModel):
    """Custom authentication credentials"""
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom headers")
    query_params: Optional[Dict[str, str]] = Field(default_factory=dict, description="Query parameters")
    body_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Body parameters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "headers": {
                    "X-API-Key": "your-api-key",
                    "X-API-Secret": "your-secret"
                },
                "query_params": {
                    "apikey": "your-key"
                }
            }
        }

class AuthConfigBase(BaseModel):
    """Base authentication configuration"""
    auth_type: AuthType = Field(..., description="Type of authentication")
    description: Optional[str] = Field(None, description="Description of auth requirements")
    required_fields: Optional[List[str]] = Field(None, description="Required credential fields")
    
class ApiKeyAuthConfig(AuthConfigBase):
    """API Key authentication configuration"""
    auth_type: AuthType = Field(AuthType.API_KEY)
    header_name: Optional[str] = Field("Authorization", description="Expected header name")
    header_prefix: Optional[str] = Field("Bearer", description="Expected header prefix")
    key_location: Optional[str] = Field("header", description="Where to send key: header, query, body")
    key_param_name: Optional[str] = Field(None, description="Parameter name if not in header")

class BasicAuthConfig(AuthConfigBase):
    """Basic authentication configuration"""
    auth_type: AuthType = Field(AuthType.BASIC)
    realm: Optional[str] = Field(None, description="Authentication realm")

class TokenExchangeAuthConfig(AuthConfigBase):
    """Token exchange authentication configuration"""
    auth_type: AuthType = Field(AuthType.TOKEN_EXCHANGE)
    login_url: str = Field(..., description="Endpoint to exchange credentials for token")
    refresh_url: Optional[str] = Field(None, description="Endpoint to refresh token")
    token_field: str = Field("token", description="JSON path to extract token from response")
    expiry_field: Optional[str] = Field("expiry", description="JSON path to extract expiry timestamp")
    login_method: str = Field("POST", description="HTTP method for login")
    refresh_method: str = Field("PUT", description="HTTP method for refresh")
    login_body_template: Dict[str, Any] = Field(..., description="Template for login request body")
    refresh_headers_template: Optional[Dict[str, str]] = Field(None, description="Headers template for refresh")
    token_duration_mins: Optional[int] = Field(None, description="Default token duration in minutes")

class OAuth2AuthConfig(AuthConfigBase):
    """OAuth2 authentication configuration"""
    auth_type: AuthType = Field(AuthType.OAUTH2)
    token_url: str = Field(..., description="Token endpoint URL")
    authorization_url: Optional[str] = Field(None, description="Authorization endpoint URL")
    scope: Optional[str] = Field(None, description="Default OAuth2 scope")
    scopes: Optional[List[str]] = Field(None, description="OAuth2 scopes as list")
    grant_type: Optional[str] = Field("client_credentials", description="OAuth2 grant type")
    grant_types: Optional[List[str]] = Field(None, description="Supported grant types")
    default_credentials: Optional[Dict[str, str]] = Field(None, description="Default OAuth2 credentials for all tenants")
    client_id_required: Optional[bool] = Field(True, description="Whether client ID is required")
    client_secret_required: Optional[bool] = Field(True, description="Whether client secret is required")
    response_type: Optional[str] = Field("code", description="OAuth2 response type")
    authorization_params: Optional[Dict[str, Any]] = Field(None, description="Additional authorization parameters")
    token_params: Optional[Dict[str, Any]] = Field(None, description="Additional token parameters")
    pkce_required: Optional[bool] = Field(False, description="Whether PKCE is required")

class CustomAuthConfig(AuthConfigBase):
    """Custom authentication configuration"""
    auth_type: AuthType = Field(AuthType.CUSTOM)
    required_headers: Optional[List[str]] = Field(None, description="Required header names")
    required_query_params: Optional[List[str]] = Field(None, description="Required query parameters")
    required_body_params: Optional[List[str]] = Field(None, description="Required body parameters")

def validate_credentials(auth_type: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate credentials based on authentication type.

    Uses plugin registry for lookup, falling back to hardcoded handlers
    if registry is not yet populated.
    """
    try:
        from plugins.registry import PluginRegistry
        handler = PluginRegistry.get_auth_handler(auth_type)
        if handler:
            return handler.validate_credentials(credentials)
    except ImportError:
        pass

    # Fallback: hardcoded validation (for backward compatibility / pre-discovery)
    if auth_type == AuthType.NONE:
        return {}
    elif auth_type == AuthType.API_KEY:
        return ApiKeyCredentials(**credentials).dict()
    elif auth_type == AuthType.BASIC:
        return BasicAuthCredentials(**credentials).dict()
    elif auth_type == AuthType.TOKEN_EXCHANGE:
        mapped = credentials.copy()
        if 'handle' in credentials and 'username' not in credentials:
            mapped['username'] = credentials['handle']
        if 'handleType' in credentials and 'handle_type' not in credentials:
            mapped['handle_type'] = credentials['handleType']
        user_fields = {k: v for k, v in mapped.items() if k in ['username', 'password', 'handle_type']}
        return TokenExchangeCredentials(**user_fields).dict()
    elif auth_type == AuthType.OAUTH2:
        user_fields = {k: v for k, v in credentials.items() if k in ['client_id', 'client_secret']}
        validated = OAuth2UserCredentials(**user_fields)
        result = credentials.copy()
        result.update(validated.dict())
        return result
    elif auth_type == AuthType.CUSTOM:
        return CustomAuthCredentials(**credentials).dict()
    else:
        raise ValueError(f"Unknown authentication type: {auth_type}")

def validate_auth_config(auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate authentication configuration based on type.

    Uses plugin registry for lookup, falling back to hardcoded handlers
    if registry is not yet populated.
    """
    try:
        from plugins.registry import PluginRegistry
        handler = PluginRegistry.get_auth_handler(auth_type)
        if handler:
            return handler.validate_config(auth_config)
    except ImportError:
        pass

    # Fallback: hardcoded validation
    if auth_type == AuthType.NONE:
        return {}
    elif auth_type == AuthType.API_KEY:
        return ApiKeyAuthConfig(**auth_config).dict()
    elif auth_type == AuthType.BASIC:
        validated = BasicAuthConfig(**auth_config)
        result = validated.dict()
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result
    elif auth_type == AuthType.TOKEN_EXCHANGE:
        mapped_config = auth_config.copy()
        if 'exchange_url' in mapped_config and 'login_url' not in mapped_config:
            mapped_config['login_url'] = mapped_config['exchange_url']
        if 'body_template' in mapped_config and 'login_body_template' not in mapped_config:
            mapped_config['login_body_template'] = mapped_config['body_template']
        validated = TokenExchangeAuthConfig(**mapped_config)
        result = validated.dict()
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result
    elif auth_type == AuthType.OAUTH2:
        validated = OAuth2AuthConfig(**auth_config)
        result = validated.dict()
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result
    elif auth_type == AuthType.CUSTOM:
        return CustomAuthConfig(**auth_config).dict()
    else:
        raise ValueError(f"Unknown authentication type: {auth_type}")

def get_credential_schema(auth_type: str) -> Dict[str, Any]:
    """Get JSON schema for credentials based on auth type."""
    try:
        from plugins.registry import PluginRegistry
        handler = PluginRegistry.get_auth_handler(auth_type)
        if handler:
            return handler.credential_schema
    except ImportError:
        pass

    # Fallback
    schemas = {
        AuthType.NONE: {},
        AuthType.API_KEY: ApiKeyCredentials.schema(),
        AuthType.BASIC: BasicAuthCredentials.schema(),
        AuthType.TOKEN_EXCHANGE: TokenExchangeCredentials.schema(),
        AuthType.OAUTH2: OAuth2UserCredentials.schema(),
        AuthType.CUSTOM: CustomAuthCredentials.schema()
    }
    return schemas.get(auth_type, {})

def get_auth_config_schema(auth_type: str) -> Dict[str, Any]:
    """Get JSON schema for auth configuration based on auth type."""
    try:
        from plugins.registry import PluginRegistry
        handler = PluginRegistry.get_auth_handler(auth_type)
        if handler:
            return handler.config_schema
    except ImportError:
        pass

    # Fallback
    schemas = {
        AuthType.NONE: {},
        AuthType.API_KEY: ApiKeyAuthConfig.schema(),
        AuthType.BASIC: BasicAuthConfig.schema(),
        AuthType.TOKEN_EXCHANGE: TokenExchangeAuthConfig.schema(),
        AuthType.OAUTH2: OAuth2AuthConfig.schema(),
        AuthType.CUSTOM: CustomAuthConfig.schema()
    }
    return schemas.get(auth_type, {})
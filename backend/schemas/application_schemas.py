"""
Pydantic schemas for Application Management System
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from uuid import UUID
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.sample_data_generator import generate_sample_from_schema

# Enums
class AppScopeEnum(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"

class AppTypeEnum(str, Enum):
    DATABASE = "database"
    EMAIL = "email"
    API = "api"
    FILE_SYSTEM = "file_system"
    MEMORY = "memory"
    FLOW = "flow"
    AI_AGENT = "ai_agent"
    SSH = "ssh"
    MQTT = "mqtt"

class AuthTypeEnum(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN_EXCHANGE = "token_exchange"
    CUSTOM = "custom"

class EventTypeEnum(str, Enum):
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    POLLING = "polling"
    MANUAL = "manual"
    EMAIL = "email"
    FORM = "form"
    MQTT = "mqtt"

class ServiceTypeEnum(str, Enum):
    API_CALL = "api_call"
    WEBHOOK = "webhook"
    EMAIL_SEND = "email_send"
    SMTP_SEND = "smtp_send"
    POP3_RECEIVE = "pop3_receive"
    IMAP_RECEIVE = "imap_receive"
    LLM_API_CALL = "llm_api_call"
    MCP_CALL = "mcp_call"
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"  # File system operations (read, write, list, etc.)
    GRAPHQL = "graphql"  # GraphQL query service
    AI_AGENT_EXECUTE = "ai_agent_execute"  # AI Agent execution service
    SSH_COMMAND = "ssh_command"  # Execute commands on remote servers via SSH
    ACTION = "action"  # Deprecated, use API_CALL
    SEARCH = "search"  # Deprecated, use API_CALL
    CREATE = "create"  # Deprecated, use API_CALL
    UPDATE = "update"  # Deprecated, use API_CALL
    DELETE = "delete"  # Deprecated, use API_CALL
    CUSTOM = "custom"  # Deprecated, use API_CALL
    TRANSFORM = "transform"  # Transform/process data

class StatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"

class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"

# Base Schemas
class ApplicationBase(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=255)
    app_scope: AppScopeEnum = Field(default=AppScopeEnum.GLOBAL)
    app_type: Optional[AppTypeEnum] = Field(None, description="Type of application: database/email/api/file_system/memory/flow")
    description: Optional[str] = None
    icon_url: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500, description="Base URL for the application API")
    auth_type: AuthTypeEnum
    auth_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    version: str = Field(default="1.0.0", max_length=20)

class ApplicationEventBase(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: EventTypeEnum
    event_configuration: Optional[Dict[str, Any]] = None
    extraction_configuration: Optional[Dict[str, Any]] = Field(None, deprecated=True, description="DEPRECATED: Use output_schema with parameter_extraction instead")
    output_schema: Dict[str, Any] = Field(..., description="Unified schema defining event data structure and parameter extraction for ALL event types")
    sample_payload: Optional[Dict[str, Any]] = None
    is_active: bool = True
    
    def generate_sample_payload(self) -> Optional[Dict[str, Any]]:
        """Generate sample payload based on output_schema"""
        if self.output_schema:
            return generate_sample_from_schema(self.output_schema)
        return None
    
    @validator('sample_payload', always=True)
    def ensure_sample_payload(cls, v, values):
        """Auto-generate sample payload if not provided but output_schema exists"""
        if v is None and values.get('output_schema'):
            return generate_sample_from_schema(values['output_schema'])
        return v

class ApplicationServiceBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    service_type: ServiceTypeEnum
    
    # Service type specific configurations
    service_config: Optional[Dict[str, Any]] = Field(None, description="Type-specific service configuration")
    
    # All fields are now in service_config
    http_method: Optional[str] = Field(None, pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    endpoint_template: Optional[str] = Field(None, max_length=500)
    headers_template: Optional[Dict[str, Any]] = None
    body_template: Optional[Dict[str, Any]] = None
    
    # Common fields
    is_async: bool = False
    async_config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    is_active: bool = True
    
    @validator('service_config')
    def validate_service_config(cls, v, values):
        """Validate service_config based on service_type"""
        if not v:
            return v
            
        service_type = values.get('service_type')
        if not service_type:
            return v
            
        try:
            if service_type == ServiceTypeEnum.API_CALL:
                ApiCallConfig(**v)
            elif service_type == ServiceTypeEnum.GRAPHQL:
                # GraphQL uses similar config to API_CALL
                ApiCallConfig(**v)
            elif service_type == ServiceTypeEnum.WEBHOOK:
                WebhookConfig(**v)
            elif service_type == ServiceTypeEnum.EMAIL_SEND:
                EmailSendConfig(**v)
            elif service_type == ServiceTypeEnum.SMTP_SEND:
                SmtpSendConfig(**v)
            elif service_type == ServiceTypeEnum.POP3_RECEIVE:
                Pop3ReceiveConfig(**v)
            elif service_type == ServiceTypeEnum.IMAP_RECEIVE:
                ImapReceiveConfig(**v)
            elif service_type == ServiceTypeEnum.LLM_API_CALL:
                LLMApiCallConfig(**v)
            elif service_type == ServiceTypeEnum.MCP_CALL:
                MCPCallConfig(**v)
            elif service_type == ServiceTypeEnum.DATABASE_QUERY:
                DatabaseQueryConfig(**v)
        except Exception as e:
            raise ValueError(f"Invalid service_config for {service_type}: {str(e)}")
            
        return v
    
    def generate_sample_input(self) -> Optional[Dict[str, Any]]:
        """Generate sample input based on input_schema"""
        if self.input_schema:
            return generate_sample_from_schema(self.input_schema)
        return None
    
    def generate_sample_output(self) -> Optional[Dict[str, Any]]:
        """Generate sample output based on output_schema"""
        if self.output_schema:
            return generate_sample_from_schema(self.output_schema)
        return None
    
    def get_default_input_schema(self) -> Dict[str, Any]:
        """Get default input schema based on service type"""
        if self.service_type == ServiceTypeEnum.API_CALL:
            return {
                "type": "object",
                "properties": {
                    "path_params": {
                        "type": "object",
                        "description": "Path parameters for URL template"
                    },
                    "query_params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Request headers"
                    },
                    "body": {
                        "type": "object",
                        "description": "Request body"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.GRAPHQL:
            return {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "object",
                        "description": "GraphQL variables"
                    },
                    "operation": {
                        "type": "string",
                        "description": "Operation name (optional)"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.WEBHOOK:
            return {
                "type": "object",
                "properties": {
                    "payload": {
                        "type": "object",
                        "description": "Webhook payload"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.EMAIL_SEND:
            return {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC recipients"
                    },
                    "template_vars": {
                        "type": "object",
                        "description": "Variables for email template"
                    }
                },
                "required": ["to"]
            }
        elif self.service_type == ServiceTypeEnum.LLM_API_CALL:
            return {
                "type": "object",
                "properties": {
                    "prompt_variables": {
                        "type": "object",
                        "description": "Variables for prompt templates"
                    },
                    "conversation_history": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        },
                        "description": "Previous conversation messages"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.MCP_CALL:
            return {
                "type": "object",
                "properties": {
                    "parameters": {
                        "type": "object",
                        "description": "Tool-specific parameters"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.DATABASE_QUERY:
            return {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL query with :param_name placeholders"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameter values for the query"
                    }
                },
                "required": ["sql"]
            }
        elif self.service_type == ServiceTypeEnum.SMTP_SEND:
            return {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "format": "email",
                        "description": "Recipient email address"
                    },
                    "cc": {
                        "type": "string", 
                        "description": "CC recipients (comma-separated)"
                    },
                    "bcc": {
                        "type": "string",
                        "description": "BCC recipients (comma-separated)"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "body_type": {
                        "type": "string",
                        "enum": ["plain", "html"],
                        "default": "plain",
                        "description": "Email body format"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Email attachments"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        elif self.service_type == ServiceTypeEnum.POP3_RECEIVE:
            return {
                "type": "object",
                "properties": {
                    "message_count": {
                        "type": "integer",
                        "default": 10,
                        "description": "Number of messages to retrieve"
                    },
                    "include_body": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include message body in response"
                    },
                    "include_attachments": {
                        "type": "boolean", 
                        "default": False,
                        "description": "Include attachments in response"
                    }
                }
            }
        elif self.service_type == ServiceTypeEnum.IMAP_RECEIVE:
            return {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "default": "INBOX", 
                        "description": "Email folder to read from"
                    },
                    "search_query": {
                        "type": "string",
                        "default": "UNSEEN",
                        "description": "IMAP search criteria"
                    },
                    "message_count": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of messages to retrieve"
                    },
                    "include_body": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include message body in response"
                    },
                    "include_attachments": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include attachments in response"
                    }
                }
            }
        else:
            return {"type": "object", "properties": {}}

class ApplicationSubscriptionBase(BaseModel):
    app_id: UUID
    auth_credentials: Optional[Dict[str, Any]] = None
    subscription_config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = Field(None, max_length=500)

# Create Schemas
class ApplicationCreate(ApplicationBase):
    tenant_id_owner: Optional[UUID] = None
    
    @validator('tenant_id_owner')
    def validate_tenant_owner(cls, v, values):
        if values.get('app_scope') == AppScopeEnum.TENANT and not v:
            raise ValueError('Tenant-specific apps must have a tenant_id_owner')
        if values.get('app_scope') == AppScopeEnum.GLOBAL and v:
            raise ValueError('Global apps cannot have a tenant_id_owner')
        return v

class ApplicationEventCreate(ApplicationEventBase):
    pass

class ApplicationServiceCreate(ApplicationServiceBase):
    pass

class ApplicationSubscriptionCreate(ApplicationSubscriptionBase):
    pass

# Update Schemas
class ApplicationUpdate(BaseModel):
    app_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon_url: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500, description="Base URL for the application API")
    auth_config: Optional[Dict[str, Any]] = None
    webhook_config: Optional[Dict[str, Any]] = None
    status: Optional[StatusEnum] = None
    version: Optional[str] = Field(None, max_length=20)

class ApplicationEventUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_configuration: Optional[Dict[str, Any]] = None
    extraction_configuration: Optional[Dict[str, Any]] = Field(None, deprecated=True, description="DEPRECATED: Use output_schema with parameter_extraction instead")
    output_schema: Optional[Dict[str, Any]] = None
    sample_payload: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ApplicationServiceUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    http_method: Optional[str] = Field(None, pattern="^(GET|POST|PUT|DELETE|PATCH)$")
    endpoint_template: Optional[str] = Field(None, max_length=500)
    headers_template: Optional[Dict[str, Any]] = None
    body_template: Optional[Dict[str, Any]] = None
    async_config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    retry_config: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    is_active: Optional[bool] = None

class ApplicationSubscriptionUpdate(BaseModel):
    auth_credentials: Optional[Dict[str, Any]] = None
    subscription_config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = Field(None, max_length=500)
    status: Optional[SubscriptionStatusEnum] = None

# Response Schemas
class ApplicationEventResponse(ApplicationEventBase):
    event_id: UUID
    app_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class ApplicationServiceResponse(ApplicationServiceBase):
    service_id: UUID
    app_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class ApplicationResponse(ApplicationBase):
    app_id: UUID
    tenant_id_owner: Optional[UUID] = None
    status: str = "active"
    seed_key: Optional[str] = None  # Key from seed application for cross-instance portability
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    events: List[ApplicationEventResponse] = []
    services: List[ApplicationServiceResponse] = []

    class Config:
        from_attributes = True

class ApplicationSubscriptionResponse(ApplicationSubscriptionBase):
    subscription_id: UUID
    tenant_id: UUID
    status: SubscriptionStatusEnum
    subscribed_at: datetime
    expires_at: Optional[datetime] = None
    application: Optional[ApplicationResponse] = None

    class Config:
        from_attributes = True

# List Response Schemas
class ApplicationListResponse(BaseModel):
    total: int
    applications: List[ApplicationResponse]

class ApplicationSubscriptionListResponse(BaseModel):
    total: int
    subscriptions: List[ApplicationSubscriptionResponse]

# Special Schemas for Complex Operations
class BulkApplicationCreate(BaseModel):
    applications: List[ApplicationCreate]

class ApplicationWithFullDetails(ApplicationResponse):
    """Application with all events, services, and subscription info"""
    subscription: Optional[ApplicationSubscriptionResponse] = None

# Schema Examples for Documentation
class ScheduleConfig(BaseModel):
    """Example schedule configuration"""
    type: str = Field(..., description="Type of schedule: interval, daily, weekly, monthly, cron")
    interval_minutes: Optional[int] = Field(None, description="For interval type")
    time: Optional[str] = Field(None, description="Time in HH:MM format")
    day_of_week: Optional[str] = Field(None, description="For weekly: monday, tuesday, etc.")
    day_of_month: Optional[int] = Field(None, description="For monthly: 1-31")
    cron_expression: Optional[str] = Field(None, description="For cron type")
    timezone: str = Field(default="UTC", description="Timezone for schedule")

class OAuth2Config(BaseModel):
    """Example OAuth2 configuration"""
    auth_url: str
    token_url: str
    refresh_url: Optional[str] = None
    scopes: List[str]
    client_id_required: bool = True
    client_secret_required: bool = True
    redirect_uri: str

class WebhookConfig(BaseModel):
    """Example webhook configuration"""
    supported: bool = True
    verification_method: Optional[str] = Field(None, description="challenge, signature, etc.")
    signature_header: Optional[str] = None
    signature_algorithm: Optional[str] = None
    event_types: Optional[List[str]] = None

class RetryConfig(BaseModel):
    """Example retry configuration"""
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=5, ge=1, le=300)
    retry_on_status_codes: List[int] = [429, 500, 502, 503, 504]
    exponential_backoff: bool = False

class AsyncConfig(BaseModel):
    """Example async service configuration"""
    callback_timeout_minutes: int = Field(default=60, ge=1, le=1440)
    callback_method: str = Field(default="webhook", description="webhook or polling")
    status_check_endpoint: Optional[str] = None
    status_check_interval_seconds: Optional[int] = Field(None, ge=10, le=300)

# Service Type Specific Configurations
class ApiCallConfig(BaseModel):
    """Configuration for API Call service type"""
    method: str = Field(..., pattern="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    endpoint_template: str = Field(..., description="URL template with {variable} placeholders")
    headers_template: Optional[Dict[str, Any]] = Field(None, description="Headers with optional placeholders")
    query_params_template: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    body_template: Optional[Union[Dict[str, Any], str]] = Field(None, description="Request body template")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_config: Optional[RetryConfig] = None
    response_type: str = Field(default="json", description="json, xml, text, binary")

class WebhookConfig(BaseModel):
    """Configuration for Webhook service type"""
    webhook_url: str = Field(..., description="Target webhook URL")
    method: str = Field(default="POST", pattern="^(POST|PUT|PATCH)$")
    headers: Optional[Dict[str, str]] = None
    signature_method: Optional[str] = Field(None, description="hmac-sha256, hmac-sha1, custom")
    signature_header: Optional[str] = Field(None, description="Header name for signature")
    retry_config: Optional[RetryConfig] = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)

class EmailSendConfig(BaseModel):
    """Configuration for Email Send service type"""
    smtp_host: Optional[str] = Field(None, description="SMTP server host")
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    use_tls: bool = Field(default=True)
    from_address: str = Field(..., description="Sender email address")
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    template_engine: str = Field(default="jinja2", description="jinja2, mustache, plain")
    subject_template: str = Field(..., description="Email subject template")
    body_template: str = Field(..., description="Email body template")
    body_type: str = Field(default="html", description="html or plain")
    attachments_config: Optional[Dict[str, Any]] = None

class LLMApiCallConfig(BaseModel):
    """Configuration for LLM API Call service type"""
    provider: str = Field(..., description="openai, anthropic, google, azure, custom")
    model: str = Field(..., description="Model identifier")
    endpoint: Optional[str] = Field(None, description="Custom endpoint for non-standard providers")
    api_version: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    system_prompt_template: Optional[str] = None
    user_prompt_template: str = Field(..., description="User message template")
    response_format: Optional[str] = Field(None, description="json_object, text")
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    retry_config: Optional[RetryConfig] = None
    
class MCPCallConfig(BaseModel):
    """Configuration for MCP (Model Context Protocol) Call service type"""
    server_name: str = Field(..., description="MCP server identifier")
    tool_name: str = Field(..., description="Tool/function name to call")
    connection_config: Dict[str, Any] = Field(..., description="Server connection configuration")
    parameter_mapping: Optional[Dict[str, str]] = Field(None, description="Map flow params to MCP params")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_on_failure: bool = Field(default=True)

class DatabaseQueryConfig(BaseModel):
    """Configuration for Database Query service type"""
    operation_type: str = Field(..., description="query, execute, batch")
    result_format: str = Field(default="json_array", description="json_array, json_object, csv")
    max_rows: int = Field(default=10000, ge=1, le=100000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    transaction_mode: str = Field(default="auto", description="auto, manual")
    fetch_size: int = Field(default=1000, ge=100, le=10000)

class SmtpSendConfig(BaseModel):
    """Configuration for SMTP Send service type"""
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP server port")
    use_tls: bool = Field(default=True, description="Use TLS/SSL encryption")
    use_ssl: bool = Field(default=False, description="Use SSL (for port 465)")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    
class Pop3ReceiveConfig(BaseModel):
    """Configuration for POP3 Receive service type"""
    pop3_host: str = Field(..., description="POP3 server hostname")
    pop3_port: int = Field(default=995, ge=1, le=65535, description="POP3 server port")
    use_ssl: bool = Field(default=True, description="Use SSL encryption")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_messages: int = Field(default=50, ge=1, le=1000, description="Maximum messages to fetch")
    delete_after_read: bool = Field(default=False, description="Delete messages after reading")
    
class ImapReceiveConfig(BaseModel):
    """Configuration for IMAP Receive service type"""
    imap_host: str = Field(..., description="IMAP server hostname")
    imap_port: int = Field(default=993, ge=1, le=65535, description="IMAP server port")
    use_ssl: bool = Field(default=True, description="Use SSL encryption")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    mailbox: str = Field(default="INBOX", description="Mailbox/folder to read from")
    max_messages: int = Field(default=50, ge=1, le=1000, description="Maximum messages to fetch")
    mark_as_read: bool = Field(default=True, description="Mark messages as read after fetching")
    search_criteria: str = Field(default="UNSEEN", description="IMAP search criteria")

# Validation helpers
def validate_json_schema(schema: Dict[str, Any]) -> bool:
    """Validate if a dictionary is a valid JSON Schema"""
    required_fields = ["type"]
    return all(field in schema for field in required_fields)

def validate_endpoint_template(template: str) -> bool:
    """Validate endpoint template has proper placeholders"""
    import re
    # Check for valid placeholder format {variable_name}
    pattern = r'\{[a-zA-Z_][a-zA-Z0-9_]*\}'
    placeholders = re.findall(pattern, template)
    # Ensure no nested or malformed placeholders
    return len(placeholders) == template.count('{')
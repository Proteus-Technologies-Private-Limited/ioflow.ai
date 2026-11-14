"""
AI Settings Schema Definitions
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, Literal, List
from enum import Enum
from datetime import datetime


class AIModelProvider(str, Enum):
    """Supported AI model providers"""
    OPENAI = "openai"
    CLAUDE = "claude"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    COHERE = "cohere"
    CUSTOM = "custom"


class AIModelConfig(BaseModel):
    """AI Model configuration"""
    provider: AIModelProvider
    model_name: str = Field(..., description="Model name (e.g., gpt-5, claude-opus-4.1, gemini-2.5-pro)")
    api_key: str = Field(..., description="API key for the AI service")
    api_endpoint: Optional[str] = Field(None, description="Custom API endpoint (for Azure OpenAI, etc.)")
    
    class Config:
        protected_namespaces = ()  # Disable model_ namespace protection
    
    # Model-specific settings
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(4000, ge=1, le=200000, description="Maximum tokens in response (updated for latest models with extended context)")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    
    # Additional provider-specific settings
    extra_settings: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('model_name')
    def validate_model_name(cls, v, values):
        """Validate model name based on provider"""
        provider = values.get('provider')
        if provider == AIModelProvider.OPENAI:
            # Updated with latest OpenAI models (August 2025)
            valid_models = [
                # GPT-5 Series (Latest - August 2025)
                'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-chat', 'gpt-5-codex',
                # GPT-4.1 Series (January 2025)
                'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
                # GPT-4o Series (Current flagship multimodal)
                'gpt-4o', 'gpt-4o-mini',
                # GPT-4 Turbo and GPT-4 (maintained for compatibility)
                'gpt-4', 'gpt-4-turbo',
                # o-series reasoning models
                'o3', 'o3-mini', 'o4-mini',
                # Legacy GPT-3.5 (deprecated but supported)
                'gpt-3.5-turbo'
            ]
            if v not in valid_models:
                raise ValueError(f"Invalid OpenAI model: {v}. Valid models: {valid_models}")
        elif provider == AIModelProvider.CLAUDE:
            # Updated with latest Anthropic Claude models (September 2025)
            valid_models = [
                # Claude 4.5 Series (Latest - September 2025)
                'claude-sonnet-4-5', 'claude-sonnet-4-5-20250929',
                # Claude 4.1 Series
                'claude-opus-4.1', 'claude-opus-4-1-20250805',
                # Claude 4 Series
                'claude-4-opus', 'claude-4-sonnet', 'claude-4-haiku',
                'claude-sonnet-4-20250514',
                # Claude 3.5 Series (maintained for compatibility)
                'claude-3-5-sonnet', 'claude-3-5-haiku',
                # Legacy Claude 3 Series
                'claude-3-sonnet', 'claude-3-opus', 'claude-3-haiku'
            ]
            if not any(vm in v.lower() for vm in ['claude-4', 'claude-3', 'claude-2', 'opus-4', 'sonnet-4']):
                raise ValueError(f"Invalid Claude model: {v}")
        elif provider == AIModelProvider.GEMINI:
            # Updated with latest Google Gemini models (2025)
            valid_models = [
                # Gemini 2.5 Series (Latest - 2025)
                'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite',
                'gemini-2.5-flash-preview-native-audio-dialog',
                'gemini-2.5-flash-exp-native-audio-thinking-dialog',
                # Gemini 2.0 Series  
                'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-pro-experimental',
                'gemini-2.0-flash-preview-image-generation',
                # Legacy Gemini 1.5 Series (maintained for compatibility)
                'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-flash-8b',
                # Legacy Gemini 1.0 Series
                'gemini-1.0-pro', 'gemini-1.0-pro-vision'
            ]
            if not any(vm in v.lower() for vm in ['gemini-2.5', 'gemini-2.0', 'gemini-1.5', 'gemini-1.0']):
                raise ValueError(f"Invalid Gemini model: {v}")
        elif provider == AIModelProvider.DEEPSEEK:
            # DeepSeek models
            valid_models = [
                'deepseek-chat', 'deepseek-reasoner', 'deepseek-r1', 'deepseek-coder',
                'deepseek-r1-distill-qwen-32b', 'deepseek-r1-distill-qwen-14b', 'deepseek-r1-distill-qwen-7b'
            ]
            if not any(vm in v.lower() for vm in ['deepseek']):
                raise ValueError(f"Invalid DeepSeek model: {v}")
        elif provider in [AIModelProvider.LM_STUDIO, AIModelProvider.OLLAMA]:
            # Local models - accept any model name since they're user-provided
            pass
        return v

    @validator('api_endpoint')
    def validate_api_endpoint(cls, v, values):
        """Validate API endpoint based on provider"""
        provider = values.get('provider')
        if provider == AIModelProvider.AZURE_OPENAI and not v:
            raise ValueError("API endpoint is required for Azure OpenAI")
        if provider in [AIModelProvider.LM_STUDIO, AIModelProvider.OLLAMA] and not v:
            # Local providers should have an endpoint, but use defaults if not provided
            pass
        return v
    
    @validator('max_tokens')
    def validate_max_tokens(cls, v, values):
        """Validate max_tokens based on model capabilities"""
        if v is None:
            return v
            
        provider = values.get('provider')
        model_name = values.get('model_name', '')
        
        # GPT-5 and o-series models have different limits
        if provider == AIModelProvider.OPENAI:
            gpt5_models = ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-chat']
            o_series_models = ['o3', 'o3-mini', 'o4-mini', 'o1', 'o1-mini', 'o1-preview']
            
            if any(model_name.startswith(prefix) for prefix in gpt5_models + o_series_models):
                # GPT-5 models can emit maximum 128,000 reasoning & output tokens
                if v > 128000:
                    raise ValueError(f"GPT-5 and o-series models support maximum 128,000 output tokens, got {v}")
        
        return v


class AISettingsResponse(BaseModel):
    """Response model for AI settings (without sensitive data)"""
    provider: Optional[AIModelProvider]
    model_name: Optional[str]

    class Config:
        protected_namespaces = ()  # Disable model_ namespace protection
    api_endpoint: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    has_api_key: bool = Field(description="Whether API key is configured")
    extra_settings: Optional[Dict[str, Any]]
    agent_framework: Optional[str] = Field(None, description="Agent framework: 'google_adk' or 'claude_code'")


class AISettingsUpdate(BaseModel):
    """Update AI settings request"""
    provider: Optional[AIModelProvider] = None
    model_name: Optional[str] = None

    class Config:
        protected_namespaces = ()  # Disable model_ namespace protection
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    extra_settings: Optional[Dict[str, Any]] = None
    agent_framework: Optional[str] = Field(None, description="Agent framework: 'google_adk' or 'claude_code'")


class AITransformRequest(BaseModel):
    """Request to generate transform code using AI"""
    natural_language_prompt: str = Field(..., description="Natural language description of the transformation")
    input_schema: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Schema of input data")
    available_variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Available global variables and node outputs")
    flow_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Flow context information")


class AITransformResponse(BaseModel):
    """Response from AI transform code generation"""
    generated_code: str = Field(..., description="Generated Python transform code")
    explanation: str = Field(..., description="Human-readable explanation of the code")
    test_cases: Optional[list] = Field(default_factory=list, description="Example test cases")
    warnings: Optional[list] = Field(default_factory=list, description="Any warnings or limitations")


class AITestConnectionRequest(BaseModel):
    """Request to test AI connection with temporary settings"""
    provider: AIModelProvider
    model_name: Optional[str] = None
    
    class Config:
        protected_namespaces = ()  # Disable model_ namespace protection
    api_key: str = Field(..., description="API key to test (not saved)")
    api_endpoint: Optional[str] = None
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(4000, ge=1, le=200000)
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0)


class AITestConnectionResponse(BaseModel):
    """Response from testing AI connection"""
    success: bool
    message: str
    model_info: Optional[Dict[str, Any]] = None
    
    class Config:
        protected_namespaces = ()  # Disable model_ namespace protection


# Conversation-related schemas

class AIConversationRequest(BaseModel):
    """Request to start or continue an AI conversation"""
    flow_id: str = Field(..., description="Flow ID")
    node_id: str = Field(..., description="Transform node ID") 
    prompt: str = Field(..., description="User prompt")
    flow_name: Optional[str] = None
    node_name: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = Field(default_factory=dict)
    available_variables: Optional[Dict[str, Any]] = Field(default_factory=dict)
    flow_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    next_node_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Information about the next connected node and its parameters")
    custom_system_prompt: Optional[str] = Field(None, description="Custom system prompt to override the default")


class AIFollowupRequest(BaseModel):
    """Request for follow-up in existing conversation"""
    conversation_id: str = Field(..., description="Conversation ID")
    followup_prompt: str = Field(..., description="Follow-up prompt")


class AIConversationMessage(BaseModel):
    """Single message in conversation history"""
    message_id: str
    sequence_number: int
    message_type: Literal['user_prompt', 'ai_response', 'system_info']
    content: str
    created_at: datetime
    
    # AI response specific fields
    generated_code: Optional[str] = None
    explanation: Optional[str] = None
    warnings: Optional[List[str]] = None
    test_cases: Optional[List[Dict]] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    was_applied: Optional[bool] = None
    applied_at: Optional[datetime] = None
    generation_time_ms: Optional[int] = None


class AIConversationResponse(BaseModel):
    """Response containing conversation and new AI response"""
    conversation_id: str
    message_id: str
    generated_code: str
    explanation: str
    warnings: Optional[List[str]] = None
    test_cases: Optional[List[Dict]] = None
    conversation_history: List[AIConversationMessage]


class AIConversationSummary(BaseModel):
    """Summary of a conversation"""
    conversation_id: str
    title: Optional[str]
    message_count: int
    last_activity_at: datetime
    created_at: datetime


class AIConversationHistoryResponse(BaseModel):
    """Full conversation history response"""
    conversation_id: str
    title: Optional[str]
    flow_id: str
    node_id: str
    flow_name: Optional[str]
    node_name: Optional[str]
    message_count: int
    status: str
    messages: List[AIConversationMessage]
    created_at: datetime
    last_activity_at: datetime


class AIApplyCodeRequest(BaseModel):
    """Request to mark code as applied"""
    message_id: str = Field(..., description="Message ID containing the code")


class AIClearConversationRequest(BaseModel):
    """Request to clear conversation history"""
    conversation_id: str = Field(..., description="Conversation ID to clear")


class AISystemPromptRequest(BaseModel):
    """Request to get the default system prompt"""
    input_schema: Optional[Dict[str, Any]] = Field(default_factory=dict)
    available_variables: Optional[Dict[str, Any]] = Field(default_factory=dict)
    flow_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    next_node_info: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AISystemPromptResponse(BaseModel):
    """Response containing the system prompt"""
    system_prompt: str = Field(..., description="The generated system prompt")
    prompt_length: int = Field(..., description="Length of the prompt in characters")
    variables_count: int = Field(..., description="Number of available variables")
    next_node_connected: bool = Field(..., description="Whether a next node is connected")
"""
FastAPI Routes for IOFlow Assistant

Provides REST API endpoints for the development agent runtime.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging
import os
import sys

# Add backend to path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from db.database import get_db
from core.auth_utils import get_current_user_optional
from .runtime_manager import RuntimeManager
from .streaming_handler import StreamingHandler
from agent_pack import get_agent as get_pack_agent
from agent_pack.runtime import set_request_token, claude_mcp_config

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/assistant", tags=["assistant"])

# Initialize runtime manager
runtime_manager = RuntimeManager()
streaming_handler = StreamingHandler(runtime_manager)


async def _authenticated_caller(req: Request):
    """(user, bearer token) of the caller, or 401. The token is what the
    agent's tools authenticate with — the caller's own identity."""
    from core.auth_utils import get_current_user_optional_direct
    db_gen = get_db()
    db = next(db_gen)
    try:
        user = await get_current_user_optional_direct(req, db)
    finally:
        db.close()
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to use the IOFlow Assistant")
    token = req.headers.get("Authorization", "")[len("Bearer "):]
    return user, token


# Pydantic models for requests/responses
class AgentInfo(BaseModel):
    id: str
    name: str
    type: str
    path: str
    description: str
    model: Optional[str] = None


class ExecuteAgentRequest(BaseModel):
    agent_id: str = Field(..., description="ID of the agent to execute")
    input: str = Field(..., description="Input text for the agent")
    api_key: Optional[str] = Field(None, description="API key for the selected provider. If not provided or 'USE_FROM_SETTINGS', uses API key from AI settings")
    model: Optional[str] = Field(None, description="Model to use. If not provided, uses model from settings")
    provider: Optional[str] = Field(None, description="Provider: google, openai, anthropic, deepseek, ollama, or lm_studio. If not provided, uses provider from settings")
    api_base: Optional[str] = Field(None, description="API base URL for local models (ollama, lm_studio)")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    force_new_session: bool = Field(False, description="Force create a new session, clearing conversation history")


class ExecuteAgentResponse(BaseModel):
    success: bool
    session_id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CancelExecutionRequest(BaseModel):
    session_id: str


class ClearConversationRequest(BaseModel):
    agent_id: str = Field(..., description="ID of the agent to clear conversation for")


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    agent_id: str
    model: str
    started_at: str
    messages: int


class SaveAssistantSettingsRequest(BaseModel):
    use_defaults: bool = Field(True, description="Whether to use default AI settings")
    provider: Optional[str] = Field(None, description="Provider override if not using defaults")
    model: Optional[str] = Field(None, description="Model override if not using defaults")
    custom_api_key: Optional[str] = Field(None, description="Custom API key if different from default")


class AssistantSettingsResponse(BaseModel):
    use_defaults: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    has_custom_api_key: bool = False
    saved: bool = False


@router.get("/agents", response_model=List[AgentInfo])
async def list_agents():
    """
    List all available agents (both Python and JSON)
    """
    try:
        agents = runtime_manager.discover_agents()
        return agents
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """
    Get information about a specific agent
    """
    agents = runtime_manager.agent_registry
    for agent in agents:
        if agent["id"] == agent_id:
            return agent

    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")


@router.post("/execute", response_model=ExecuteAgentResponse)
async def execute_agent(request: ExecuteAgentRequest, req: Request):
    """
    Start agent execution with the provided configuration.
    Priority for API key: 1) Provided in request, 2) Custom from assistant settings, 3) Default from AI settings
    """
    try:
        logger.info(f"Execute agent called with: api_key={'USE_FROM_SETTINGS' if request.api_key == 'USE_FROM_SETTINGS' else 'PROVIDED'}, provider={request.provider}, model={request.model}")

        # The assistant acts on IOFlow AS the caller, so it needs one. It used to
        # run anonymously whenever the request carried its own LLM key.
        caller_user, caller_token = await _authenticated_caller(req)

        # If no API key provided, try to get it from settings
        api_key_to_use = request.api_key
        provider_to_use = request.provider
        model_to_use = request.model
        ai_config = None  # Will be populated from user settings if available
        user = caller_user
        agent_framework = 'google_adk'

        if not api_key_to_use or api_key_to_use == 'USE_FROM_SETTINGS':
            # Get user's settings
            from sqlalchemy.orm import Session
            from db.database import get_db
            from core.auth_utils import get_current_user_optional_direct
            from db.user_settings_models import UserSettingsHelper
            from utils.crypto_utils import decrypt_data

            db_gen = get_db()
            db: Session = next(db_gen)

            user = None
            try:
                user = await get_current_user_optional_direct(req, db)
                if user:
                    # First check assistant-specific settings
                    assistant_config = UserSettingsHelper.get_assistant_config(db, user.user_id)

                    if not assistant_config.get("use_defaults") and assistant_config.get("custom_api_key_hash"):
                        # Use custom assistant API key
                        try:
                            api_key_to_use = decrypt_data(assistant_config["custom_api_key_hash"])
                            # Also use custom provider/model if set
                            if assistant_config.get("provider"):
                                provider_to_use = assistant_config["provider"]
                            if assistant_config.get("model"):
                                model_to_use = assistant_config["model"]
                        except Exception as e:
                            logger.warning(f"Could not decrypt custom API key: {e}")

                    # Get AI settings (for API key, provider/model, and agent framework)
                    ai_config = UserSettingsHelper.get_ai_config(db, user.user_id)
                    # Capture agent_framework early so it's available before API key validation
                    if ai_config.get('agent_framework') == 'claude_code':
                        agent_framework = 'claude_code'

                    # If still no API key or it's still USE_FROM_SETTINGS, use AI settings API key
                    if not api_key_to_use or api_key_to_use == 'USE_FROM_SETTINGS':
                        api_key_hash = ai_config.get('api_key_hash')
                        if api_key_hash:
                            try:
                                api_key_to_use = decrypt_data(api_key_hash)
                                logger.info(f"Using API key from AI settings for user {user.email}")
                            except Exception as e:
                                logger.warning(f"Could not decrypt API key from settings: {e}")

                    # If using defaults (or provider/model not set), get from AI settings
                    if assistant_config.get("use_defaults", True):
                        # Map AI settings provider to assistant provider format
                        provider_mapping = {
                            "gemini": "google",
                            "openai": "openai",
                            "claude": "anthropic",
                            "anthropic": "anthropic",
                            "deepseek": "deepseek",
                            "lm_studio": "lm_studio",
                            "ollama": "ollama",
                            "azure_openai": "azure_openai"
                        }

                        ai_provider = ai_config.get('provider')
                        ai_model = ai_config.get('model_name')

                        # Only override if not already set from request
                        if not provider_to_use and ai_provider:
                            provider_to_use = provider_mapping.get(ai_provider.lower(), ai_provider.lower())
                            logger.info(f"Using provider from AI settings: {ai_provider} -> {provider_to_use}")

                        if not model_to_use and ai_model:
                            model_to_use = ai_model
                            logger.info(f"Using model from AI settings: {model_to_use}")
            finally:
                db.close()

        if (not api_key_to_use or api_key_to_use == 'USE_FROM_SETTINGS') and agent_framework != 'claude_code':
            logger.error(f"Failed to get API key. api_key_to_use={api_key_to_use}")
            raise ValueError("API key is required. Please configure it in settings or provide it directly.")

        # Apply fallback defaults if still not set
        if not provider_to_use:
            provider_to_use = "google"
            logger.warning(f"No provider specified, using default: {provider_to_use}")

        if not model_to_use:
            # Use provider-specific default
            from config.models_config import AIModelsConfig
            provider_info = AIModelsConfig.get_provider_info(provider_to_use)
            model_to_use = provider_info.get("default_model", "gemini-2.5-flash")
            logger.warning(f"No model specified, using default for {provider_to_use}: {model_to_use}")

        # Get user_id for conversation persistence
        user_id = None
        user_email = None
        if user:
            user_id = user.user_id
            user_email = user.email
            logger.info(f"User {user_email} executing agent {request.agent_id}")

        # Check if user has selected Claude Code as agent framework
        agent_framework = 'google_adk'
        if user:
            if ai_config:
                agent_framework = ai_config.get('agent_framework', 'google_adk')
            else:
                # ai_config wasn't loaded yet (API key was provided directly) — load it just for framework check
                try:
                    from db.user_settings_models import UserSettingsHelper
                    from db.database import get_db as _get_db
                    _db = next(_get_db())
                    try:
                        _cfg = UserSettingsHelper.get_ai_config(_db, user.user_id)
                        agent_framework = _cfg.get('agent_framework', 'google_adk')
                    finally:
                        _db.close()
                except Exception:
                    pass

        # Log what we're passing (first 10 chars of key for security)
        logger.info(f"Executing agent with: framework={agent_framework}, provider={provider_to_use}, model={model_to_use}, api_key={api_key_to_use[:10] if api_key_to_use else 'EMPTY'}...")

        # Route to Claude Code if selected
        if agent_framework == 'claude_code':
            # Don't pass non-Claude models to Claude Code CLI — it only works with Anthropic models.
            # Use CLAUDE_CODE_MODEL env var or let the CLI use its default.
            claude_model = os.environ.get("CLAUDE_CODE_MODEL") or None
            result = await _execute_with_claude_code(
                agent_id=request.agent_id,
                input_text=request.input,
                model=claude_model,
                user_id=user_id,
                user_email=user_email,
                ioflow_token=caller_token,
            )
        else:
            # The ADK agent builds its MCP toolset inside this task; the token
            # reaches it through the request ContextVar, never os.environ.
            set_request_token(caller_token)
            result = await runtime_manager.execute_agent(
                agent_id=request.agent_id,
                input_text=request.input,
                api_key=api_key_to_use,
                model=model_to_use,
                provider=provider_to_use,
                api_base=request.api_base,
                session_id=request.session_id,
                user_id=user_id,
                force_new_session=request.force_new_session
            )

        return ExecuteAgentResponse(
            success=result.get("success", False),
            session_id=result.get("session_id", ""),
            result=result.get("result"),
            error=result.get("error")
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{session_id}")
async def cancel_execution(session_id: str):
    """
    Cancel an active agent execution
    """
    result = runtime_manager.cancel_execution(session_id)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=404, detail=result["message"])


@router.post("/clear-conversation")
async def clear_conversation(
    request: ClearConversationRequest,
    req: Request,
    current_user = Depends(get_current_user_optional)
):
    """
    Clear conversation history for a specific agent
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    success = runtime_manager.clear_conversation(
        user_id=current_user.user_id,
        agent_id=request.agent_id
    )

    if success:
        logger.info(f"Cleared conversation for user {current_user.email} and agent {request.agent_id}")
        return {"success": True, "message": "Conversation cleared"}
    else:
        return {"success": False, "message": "No conversation to clear"}


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """
    Get the status of an execution session
    """
    status = runtime_manager.get_session_status(session_id)
    if status:
        return SessionStatusResponse(**status)
    else:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/sessions/active")
async def list_active_sessions():
    """
    List all active execution sessions
    """
    sessions = runtime_manager.list_active_sessions()
    return sessions


@router.get("/sessions/history")
async def get_session_history(limit: int = 50):
    """
    Get recent session history
    """
    history = runtime_manager.session_manager.get_session_history(limit)
    return history


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming agent responses
    """
    try:
        await streaming_handler.handle_websocket(websocket, session_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@router.get("/models")
async def list_models():
    """
    List available models from centralized configuration
    """
    from config.models_config import AIModelsConfig

    models = AIModelsConfig.get_all_models_detailed()
    return models


@router.get("/models-legacy")
async def list_models_legacy():
    """
    Legacy models endpoint (deprecated - use /models)
    """
    models = [
        # Google Gemini 2.5 Models (Latest - 2025)
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "provider": "google",
            "description": "State-of-the-art thinking model for complex reasoning",
            "default": True
        },
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "provider": "google",
            "description": "Fast thinking model for everyday tasks with 1M context"
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash-Lite Preview",
            "provider": "google",
            "description": "Most cost-efficient and fastest 2.5 model"
        },
        # Google Gemini 2.0 Models
        {
            "id": "gemini-2.0-flash-exp",
            "name": "Gemini 2.0 Flash (Experimental)",
            "provider": "google",
            "description": "Fast, experimental version of Gemini 2.0"
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "provider": "google",
            "description": "Fast and efficient Gemini model"
        },
        # Google Gemini 1.5 Models (Legacy)
        {
            "id": "gemini-1.5-pro",
            "name": "Gemini 1.5 Pro",
            "provider": "google",
            "description": "Stable pro model (legacy)"
        },
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash",
            "provider": "google",
            "description": "Stable flash model (legacy)"
        },
        # OpenAI GPT-5 Models (Latest - 2025)
        {
            "id": "gpt-5",
            "name": "GPT-5",
            "provider": "openai",
            "description": "Best model for coding and agentic tasks (74.9% SWE-bench)"
        },
        {
            "id": "gpt-5-mini",
            "name": "GPT-5 Mini",
            "provider": "openai",
            "description": "Smaller, cost-effective GPT-5 variant"
        },
        {
            "id": "gpt-5-nano",
            "name": "GPT-5 Nano",
            "provider": "openai",
            "description": "Most compact and efficient GPT-5 version"
        },
        {
            "id": "gpt-5-chat-latest",
            "name": "GPT-5 Chat Latest",
            "provider": "openai",
            "description": "Non-reasoning GPT-5 for chat applications"
        },
        {
            "id": "gpt-5-codex",
            "name": "GPT-5 Codex",
            "provider": "openai",
            "description": "Advanced code generation and understanding model"
        },
        # OpenAI GPT-4 Models
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "provider": "openai",
            "description": "OpenAI's flagship multimodal model"
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "provider": "openai",
            "description": "Smaller, faster, cheaper GPT-4o variant"
        },
        {
            "id": "gpt-4-turbo",
            "name": "GPT-4 Turbo",
            "provider": "openai",
            "description": "GPT-4 Turbo with vision support"
        },
        # OpenAI Specialized Models
        {
            "id": "gpt-realtime",
            "name": "GPT-Realtime",
            "provider": "openai",
            "description": "Advanced speech-to-speech model"
        },
        # Anthropic Claude 4 Models (Latest)
        {
            "id": "claude-opus-4-1-20250805",
            "name": "Claude Opus 4.1",
            "provider": "anthropic",
            "description": "Best coding model, 200K context"
        },
        {
            "id": "claude-opus-4-20250514",
            "name": "Claude Opus 4",
            "provider": "anthropic",
            "description": "Powerful model for complex tasks"
        },
        {
            "id": "claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4",
            "provider": "anthropic",
            "description": "Balanced speed and intelligence"
        },
        # Anthropic Claude 3.7 Model
        {
            "id": "claude-3-7-sonnet-20250219",
            "name": "Claude 3.7 Sonnet",
            "provider": "anthropic",
            "description": "Enhanced Sonnet model"
        },
        # Anthropic Claude 3.5 Models
        {
            "id": "claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku",
            "provider": "anthropic",
            "description": "Fast and cost-effective model"
        },
        # Anthropic Claude 3 Model
        {
            "id": "claude-3-haiku-20240307",
            "name": "Claude 3 Haiku",
            "provider": "anthropic",
            "description": "Fast, compact model"
        }
    ]
    return models


@router.get("/default-settings")
async def get_default_assistant_settings(request: Request):
    """
    Get default assistant settings from AI settings configuration
    Also includes user's saved assistant settings if available
    """
    logger.info("=== DEFAULT SETTINGS API CALLED ===")
    try:
        from sqlalchemy.orm import Session
        from db.database import get_db
        from core.auth_utils import get_current_user_optional_direct
        from db.user_settings_models import UserSettingsHelper, AssistantSettingsData, SettingType
        from utils.crypto_utils import decrypt_data

        # Try to get current user from the request
        db_gen = get_db()
        db: Session = next(db_gen)

        try:
            # Extract user from request if authenticated
            user = await get_current_user_optional_direct(request, db)
            logger.info(f"User authenticated: {user.email if user else 'None'}")

            if user:
                # Get AI configuration from user settings
                ai_config = UserSettingsHelper.get_ai_config(db, user.user_id)
                logger.info(f"AI Config loaded: provider={ai_config.get('provider')}, model={ai_config.get('model_name')}, has_key={bool(ai_config.get('api_key_hash'))}")

                # Get assistant-specific configuration
                assistant_config = UserSettingsHelper.get_assistant_config(db, user.user_id)
                logger.info(f"Assistant Config: {assistant_config}")

                # Map AI settings provider to assistant provider format
                provider_mapping = {
                    "gemini": "google",
                    "openai": "openai",
                    "claude": "anthropic",
                    "anthropic": "anthropic",
                    "deepseek": "deepseek",
                    "lm_studio": "lm_studio",
                    "ollama": "ollama",
                    "azure_openai": "azure_openai"
                }

                provider = str(ai_config.get('provider', '')).lower() if ai_config.get('provider') else None
                mapped_provider = provider_mapping.get(provider, provider) if provider else None
                logger.info(f"Provider mapping: {ai_config.get('provider')} -> {provider} -> {mapped_provider}")

                # Check if API key exists but DON'T send it to frontend for security
                api_key_hash = ai_config.get('api_key_hash')

                # Check if user has saved assistant settings (not the default)
                has_saved_assistant_settings = False
                assistant_setting = UserSettingsHelper.get_setting(db, user.user_id, SettingType.ASSISTANT_CONFIG.value)
                if assistant_setting:
                    has_saved_assistant_settings = True

                response_data = {
                    "provider": mapped_provider,
                    "model": ai_config.get('model_name'),
                    "has_api_key": bool(api_key_hash),
                    "api_key": None,  # Never send actual API key to frontend
                    "api_key_configured": bool(api_key_hash),
                    # Include assistant-specific settings
                    "assistant_settings": {
                        "use_defaults": assistant_config.get("use_defaults", True),
                        "provider": assistant_config.get("provider"),
                        "model": assistant_config.get("model"),
                        "has_custom_api_key": bool(assistant_config.get("custom_api_key_hash")),
                        "saved": has_saved_assistant_settings
                    }
                }

                logger.info(f"Returning response: provider={response_data['provider']}, model={response_data['model']}, has_api_key={response_data['has_api_key']}")
                return response_data
            else:
                logger.info("No user authenticated, returning empty settings")
                # No user authenticated, return empty settings
                return {
                    "provider": None,
                    "model": None,
                    "has_api_key": False,
                    "api_key": None,
                    "api_key_configured": False,
                    "assistant_settings": {
                        "use_defaults": True,
                        "provider": None,
                        "model": None,
                        "has_custom_api_key": False,
                        "saved": False
                    }
                }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get default assistant settings: {e}")
        # Return empty settings on error
        return {
            "provider": None,
            "model": None,
            "has_api_key": False,
            "api_key": None,
            "api_key_configured": False,
            "assistant_settings": {
                "use_defaults": True,
                "provider": None,
                "model": None,
                "has_custom_api_key": False,
                "saved": False
            }
        }


@router.post("/save-settings", response_model=AssistantSettingsResponse)
async def save_assistant_settings(
    request: SaveAssistantSettingsRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Save user's assistant-specific settings to database
    """
    try:
        from db.user_settings_models import UserSettingsHelper
        from utils.crypto_utils import encrypt_data

        if not current_user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Encrypt custom API key if provided
        custom_api_key_hash = None
        if request.custom_api_key and not request.use_defaults:
            custom_api_key_hash = encrypt_data(request.custom_api_key)

        # Save assistant configuration
        UserSettingsHelper.set_assistant_config(
            db=db,
            user_id=current_user.user_id,
            use_defaults=request.use_defaults,
            provider=request.provider if not request.use_defaults else None,
            model=request.model if not request.use_defaults else None,
            custom_api_key_hash=custom_api_key_hash
        )

        return AssistantSettingsResponse(
            use_defaults=request.use_defaults,
            provider=request.provider if not request.use_defaults else None,
            model=request.model if not request.use_defaults else None,
            has_custom_api_key=bool(custom_api_key_hash),
            saved=True
        )

    except Exception as e:
        logger.error(f"Failed to save assistant settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-settings", response_model=AssistantSettingsResponse)
async def get_user_assistant_settings(request: Request):
    """
    Get user's saved assistant-specific settings
    """
    try:
        from sqlalchemy.orm import Session
        from db.database import get_db
        from core.auth_utils import get_current_user_optional_direct
        from db.user_settings_models import UserSettingsHelper, AssistantSettingsData, SettingType

        db_gen = get_db()
        db: Session = next(db_gen)

        try:
            user = await get_current_user_optional_direct(request, db)

            if user:
                # Get assistant-specific configuration
                assistant_config = UserSettingsHelper.get_assistant_config(db, user.user_id)

                return AssistantSettingsResponse(
                    use_defaults=assistant_config.get("use_defaults", True),
                    provider=assistant_config.get("provider"),
                    model=assistant_config.get("model"),
                    has_custom_api_key=bool(assistant_config.get("custom_api_key_hash")),
                    saved=assistant_config != AssistantSettingsData.get_assistant_config_default()
                )
            else:
                # Return default settings
                return AssistantSettingsResponse(
                    use_defaults=True,
                    provider=None,
                    model=None,
                    has_custom_api_key=False,
                    saved=False
                )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get user assistant settings: {e}")
        # Return default settings on error
        return AssistantSettingsResponse(
            use_defaults=True,
            provider=None,
            model=None,
            has_custom_api_key=False,
            saved=False
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    try:
        has_adk = runtime_manager.executor.adk_session_service is not None
        agent_count = len(runtime_manager.agent_registry)
        active_sessions = len(runtime_manager.session_manager.get_active_sessions())

        return {
            "status": "healthy",
            "adk_available": has_adk,
            "agents_discovered": agent_count,
            "active_sessions": active_sessions
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _execute_with_claude_code(
    agent_id: str,
    input_text: str,
    model: str = "",
    user_id: str = None,
    user_email: str = None,
    ioflow_token: str = "",
) -> Dict[str, Any]:
    """Execute agent using Claude Code CLI instead of Google ADK.

    ``ioflow_token`` is the CALLER's bearer: the agent's tools act as them.
    """
    from services.claude_code_service import ClaudeCodeService, DEFAULT_ALLOWED_TOOLS
    import tempfile
    import re

    claude_path = os.environ.get("CLAUDE_CODE_PATH", "")
    service = ClaudeCodeService(claude_path=claude_path)

    if not service.is_available():
        return {
            "success": False,
            "error": "Claude Code CLI is not installed. Install with: npm install -g @anthropic-ai/claude-code"
        }

    # Load agent system prompt / instruction
    agent_system_prompt = ""
    agent_description = ""
    for agent in runtime_manager.agent_registry:
        if agent["id"] == agent_id:
            agent_description = agent.get("description", "")
            agent_path = agent.get("path", "")
            agent_type = agent.get("type", "")

            if agent_type == "json" and agent_path:
                try:
                    import json as _json
                    with open(agent_path, 'r') as f:
                        config = _json.load(f)
                    agent_system_prompt = config.get("system_prompt", "")
                    if config.get("instruction"):
                        agent_system_prompt = f"{agent_system_prompt}\n\n{config['instruction']}" if agent_system_prompt else config["instruction"]
                except Exception:
                    pass
            elif agent_type == "python" and get_pack_agent(agent_id):
                # Pack agents: the one definition (backend/agent_pack).
                agent_system_prompt = get_pack_agent(agent_id)["prompt"]
            elif agent_type == "python" and agent_path:
                try:
                    module_path = os.path.join(agent_path, "agent.py")
                    if os.path.exists(module_path):
                        with open(module_path, 'r') as f:
                            source = f.read()
                        instr_match = re.search(r'instruction\s*=\s*"""(.*?)"""', source, re.DOTALL)
                        if instr_match:
                            agent_system_prompt = instr_match.group(1).strip()
                except Exception:
                    pass
            break

    # Build system prompt and MCP config
    base_url = os.environ.get("IOFLOW_BASE_URL", "http://localhost:7001")
    token = ioflow_token or ""
    auth_header = f"Bearer {token}" if token else ""

    # Working directory
    base_dir = os.path.join(tempfile.gettempdir(), "ioflow_claude_agent")
    working_dir = os.path.join(base_dir, user_id or "anonymous", agent_id or "default")
    os.makedirs(working_dir, exist_ok=True)

    complex_agents = {"flow_designer", "flow_design_editor", "seed_application_designer"}
    mcp_config_path = None

    if agent_id in complex_agents:
        # --- MCP-native path: the bridge's tools via bridge_proxy, limited to
        # the agent-pack agent's tools (the same surface ADK and the plugin use).
        mcp_config = claude_mcp_config(agent_id, token)

        mcp_config_path = os.path.join(working_dir, ".mcp_config.json")
        import json as _json2
        # It carries the caller's token: readable by this process only.
        fd = os.open(mcp_config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            _json2.dump(mcp_config, f, indent=2)
        os.chmod(mcp_config_path, 0o600)

        full_system_prompt = ""
        if agent_system_prompt:
            full_system_prompt = agent_system_prompt
        elif agent_description:
            full_system_prompt = f"You are {agent_id}. {agent_description}"

        # Add Claude-Code-specific instruction: use MCP tools only, no direct API calls
        full_system_prompt += """

## IMPORTANT: Tool Usage Rules
- You have MCP tools available (e.g. validate_and_save_flow, list_applications, etc.) — call them directly as tool calls.
- Do NOT use Bash/curl to call IOFlow APIs. You do not have API credentials for direct HTTP calls.
- All IOFlow operations MUST go through the MCP tools which handle authentication automatically.
- Use Bash only for non-API tasks like file operations if needed."""
    else:
        # --- Curl-based path (for simple info/analyst agents) ---
        mcp_instructions = f"""
## IOFlow MCP API Access

Use Bash with curl to call IOFlow's MCP API. The ONLY endpoint is: POST {base_url}/api/mcp/tools/execute

```bash
curl -s -X POST "{base_url}/api/mcp/tools/execute" -H "Content-Type: application/json" -H "Authorization: {auth_header}" -d '{{"tool": "TOOL_NAME", "parameters": {{}}}}'
```

Info tools: get_application_categories, list_applications, search_applications, get_application_services_list,
get_service_information, search_services, search_flows, get_seed_application, ioflow_get_app_guide.
Always call guide tools first — they return the exact fields and structure.
"""
        full_system_prompt = ""
        if agent_system_prompt:
            full_system_prompt = agent_system_prompt + "\n\n"
        elif agent_description:
            full_system_prompt = f"You are {agent_id}. {agent_description}\n\n"
        full_system_prompt += mcp_instructions

    # Execute and collect response
    accumulated_text = ""
    try:
        async for event in service.stream_prompt(
            prompt=input_text,
            cwd=working_dir,
            system_prompt=full_system_prompt,
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebSearch", "WebFetch"],
            max_budget_usd=float(os.environ.get("CLAUDE_CODE_MAX_BUDGET_USD", "5.0")),
            model=model or os.environ.get("CLAUDE_CODE_MODEL") or None,
            max_turns=int(os.environ.get("CLAUDE_CODE_MAX_TURNS",
                          "15" if agent_id in complex_agents else "8")),
            mcp_config_path=mcp_config_path,
        ):
            event_type = event.get("type", "")
            if event_type == "assistant_text":
                accumulated_text += event.get("content", "")
            elif event_type == "error":
                return {
                    "success": False,
                    "error": event.get("message", "Unknown Claude Code error"),
                }

        return {
            "success": True,
            "session_id": f"claude_code_{agent_id}",
            "result": {
                "response": accumulated_text,
                "framework": "claude_code",
            },
        }

    except Exception as e:
        logger.error(f"Claude Code execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Claude Code execution failed: {str(e)}",
        }


# Export router for inclusion in main app
__all__ = ['router']
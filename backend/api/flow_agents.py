"""
Flow Agent Management API endpoints
This is separate from the flow execution and won't interfere with it.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import os
from pathlib import Path
import logging

from db.database import get_db
from api.auth import get_current_user
from db.models import User
from services.flow_agent_executor import FlowAgentExecutor
from core.security import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[Dict[str, Any]])
async def list_flow_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available flow agent configurations"""
    try:
        configs_dir = Path(__file__).parent.parent / "flow_agent_configs"
        agent_configs = []

        if configs_dir.exists():
            for config_file in configs_dir.glob("*.json"):
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                        agent_configs.append(config)
                except Exception as e:
                    logger.error(f"Failed to load config {config_file}: {e}")

        return agent_configs
    except Exception as e:
        logger.error(f"Failed to list flow agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list flow agents"
        )

@router.post("/", response_model=Dict[str, Any])
async def create_flow_agent(
    agent_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update a flow agent configuration"""
    try:
        agent_id = agent_config.get('agent_id')
        if not agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="agent_id is required"
            )

        # Ensure the directory exists
        configs_dir = Path(__file__).parent.parent / "flow_agent_configs"
        configs_dir.mkdir(exist_ok=True)

        # Save the configuration
        config_path = configs_dir / f"{agent_id}.json"
        with open(config_path, 'w') as f:
            json.dump(agent_config, f, indent=2)

        return {
            "message": f"Agent configuration saved: {agent_id}",
            "agent_id": agent_id
        }
    except Exception as e:
        logger.error(f"Failed to create flow agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create flow agent: {str(e)}"
        )

@router.post("/execute", response_model=Dict[str, Any])
async def execute_flow_agent(
    request_data: Dict[str, Any],
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute a flow agent directly for testing"""
    try:
        logger.info(f"Executing flow agent for user: {current_user.email}")

        # Check user's agent_framework setting
        from db.user_settings_models import UserSettingsHelper
        ai_config = UserSettingsHelper.get_ai_config(db, current_user.user_id)
        agent_framework = ai_config.get('agent_framework', 'google_adk')

        # If user has selected Claude Code framework, route to Claude Code executor
        if agent_framework == 'claude_code':
            return await _execute_with_claude_code(request_data, http_request, db, current_user)

        # Default: Google ADK execution
        return await _execute_with_google_adk(request_data, http_request, db, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute flow agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute flow agent: {str(e)}"
        )


async def _execute_with_claude_code(
    request_data: Dict[str, Any],
    http_request: Request,
    db: Session,
    current_user: User
) -> Dict[str, Any]:
    """Execute agent using Claude Code CLI."""
    from services.claude_code_service import ClaudeCodeService, DEFAULT_ALLOWED_TOOLS
    import os
    import tempfile

    agent_id = request_data.get('agent_id', '')
    input_text = request_data.get('input', '')
    system_prompt = request_data.get('system_prompt', '')
    instruction = request_data.get('instruction', '')
    model = request_data.get('model', '')
    tools = request_data.get('tools', [])

    claude_path = os.environ.get("CLAUDE_CODE_PATH", "")
    service = ClaudeCodeService(claude_path=claude_path)

    if not service.is_available():
        return {
            'error': True,
            'message': 'Claude Code CLI is not installed. Install with: npm install -g @anthropic-ai/claude-code'
        }

    # Claude Code CLI only works with Anthropic models — ignore non-Claude model from settings
    model = os.environ.get("CLAUDE_CODE_MODEL") or None

    # Build system prompt
    full_system_prompt = system_prompt
    if instruction:
        full_system_prompt = f"{full_system_prompt}\n\n{instruction}" if full_system_prompt else instruction

    # Add user context
    context_parts = []
    if hasattr(current_user, 'email') and current_user.email:
        context_parts.append(f"Authenticated user email: {current_user.email}")
    if hasattr(current_user, 'user_id') and current_user.user_id:
        context_parts.append(f"User ID: {current_user.user_id}")
    if hasattr(current_user, 'tenant_id') and current_user.tenant_id:
        context_parts.append(f"Tenant ID: {current_user.tenant_id}")

    if context_parts:
        context_prefix = "[SYSTEM CONTEXT]\n" + "\n".join(context_parts) + "\n\n[USER REQUEST]\n"
        final_input = f"{context_prefix}{input_text}"
    else:
        final_input = input_text

    # Create working directory
    base_dir = os.path.join(tempfile.gettempdir(), "ioflow_claude_agent")
    working_dir = os.path.join(base_dir, current_user.user_id, agent_id or "default")
    os.makedirs(working_dir, exist_ok=True)

    # Determine allowed tools
    allowed_tools = None
    if tools:
        allowed_tools = []
        for tool in tools:
            if isinstance(tool, str):
                allowed_tools.append(tool)
            elif isinstance(tool, dict):
                tool_name = tool.get('function') or tool.get('name')
                if tool_name:
                    allowed_tools.append(tool_name)

    # Collect all output
    accumulated_text = ""
    try:
        async for event in service.stream_prompt(
            prompt=final_input,
            cwd=working_dir,
            system_prompt=full_system_prompt,
            allowed_tools=allowed_tools if allowed_tools else list(DEFAULT_ALLOWED_TOOLS),
            max_budget_usd=float(os.environ.get("CLAUDE_CODE_MAX_BUDGET_USD", "2.0")),
            model=model or os.environ.get("CLAUDE_CODE_MODEL") or None,
        ):
            event_type = event.get("type", "")
            if event_type == "assistant_text":
                accumulated_text += event.get("content", "")
            elif event_type == "error":
                return {
                    "error": True,
                    "message": event.get("message", "Unknown error"),
                    "agent_id": agent_id,
                    "framework": "claude_code",
                }

        from datetime import datetime
        return {
            "success": True,
            "agent_id": agent_id,
            "response": accumulated_text,
            "model": model or "claude-code-default",
            "framework": "claude_code",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to execute Claude Code agent: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to execute Claude Code agent: {str(e)}",
            "framework": "claude_code",
        }


async def _execute_with_google_adk(
    request_data: Dict[str, Any],
    http_request: Request,
    db: Session,
    current_user: User
) -> Dict[str, Any]:
    """Execute agent using Google ADK (original implementation)."""
    # Extract parameters
    agent_id = request_data.get('agent_id')
    input_text = request_data.get('input', '')
    use_dynamic = request_data.get('use_dynamic', False)
    system_prompt = request_data.get('system_prompt', '')
    instruction = request_data.get('instruction', '')
    model = request_data.get('model', 'gemini-2.0-flash-exp')
    tools = request_data.get('tools', [])

    authorization = http_request.headers.get("Authorization", "")
    api_key = None

    if authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "")
        token_type = 'API key' if api_key.startswith('ioflow_') else 'JWT'
        logger.info(f"Extracted token from Authorization header (type: {token_type})")

    if not api_key:
        api_key = request_data.get('api_key')
        if api_key:
            logger.info("Using api_key from request body")

    if not api_key:
        logger.info("No token found, generating temporary JWT for agent execution")
        auth_service = AuthService(db)
        api_key = auth_service.create_access_token(
            data={
                "sub": current_user.user_id,
                "tenant_id": current_user.tenant_id,
                "email": current_user.email
            }
        )
        logger.info("Generated temporary session token for agent")

    executor = FlowAgentExecutor(
        service_config={},
        auth_credentials={'api_key': api_key},
        subscription_id=None,
        auth_config={}
    )

    parameters = {
        'operation': 'execute',
        'agent_id': agent_id,
        'input': input_text,
        'use_dynamic': use_dynamic,
        'system_prompt': system_prompt,
        'instruction': instruction,
        'model': model,
        'tools': tools,
        'api_key': api_key
    }

    result = await executor._execute_agent(parameters, {
        'user_id': current_user.user_id,
        'tenant_id': current_user.tenant_id,
        'user_email': current_user.email
    })

    return result

@router.get("/{agent_id}", response_model=Dict[str, Any])
async def get_flow_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific flow agent configuration"""
    try:
        config_path = Path(__file__).parent.parent / "flow_agent_configs" / f"{agent_id}.json"

        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent configuration not found: {agent_id}"
            )

        with open(config_path, 'r') as f:
            config = json.load(f)

        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get flow agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get flow agent"
        )

@router.delete("/{agent_id}")
async def delete_flow_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a flow agent configuration"""
    try:
        config_path = Path(__file__).parent.parent / "flow_agent_configs" / f"{agent_id}.json"

        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent configuration not found: {agent_id}"
            )

        config_path.unlink()

        return {"message": f"Agent configuration deleted: {agent_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete flow agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete flow agent"
        )
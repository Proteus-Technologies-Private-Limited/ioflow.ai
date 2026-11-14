"""
Claude Code Agent router for IOFlow -- WebSocket streaming + REST endpoints.

Provides the same Claude Code agent functionality as twasta.ai but adapted
for IOFlow's architecture and agent system.
"""
import asyncio
import json
import logging
import os
import secrets
import time
import uuid
import tempfile

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from db.database import get_db
from core.auth_utils import get_current_user_required as get_current_user
from db.models import User
from services.claude_code_service import ClaudeCodeService, DEFAULT_ALLOWED_TOOLS
from services.claude_code_agent_session import claude_code_session_store

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Claude Code service (singleton)
# ---------------------------------------------------------------------------

_service: ClaudeCodeService | None = None


def get_service() -> ClaudeCodeService:
    global _service
    if _service is None:
        claude_path = os.environ.get("CLAUDE_CODE_PATH", "")
        _service = ClaudeCodeService(claude_path=claude_path)
    return _service


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    agent_id: str = ""
    working_dir: str = ""


class CreateSessionResponse(BaseModel):
    session_id: str


class AvailabilityResponse(BaseModel):
    available: bool
    claude_path: str = ""
    message: str = ""


class PermissionRequest(BaseModel):
    tool_name: str
    tool_input: dict = {}
    detail: str = ""


class PermissionResponse(BaseModel):
    decision: str  # "allow" or "deny"


class ExecuteRequest(BaseModel):
    agent_id: str = ""
    input: str = ""
    system_prompt: str = ""
    instruction: str = ""
    model: str = ""
    tools: list = []
    max_turns: Optional[int] = None
    max_budget_usd: Optional[float] = None


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/check-availability", response_model=AvailabilityResponse)
def check_availability():
    """Check if Claude Code CLI is installed and available."""
    service = get_service()
    if service.is_available():
        return AvailabilityResponse(
            available=True,
            claude_path=service.claude_path,
            message="Claude Code CLI is available.",
        )
    return AvailabilityResponse(
        available=False,
        message="Claude Code CLI is not installed. Install with: npm install -g @anthropic-ai/claude-code",
    )


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Claude Code agent session."""
    service = get_service()
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Claude Code CLI is not installed or not found. "
                   "Install it with: npm install -g @anthropic-ai/claude-code",
        )

    # Create a working directory for the agent
    working_dir = payload.working_dir
    if not working_dir:
        # Use a temp directory under IOFlow's data path
        base_dir = os.path.join(tempfile.gettempdir(), "ioflow_claude_agent")
        working_dir = os.path.join(base_dir, current_user.user_id, payload.agent_id or "default")
        os.makedirs(working_dir, exist_ok=True)

    session = claude_code_session_store.create(
        user_id=current_user.user_id,
        tenant_id=getattr(current_user, 'tenant_id', ''),
        agent_id=payload.agent_id,
        working_dir=working_dir,
    )
    return CreateSessionResponse(session_id=session.id)


@router.post("/execute", response_model=Dict[str, Any])
async def execute_agent(
    request_data: ExecuteRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a Claude Code agent synchronously (non-streaming).
    Collects all output and returns the result.
    For streaming, use the WebSocket endpoint instead.
    """
    service = get_service()
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Claude Code CLI is not installed.",
        )

    # Create temp working directory
    base_dir = os.path.join(tempfile.gettempdir(), "ioflow_claude_agent")
    working_dir = os.path.join(base_dir, current_user.user_id, request_data.agent_id or "default")
    os.makedirs(working_dir, exist_ok=True)

    # Build system prompt
    system_prompt = request_data.system_prompt
    if request_data.instruction:
        system_prompt = f"{system_prompt}\n\n{request_data.instruction}" if system_prompt else request_data.instruction

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
        final_input = f"{context_prefix}{request_data.input}"
    else:
        final_input = request_data.input

    # Determine tools
    allowed_tools = None
    if request_data.tools:
        allowed_tools = []
        for tool in request_data.tools:
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
            system_prompt=system_prompt,
            allowed_tools=allowed_tools if allowed_tools else list(DEFAULT_ALLOWED_TOOLS),
            max_budget_usd=request_data.max_budget_usd or 2.0,
            model=request_data.model or None,
            max_turns=request_data.max_turns,
        ):
            event_type = event.get("type", "")
            if event_type == "assistant_text":
                accumulated_text += event.get("content", "")
            elif event_type == "error":
                return {
                    "error": True,
                    "message": event.get("message", "Unknown error"),
                    "agent_id": request_data.agent_id,
                }

        return {
            "success": True,
            "agent_id": request_data.agent_id,
            "response": accumulated_text,
            "model": request_data.model or "claude-code-default",
            "framework": "claude_code",
        }

    except Exception as e:
        logger.error("Failed to execute Claude Code agent: %s", e, exc_info=True)
        return {
            "error": True,
            "message": f"Failed to execute Claude Code agent: {str(e)}",
        }


# ---------------------------------------------------------------------------
# Permission endpoint (called by the hook script, NOT by the frontend)
# ---------------------------------------------------------------------------

PERMISSION_TIMEOUT_SECONDS = 300


@router.post("/permission/{session_id}", response_model=PermissionResponse)
async def handle_permission(session_id: str, payload: PermissionRequest, request: Request):
    """
    Called by the PreToolUse hook script running inside the Claude CLI subprocess.
    Blocks until the frontend user approves/denies via the WebSocket, or timeout.

    Only that hook may call it: it presents the session's ``hook_secret``.
    """
    session = claude_code_session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    presented = request.headers.get("X-IOFlow-Hook-Secret", "")
    if not presented or not secrets.compare_digest(presented, session.hook_secret):
        raise HTTPException(status_code=403, detail="Not this session's permission hook")

    ws = session._websocket
    if ws is None:
        return PermissionResponse(decision="deny")

    permission_id = str(uuid.uuid4())
    event = asyncio.Event()
    session._pending_permission = {
        "id": permission_id,
        "tool_name": payload.tool_name,
        "tool_input": payload.tool_input,
        "detail": payload.detail,
        "event": event,
        "decision": "deny",
    }

    try:
        await ws.send_text(json.dumps({
            "type": "permission_request",
            "permission_id": permission_id,
            "tool_name": payload.tool_name,
            "detail": payload.detail,
            "tool_input": payload.tool_input,
        }))
    except Exception as e:
        logger.error("Failed to send permission_request via WS: %s", e)
        session._pending_permission = None
        return PermissionResponse(decision="deny")

    try:
        await asyncio.wait_for(event.wait(), timeout=PERMISSION_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Permission timeout for session %s, tool %s", session_id, payload.tool_name)

    decision = session._pending_permission.get("decision", "deny") if session._pending_permission else "deny"
    session._pending_permission = None
    return PermissionResponse(decision=decision)


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------


async def _kill_active_process(session) -> None:
    """Terminate and kill the active subprocess on a session."""
    proc = session._active_process
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=0.5)
    except (asyncio.TimeoutError, ProcessLookupError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


async def _resolve_pending_permission(session, decision: str = "deny") -> None:
    """Resolve any pending permission request with the given decision."""
    pending = session._pending_permission
    if pending is not None:
        pending["decision"] = decision
        evt = pending.get("event")
        if evt and not evt.is_set():
            evt.set()


async def _cancel_streaming(session) -> None:
    """Kill subprocess and cancel the streaming asyncio task."""
    await _resolve_pending_permission(session, "deny")
    await _kill_active_process(session)
    task = session._streaming_task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    session._streaming_task = None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, token: str = ""):
    session = claude_code_session_store.get(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    # Only the user who created the session may drive it (?token=<JWT or ioflow_ key>).
    from dev_agent_runtime.streaming_handler import verified_caller
    caller = await verified_caller(token or websocket.query_params.get("token"))
    if caller is None or str(caller.user_id) != str(session.user_id):
        await websocket.close(code=4401, reason="Not authorized for this session")
        return

    service = get_service()
    if not service.is_available():
        await websocket.accept()
        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": "Claude Code CLI is not installed.",
            })
        )
        await websocket.close(code=4003, reason="Claude Code CLI not available")
        return

    await websocket.accept()
    session._websocket = websocket

    async def _run_streaming(message_data: dict):
        """Run Claude Code streaming as an asyncio task."""
        _perf_start = time.time()

        try:
            input_text = message_data.get("input", "")
            system_prompt = message_data.get("system_prompt", "")
            instruction = message_data.get("instruction", "")
            model = message_data.get("model", "")
            tools = message_data.get("tools", [])
            max_turns = message_data.get("max_turns")
            max_budget_usd = message_data.get("max_budget_usd", 2.0)

            # Build combined system prompt
            if instruction:
                system_prompt = f"{system_prompt}\n\n{instruction}" if system_prompt else instruction

            # Determine tools
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

            # Take file snapshot before
            before_snapshot = await asyncio.to_thread(service.snapshot_files, session.working_dir)

            # Send initial progress
            start_time = time.time()
            last_activity = "thinking"
            await websocket.send_text(
                json.dumps({
                    "type": "progress",
                    "status": "thinking",
                    "elapsed": 0,
                })
            )

            # Background heartbeat
            heartbeat_stop = asyncio.Event()

            async def _heartbeat():
                nonlocal last_activity
                while not heartbeat_stop.is_set():
                    await asyncio.sleep(2)
                    if heartbeat_stop.is_set():
                        break
                    elapsed = int(time.time() - start_time)
                    status = "awaiting_permission" if session._pending_permission else last_activity
                    try:
                        await websocket.send_text(
                            json.dumps({
                                "type": "progress",
                                "status": status,
                                "elapsed": elapsed,
                            })
                        )
                    except Exception:
                        break

            heartbeat_task = asyncio.create_task(_heartbeat())

            # Each task starts fresh
            session.claude_session_id = None
            result_session_id = None
            _accumulated_text = ""

            try:
                async for event in service.stream_prompt(
                    prompt=input_text,
                    cwd=session.working_dir,
                    session_id=None,
                    system_prompt=system_prompt,
                    allowed_tools=allowed_tools if allowed_tools else list(DEFAULT_ALLOWED_TOOLS),
                    max_budget_usd=max_budget_usd,
                    model=model or None,
                    session=session,
                    ioflow_session_id=session_id,
                    max_turns=max_turns,
                ):
                    event_type = event.get("type", "")

                    if event_type == "assistant_text":
                        last_activity = "responding"
                        _accumulated_text += event.get("content", "")
                        await websocket.send_text(
                            json.dumps({
                                "type": "assistant_text",
                                "content": event["content"],
                            })
                        )

                    elif event_type == "tool_activity":
                        tool_name = event.get("tool", "")
                        last_activity = tool_name.lower()
                        await websocket.send_text(
                            json.dumps({
                                "type": "tool_activity",
                                "tool": tool_name,
                                "file": event.get("file", ""),
                            })
                        )

                    elif event_type == "session_init":
                        sid = event.get("session_id")
                        if sid:
                            result_session_id = sid
                            session.claude_session_id = sid

                    elif event_type == "result":
                        result_session_id = event.get("session_id", result_session_id)

                    elif event_type == "error":
                        await websocket.send_text(
                            json.dumps({
                                "type": "error",
                                "message": event.get("message", "Unknown error"),
                            })
                        )
            finally:
                heartbeat_stop.set()
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            # Detect changed files
            changed_files = await asyncio.to_thread(
                service.get_changed_files, session.working_dir, before_snapshot
            )

            # Send completion
            await websocket.send_text(
                json.dumps({
                    "type": "complete",
                    "response": _accumulated_text,
                    "changed_files": changed_files,
                    "claude_session_id": session.claude_session_id or "",
                })
            )

        except asyncio.CancelledError:
            logger.info("Streaming task cancelled for session %s", session_id)
            try:
                await websocket.send_text(
                    json.dumps({
                        "type": "cancelled",
                        "claude_session_id": session.claude_session_id or "",
                    })
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("Agent streaming error: %s", e)
            try:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": str(e)})
                )
            except Exception:
                pass
        finally:
            session._streaming_task = None

    # Main WebSocket receive loop
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "message":
                session._streaming_task = asyncio.create_task(
                    _run_streaming(message)
                )

            elif msg_type == "cancel":
                logger.info("Cancel requested for session %s", session_id)
                await _cancel_streaming(session)

            elif msg_type == "permission_response":
                perm_id = message.get("permission_id", "")
                decision = message.get("decision", "deny")
                pending = session._pending_permission
                if pending and pending.get("id") == perm_id:
                    pending["decision"] = decision
                    evt = pending.get("event")
                    if evt and not evt.is_set():
                        evt.set()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
        await _resolve_pending_permission(session, "deny")
        session._websocket = None
        await _cancel_streaming(session)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        await _resolve_pending_permission(session, "deny")
        session._websocket = None
        await _cancel_streaming(session)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(e)})
            )
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass

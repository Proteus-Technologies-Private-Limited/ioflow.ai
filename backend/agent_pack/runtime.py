"""
How an IOFlow Assistant agent reaches its tools, per request.

The assistant used to hand each caller's token to its agents through the
process-wide ``os.environ['IOFLOW_API_KEY']``: two concurrent sessions raced on
it and one tenant's agent could run as another. The token now travels in a
ContextVar set for the request (``set_request_token``) and read when the agent
module builds its MCP toolset (``bridge_server_params``) — which happens inside
that same request task.

Agents get the MCP BRIDGE's tools through ``mcp_server/bridge_proxy.py``,
restricted to the tools their agent-pack entry declares — the same tool surface
and the same names the Claude Code plugin and external agents use.
"""
from __future__ import annotations

import contextvars
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import get_agent

_REQUEST_TOKEN: contextvars.ContextVar = contextvars.ContextVar("ioflow_agent_request_token", default=None)

BACKEND_DIR = Path(__file__).resolve().parent.parent
BRIDGE_PROXY = BACKEND_DIR / "mcp_server" / "bridge_proxy.py"


def set_request_token(token: Optional[str]) -> contextvars.Token:
    """Bind the caller's IOFlow token (JWT or ``ioflow_`` key) to this request."""
    return _REQUEST_TOKEN.set(token or None)


def current_ioflow_token() -> str:
    """The current request's token; the server's own env key only outside a request."""
    token = _REQUEST_TOKEN.get()
    if token:
        return token
    return os.environ.get("IOFLOW_API_KEY", "")


def ioflow_base_url() -> str:
    return os.environ.get("IOFLOW_BASE_URL", "http://localhost:7001")


def bridge_server_params(agent_name: str, token: Optional[str] = None) -> Dict[str, Any]:
    """``StdioServerParameters`` kwargs for one pack agent's MCP toolset."""
    agent = get_agent(agent_name)
    env = {k: v for k, v in os.environ.items() if k != "IOFLOW_API_KEY"}
    env.update({
        "IOFLOW_API_KEY": token if token is not None else current_ioflow_token(),
        "IOFLOW_BASE_URL": ioflow_base_url(),
        "IOFLOW_TOOL_ALLOWLIST": ",".join(agent["tools"]) if agent else "",
        "PYTHONPATH": str(BACKEND_DIR),
    })
    return {"command": sys.executable, "args": [str(BRIDGE_PROXY)], "env": env}


def claude_mcp_config(agent_name: str, token: str) -> Dict[str, Any]:
    """The ``--mcp-config`` document for a Claude Code run of one pack agent."""
    params = bridge_server_params(agent_name, token=token)
    keep = ("IOFLOW_API_KEY", "IOFLOW_BASE_URL", "IOFLOW_TOOL_ALLOWLIST", "PYTHONPATH")
    return {"mcpServers": {"ioflow": {
        "command": params["command"],
        "args": params["args"],
        "env": {k: params["env"][k] for k in keep},
    }}}

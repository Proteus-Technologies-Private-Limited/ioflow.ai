#!/usr/bin/env python3
"""
IOFlow MCP bridge proxy (stdio) — the Python twin of ioflow-plugin/mcp-proxy.mjs.

Speaks MCP over stdio and forwards every call to the HTTP MCP bridge
(``GET /api/mcp/tools``, ``POST /api/mcp/tools/execute``), so an agent started
by the IOFlow Assistant sees EXACTLY the tool set the Claude Code plugin and
external agents (Twasta's Ask-AI) see: one tool surface, named once, with no
business logic here.

Environment:
  IOFLOW_API_KEY         bearer used for every call (an ``ioflow_`` API key or a
                         user JWT) — required
  IOFLOW_BASE_URL        bridge base URL (default http://localhost:7001)
  IOFLOW_TOOL_ALLOWLIST  optional comma list: only these tools are listed and
                         callable (an agent pack agent's ``tools``)

Standard library only.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("IOFLOW_BASE_URL", "http://localhost:7001").rstrip("/")
API_KEY = os.environ.get("IOFLOW_API_KEY", "")
ALLOW = {t.strip() for t in os.environ.get("IOFLOW_TOOL_ALLOWLIST", "").split(",") if t.strip()}
TIMEOUT = float(os.environ.get("IOFLOW_PROXY_TIMEOUT", "180"))

_tools_cache = None


def _log(msg: str) -> None:
    sys.stderr.write(f"ioflow-bridge-proxy: {msg}\n")
    sys.stderr.flush()


def _http(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "null")


def _tools():
    global _tools_cache
    if _tools_cache is None:
        try:
            tools = _http("GET", "/api/mcp/tools") or []
        except Exception as e:  # pragma: no cover - network
            _log(f"could not list tools: {e}")
            return []
        _tools_cache = [t for t in tools if not ALLOW or t.get("name") in ALLOW]
    return _tools_cache


def _call(name: str, args):
    if ALLOW and name not in ALLOW:
        return {"success": False, "error": f"Tool '{name}' is not available to this agent", "tool": name}
    try:
        return _http("POST", "/api/mcp/tools/execute", {"tool": name, "parameters": args or {}})
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode(errors='replace')[:2000]}", "tool": name}
    except Exception as e:  # pragma: no cover - network
        return {"success": False, "error": str(e), "tool": name}


def _send(obj) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def handle(req) -> None:
    rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
    if method == "initialize":
        _send({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion") or "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "ioflow-bridge-proxy", "version": "1.0.0"},
        }})
    elif method == "tools/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": t["name"], "description": t.get("description") or "",
             "inputSchema": t.get("input_schema") or {"type": "object", "properties": {}}}
            for t in _tools()
        ]}})
    elif method == "tools/call":
        result = _call(params.get("name"), params.get("arguments"))
        payload = result.get("result", result) if isinstance(result, dict) else result
        _send({"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
            "isError": isinstance(result, dict) and result.get("success") is False,
        }})
    elif method in ("resources/list",):
        _send({"jsonrpc": "2.0", "id": rid, "result": {"resources": []}})
    elif method in ("prompts/list",):
        _send({"jsonrpc": "2.0", "id": rid, "result": {"prompts": []}})
    elif method == "ping":
        _send({"jsonrpc": "2.0", "id": rid, "result": {}})
    elif rid is not None and not str(method or "").startswith("notifications/"):
        _send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}})


def main() -> int:
    if not API_KEY:
        _log("IOFLOW_API_KEY not set")
        return 1
    _log(f"connecting to {BASE_URL}" + (f" ({len(ALLOW)} allowed tools)" if ALLOW else ""))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _log(f"invalid JSON: {line[:200]}")
            continue
        try:
            handle(req)
        except Exception as e:  # pragma: no cover
            if req.get("id") is not None:
                _send({"jsonrpc": "2.0", "id": req["id"], "error": {"code": -32603, "message": str(e)}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

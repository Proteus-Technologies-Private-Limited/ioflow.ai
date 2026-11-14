#!/usr/bin/env python3
"""
Claude Code PreToolUse hook for IOFlow.

This script runs as a Claude Code hook when a tool use is attempted.
It reads session configuration from {cwd}/.claude/.ioflow_session and
either auto-allows, auto-denies, or routes to the IOFlow backend for
interactive permission handling.

Adapted from twasta.ai's permission hook.
"""
import json
import os
import sys
import urllib.request
import urllib.error
import logging

LOG_PATH = os.environ.get("IOFLOW_HOOK_LOG", "/tmp/ioflow_hook.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ioflow_hook")

# Tools that are always auto-allowed (safe, read-only operations)
AUTO_ALLOW_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Task",
}


def main():
    """Read hook input from stdin and decide whether to allow or deny."""
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except Exception as e:
        log.error("Failed to parse hook input: %s", e)
        # Fail open
        print(json.dumps({"decision": "allow"}))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    log.info("Hook called: tool=%s", tool_name)

    # Find the session file in the current working directory
    cwd = os.getcwd()
    session_file = os.path.join(cwd, ".claude", ".ioflow_session")

    if not os.path.exists(session_file):
        # Not an IOFlow project — allow everything
        log.info("No .ioflow_session file, allowing")
        print(json.dumps({"decision": "allow"}))
        return

    try:
        with open(session_file, "r") as f:
            session_data = json.load(f)
    except Exception as e:
        log.error("Failed to read session file: %s", e)
        print(json.dumps({"decision": "allow"}))
        return

    session_id = session_data.get("session_id", "")
    backend_url = session_data.get("backend_url", "http://localhost:7001")
    allowed_tools = session_data.get("allowed_tools")

    # If allowed_tools is specified, enforce it
    if allowed_tools is not None:
        if tool_name not in allowed_tools:
            log.info("Tool %s not in allowed_tools %s, denying", tool_name, allowed_tools)
            print(json.dumps({"decision": "deny", "reason": f"Tool {tool_name} not allowed for this task"}))
            return
        else:
            log.info("Tool %s in allowed_tools, allowing", tool_name)
            print(json.dumps({"decision": "allow"}))
            return

    # Auto-allow safe tools
    if tool_name in AUTO_ALLOW_TOOLS:
        log.info("Auto-allowing safe tool: %s", tool_name)
        print(json.dumps({"decision": "allow"}))
        return

    # Route to backend for interactive permission
    if not session_id:
        log.warning("No session_id in session file, allowing")
        print(json.dumps({"decision": "allow"}))
        return

    permission_url = f"{backend_url}/api/v1/claude-code-agent/permission/{session_id}"
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input,
        "detail": f"Agent wants to use {tool_name}",
    }).encode("utf-8")

    log.info("Requesting permission from %s", permission_url)

    try:
        req = urllib.request.Request(
            permission_url,
            data=payload,
            headers={"Content-Type": "application/json",
                     "X-IOFlow-Hook-Secret": session_data.get("hook_secret", "")},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            decision = result.get("decision", "deny")
            log.info("Permission result: %s", decision)
            print(json.dumps({"decision": decision}))
    except urllib.error.HTTPError as e:
        # The backend answered and refused (bad secret, unknown session): deny.
        log.error("HTTP error from backend: %s", e)
        print(json.dumps({"decision": "deny"}))
    except Exception as e:
        log.error("Failed to get permission: %s", e)
        # Fail open
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()

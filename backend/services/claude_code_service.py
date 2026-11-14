"""
Claude Code CLI integration service for IOFlow.

Wraps the `claude` CLI binary to provide async streaming AI responses.
Adapted from twasta.ai's Claude Code agent implementation.
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from services.claude_code_agent_session import ClaudeCodeAgentSession

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]


class ClaudeCodeService:
    """Wraps the Claude Code CLI for async streaming interactions."""

    def __init__(self, claude_path: str = ""):
        self.claude_path = claude_path or shutil.which("claude") or ""

    def is_available(self) -> bool:
        """Check if the claude CLI binary is installed and accessible."""
        return bool(self.claude_path) and os.path.isfile(self.claude_path)

    def snapshot_files(self, cwd: str) -> dict[str, tuple[float, str]]:
        """
        Take a snapshot of file mtimes and content hashes in the project dir.
        Returns {relative_path: (mtime, content_hash)}.
        """
        snapshot: dict[str, tuple[float, str]] = {}
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            return snapshot

        for fpath in cwd_path.rglob("*"):
            if fpath.is_file() and not fpath.name.startswith("."):
                try:
                    rel = str(fpath.relative_to(cwd_path))
                    mtime = fpath.stat().st_mtime
                    content_hash = hashlib.md5(fpath.read_bytes()).hexdigest()
                    snapshot[rel] = (mtime, content_hash)
                except (OSError, ValueError):
                    continue
        return snapshot

    def get_changed_files(
        self, cwd: str, before_snapshot: dict[str, tuple[float, str]]
    ) -> list[dict]:
        """
        Compare current files against a previous snapshot.
        Returns list of {"path": str, "content": str} for changed/new files.
        """
        after_snapshot = self.snapshot_files(cwd)
        changed: list[dict] = []
        cwd_path = Path(cwd)

        for rel_path, (after_mtime, after_hash) in after_snapshot.items():
            before = before_snapshot.get(rel_path)
            if before is None or before[1] != after_hash:
                try:
                    content = (cwd_path / rel_path).read_text(encoding="utf-8")
                    changed.append({"path": rel_path, "content": content})
                except (OSError, UnicodeDecodeError):
                    continue

        return changed

    def _write_hook_settings(
        self,
        project_dir: str,
        session_id: str,
        backend_url: str = "",
        allowed_tools: list[str] | None = None,
    ) -> None:
        """
        Set up permission handling for a Claude CLI session.

        Writes a session file in the project's .claude/ directory
        containing the session ID, backend URL, and allowed tools list.
        """
        if not backend_url:
            backend_url = os.environ.get("IOFLOW_BACKEND_URL", "http://localhost:7001")

        hook_script = str(
            Path(__file__).resolve().parent.parent
            / "agent" / "claude_code_hooks" / "permission_hook.py"
        )

        # Write session file to project directory
        claude_dir = Path(project_dir) / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        session_file = claude_dir / ".ioflow_session"
        session_data: dict = {
            "session_id": session_id,
            "backend_url": backend_url,
        }
        if allowed_tools is not None:
            session_data["allowed_tools"] = allowed_tools
        try:
            from services.claude_code_agent_session import claude_code_session_store
            ioflow_session = claude_code_session_store.get(session_id)
            if ioflow_session is not None:
                session_data["hook_secret"] = ioflow_session.hook_secret
        except Exception as e:  # pragma: no cover - the hook then gets a 403
            logger.warning("Could not attach the permission hook secret: %s", e)
        fd = os.open(str(session_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(session_data))
        logger.info("Wrote session file to %s", session_file)

        # Ensure global settings have the hook command
        global_settings_path = Path.home() / ".claude" / "settings.json"
        global_settings: dict = {}
        if global_settings_path.exists():
            try:
                global_settings = json.loads(global_settings_path.read_text())
            except (json.JSONDecodeError, OSError):
                global_settings = {}

        hook_config = {
            "PreToolUse": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {hook_script}",
                            "timeout": 300,
                        }
                    ],
                }
            ]
        }

        if global_settings.get("hooks") != hook_config:
            global_settings["hooks"] = hook_config
            global_settings_path.write_text(json.dumps(global_settings, indent=2))
            logger.info("Updated global Claude hook settings")

    async def stream_prompt(
        self,
        prompt: str,
        cwd: str,
        session_id: str | None = None,
        system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        max_budget_usd: float | None = None,
        model: str | None = None,
        session: "ClaudeCodeAgentSession | None" = None,
        ioflow_session_id: str | None = None,
        max_turns: int | None = None,
        effort: str | None = None,
        mcp_config_path: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Run `claude -p` with streaming JSON output and yield parsed events.

        Yields dicts:
          {"type": "assistant_text", "content": "..."}
          {"type": "tool_activity", "tool": "...", "file": "..."}
          {"type": "result", "session_id": "...", "cost_usd": ...}
          {"type": "error", "message": "..."}
        """
        if not self.is_available():
            yield {"type": "error", "message": "Claude Code CLI is not installed."}
            return

        tools = allowed_tools if allowed_tools is not None else list(DEFAULT_ALLOWED_TOOLS)

        # Write hook settings for interactive permission handling
        if ioflow_session_id:
            try:
                self._write_hook_settings(cwd, ioflow_session_id, allowed_tools=tools or None)
            except Exception as e:
                logger.warning("Failed to write hook settings: %s", e)

        cmd = [
            self.claude_path,
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--dangerously-skip-permissions",
        ]

        # Add MCP server config if provided
        if mcp_config_path:
            cmd.extend(["--mcp-config", mcp_config_path])
            # With MCP, don't restrict tools - let Claude access both native and MCP tools
            logger.info("MCP config provided, skipping --allowedTools to expose MCP tools")
        elif allowed_tools is not None and len(allowed_tools) == 0:
            cmd.extend(["--allowedTools", "__none__"])
        else:
            for tool in tools:
                cmd.extend(["--allowedTools", tool])

        # Max turns
        if max_turns is not None:
            cmd.extend(["--max-turns", str(max_turns)])

        # System prompt
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # Session resume
        if session_id:
            cmd.extend(["--resume", session_id])

        # Cost cap
        if max_budget_usd:
            cmd.extend(["--max-budget-usd", str(max_budget_usd)])

        # Model override
        if model:
            cmd.extend(["--model", model])

        # Effort level
        if effort:
            cmd.extend(["--effort", effort])

        # Prompt is the last argument
        cmd.append(prompt)

        logger.info("Starting Claude Code CLI: cwd=%s", cwd)
        logger.info("CLI command args: %s", " ".join(cmd[:10]) + " ...")

        # Clean env: remove CLAUDECODE to avoid "nested session" block
        clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
                limit=10 * 1024 * 1024,
            )
        except FileNotFoundError:
            yield {"type": "error", "message": "Claude Code CLI binary not found."}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Failed to start Claude Code: {e}"}
            return

        # Store process reference on session for cancellation support
        if session is not None:
            session._active_process = proc

        result_session_id = session_id
        accumulated_text = ""
        _event_count = 0
        # State for streaming Write/Edit tool content
        _write_tool_name = ""
        _write_partial_json = ""
        _write_in_content = False
        _write_content_offset = 0
        _write_streamed_len = 0

        try:
            logger.info("Starting to read CLI stdout (pid=%s)", proc.pid)
            while True:
                line = await proc.stdout.readline()
                if not line:
                    logger.info("EOF from CLI (pid=%s, returncode=%s, events=%d)",
                                proc.pid, proc.returncode, _event_count)
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")
                _event_count += 1

                # Capture session_id from ANY event that carries it
                _evt_sid = event.get("session_id")
                if _evt_sid and _evt_sid != result_session_id:
                    result_session_id = _evt_sid
                    if session is not None:
                        session.claude_session_id = _evt_sid
                    yield {
                        "type": "session_init",
                        "session_id": _evt_sid,
                    }

                if event_type == "system":
                    logger.info("CLI session initialized: model=%s", event.get("model", ""))
                    continue

                elif event_type == "stream_event":
                    inner = event.get("event", {})
                    inner_type = inner.get("type", "")

                    if inner_type == "content_block_delta":
                        delta = inner.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                accumulated_text += text
                                yield {"type": "assistant_text", "content": text}

                        elif delta_type == "input_json_delta":
                            # Accumulate partial JSON for ALL tools (needed for tool_detail)
                            chunk = delta.get("partial_json", "")
                            _write_partial_json += chunk
                            if _write_tool_name in ("Write", "Edit"):
                                if not _write_in_content:
                                    for marker in ('"content":"', '"content": "',
                                                   '"new_string":"', '"new_string": "'):
                                        idx = _write_partial_json.find(marker)
                                        if idx != -1:
                                            _write_in_content = True
                                            _write_content_offset = idx + len(marker)
                                            break
                                if _write_in_content:
                                    raw = _write_partial_json[_write_content_offset:]
                                    if raw.endswith("\\") and not raw.endswith("\\\\"):
                                        raw = raw[:-1]
                                    decoded = (
                                        raw
                                        .replace("\\\\", "\x00BS\x00")
                                        .replace('\\"', '"')
                                        .replace("\\n", "\n")
                                        .replace("\\r", "\r")
                                        .replace("\\t", "\t")
                                        .replace("\\/", "/")
                                        .replace("\x00BS\x00", "\\")
                                    )
                                    new_text = decoded[_write_streamed_len:]
                                    _write_streamed_len = len(decoded)
                                    if new_text:
                                        yield {"type": "assistant_text", "content": new_text}

                    elif inner_type == "content_block_start":
                        block = inner.get("content_block", {})
                        block_type = block.get("type", "")
                        if block_type == "tool_use":
                            tool_name = block.get("name", "")
                            _write_tool_name = tool_name
                            _write_partial_json = ""
                            _write_in_content = False
                            _write_content_offset = 0
                            _write_streamed_len = 0
                            yield {
                                "type": "tool_activity",
                                "tool": tool_name,
                                "file": "",
                            }
                        elif block_type == "thinking":
                            yield {"type": "assistant_text", "content": ""}

                    elif inner_type == "content_block_stop":
                        # Emit tool_detail with parsed input for the completed tool call
                        if _write_tool_name and _write_partial_json:
                            try:
                                tool_input = json.loads(_write_partial_json)
                                file_path = (
                                    tool_input.get("file_path", "")
                                    or tool_input.get("path", "")
                                    or tool_input.get("pattern", "")
                                    or tool_input.get("command", "")
                                )
                                yield {
                                    "type": "tool_detail",
                                    "tool": _write_tool_name,
                                    "file": file_path,
                                    "input": tool_input,
                                }
                            except (json.JSONDecodeError, Exception):
                                pass
                        _write_tool_name = ""
                        _write_partial_json = ""
                        _write_in_content = False
                        _write_streamed_len = 0

                elif event_type == "assistant":
                    message = event.get("message", {})
                    content_blocks = message.get("content", [])
                    for block in content_blocks:
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            if not text:
                                continue
                            if accumulated_text and not text.startswith(accumulated_text):
                                accumulated_text = ""
                            if len(text) > len(accumulated_text):
                                delta = text[len(accumulated_text):]
                                accumulated_text = text
                                yield {"type": "assistant_text", "content": delta}
                            else:
                                accumulated_text = text
                        elif block.get("type") == "tool_use":
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            file_path = (
                                tool_input.get("file_path", "")
                                or tool_input.get("path", "")
                                or tool_input.get("pattern", "")
                                or tool_input.get("command", "")
                            )
                            yield {
                                "type": "tool_activity",
                                "tool": tool_name,
                                "file": file_path,
                            }
                    accumulated_text = ""

                elif event_type == "result":
                    result_session_id = event.get("session_id", session_id)
                    cost_usd = event.get("total_cost_usd") or event.get("cost_usd", 0)
                    input_tokens = event.get("input_tokens", 0)
                    output_tokens = event.get("output_tokens", 0)
                    usage = event.get("usage", {})
                    if isinstance(usage, dict):
                        input_tokens = input_tokens or usage.get("input_tokens", 0)
                        output_tokens = output_tokens or usage.get("output_tokens", 0)
                    logger.info(
                        "CLI result: cost=$%.4f, turns=%s, duration=%sms, "
                        "input_tokens=%s, output_tokens=%s",
                        cost_usd, event.get("num_turns", "?"),
                        event.get("duration_ms", "?"),
                        input_tokens or "?", output_tokens or "?",
                    )
                    yield {
                        "type": "result",
                        "session_id": result_session_id or "",
                        "cost_usd": cost_usd,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    }

                elif event_type in ("rate_limit_event", "user"):
                    continue

                elif event_type == "error":
                    error_msg = event.get("error", {})
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(error_msg))
                    yield {"type": "error", "message": str(error_msg)}

        except asyncio.CancelledError:
            logger.info("Claude Code stream cancelled")
            raise
        except Exception as e:
            logger.error("Error reading Claude Code output: %s", e)
            yield {"type": "error", "message": f"Stream error: {e}"}
        finally:
            if session is not None:
                session._active_process = None

            if proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except (asyncio.TimeoutError, ProcessLookupError):
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass

            # Log stderr if process exited with error
            if proc.returncode and proc.returncode != 0:
                try:
                    stderr_data = await proc.stderr.read()
                    if stderr_data:
                        stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
                        logger.error("Claude Code CLI stderr (rc=%d): %s", proc.returncode, stderr_text[:2000])
                except Exception:
                    pass

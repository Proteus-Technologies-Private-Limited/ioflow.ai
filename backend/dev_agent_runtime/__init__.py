"""
Development Agent Runtime for IOFlow

This module provides a runtime environment for executing ADK agents
with dynamic configuration from the UI, including:
- Dynamic API key injection
- Model selection at runtime
- Execution cancellation support
- WebSocket streaming of responses
"""

# Apply LiteLLM patches before any other imports
from .patch_litellm import patch_litellm_imports
patch_litellm_imports()

from .runtime_manager import RuntimeManager
from .session_manager import SessionManager
from .runtime_executor import RuntimeExecutor

__all__ = ['RuntimeManager', 'SessionManager', 'RuntimeExecutor']
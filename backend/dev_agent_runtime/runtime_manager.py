"""
Runtime Manager for Dynamic Agent Execution

Manages the discovery, loading, and execution of ADK agents with
dynamic configuration support.
"""

import os
import sys
import json
import importlib.util
import logging
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import Google ADK components FIRST
try:
    from google.adk import Runner
    from google.adk.agents import LlmAgent
    from google.adk.sessions import InMemorySessionService
    from google import adk
    import google.genai as genai
    import google.generativeai as genai_config
    HAS_GOOGLE_ADK = True
except ImportError:
    HAS_GOOGLE_ADK = False
    Runner = None
    LlmAgent = None
    InMemorySessionService = None
    adk = None
    genai = None
    genai_config = None

# Apply LiteLLM patches AFTER Google ADK has imported litellm
# This allows us to patch the imported references
try:
    from . import patch_litellm
    patch_litellm.patch_litellm_imports()
except Exception as e:
    logging.warning(f"Could not apply LiteLLM patches: {e}")

# Apply JSON error handling patches (model-agnostic)
try:
    from . import json_error_handler
    json_error_handler.apply_json_error_handling_patches()
except Exception as e:
    logging.warning(f"Could not apply JSON error handling patches: {e}")

from .session_manager import SessionManager
from .runtime_executor import RuntimeExecutor

logger = logging.getLogger(__name__)


class RuntimeManager:
    """
    Manages runtime execution of ADK agents with dynamic configuration
    """

    def __init__(self):
        self.session_manager = SessionManager()
        self.executor = RuntimeExecutor(self.session_manager)
        self.loaded_agents = {}
        self.agent_registry = []

        # Initialize session service if ADK is available
        if HAS_GOOGLE_ADK:
            self.session_service = InMemorySessionService()
        else:
            self.session_service = None

        # Discover available agents on initialization
        self.discover_agents()

    def discover_agents(self) -> List[Dict[str, Any]]:
        """
        Discover all available agents from both Python and JSON sources
        """
        agents = []

        # Discover Python agents from backend/agent/
        agent_dir = Path(__file__).parent.parent / "agent"
        if agent_dir.exists():
            for subdir in agent_dir.iterdir():
                if subdir.is_dir():
                    agent_py = subdir / "agent.py"
                    if agent_py.exists():
                        agent_info = {
                            "id": subdir.name,
                            "name": subdir.name.replace("_", " ").title(),
                            "type": "python",
                            "path": str(agent_py),
                            "description": self._get_agent_description(agent_py)
                        }
                        agents.append(agent_info)
                        logger.info(f"Discovered Python agent: {subdir.name}")

        # Discover JSON agents from backend/flow_agent_configs/
        json_config_dir = Path(__file__).parent.parent / "flow_agent_configs"
        if json_config_dir.exists():
            for json_file in json_config_dir.glob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                        agent_info = {
                            "id": json_file.stem,
                            "name": data.get("description", json_file.stem.replace("_", " ").title()),
                            "type": "json",
                            "path": str(json_file),
                            "description": data.get("description", ""),
                            "model": data.get("model", "gemini-2.0-flash-exp")
                        }
                        agents.append(agent_info)
                        logger.info(f"Discovered JSON agent: {json_file.stem}")
                except Exception as e:
                    logger.warning(f"Failed to read agent config {json_file}: {e}")

        self.agent_registry = agents
        return agents

    def _get_agent_description(self, agent_path: Path) -> str:
        """
        Extract description from Python agent file docstring
        """
        try:
            with open(agent_path, 'r') as f:
                content = f.read()
                # Look for module docstring
                if content.strip().startswith('"""'):
                    end_idx = content.find('"""', 3)
                    if end_idx != -1:
                        docstring = content[3:end_idx].strip()
                        # Get first paragraph as description
                        lines = docstring.split('\n')
                        description_lines = []
                        for line in lines:
                            if line.strip() == "":
                                break
                            description_lines.append(line.strip())
                        return " ".join(description_lines)
        except Exception:
            pass
        return ""

    async def load_agent(self, agent_id: str, api_key: str, model: str, provider: str = None, api_base: str = None) -> Optional[Any]:
        """
        Load an agent with dynamic configuration
        """
        if not HAS_GOOGLE_ADK:
            raise RuntimeError("Google ADK is not installed")

        # Find agent in registry
        agent_info = None
        for agent in self.agent_registry:
            if agent["id"] == agent_id:
                agent_info = agent
                break

        if not agent_info:
            raise ValueError(f"Agent {agent_id} not found")

        # Default to google provider if not specified
        if not provider:
            provider = "google"
            # If no provider specified, check environment for defaults
            if not api_key:
                api_key = os.getenv('GOOGLE_API_KEY', '')
            if not model or model == "gemini-2.0-flash-exp":
                model = os.getenv('AGENT_MODEL', 'gemini-2.0-flash-exp')

        # Validate provider
        if provider not in ["google", "openai", "anthropic", "deepseek", "ollama", "lm_studio"]:
            raise ValueError(f"Unsupported provider: {provider}")

        # Log configuration (without exposing full API key)
        logger.info(f"Loading agent {agent_id} with provider={provider}, model={model}, api_key={'present' if api_key else 'missing'}")
        if api_base:
            logger.info(f"Using custom API base: {api_base}")

        # Load based on type
        if agent_info["type"] == "python":
            return await self._load_python_agent(agent_info, model, provider, api_key, api_base)
        elif agent_info["type"] == "json":
            return await self._load_json_agent(agent_info, model, provider, api_key, api_base)
        else:
            raise ValueError(f"Unknown agent type: {agent_info['type']}")

    async def _load_python_agent(self, agent_info: Dict[str, Any], model: str, provider: str, api_key: str, api_base: str = None) -> Any:
        """
        Load a Python-based ADK agent
        """
        agent_path = Path(agent_info["path"])

        # Create a unique module name to avoid conflicts
        module_name = f"agent_{agent_info['id']}_{uuid.uuid4().hex[:8]}"

        # Load the agent module in isolation
        spec = importlib.util.spec_from_file_location(module_name, agent_path)
        module = importlib.util.module_from_spec(spec)

        # Store the original sys.modules to restore later
        original_modules = dict(sys.modules)

        # Format model string for ADK 1.22+ registry validation
        # Non-Google providers require "provider/model" format for LiteLLM
        formatted_model = model
        if provider != "google":
            if provider == "openai" and not model.startswith("openai/"):
                formatted_model = f"openai/{model}"
            elif provider == "anthropic" and not model.startswith("anthropic/"):
                formatted_model = f"anthropic/{model}"
            elif provider == "deepseek" and not model.startswith("deepseek/"):
                formatted_model = f"deepseek/{model}"
            elif provider == "ollama" and not model.startswith("ollama"):
                formatted_model = f"ollama_chat/{model}"
            elif provider == "lm_studio" and not model.startswith("openai/"):
                formatted_model = f"openai/{model}"
            logger.info(f"Formatted model for LiteLLM registry: {model} -> {formatted_model}")

        # Set environment variable for model before loading
        # Use formatted model so agent creation uses correct format
        os.environ['AGENT_MODEL'] = formatted_model
        os.environ['IOFLOW_ANALYST_MODEL'] = formatted_model  # For specific agents
        os.environ['FLOW_DESIGNER_MODEL'] = formatted_model

        # The agent module builds its MCP toolset at import time with the CALLER's
        # IOFlow token, which it reads from the request ContextVar
        # (agent_pack.runtime.set_request_token). The LLM provider key below is
        # never an IOFlow credential and is not put in IOFLOW_API_KEY.

        # Set provider-specific API keys before loading for LiteLLM to pick up
        if provider != "google" and api_key:
            if provider == "openai":
                os.environ['OPENAI_API_KEY'] = api_key
                logger.info("Set OPENAI_API_KEY in environment for LiteLLM")
            elif provider == "anthropic":
                os.environ['ANTHROPIC_API_KEY'] = api_key
                logger.info("Set ANTHROPIC_API_KEY in environment for LiteLLM")
            elif provider == "deepseek":
                os.environ['DEEPSEEK_API_KEY'] = api_key
                logger.info("Set DEEPSEEK_API_KEY in environment for LiteLLM")
            elif provider in ["lm_studio"]:
                os.environ['OPENAI_API_KEY'] = api_key or "dummy-key-for-local"
                if api_base:
                    os.environ['OPENAI_API_BASE'] = api_base
                    logger.info(f"Set OPENAI_API_BASE={api_base} for LM Studio")

        try:
            # Add module to sys.modules temporarily for imports
            sys.modules[module_name] = module

            # Execute the module
            spec.loader.exec_module(module)

            # Get the root_agent
            if hasattr(module, 'root_agent'):
                agent = module.root_agent

                # Override the agent's model with the appropriate provider
                if provider == "google":
                    # For Google provider, create a custom Gemini instance with the API key
                    try:
                        from google.adk.models.google_llm import Gemini
                        from google.genai import Client
                        from google.genai import types

                        # Create a custom Gemini class that uses the provided API key
                        class CustomGemini(Gemini):
                            def __init__(self, model_name: str, api_key: str):
                                super().__init__()
                                self.model = model_name
                                self._api_key = api_key
                                self._client = None
                                self._live_client = None

                            @property
                            def api_client(self) -> Client:
                                """Override to use custom API key"""
                                if self._client is None:
                                    # Get headers from parent class
                                    headers = {}
                                    try:
                                        headers = super()._tracking_headers
                                    except:
                                        pass

                                    self._client = Client(
                                        api_key=self._api_key,
                                        http_options=types.HttpOptions(
                                            headers=headers,
                                            retry_options=self.retry_options if hasattr(self, 'retry_options') else None,
                                        )
                                    )
                                return self._client

                            @property
                            def _live_api_client(self) -> Client:
                                """Override for live API client as well"""
                                if self._live_client is None:
                                    headers = {}
                                    api_version = 'v1alpha'
                                    try:
                                        headers = super()._tracking_headers
                                        api_version = super()._live_api_version
                                    except:
                                        pass

                                    self._live_client = Client(
                                        api_key=self._api_key,
                                        http_options=types.HttpOptions(
                                            headers=headers,
                                            api_version=api_version
                                        )
                                    )
                                return self._live_client

                        # Create custom Gemini instance with the API key
                        custom_gemini = CustomGemini(model_name=model, api_key=api_key)

                        # Try to set model - handle Pydantic model immutability
                        try:
                            agent.model = custom_gemini
                            # Verify assignment worked
                            if agent.model != custom_gemini:
                                raise AttributeError("Model assignment did not persist")
                        except (AttributeError, TypeError) as assign_err:
                            logger.info(f"Direct model assignment failed ({assign_err}), using model_copy")
                            # Use Pydantic's model_copy for immutable models
                            if hasattr(agent, 'model_copy'):
                                agent = agent.model_copy(update={'model': custom_gemini})
                            else:
                                # Fallback for older Pydantic
                                agent = agent.copy(update={'model': custom_gemini})

                        logger.info(f"Overrode agent model with custom Gemini using dynamic API key for model: {model}")
                        logger.info(f"API key first 10 chars: {api_key[:10] if api_key else 'EMPTY'}...")
                        # Test the configuration
                        try:
                            test_client = custom_gemini.api_client
                            logger.info(f"Successfully created test client with custom API key")
                        except Exception as e:
                            logger.error(f"Failed to create test client: {e}")

                    except Exception as e:
                        logger.error(f"Failed to create custom Gemini model: {e}")
                        # Fall back to setting environment variable as last resort
                        os.environ['GOOGLE_API_KEY'] = api_key
                        logger.info("Falling back to environment variable for API key")

                elif provider != "google":
                    # For non-Google providers, create custom LiteLLM wrapper with API key
                    # Latest LiteLLM (1.77+) handles o1 models automatically
                    try:
                        from google.adk.models.lite_llm import LiteLlm
                        import litellm
                        from .litellm_wrapper import CustomLiteLLMWrapper, DeepSeekLiteLLMWrapper, OllamaLiteLLMWrapper, LMStudioLiteLLMWrapper

                        # Check if this is an o1 model (for logging purposes)
                        wrapper_check = CustomLiteLLMWrapper(model, provider)
                        if wrapper_check.is_o1_model:
                            logger.info(f"Detected o1/reasoning model: {model}")
                            logger.info("LiteLLM 1.77+ will automatically route to v1/responses endpoint")

                        # Create a custom LiteLLM class that uses the provided API key
                        class CustomLiteLLM(LiteLlm):
                            def __init__(self, model_name: str, api_key: str, provider: str, api_base: str = None):
                                # Format model string for LiteLLM
                                if provider == "openai":
                                    formatted_model = f"openai/{model_name}" if not model_name.startswith("openai/") else model_name
                                    api_key_env_var = "OPENAI_API_KEY"
                                elif provider == "anthropic":
                                    formatted_model = f"anthropic/{model_name}" if not model_name.startswith("anthropic/") else model_name
                                    api_key_env_var = "ANTHROPIC_API_KEY"
                                elif provider == "deepseek":
                                    formatted_model = f"deepseek/{model_name}" if not model_name.startswith("deepseek/") else model_name
                                    api_key_env_var = "DEEPSEEK_API_KEY"
                                elif provider == "ollama":
                                    formatted_model = f"ollama_chat/{model_name}" if not model_name.startswith("ollama") else model_name
                                    api_key_env_var = None  # Ollama doesn't need API key
                                    object.__setattr__(self, 'api_base', api_base or "http://localhost:11434")
                                elif provider == "lm_studio":
                                    # For LM Studio, always use openai/ prefix for LiteLLM
                                    # This tells LiteLLM to use OpenAI-compatible API
                                    formatted_model = f"openai/{model_name}" if not model_name.startswith("openai/") else model_name
                                    api_key_env_var = "OPENAI_API_KEY"  # LM Studio uses OpenAI-compatible API
                                    api_base_value = api_base or "http://localhost:1234/v1"
                                    object.__setattr__(self, 'api_base', api_base_value)
                                    # Set environment variable immediately in init
                                    logger.info(f"[Init] Setting OPENAI_API_BASE={api_base_value}")
                                    os.environ['OPENAI_API_BASE'] = api_base_value
                                else:
                                    formatted_model = model_name
                                    api_key_env_var = None

                                # Initialize the parent class first
                                super().__init__(model=formatted_model)

                                # Use object.__setattr__ to bypass Pydantic's validation for these custom attributes
                                object.__setattr__(self, 'api_key_env_var', api_key_env_var)
                                object.__setattr__(self, '_api_key', api_key)
                                object.__setattr__(self, '_provider', provider)

                            async def generate_content_async(self, *args, **kwargs):
                                # Temporarily set the API key for this request
                                api_key_env_var = object.__getattribute__(self, 'api_key_env_var')
                                _api_key = object.__getattribute__(self, '_api_key')
                                _provider = object.__getattribute__(self, '_provider')

                                old_env_value = os.environ.get(api_key_env_var) if api_key_env_var else None
                                old_api_base = os.environ.get('OPENAI_API_BASE', None)

                                try:
                                    if api_key_env_var and _api_key:
                                        os.environ[api_key_env_var] = _api_key

                                    # Set API base for local models
                                    if _provider in ['ollama', 'lm_studio'] and hasattr(self, 'api_base'):
                                        api_base_value = object.__getattribute__(self, 'api_base')
                                        if api_base_value:
                                            logger.info(f"[CustomLiteLLM] Setting OPENAI_API_BASE for {_provider}: {api_base_value}")
                                            os.environ['OPENAI_API_BASE'] = api_base_value
                                            # Also pass api_base directly to kwargs for LiteLLM
                                            kwargs['api_base'] = api_base_value
                                            kwargs['base_url'] = api_base_value  # Try both parameter names
                                            logger.info(f"[CustomLiteLLM] Added api_base and base_url to kwargs: {api_base_value}")

                                    # Call parent's generate_content_async and yield from it
                                    # The parent method returns an async generator, not a coroutine
                                    # LiteLLM 1.77+ handles o1 models automatically
                                    async for response in super().generate_content_async(*args, **kwargs):
                                        yield response
                                finally:
                                    # Restore the original environment variables
                                    if api_key_env_var:
                                        if old_env_value is not None:
                                            os.environ[api_key_env_var] = old_env_value
                                        elif api_key_env_var in os.environ:
                                            del os.environ[api_key_env_var]

                                    # Restore API base
                                    if old_api_base is not None:
                                        os.environ['OPENAI_API_BASE'] = old_api_base
                                    elif 'OPENAI_API_BASE' in os.environ:
                                        del os.environ['OPENAI_API_BASE']

                        # Create custom LiteLLM instance with the API key and api_base
                        logger.info(f"Creating CustomLiteLLM for {provider}: model={model}, api_base={api_base}")
                        custom_litellm = CustomLiteLLM(model_name=model, api_key=api_key, provider=provider, api_base=api_base)

                        # Try to set model - handle Pydantic model immutability
                        try:
                            agent.model = custom_litellm
                            # Verify assignment worked
                            if agent.model != custom_litellm:
                                raise AttributeError("Model assignment did not persist")
                        except (AttributeError, TypeError) as assign_err:
                            logger.info(f"Direct model assignment failed ({assign_err}), using model_copy")
                            # Use Pydantic's model_copy for immutable models
                            if hasattr(agent, 'model_copy'):
                                agent = agent.model_copy(update={'model': custom_litellm})
                            else:
                                # Fallback for older Pydantic
                                agent = agent.copy(update={'model': custom_litellm})

                        logger.info(f"Overrode agent model with custom LiteLLM for {provider}: {model}")
                        logger.info(f"API key first 10 chars: {api_key[:10] if api_key else 'EMPTY'}...")
                        if api_base:
                            logger.info(f"API base URL configured: {api_base}")

                    except ImportError as e:
                        logger.warning(f"LiteLLM not available, falling back to environment variables: {e}")
                        # Fall back to setting environment variables
                        if provider == "openai":
                            os.environ['OPENAI_API_KEY'] = api_key
                        elif provider == "anthropic":
                            os.environ['ANTHROPIC_API_KEY'] = api_key
                        elif provider == "deepseek":
                            os.environ['DEEPSEEK_API_KEY'] = api_key
                        elif provider in ["ollama", "lm_studio"]:
                            # Local models may not need real API keys
                            if api_key:
                                os.environ['OPENAI_API_KEY'] = api_key
                            else:
                                os.environ['OPENAI_API_KEY'] = "dummy-key-for-local"

                logger.info(f"Loaded Python agent {agent_info['id']} with provider {provider}")
                return agent
            else:
                raise ValueError(f"Agent {agent_info['id']} does not export root_agent")
        finally:
            # Clean up: Remove any modules that were imported during loading
            # This prevents module conflicts between different agent loads
            modules_to_remove = []
            for key in sys.modules:
                if key not in original_modules and (key.startswith("agent_") or key.startswith("flow_")):
                    modules_to_remove.append(key)

            for key in modules_to_remove:
                del sys.modules[key]

    async def _load_json_agent(self, agent_info: Dict[str, Any], model: str, provider: str, api_key: str, api_base: str = None) -> Any:
        """
        Load a JSON-configured agent
        """
        with open(agent_info["path"], 'r') as f:
            config = json.load(f)

        # Extract configuration
        name = config.get("agent_id", agent_info["id"])
        description = config.get("description", "")
        system_prompt = config.get("system_prompt", "")
        instruction = config.get("instruction", "")
        tools_config = config.get("tools", [])

        # Use instruction as-is without adding base instructions
        # The agent's own instructions should handle the workflow
        full_instruction = ""
        if system_prompt:
            full_instruction = system_prompt
        if instruction:
            if full_instruction:
                full_instruction += f"\n\n{instruction}"
            else:
                full_instruction = instruction

        # Load tools from flow_agent_tools
        tools = []
        if tools_config:
            tools = await self._load_tools_for_agent(name, tools_config)

        # Create the ADK Agent with appropriate model
        if provider == "google":
            # For Google provider, create a custom Gemini instance with the API key
            try:
                from google.adk.models.google_llm import Gemini
                from google.genai import Client
                from google.genai import types

                # Create a custom Gemini class that uses the provided API key
                class CustomGemini(Gemini):
                    def __init__(self, model_name: str, api_key: str):
                        super().__init__()
                        self.model = model_name
                        self._api_key = api_key
                        self._client = None
                        self._live_client = None

                    @property
                    def api_client(self) -> Client:
                        """Override to use custom API key"""
                        if self._client is None:
                            # Get headers from parent class
                            headers = {}
                            try:
                                headers = super()._tracking_headers
                            except:
                                pass

                            self._client = Client(
                                api_key=self._api_key,
                                http_options=types.HttpOptions(
                                    headers=headers,
                                    retry_options=self.retry_options if hasattr(self, 'retry_options') else None,
                                )
                            )
                        return self._client

                    @property
                    def _live_api_client(self) -> Client:
                        """Override for live API client as well"""
                        if self._live_client is None:
                            headers = {}
                            api_version = 'v1alpha'
                            try:
                                headers = super()._tracking_headers
                                api_version = super()._live_api_version
                            except:
                                pass

                            self._live_client = Client(
                                api_key=self._api_key,
                                http_options=types.HttpOptions(
                                    headers=headers,
                                    api_version=api_version
                                )
                            )
                        return self._live_client

                agent_model = CustomGemini(model_name=model, api_key=api_key)
                logger.info(f"Using custom Gemini model with dynamic API key: {model}")
            except Exception as e:
                logger.error(f"Failed to create custom Gemini model: {e}")
                # Fall back to default model
                agent_model = model
                os.environ['GOOGLE_API_KEY'] = api_key
        else:
            # For non-Google providers, create custom LiteLLM wrapper with API key
            try:
                from google.adk.models.lite_llm import LiteLlm
                import litellm
                from .litellm_wrapper import DeepSeekLiteLLMWrapper, OllamaLiteLLMWrapper, LMStudioLiteLLMWrapper

                # Create a custom LiteLLM class that uses the provided API key
                class CustomLiteLLM(LiteLlm):
                    def __init__(self, model_name: str, api_key: str, provider: str, api_base: str = None):
                        # Format model string for LiteLLM
                        if provider == "openai":
                            formatted_model = f"openai/{model_name}" if not model_name.startswith("openai/") else model_name
                            api_key_env_var = "OPENAI_API_KEY"
                        elif provider == "anthropic":
                            formatted_model = f"anthropic/{model_name}" if not model_name.startswith("anthropic/") else model_name
                            api_key_env_var = "ANTHROPIC_API_KEY"
                        elif provider == "deepseek":
                            formatted_model = f"deepseek/{model_name}" if not model_name.startswith("deepseek/") else model_name
                            api_key_env_var = "DEEPSEEK_API_KEY"
                        elif provider == "ollama":
                            formatted_model = f"ollama_chat/{model_name}" if not model_name.startswith("ollama") else model_name
                            api_key_env_var = None
                            object.__setattr__(self, 'api_base', api_base or "http://localhost:11434")
                        elif provider == "lm_studio":
                            # For LM Studio, always use openai/ prefix for LiteLLM
                            # This tells LiteLLM to use OpenAI-compatible API
                            formatted_model = f"openai/{model_name}" if not model_name.startswith("openai/") else model_name
                            api_key_env_var = "OPENAI_API_KEY"
                            api_base_value = api_base or "http://localhost:1234/v1"
                            object.__setattr__(self, 'api_base', api_base_value)
                            # Set environment variable immediately in init
                            logger.info(f"[Init JSON] Setting OPENAI_API_BASE={api_base_value}")
                            os.environ['OPENAI_API_BASE'] = api_base_value
                        else:
                            formatted_model = model_name
                            api_key_env_var = None

                        super().__init__(model=formatted_model)

                        # Use object.__setattr__ to bypass Pydantic's validation for these custom attributes
                        object.__setattr__(self, 'api_key_env_var', api_key_env_var)
                        object.__setattr__(self, '_api_key', api_key)
                        object.__setattr__(self, '_provider', provider)

                    async def generate_content_async(self, *args, **kwargs):
                        # Temporarily set the API key and base for this request
                        api_key_env_var = object.__getattribute__(self, 'api_key_env_var')
                        _api_key = object.__getattribute__(self, '_api_key')
                        _provider = object.__getattribute__(self, '_provider')

                        old_env_value = os.environ.get(api_key_env_var) if api_key_env_var else None
                        old_api_base = os.environ.get('OPENAI_API_BASE', None)
                        try:
                            if api_key_env_var and _api_key:
                                os.environ[api_key_env_var] = _api_key
                            # Set API base for local models
                            if _provider in ['ollama', 'lm_studio'] and hasattr(self, 'api_base'):
                                api_base_value = object.__getattribute__(self, 'api_base')
                                logger.info(f"[CustomLiteLLM JSON] Setting OPENAI_API_BASE for {_provider}: {api_base_value}")
                                os.environ['OPENAI_API_BASE'] = api_base_value
                                # Also pass api_base directly to kwargs for LiteLLM
                                kwargs['api_base'] = api_base_value
                                kwargs['base_url'] = api_base_value  # Try both parameter names
                                logger.info(f"[CustomLiteLLM JSON] Added api_base and base_url to kwargs: {api_base_value}")
                            # Call the parent's generate_content_async and yield from it
                            # The parent method returns an async generator, not a coroutine
                            async for response in super().generate_content_async(*args, **kwargs):
                                yield response
                        finally:
                            # Restore the original environment variables
                            if api_key_env_var:
                                if old_env_value is not None:
                                    os.environ[api_key_env_var] = old_env_value
                                elif api_key_env_var in os.environ:
                                    del os.environ[api_key_env_var]
                            # Restore API base
                            if old_api_base is not None:
                                os.environ['OPENAI_API_BASE'] = old_api_base
                            elif 'OPENAI_API_BASE' in os.environ:
                                del os.environ['OPENAI_API_BASE']

                # Create custom LiteLLM instance with the API key and api_base
                agent_model = CustomLiteLLM(model_name=model, api_key=api_key, provider=provider, api_base=api_base)
                logger.info(f"Using custom LiteLLM model for {provider}: {model}")
            except ImportError as e:
                logger.warning(f"LiteLLM not available, using default model and setting env: {e}")
                agent_model = model
                # Fall back to setting environment variables
                if provider == "openai":
                    os.environ['OPENAI_API_KEY'] = api_key
                elif provider == "anthropic":
                    os.environ['ANTHROPIC_API_KEY'] = api_key
                elif provider == "deepseek":
                    os.environ['DEEPSEEK_API_KEY'] = api_key
                elif provider in ["ollama", "lm_studio"]:
                    # Local models may not need real API keys
                    if api_key:
                        os.environ['OPENAI_API_KEY'] = api_key
                    else:
                        os.environ['OPENAI_API_KEY'] = "dummy-key-for-local"

        agent = LlmAgent(
            name=name,
            model=agent_model,  # Use the configured model
            description=description,
            instruction=full_instruction,
            tools=tools,  # Now includes actual tools
            generate_content_config={
                "temperature": 0.7,
                "max_output_tokens": 2048
            }
        )

        logger.info(f"Loaded JSON agent {agent_info['id']} with provider {provider}, model {model} and {len(tools)} tools")
        return agent

    async def _load_tools_for_agent(self, agent_name: str, tools_config: List[Dict[str, Any]]) -> List[Any]:
        """
        Load tools for a JSON-configured agent
        """
        from google.adk.tools.function_tool import FunctionTool

        tools = []

        # Import the appropriate tool modules based on agent
        tool_modules = {}

        # Determine which modules to import based on tool names
        for tool_cfg in tools_config:
            tool_name = tool_cfg.get("function", tool_cfg.get("name"))

            # Map tools to their modules
            if tool_name in ["get_weather", "get_current_time"]:
                if "weather_tools" not in tool_modules:
                    from flow_agent_tools import weather_tools
                    tool_modules["weather_tools"] = weather_tools
            elif tool_name in ["calculate", "convert_units"]:
                if "math_tools" not in tool_modules:
                    from flow_agent_tools import math_tools
                    tool_modules["math_tools"] = math_tools
            elif tool_name in ["count_words", "reverse_text", "to_uppercase", "to_lowercase"]:
                if "text_tools" not in tool_modules:
                    from flow_agent_tools import text_tools
                    tool_modules["text_tools"] = text_tools

        # Create ADK tools
        for tool_cfg in tools_config:
            tool_name = tool_cfg.get("function", tool_cfg.get("name"))
            description = tool_cfg.get("description", "")

            # Find the actual function
            func = None
            for module in tool_modules.values():
                if hasattr(module, tool_name):
                    func = getattr(module, tool_name)
                    break

            if func:
                # Create an ADK FunctionTool
                tool = FunctionTool(func)
                tools.append(tool)
                logger.info(f"Loaded tool: {tool_name} for agent {agent_name}")
            else:
                logger.warning(f"Tool function '{tool_name}' not found for agent {agent_name}")

        return tools

    async def execute_agent(
        self,
        agent_id: str,
        input_text: str,
        api_key: str,
        model: str,
        provider: Optional[str] = None,
        api_base: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        force_new_session: bool = False
    ) -> Dict[str, Any]:
        """
        Execute an agent with the given input and configuration.
        Supports conversation persistence when user_id is provided.
        """
        try:
            # Load the agent with configuration
            agent = await self.load_agent(agent_id, api_key, model, provider, api_base)

            # Get or create session based on user_id if provided
            if user_id:
                # Use persistent session for user-agent combination
                session = self.session_manager.get_or_create_user_agent_session(
                    user_id=user_id,
                    agent_id=agent_id,
                    model=model,
                    force_new=force_new_session
                )
                session_id = session.session_id
            else:
                # Fallback to old behavior if no user_id
                if not session_id:
                    session_id = str(uuid.uuid4())

                # Check if session already exists (for WebSocket reconnection)
                session = self.session_manager.get_session(session_id)
                if not session:
                    session = self.session_manager.create_session(
                        session_id=session_id,
                        agent_id=agent_id,
                        model=model
                    )

            # Execute through the executor with conversation history
            result = await self.executor.execute(
                agent=agent,
                input_text=input_text,
                session=session,
                preserve_history=bool(user_id)  # Pass flag to preserve conversation context
            )

            return {
                "success": True,
                "session_id": session_id,
                "result": result,
                "conversation_continued": bool(user_id and len(session.messages) > 1)
            }

        except Exception as e:
            logger.error(f"Failed to execute agent {agent_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def cancel_execution(self, session_id: str) -> Dict[str, Any]:
        """
        Cancel an active agent execution
        """
        if self.executor.cancel_execution(session_id):
            return {"success": True, "message": "Execution cancelled"}
        else:
            return {"success": False, "message": "Session not found or already completed"}

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a session
        """
        session = self.session_manager.get_session(session_id)
        if session:
            return {
                "session_id": session.session_id,
                "status": session.status,
                "agent_id": session.agent_id,
                "model": session.model,
                "started_at": session.created_at.isoformat(),
                "messages": len(session.messages)
            }
        return None

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions
        """
        sessions = self.session_manager.get_active_sessions()
        return [
            {
                "session_id": s.session_id,
                "agent_id": s.agent_id,
                "status": s.status,
                "started_at": s.created_at.isoformat()
            }
            for s in sessions
        ]

    def clear_conversation(self, user_id: str, agent_id: str) -> bool:
        """
        Clear conversation history for a specific user-agent combination
        """
        return self.session_manager.clear_user_agent_session(user_id, agent_id)
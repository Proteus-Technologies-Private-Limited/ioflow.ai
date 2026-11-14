"""
Custom LiteLLM wrapper for multi-provider support
Works around Google ADK's LiteLLM compatibility issues
Updated to support latest LiteLLM v1.77+ with native o1 model support
"""

import os
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

class CustomLiteLLMWrapper:
    """
    Custom wrapper to handle LiteLLM integration for OpenAI, Anthropic, DeepSeek, Ollama, and LM Studio models
    This works around the Google ADK LiteLLM compatibility issues
    """

    def __init__(self, model: str, provider: str, api_base: Optional[str] = None):
        self.model = model
        self.provider = provider
        self.api_base = api_base
        self.litellm_model = self._get_litellm_model_string(provider, model)
        # Check if this is an o1 model (for logging purposes)
        self.is_o1_model = self._is_o1_model(model)

    def _get_litellm_model_string(self, provider: str, model: str) -> str:
        """Format model string for LiteLLM"""
        if provider == "openai":
            return f"openai/{model}" if not model.startswith("openai/") else model
        elif provider == "anthropic":
            return f"anthropic/{model}" if not model.startswith("anthropic/") else model
        elif provider == "deepseek":
            return f"deepseek/{model}" if not model.startswith("deepseek/") else model
        elif provider == "ollama":
            # Use ollama_chat for better compatibility
            return f"ollama_chat/{model}" if not model.startswith("ollama") else model
        elif provider == "lm_studio":
            return f"openai/{model}" if not model.startswith("openai/") else model
        else:
            return model

    def _is_o1_model(self, model: str) -> bool:
        """Check if model is an o1/reasoning model
        Note: With LiteLLM 1.77+, these models are automatically routed correctly"""
        # OpenAI o1 models and reasoning models
        o1_models = ['o1', 'o1-preview', 'o1-mini', 'o3', 'o3-mini']
        # DeepSeek reasoning models
        deepseek_reasoning = ['r1', 'reasoner']
        return any(o1_model in model.lower() for o1_model in o1_models) or \
               any(reasoning in model.lower() for reasoning in deepseek_reasoning)

    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration for agent"""
        config = {
            "model": self.litellm_model,
            "provider": self.provider,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        # Add note if it's an o1 model
        if self.is_o1_model:
            if self.provider == "deepseek":
                config["note"] = "DeepSeek reasoning model - LiteLLM will handle reasoning content"
            else:
                config["note"] = "O1 model - LiteLLM will automatically use v1/responses endpoint"

        return config

    @staticmethod
    def is_supported_provider(provider: str) -> bool:
        """Check if provider is supported for LiteLLM integration"""
        return provider in ["openai", "anthropic", "deepseek", "ollama", "lm_studio"]

    @staticmethod
    def setup_api_keys(provider: str, api_key: str):
        """Setup API keys for the provider"""
        if provider == "openai":
            os.environ['OPENAI_API_KEY'] = api_key
        elif provider == "anthropic":
            os.environ['ANTHROPIC_API_KEY'] = api_key
        elif provider == "deepseek":
            os.environ['DEEPSEEK_API_KEY'] = api_key
        elif provider in ["ollama", "lm_studio"]:
            # Local models don't need real API keys, but LiteLLM may require a dummy one
            os.environ['OPENAI_API_KEY'] = api_key if api_key else "dummy-key-for-local"
        else:
            os.environ['GOOGLE_API_KEY'] = api_key


class DeepSeekLiteLLMWrapper(CustomLiteLLMWrapper):
    """
    DeepSeek-specific wrapper with support for latest models
    """

    # Latest DeepSeek models available as of 2025
    DEEPSEEK_MODELS = {
        # Chat models
        "deepseek-chat": {"context": 32768, "description": "Standard chat model"},
        "deepseek-reasoner": {"context": 128000, "description": "V3.1 with enhanced reasoning"},

        # Reasoning models (R1 series)
        "deepseek-r1": {"context": 128000, "description": "671B reasoning model"},
        "deepseek-r1-0528": {"context": 128000, "description": "Enhanced reasoning model"},

        # Distilled models (more efficient)
        "deepseek-r1-distill-llama-70b": {"context": 32768, "description": "70B distilled model"},
        "deepseek-r1-distill-qwen-32b": {"context": 32768, "description": "32B distilled model"},
        "deepseek-r1-distill-qwen-14b": {"context": 32768, "description": "14B distilled model"},
        "deepseek-r1-distill-qwen-7b": {"context": 32768, "description": "7B distilled model"},
        "deepseek-r1-distill-qwen-1.5b": {"context": 32768, "description": "1.5B distilled model"},

        # Specialized models
        "deepseek-coder": {"context": 16384, "description": "Code generation model"},
    }

    def __init__(self, model: str):
        # Clean model name if it includes deepseek/ prefix
        clean_model = model.replace("deepseek/", "") if model.startswith("deepseek/") else model
        super().__init__(clean_model, "deepseek")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the DeepSeek model"""
        clean_model = self.model.replace("deepseek/", "") if self.model.startswith("deepseek/") else self.model
        if clean_model in self.DEEPSEEK_MODELS:
            return self.DEEPSEEK_MODELS[clean_model]
        return {"context": 32768, "description": "Unknown DeepSeek model"}

    @classmethod
    def get_recommended_model(cls, use_case: str) -> str:
        """Get recommended DeepSeek model for specific use case"""
        recommendations = {
            "chat": "deepseek-chat",
            "reasoning": "deepseek-r1",
            "code": "deepseek-coder",
            "efficient": "deepseek-r1-distill-qwen-32b",
            "budget": "deepseek-r1-distill-qwen-7b"
        }
        return recommendations.get(use_case, "deepseek-chat")


class OllamaLiteLLMWrapper(CustomLiteLLMWrapper):
    """
    Ollama-specific wrapper for local model support
    """

    # Common Ollama models
    OLLAMA_MODELS = {
        # Llama models
        "llama3.2": {"size": "3B/1B", "description": "Latest Llama 3.2 models"},
        "llama3.1": {"size": "8B/70B/405B", "description": "Llama 3.1 family"},
        "llama3": {"size": "8B/70B", "description": "Llama 3 models"},
        "llama2": {"size": "7B/13B/70B", "description": "Llama 2 models"},

        # Mistral models
        "mistral": {"size": "7B", "description": "Mistral 7B"},
        "mixtral": {"size": "8x7B/8x22B", "description": "Mixtral MoE models"},

        # Google models
        "gemma2": {"size": "2B/9B/27B", "description": "Google Gemma 2"},
        "gemma": {"size": "2B/7B", "description": "Google Gemma"},

        # Other popular models
        "phi3": {"size": "3.8B/14B", "description": "Microsoft Phi-3"},
        "qwen2.5": {"size": "0.5B-72B", "description": "Alibaba Qwen 2.5"},
        "deepseek-coder-v2": {"size": "16B/236B", "description": "DeepSeek Coder V2"},
        "codellama": {"size": "7B/13B/34B/70B", "description": "Code Llama"},
        "starcoder2": {"size": "3B/7B/15B", "description": "StarCoder 2"},
        "nomic-embed-text": {"size": "137M", "description": "Embedding model"},
    }

    DEFAULT_OLLAMA_URL = "http://localhost:11434"

    def __init__(self, model: str, api_base: Optional[str] = None):
        # Clean model name
        clean_model = model.replace("ollama/", "").replace("ollama_chat/", "") if "ollama" in model else model
        super().__init__(clean_model, "ollama", api_base or self.DEFAULT_OLLAMA_URL)

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Ollama model"""
        base_model = self.model.split(":")[0]  # Handle tags like llama3:latest
        if base_model in self.OLLAMA_MODELS:
            return self.OLLAMA_MODELS[base_model]
        return {"size": "Unknown", "description": "Custom Ollama model"}

    @classmethod
    def list_available_models(cls, api_base: Optional[str] = None) -> List[str]:
        """List models available in the Ollama instance"""
        try:
            import requests
            base_url = api_base or cls.DEFAULT_OLLAMA_URL
            response = requests.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m["name"] for m in models]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
        return []


class LMStudioLiteLLMWrapper(CustomLiteLLMWrapper):
    """
    LM Studio-specific wrapper for local model support
    """

    DEFAULT_LM_STUDIO_URL = "http://localhost:1234/v1"

    def __init__(self, model: str, api_base: Optional[str] = None):
        # LM Studio uses OpenAI-compatible API
        clean_model = model.replace("lm_studio/", "") if model.startswith("lm_studio/") else model
        super().__init__(clean_model, "lm_studio", api_base or self.DEFAULT_LM_STUDIO_URL)

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the LM Studio model"""
        return {
            "description": "Local model via LM Studio",
            "api_compatible": "OpenAI",
            "endpoint": self.api_base
        }

    @classmethod
    def list_available_models(cls, api_base: Optional[str] = None) -> List[str]:
        """List models available in the LM Studio instance"""
        try:
            import requests
            base_url = api_base or cls.DEFAULT_LM_STUDIO_URL
            response = requests.get(f"{base_url}/models")
            if response.status_code == 200:
                models = response.json().get("data", [])
                return [m["id"] for m in models]
        except Exception as e:
            logger.warning(f"Could not list LM Studio models: {e}")
        return []

    @classmethod
    def get_server_info(cls, api_base: Optional[str] = None) -> Dict[str, Any]:
        """Get LM Studio server information"""
        try:
            import requests
            base_url = api_base or cls.DEFAULT_LM_STUDIO_URL
            response = requests.get(f"{base_url.rstrip('/v1')}/server/info")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Could not get LM Studio server info: {e}")
        return {}


def create_litellm_model(provider: str, model: str, api_key: str, api_base: Optional[str] = None) -> Optional[Any]:
    """
    Create a LiteLLM model instance if available
    With LiteLLM 1.77+, o1 models are natively supported and automatically routed
    Returns None if LiteLLM is not available or there's an error
    """
    try:
        # Try to import Google ADK's LiteLLM
        from google.adk.models.lite_llm import LiteLlm

        # Setup API key
        CustomLiteLLMWrapper.setup_api_keys(provider, api_key)

        # Get formatted model string based on provider
        if provider == "ollama":
            wrapper = OllamaLiteLLMWrapper(model, api_base)
        elif provider == "lm_studio":
            wrapper = LMStudioLiteLLMWrapper(model, api_base)
        elif provider == "deepseek":
            wrapper = DeepSeekLiteLLMWrapper(model)
        else:
            wrapper = CustomLiteLLMWrapper(model, provider, api_base)

        # Log if it's an o1 model
        if wrapper.is_o1_model:
            if provider == "deepseek":
                logger.info(f"Creating LiteLLM model for DeepSeek reasoning model: {wrapper.litellm_model}")
                logger.info("LiteLLM will handle DeepSeek reasoning content extraction")
            else:
                logger.info(f"Creating LiteLLM model for o1/reasoning model: {wrapper.litellm_model}")
                logger.info("LiteLLM 1.77+ will automatically route to v1/responses endpoint")

        # Create LiteLLM model with api_base for local models
        if api_base and provider in ["ollama", "lm_studio"]:
            logger.info(f"Creating local model with base URL: {api_base}")
            return LiteLlm(model=wrapper.litellm_model, api_base=api_base)
        else:
            # Create LiteLLM model - latest version handles o1 models automatically
            return LiteLlm(model=wrapper.litellm_model)

    except ImportError as e:
        logger.warning(f"LiteLLM not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating LiteLLM model: {e}")
        return None


def override_agent_model(agent: Any, provider: str, model: str, api_key: str, api_base: Optional[str] = None) -> bool:
    """
    Override an agent's model with LiteLLM if provider is not Google
    Returns True if override was successful, False otherwise
    """
    if provider == "google" or not CustomLiteLLMWrapper.is_supported_provider(provider):
        logger.info(f"Using default model for provider: {provider}")
        return False

    # Try to create LiteLLM model
    litellm_model = create_litellm_model(provider, model, api_key, api_base)

    if litellm_model:
        try:
            # Override the agent's model
            agent.model = litellm_model
            if provider == "ollama":
                wrapper = OllamaLiteLLMWrapper(model, api_base)
            elif provider == "lm_studio":
                wrapper = LMStudioLiteLLMWrapper(model, api_base)
            else:
                wrapper = CustomLiteLLMWrapper(model, provider, api_base)

            if wrapper.is_o1_model:
                logger.info(f"Successfully overrode agent with o1 model: {provider}/{model}")
            else:
                logger.info(f"Successfully overrode agent model with LiteLLM for {provider}/{model}")

            if api_base:
                logger.info(f"Using custom API base: {api_base}")
            return True
        except Exception as e:
            logger.error(f"Failed to override agent model: {e}")
            return False
    else:
        # Fallback: Try direct model string assignment
        # Some agents might accept model strings directly
        try:
            wrapper = CustomLiteLLMWrapper(model, provider, api_base)
            agent.model = wrapper.litellm_model
            logger.info(f"Fallback: Set agent model string to {wrapper.litellm_model}")
            return True
        except Exception as e:
            logger.warning(f"Could not override agent model: {e}")
            return False
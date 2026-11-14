"""
Centralized AI Models Configuration

This module provides a single source of truth for all AI model configurations
used across IOFlow, including AI Settings and Assistant features.
"""

from typing import Dict, List, Any


class AIModelsConfig:
    """Centralized configuration for all AI models and providers"""

    # Provider configurations with metadata
    PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "requires_endpoint": False,
            "default_model": "gpt-5-mini",
            "description": "Latest GPT-5 models with advanced reasoning, cost-effective variants, and enhanced capabilities"
        },
        "claude": {
            "name": "Anthropic Claude",
            "requires_endpoint": False,
            "default_model": "claude-sonnet-4-5",
            "description": "Latest Claude Sonnet 4.5 - best for coding and complex agents"
        },
        "gemini": {
            "name": "Google Gemini",
            "requires_endpoint": False,
            "default_model": "gemini-2.5-flash",
            "description": "Latest Gemini 2.5 models with thinking capabilities and extended context"
        },
        "azure_openai": {
            "name": "Azure OpenAI",
            "requires_endpoint": True,
            "default_model": "gpt-4",
            "description": "OpenAI models hosted on Microsoft Azure"
        },
        "deepseek": {
            "name": "DeepSeek",
            "requires_endpoint": False,
            "default_model": "deepseek-chat",
            "description": "DeepSeek AI models with strong reasoning capabilities"
        },
        "lm_studio": {
            "name": "LM Studio (Local)",
            "requires_endpoint": True,
            "requires_api_base": True,
            "default_api_base": "http://localhost:1234/v1",
            "default_model": "mistral-7b-instruct-v0.2",
            "description": "Run models locally with LM Studio"
        },
        "ollama": {
            "name": "Ollama (Local)",
            "requires_endpoint": True,
            "requires_api_base": True,
            "default_api_base": "http://localhost:11434",
            "default_model": "llama3.2",
            "description": "Run models locally with Ollama"
        }
    }

    # All available models organized by provider
    MODELS = {
        "openai": [
            # GPT-5.1 Series (Latest - November 2025)
            "gpt-5.1", "gpt-5.1-mini", "gpt-5.1-nano", "gpt-5.1-codex", "gpt-5.1-codex-mini",
            # GPT-5 Series (August 2025)
            "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5-chat", "gpt-5-codex",
            "gpt-5-chat-latest",
            # GPT-4.1 Series (January 2025)
            "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
            # GPT-4o Series (Current flagship multimodal)
            "gpt-4o", "gpt-4o-mini",
            # GPT-4 Turbo and GPT-4 (maintained for compatibility)
            "gpt-4", "gpt-4-turbo",
            # o-series reasoning models
            "o3", "o3-mini", "o4-mini",
            # Specialized models
            "gpt-realtime",
            # Legacy GPT-3.5 (deprecated but supported)
            "gpt-3.5-turbo"
        ],
        "claude": [
            # Claude 4.5 Series (Latest - October/November 2025)
            "claude-opus-4-5", "claude-opus-4-5-20251101",
            "claude-sonnet-4-5", "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5", "claude-haiku-4-5-20251001",
            # Claude 4.1 Series
            "claude-opus-4.1", "claude-opus-4-1-20250805",
            # Claude 4 Series
            "claude-4-opus", "claude-4-sonnet", "claude-4-haiku",
            "claude-opus-4-20250514", "claude-sonnet-4-20250514",
            # Claude 3.7 Series
            "claude-3-7-sonnet-20250219",
            # Claude 3.5 Series (maintained for compatibility)
            "claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-5-haiku-20241022",
            # Legacy Claude 3 Series
            "claude-3-sonnet", "claude-3-opus", "claude-3-haiku", "claude-3-haiku-20240307"
        ],
        "gemini": [
            # Gemini 3 Series (Latest - 2025)
            "gemini-3-pro", "gemini-3-flash", "gemini-3-flash-lite",
            # Gemini 2.5 Series
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-2.5-flash-preview-native-audio-dialog",
            "gemini-2.5-flash-exp-native-audio-thinking-dialog",
            # Gemini 2.0 Series
            "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.0-pro-experimental",
            "gemini-2.0-flash-exp",
            "gemini-2.0-flash-preview-image-generation",
            # Legacy Gemini 1.5 Series (maintained for compatibility)
            "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b",
            # Legacy Gemini 1.0 Series
            "gemini-1.0-pro", "gemini-1.0-pro-vision"
        ],
        "azure_openai": [
            "gpt-5.1", "gpt-5", "gpt-4.5", "gpt-4", "gpt-4-turbo", "gpt-35-turbo", "gpt-4o", "gpt-4o-mini"
        ],
        "deepseek": [
            "deepseek-chat",
            "deepseek-reasoner",
            "deepseek-r1",
            "deepseek-coder",
            "deepseek-r1-distill-qwen-32b",
            "deepseek-r1-distill-qwen-14b",
            "deepseek-r1-distill-qwen-7b"
        ],
        "lm_studio": [
            # Common local models (users can add custom ones)
            "qwen/qwen2.5-coder-14b",
            "mistral-7b-instruct-v0.2",
            "deepseek-r1-distill-qwen-14b"
        ],
        "ollama": [
            # Common Ollama models (users can add custom ones)
            "llama3.2",
            "mistral",
            "phi3",
            "codellama"
        ]
    }

    # Detailed model information for API responses
    MODELS_DETAILED = {
        # Google Gemini 3 Models (Latest)
        "gemini-3-pro": {
            "name": "Gemini 3 Pro",
            "provider": "google",
            "description": "Most advanced Gemini model for complex reasoning",
            "default": True
        },
        "gemini-3-flash": {
            "name": "Gemini 3 Flash",
            "provider": "google",
            "description": "Fast and capable Gemini 3 model"
        },
        "gemini-3-flash-lite": {
            "name": "Gemini 3 Flash Lite",
            "provider": "google",
            "description": "Lightweight and cost-efficient Gemini 3"
        },
        # Google Gemini 2.5 Models
        "gemini-2.5-pro": {
            "name": "Gemini 2.5 Pro",
            "provider": "google",
            "description": "State-of-the-art thinking model for complex reasoning"
        },
        "gemini-2.5-flash": {
            "name": "Gemini 2.5 Flash",
            "provider": "google",
            "description": "Fast thinking model for everyday tasks with 1M context"
        },
        "gemini-2.5-flash-lite": {
            "name": "Gemini 2.5 Flash-Lite Preview",
            "provider": "google",
            "description": "Most cost-efficient and fastest 2.5 model"
        },
        "gemini-2.0-flash-exp": {
            "name": "Gemini 2.0 Flash (Experimental)",
            "provider": "google",
            "description": "Fast, experimental version of Gemini 2.0"
        },
        "gemini-2.0-flash": {
            "name": "Gemini 2.0 Flash",
            "provider": "google",
            "description": "Fast and efficient Gemini model"
        },
        "gemini-1.5-pro": {
            "name": "Gemini 1.5 Pro",
            "provider": "google",
            "description": "Stable pro model (legacy)"
        },
        "gemini-1.5-flash": {
            "name": "Gemini 1.5 Flash",
            "provider": "google",
            "description": "Stable flash model (legacy)"
        },

        # OpenAI GPT-5.1 Models (Latest - November 2025)
        "gpt-5.1": {
            "name": "GPT-5.1",
            "provider": "openai",
            "description": "Latest flagship model with enhanced capabilities"
        },
        "gpt-5.1-mini": {
            "name": "GPT-5.1 Mini",
            "provider": "openai",
            "description": "Balanced performance and cost"
        },
        "gpt-5.1-nano": {
            "name": "GPT-5.1 Nano",
            "provider": "openai",
            "description": "Fastest and most efficient GPT-5.1 variant"
        },
        "gpt-5.1-codex": {
            "name": "GPT-5.1 Codex",
            "provider": "openai",
            "description": "Optimized for code generation"
        },
        "gpt-5.1-codex-mini": {
            "name": "GPT-5.1 Codex Mini",
            "provider": "openai",
            "description": "Efficient code generation model"
        },

        # OpenAI GPT-5 Models
        "gpt-5": {
            "name": "GPT-5",
            "provider": "openai",
            "description": "Best model for coding and agentic tasks (74.9% SWE-bench)"
        },
        "gpt-5-mini": {
            "name": "GPT-5 Mini",
            "provider": "openai",
            "description": "Smaller, cost-effective GPT-5 variant"
        },
        "gpt-5-nano": {
            "name": "GPT-5 Nano",
            "provider": "openai",
            "description": "Most compact and efficient GPT-5 version"
        },
        "gpt-5-chat-latest": {
            "name": "GPT-5 Chat Latest",
            "provider": "openai",
            "description": "Non-reasoning GPT-5 for chat applications"
        },
        "gpt-5-codex": {
            "name": "GPT-5 Codex",
            "provider": "openai",
            "description": "Advanced code generation and understanding model"
        },

        # OpenAI GPT-4 Models
        "gpt-4o": {
            "name": "GPT-4o",
            "provider": "openai",
            "description": "OpenAI's flagship multimodal model"
        },
        "gpt-4o-mini": {
            "name": "GPT-4o Mini",
            "provider": "openai",
            "description": "Smaller, faster, cheaper GPT-4o variant"
        },
        "gpt-4-turbo": {
            "name": "GPT-4 Turbo",
            "provider": "openai",
            "description": "GPT-4 Turbo with vision support"
        },
        "gpt-realtime": {
            "name": "GPT-Realtime",
            "provider": "openai",
            "description": "Advanced speech-to-speech model"
        },

        # Anthropic Claude 4.5 Models (Latest - October/November 2025)
        "claude-opus-4-5": {
            "name": "Claude Opus 4.5",
            "provider": "anthropic",
            "description": "Most intelligent Claude model with maximum capability"
        },
        "claude-opus-4-5-20251101": {
            "name": "Claude Opus 4.5 (20251101)",
            "provider": "anthropic",
            "description": "Dated version of Claude Opus 4.5"
        },
        "claude-sonnet-4-5": {
            "name": "Claude Sonnet 4.5",
            "provider": "anthropic",
            "description": "Best model for coding and complex agents"
        },
        "claude-sonnet-4-5-20250929": {
            "name": "Claude Sonnet 4.5 (20250929)",
            "provider": "anthropic",
            "description": "Dated version of Claude Sonnet 4.5"
        },
        "claude-haiku-4-5": {
            "name": "Claude Haiku 4.5",
            "provider": "anthropic",
            "description": "Fastest Haiku with extended thinking capabilities"
        },
        "claude-haiku-4-5-20251001": {
            "name": "Claude Haiku 4.5 (20251001)",
            "provider": "anthropic",
            "description": "Dated version of Claude Haiku 4.5"
        },

        # Anthropic Claude 4.1 Models
        "claude-opus-4-1-20250805": {
            "name": "Claude Opus 4.1",
            "provider": "anthropic",
            "description": "Best coding model, 200K context"
        },

        # Anthropic Claude 4 Models
        "claude-opus-4-20250514": {
            "name": "Claude Opus 4",
            "provider": "anthropic",
            "description": "Powerful model for complex tasks"
        },
        "claude-sonnet-4-20250514": {
            "name": "Claude Sonnet 4",
            "provider": "anthropic",
            "description": "Balanced speed and intelligence"
        },
        "claude-4-opus": {
            "name": "Claude 4 Opus (Generic)",
            "provider": "anthropic",
            "description": "Generic Claude 4 Opus model"
        },
        "claude-4-sonnet": {
            "name": "Claude 4 Sonnet (Generic)",
            "provider": "anthropic",
            "description": "Generic Claude 4 Sonnet model"
        },
        "claude-4-haiku": {
            "name": "Claude 4 Haiku (Generic)",
            "provider": "anthropic",
            "description": "Generic Claude 4 Haiku model"
        },

        # Anthropic Claude 3.7 Model
        "claude-3-7-sonnet-20250219": {
            "name": "Claude 3.7 Sonnet",
            "provider": "anthropic",
            "description": "Enhanced Sonnet model"
        },

        # Anthropic Claude 3.5 Models
        "claude-3-5-sonnet": {
            "name": "Claude 3.5 Sonnet (Generic)",
            "provider": "anthropic",
            "description": "Generic Claude 3.5 Sonnet"
        },
        "claude-3-5-haiku-20241022": {
            "name": "Claude 3.5 Haiku",
            "provider": "anthropic",
            "description": "Fast and cost-effective model"
        },
        "claude-3-5-haiku": {
            "name": "Claude 3.5 Haiku (Generic)",
            "provider": "anthropic",
            "description": "Generic Claude 3.5 Haiku"
        },

        # Anthropic Claude 3 Models
        "claude-3-opus": {
            "name": "Claude 3 Opus",
            "provider": "anthropic",
            "description": "Legacy Claude 3 Opus"
        },
        "claude-3-sonnet": {
            "name": "Claude 3 Sonnet",
            "provider": "anthropic",
            "description": "Legacy Claude 3 Sonnet"
        },
        "claude-3-haiku-20240307": {
            "name": "Claude 3 Haiku (20240307)",
            "provider": "anthropic",
            "description": "Fast, compact model"
        },
        "claude-3-haiku": {
            "name": "Claude 3 Haiku",
            "provider": "anthropic",
            "description": "Legacy Claude 3 Haiku"
        },

        # DeepSeek Models
        "deepseek-chat": {
            "name": "DeepSeek Chat",
            "provider": "deepseek",
            "description": "Standard chat model"
        },
        "deepseek-reasoner": {
            "name": "DeepSeek Reasoner (V3.1)",
            "provider": "deepseek",
            "description": "Enhanced reasoning capabilities"
        },
        "deepseek-r1": {
            "name": "DeepSeek R1",
            "provider": "deepseek",
            "description": "671B parameter reasoning model"
        },
        "deepseek-coder": {
            "name": "DeepSeek Coder",
            "provider": "deepseek",
            "description": "Specialized for code generation"
        },
        "deepseek-r1-distill-qwen-32b": {
            "name": "DeepSeek R1 Distill 32B",
            "provider": "deepseek",
            "description": "Efficient 32B distilled model"
        },
        "deepseek-r1-distill-qwen-14b": {
            "name": "DeepSeek R1 Distill 14B",
            "provider": "deepseek",
            "description": "Efficient 14B distilled model"
        },
        "deepseek-r1-distill-qwen-7b": {
            "name": "DeepSeek R1 Distill 7B",
            "provider": "deepseek",
            "description": "Budget-friendly 7B model"
        },

        # LM Studio Models (Common - user can enter custom ones)
        "qwen/qwen2.5-coder-14b": {
            "name": "Qwen 2.5 Coder 14B",
            "provider": "lm_studio",
            "description": "Local code generation model"
        },
        "mistral-7b-instruct-v0.2": {
            "name": "Mistral 7B Instruct v0.2",
            "provider": "lm_studio",
            "description": "Local instruction-following model"
        },
        "deepseek-r1-distill-qwen-14b": {
            "name": "DeepSeek R1 Distill 14B (Local)",
            "provider": "lm_studio",
            "description": "Local reasoning model"
        },

        # Ollama Models (Common - user can enter custom ones)
        "llama3.2": {
            "name": "Llama 3.2",
            "provider": "ollama",
            "description": "Local Llama model"
        },
        "mistral": {
            "name": "Mistral",
            "provider": "ollama",
            "description": "Local Mistral model"
        },
        "phi3": {
            "name": "Phi-3",
            "provider": "ollama",
            "description": "Local Microsoft Phi model"
        },
        "codellama": {
            "name": "Code Llama",
            "provider": "ollama",
            "description": "Local code-specialized model"
        }
    }

    @classmethod
    def get_providers(cls) -> Dict[str, Any]:
        """Get all provider configurations"""
        return cls.PROVIDERS

    @classmethod
    def get_provider_models(cls, provider: str) -> List[str]:
        """Get list of models for a specific provider"""
        return cls.MODELS.get(provider, [])

    @classmethod
    def get_all_models_detailed(cls) -> List[Dict[str, Any]]:
        """Get detailed information for all models as a list"""
        models = []
        for model_id, info in cls.MODELS_DETAILED.items():
            models.append({
                "id": model_id,
                **info
            })
        return models

    @classmethod
    def get_model_info(cls, model_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific model"""
        return cls.MODELS_DETAILED.get(model_id, {
            "name": model_id,
            "provider": "unknown",
            "description": "Custom or unknown model"
        })

    @classmethod
    def is_valid_model(cls, provider: str, model: str) -> bool:
        """Check if a model is valid for a given provider"""
        provider_models = cls.MODELS.get(provider, [])
        return model in provider_models

    @classmethod
    def get_provider_info(cls, provider: str) -> Dict[str, Any]:
        """Get information about a specific provider"""
        return cls.PROVIDERS.get(provider, {})

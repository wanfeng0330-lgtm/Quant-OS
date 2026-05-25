"""LLM Provider Factory."""

from __future__ import annotations

import logging
from typing import Any

from quant_os_shared.config.settings import get_settings

from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    _providers: dict[str, type[LLMProvider]] = {
        "deepseek": DeepSeekProvider,
        "openai": OpenAIProvider,
        "mimo": OpenAIProvider,
        "claude": ClaudeProvider,
    }

    _instances: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a new LLM provider."""
        cls._providers[name] = provider_class

    @classmethod
    def create(
        cls,
        provider_name: str | None = None,
        **kwargs: Any,
    ) -> LLMProvider:
        """Create an LLM provider instance.

        Args:
            provider_name: Name of the provider (default: from settings)
            **kwargs: Additional arguments to pass to the provider

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider is not found
        """
        settings = get_settings()
        name = provider_name or settings.llm.default_provider

        # Return cached instance if available
        if name in cls._instances:
            return cls._instances[name]

        if name not in cls._providers:
            raise ValueError(f"Unknown LLM provider: {name}")

        provider_class = cls._providers[name]

        # Get provider-specific config from settings
        provider_config = cls._get_provider_config(name, settings)

        # Create instance
        instance = provider_class(**{**provider_config, **kwargs})

        # Cache instance
        cls._instances[name] = instance

        logger.info("Created LLM provider: %s", name)
        return instance

    @classmethod
    def _get_provider_config(cls, name: str, settings: Any) -> dict[str, Any]:
        """Get provider-specific configuration from settings."""
        if name == "deepseek":
            return {
                "api_key": settings.llm.deepseek_api_key,
                "base_url": settings.llm.deepseek_base_url,
                "default_model": settings.llm.deepseek_model,
            }
        elif name == "openai":
            config = {
                "api_key": settings.llm.openai_api_key,
                "default_model": settings.llm.openai_model,
            }
            if settings.llm.openai_base_url:
                config["base_url"] = settings.llm.openai_base_url
            return config
        elif name == "mimo":
            return {
                "api_key": settings.llm.mimo_api_key,
                "base_url": settings.llm.mimo_base_url,
                "default_model": settings.llm.mimo_model,
                "provider_label": "mimo",
            }
        elif name == "claude":
            return {
                "api_key": settings.llm.claude_api_key,
            }
        elif name == "qwen":
            return {
                "api_key": settings.llm.qwen_api_key,
            }
        elif name == "gemini":
            return {
                "api_key": settings.llm.gemini_api_key,
            }
        else:
            return {}

    @classmethod
    def get_default(cls) -> LLMProvider:
        """Get the default LLM provider from settings."""
        settings = get_settings()
        return cls.create(settings.llm.default_provider)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the provider instance cache."""
        cls._instances.clear()


# Convenience function
def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Get an LLM provider instance."""
    return LLMProviderFactory.create(provider_name)

"""
LLM provider factory.

Usage:
    from app.ai.providers.factory import get_llm_provider
    provider = get_llm_provider()
    result = await provider.generate_structured(prompt, schema)

Provider resolution:
  1. ``name`` argument (if supplied)
  2. ``settings.LLM_PROVIDER`` environment variable

IMPORTANT: Unlike the Phase 1–3 factory which silently fell back to Mock,
this factory raises ``LLMProviderError`` for unregistered providers.
Silently using mock output in production would produce fabricated legal
analysis without any visible error signal.

Set ``LLM_PROVIDER=mock`` explicitly for development / testing.
"""

from __future__ import annotations

from typing import Dict, Optional, Type

from app.ai.providers.base import BaseLLMProvider, LLMProviderError, MockLLMProvider
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
# To add a new provider:
#   1. Implement BaseLLMProvider in app/ai/providers/<name>.py
#   2. Import it here and add to _REGISTRY.
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[BaseLLMProvider]] = {
    "mock": MockLLMProvider,
    # "gemini":    GeminiLLMProvider,    # registered in providers/gemini.py
    # "openai":    OpenAILLMProvider,    # future
    # "anthropic": AnthropicLLMProvider, # future
}

# Attempt to register the Gemini provider if the SDK is available.
try:
    from app.ai.providers.gemini import GeminiLLMProvider  # type: ignore[import]
    _REGISTRY["gemini"] = GeminiLLMProvider
    logger.debug("Gemini LLM provider registered.")
except ImportError:
    logger.debug("google-generativeai SDK not installed; Gemini provider unavailable.")
except Exception as _e:
    logger.debug("Gemini provider registration skipped: %s", _e)

# Register the Groq provider (uses httpx — always available).
try:
    from app.ai.providers.groq import GroqLLMProvider
    _REGISTRY["groq"] = GroqLLMProvider
    logger.debug("Groq LLM provider registered.")
except Exception as _e:
    logger.debug("Groq provider registration skipped: %s", _e)


def get_llm_provider(name: Optional[str] = None) -> BaseLLMProvider:
    """
    Resolve and instantiate the configured LLM provider.

    Args:
        name: Override the provider name (optional).  When omitted the value
              from ``settings.AI_PROVIDER`` or ``settings.LLM_PROVIDER`` is used.

    Returns:
        A ready-to-use ``BaseLLMProvider`` instance.

    Raises:
        LLMProviderError: If the named provider is not in the registry.
            Configure LLM_PROVIDER=mock for development without credentials.
    """
    from app.core.config import settings

    raw_name = name or getattr(settings, "AI_PROVIDER", None) or settings.LLM_PROVIDER
    provider_name = raw_name.lower().strip()

    if provider_name in _REGISTRY:
        logger.debug("Resolved LLM provider: %s", provider_name)
        return _REGISTRY[provider_name]()

    raise LLMProviderError(
        provider=provider_name,
        reason=(
            f"Provider '{provider_name}' is not registered.  "
            f"Available providers: {sorted(_REGISTRY.keys())}.  "
            "Set LLM_PROVIDER=mock for development without credentials."
        ),
    )


class AIProviderFactory:
    """
    Static factory interface for obtaining AI LLM providers.
    """

    @staticmethod
    def get_provider(name: Optional[str] = None) -> BaseLLMProvider:
        return get_llm_provider(name)

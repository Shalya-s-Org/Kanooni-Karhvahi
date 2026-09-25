"""
Embedding provider factory.

Usage:
    from app.rag.embeddings.factory import get_embedding_provider
    provider = get_embedding_provider()
    vector = await provider.embed_text("What is the payment deadline?")

Provider resolution order:
  1. ``name`` argument (if supplied)
  2. ``settings.EMBEDDING_PROVIDER`` environment variable

If the requested provider is not registered (e.g. "gemini" without the SDK
installed), the factory raises ``EmbeddingProviderError`` rather than
silently falling back to Mock — silent fallback in production would produce
meaningless zero-like vectors that appear to work but deliver no semantic
signal.

The Mock provider is available for tests and must be requested explicitly
by setting EMBEDDING_PROVIDER=mock.
"""

from __future__ import annotations

from typing import Dict, Optional, Type

from app.core.logging import logger
from app.rag.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingProviderError,
    MockEmbeddingProvider,
)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
# To add a new provider:
#   1. Implement BaseEmbeddingProvider in app/rag/embeddings/providers/<name>.py
#   2. Import it here and add to _REGISTRY.
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[BaseEmbeddingProvider]] = {
    "mock": MockEmbeddingProvider,
    # "openai":  OpenAIEmbeddingProvider,    # Phase 4+ — add when SDK is available
    # "gemini":  GeminiEmbeddingProvider,    # Phase 4+ — add when SDK is available
    # "huggingface": HuggingFaceEmbeddingProvider,
}


def get_embedding_provider(name: Optional[str] = None) -> BaseEmbeddingProvider:
    """
    Resolve and instantiate the configured embedding provider.

    Args:
        name: Override the provider name (optional).  When omitted the value
              from ``settings.EMBEDDING_PROVIDER`` is used.

    Returns:
        A ready-to-use ``BaseEmbeddingProvider`` instance.

    Raises:
        EmbeddingProviderError: If the named provider is not in the registry.
            This is intentional — the application must not silently fall back
            to a mock provider in production.  Configure EMBEDDING_PROVIDER=mock
            explicitly for development/testing without real credentials.
    """
    from app.core.config import settings

    provider_name = (name or settings.EMBEDDING_PROVIDER).lower().strip()

    if provider_name in _REGISTRY:
        provider_cls = _REGISTRY[provider_name]
        logger.debug("Resolved embedding provider: %s", provider_name)
        return provider_cls()

    raise EmbeddingProviderError(
        provider=provider_name,
        reason=(
            f"Provider '{provider_name}' is not registered.  "
            f"Available providers: {sorted(_REGISTRY.keys())}.  "
            "Set EMBEDDING_PROVIDER=mock for development without credentials."
        ),
    )

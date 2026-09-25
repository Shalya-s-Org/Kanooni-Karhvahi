"""
Backward-compatibility shim.

The canonical embedding provider implementation lives in app.rag.embeddings.
This module re-exports from there so that any code that imported from
app.ai.embeddings.base continues to work unchanged.
"""
# Re-export the canonical classes.
from app.rag.embeddings.base import (  # noqa: F401
    BaseEmbeddingProvider as EmbeddingProvider,
    MockEmbeddingProvider,
    EmbeddingProviderError,
)

__all__ = ["EmbeddingProvider", "MockEmbeddingProvider", "EmbeddingProviderError"]

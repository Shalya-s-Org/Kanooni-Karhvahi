"""
Embedding provider abstraction and factory.

Providers are resolved via settings.EMBEDDING_PROVIDER.
The rest of the system calls embedding_provider.embed_text(...)
rather than any vendor SDK directly.
"""
from app.rag.embeddings.base import BaseEmbeddingProvider, MockEmbeddingProvider
from app.rag.embeddings.factory import get_embedding_provider

__all__ = [
    "BaseEmbeddingProvider",
    "MockEmbeddingProvider",
    "get_embedding_provider",
]

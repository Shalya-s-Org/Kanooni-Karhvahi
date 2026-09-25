from typing import Dict, Type
from app.ai.embeddings.base import EmbeddingProvider, MockEmbeddingProvider
from app.core.config import settings
from app.core.logging import logger

_EMBEDDINGS: Dict[str, Type[EmbeddingProvider]] = {
    "mock": MockEmbeddingProvider,
}


def get_embedding_provider(name: str = None) -> EmbeddingProvider:
    provider_name = (name or settings.EMBEDDING_PROVIDER).lower()

    if provider_name in _EMBEDDINGS:
        return _EMBEDDINGS[provider_name]()

    logger.warning("Embedding provider '%s' not registered yet. Falling back to MockEmbeddingProvider.", provider_name)
    return MockEmbeddingProvider()

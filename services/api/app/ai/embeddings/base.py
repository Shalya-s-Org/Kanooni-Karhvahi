from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """
    Abstract Base Class for vector embedding generation.
    Decouples vectorization from concrete provider SDKs.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Returns embedding dimension size (e.g. 768, 1536).
        """
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for a single string.
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for a batch of strings.
        """
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock embedding provider producing deterministic zero vectors.
    """

    def __init__(self, dim: int = 768):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> List[float]:
        return [0.0] * self._dim

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]

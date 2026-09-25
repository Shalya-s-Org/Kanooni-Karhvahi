"""
Base embedding provider abstraction.

All embedding calls in the application go through BaseEmbeddingProvider.
No vendor SDK is ever called directly outside a concrete provider subclass.
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for vector embedding generation.
    Decouples vectorisation from concrete provider SDKs.

    Subclasses MUST implement:
      - dimension   (property)
      - embed_text  (async, single string → List[float])
      - embed_batch (async, list of strings → List[List[float]])
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension (e.g. 768, 1536, 3072)."""

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The source text to embed.

        Returns:
            A list of floats of length ``self.dimension``.

        Raises:
            EmbeddingProviderError: If the provider is unavailable or credentials
                are missing in a production context.
        """

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for a list of strings in a single provider call.

        Implementations MUST send texts in a single batch request where the
        provider supports it — do NOT issue one network call per text.

        Args:
            texts: List of source strings to embed.

        Returns:
            A list of embedding vectors, one per input string,
            each of length ``self.dimension``.
        """


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock embedding provider for testing and CI.

    Produces unit-normalised vectors derived from a stable SHA-256 hash of
    the input text so that:
      - Identical text → identical vector (deterministic).
      - Different texts → different vectors (useful for retrieval ranking).
      - Vectors are L2-normalised so cosine distance behaves as expected.

    This provider MUST NOT be used in production.
    It is safe to use in automated tests because retrieval ranking is
    reproducible without an external AI API.
    """

    def __init__(self, dim: int = 0) -> None:
        """
        Args:
            dim: Override embedding dimension.  When 0 (default) the dimension
                 is read from ``settings.EMBEDDING_DIMENSION`` at call time.
                 Pass an explicit value in tests to avoid importing settings.
        """
        self._dim = dim

    @property
    def dimension(self) -> int:
        if self._dim:
            return self._dim
        # Lazy import to avoid circular imports at module load time.
        from app.core.config import settings
        return settings.EMBEDDING_DIMENSION

    def _deterministic_vector(self, text: str) -> List[float]:
        """
        Derive a stable, unit-normalised vector from the SHA-256 hash of *text*.

        Strategy:
          1. Hash the UTF-8 encoded text with SHA-256 (32 bytes = 256 bits).
          2. Tile/fold the hash bytes to fill ``dimension`` floats in [-1, 1].
          3. L2-normalise the result so cosine distance is meaningful.

        The approach is O(dimension) time, produces the same output for the
        same input on every platform and Python version, and requires no
        third-party libraries.
        """
        dim = self.dimension
        digest = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes

        # Tile digest bytes to cover `dim` positions.
        tiled = bytearray()
        while len(tiled) < dim:
            tiled.extend(digest)
        tiled = tiled[:dim]

        # Map each byte [0, 255] → [-1.0, 1.0]
        raw = [(b / 127.5) - 1.0 for b in tiled]

        # L2-normalise so the vector lives on the unit hypersphere.
        norm = math.sqrt(sum(v * v for v in raw))
        if norm < 1e-9:
            # Degenerate case (all zeros) — return uniform vector.
            return [1.0 / math.sqrt(dim)] * dim
        return [v / norm for v in raw]

    async def embed_text(self, text: str) -> List[float]:
        return self._deterministic_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._deterministic_vector(t) for t in texts]


class EmbeddingProviderError(Exception):
    """
    Raised when an embedding provider is unavailable or misconfigured.
    The caller should treat this as a non-retryable configuration error
    unless the underlying cause is a transient network failure.
    """

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"Embedding provider '{provider}' error: {reason}")
        self.provider = provider
        self.reason = reason

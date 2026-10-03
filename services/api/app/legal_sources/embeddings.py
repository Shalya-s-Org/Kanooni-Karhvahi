"""
Embedding generation service for verified legal source chunks (Phase 6).

Reuses the unified BaseEmbeddingProvider abstraction.
Never creates a disconnected or ad-hoc embedding architecture.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.legal_source import LegalSourceChunk, LegalSourceVersion
from app.rag.embeddings.base import BaseEmbeddingProvider, EmbeddingProviderError
from app.rag.embeddings.factory import get_embedding_provider


class LegalSourceEmbeddingService:
    """
    Embeds LegalSourceChunk records in batches using the configured embedding provider.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        self._provider = provider

    def _get_provider(self) -> BaseEmbeddingProvider:
        return self._provider or get_embedding_provider()

    async def embed_version_chunks(
        self,
        version_id: uuid.UUID,
        db: AsyncSession,
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Embed all chunks for a specific LegalSourceVersion that do not yet have embeddings.

        Returns:
            Number of chunks successfully embedded.

        Raises:
            EmbeddingProviderError: If the provider is unavailable or fails.
        """
        provider = self._get_provider()
        batch_limit = batch_size or settings.EMBEDDING_BATCH_SIZE or 32

        # Fetch chunks for this version
        result = await db.execute(
            select(LegalSourceChunk)
            .where(
                LegalSourceChunk.legal_source_version_id == version_id,
                LegalSourceChunk.embedding.is_(None),
            )
            .order_by(LegalSourceChunk.chunk_index)
        )
        chunks: List[LegalSourceChunk] = list(result.scalars().all())

        if not chunks:
            logger.info("No un-embedded chunks for legal source version %s", version_id)
            return 0

        total_embedded = 0

        # Process in batches
        for i in range(0, len(chunks), batch_limit):
            batch = chunks[i : i + batch_limit]
            texts = [c.text for c in batch]

            try:
                embeddings = await provider.embed_batch(texts)
            except Exception as e:
                logger.error(
                    "Failed to generate embeddings for legal source version %s: %s",
                    version_id,
                    e,
                )
                raise EmbeddingProviderError(
                    f"Embedding generation failed for legal source version {version_id}: {e}"
                ) from e

            for chunk, vec in zip(batch, embeddings):
                chunk.embedding = vec
                total_embedded += 1

        await db.flush()
        logger.info(
            "Successfully embedded %d chunks for legal source version %s",
            total_embedded,
            version_id,
        )
        return total_embedded


legal_source_embedding_service = LegalSourceEmbeddingService()

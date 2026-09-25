"""
Celery task: generate_document_embeddings

Flow:
  document_id
    → load all DocumentChunk records (no embedding yet)
    → batch texts (settings.EMBEDDING_BATCH_SIZE per request)
    → embedding provider
    → store vectors in document_chunks.embedding
    → mark document status

This task is enqueued after chunk_and_persist completes in the pipeline.
It can also be triggered independently (e.g. to re-embed after a model change).

The task follows the same asyncio.run() + AsyncSessionLocal() pattern as
process_document to run async SQLAlchemy inside a synchronous Celery worker.
"""

import asyncio
import uuid
import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.generate_embeddings",
    bind=True,
    max_retries=3,
)
def generate_document_embeddings(self, document_id_str: str) -> dict:
    """
    Chunks the document (idempotent) and generates embeddings for all chunks.

    Args:
        document_id_str: String UUID of the document to process.

    Returns:
        dict with keys: document_id, chunks_indexed, status

    Raises:
        Retries automatically on transient errors (max 3 attempts, 30s delay).
    """
    logger.info("Celery generate_embeddings triggered for document %s", document_id_str)

    try:
        from app.database.session import AsyncSessionLocal
        from app.services.document_service import _generate_and_store_embeddings
        from app.rag.chunking import document_chunker
        from app.rag.embeddings.factory import get_embedding_provider
        from app.rag.embeddings.base import EmbeddingProviderError

        doc_id = uuid.UUID(document_id_str)

        async def _run() -> dict:
            async with AsyncSessionLocal() as session:
                # Chunking is idempotent — safe to re-run.
                chunks = await document_chunker.chunk_and_persist(doc_id, session)
                if not chunks:
                    logger.warning("No chunks produced for document %s", doc_id)
                    return {"document_id": document_id_str, "chunks_indexed": 0, "status": "no_chunks"}

                try:
                    provider = get_embedding_provider()
                    count = await _generate_and_store_embeddings(doc_id, provider, session)
                    return {
                        "document_id": document_id_str,
                        "chunks_indexed": count,
                        "status": "ok",
                    }
                except EmbeddingProviderError as emb_err:
                    logger.warning(
                        "Embedding provider unavailable for document %s: %s",
                        doc_id, emb_err,
                    )
                    return {
                        "document_id": document_id_str,
                        "chunks_indexed": 0,
                        "status": "embedding_provider_unavailable",
                    }

        return asyncio.run(_run())

    except Exception as exc:
        logger.error(
            "Celery generate_embeddings failed for %s: %s",
            document_id_str, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30)

from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.generate_embeddings")
def generate_embeddings(document_id: str) -> dict:
    """
    Chunks document text and generates vector embeddings for pgvector storage.
    TODO (Phase 4): Connect to EmbeddingProvider and insert into postgres.
    """
    logger.info("Generating embeddings for document %s", document_id)
    return {
        "document_id": document_id,
        "chunks_indexed": 0
    }

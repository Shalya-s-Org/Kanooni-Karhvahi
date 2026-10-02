"""
Celery task: analyze_document (Phase 5)

Generates an AI document summary in the background.
Called after chunking and embedding complete (or can be invoked independently).

Follows the same asyncio.run() + AsyncSessionLocal() pattern as
process_document and generate_embeddings.
"""

import asyncio
import uuid
import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.analyze_document",
    bind=True,
    max_retries=2,
)
def analyze_document(self, document_id_str: str) -> dict:
    """
    Generate an AI document summary for the given document.

    Args:
        document_id_str: String UUID of the document to analyse.

    Returns:
        dict with keys: document_id, status, provider
    """
    logger.info("Celery analyze_document triggered for %s", document_id_str)
    try:
        from app.database.session import AsyncSessionLocal
        from app.analysis.document_summary import document_summary_service

        doc_id = uuid.UUID(document_id_str)

        async def _run() -> dict:
            async with AsyncSessionLocal() as session:
                analysis = await document_summary_service.generate_summary(doc_id, session)
                return {
                    "document_id": document_id_str,
                    "status": analysis.status,
                    "provider": analysis.provider or "unknown",
                }

        return asyncio.run(_run())

    except Exception as exc:
        logger.error(
            "Celery analyze_document failed for %s: %s", document_id_str, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=60)

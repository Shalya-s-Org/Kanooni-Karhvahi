import asyncio
import uuid
import logging
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.process_document", bind=True, max_retries=3)
def process_document(self, document_id_str: str) -> dict:
    """
    Celery background worker task orchestrating the document extraction & OCR pipeline.
    """
    logger.info("Celery task process_document triggered for ID: %s", document_id_str)
    try:
        from app.database.session import AsyncSessionLocal
        from app.services.document_service import document_service

        doc_id = uuid.UUID(document_id_str)

        async def _run():
            async with AsyncSessionLocal() as session:
                return await document_service.process_document_pipeline(doc_id, session)

        doc = asyncio.run(_run())
        return {
            "document_id": str(doc.id),
            "status": doc.status,
            "page_count": doc.page_count,
            "ocr_required": doc.ocr_required,
        }
    except Exception as exc:
        logger.error("Error executing Celery process_document for %s: %s", document_id_str, exc, exc_info=True)
        # Attempt retry if recoverable
        raise self.retry(exc=exc, countdown=10)

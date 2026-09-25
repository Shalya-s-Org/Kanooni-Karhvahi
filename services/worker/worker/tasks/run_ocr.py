from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.run_ocr")
def run_ocr(document_id: str, file_path: str) -> dict:
    """
    Extracts text and spatial layout coordinates from document scans or images.
    TODO (Phase 2): Connect to configured OCRProvider.
    """
    logger.info("Executing OCR for document %s at %s", document_id, file_path)
    return {
        "document_id": document_id,
        "ocr_completed": True,
        "extracted_chars": 0
    }

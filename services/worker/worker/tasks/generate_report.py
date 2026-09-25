from worker.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.generate_report")
def generate_report(document_id: str, format: str = "pdf") -> dict:
    """
    Renders a formatted plain-language summary briefing document.
    TODO (Phase 5): Implement HTML/PDF report template rendering.
    """
    logger.info("Generating %s report for document %s", format, document_id)
    return {
        "document_id": document_id,
        "format": format,
        "report_url": None
    }

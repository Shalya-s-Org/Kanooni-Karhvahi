import asyncio
import logging
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.cleanup_documents")
def cleanup_expired_documents() -> dict:
    """
    Celery periodic task to purge expired documents according to 24-hour TTL policy.
    """
    logger.info("Executing periodic expired document privacy cleanup...")
    try:
        from app.database.session import AsyncSessionLocal
        from app.services.document_service import document_service

        async def _run():
            async with AsyncSessionLocal() as session:
                return await document_service.cleanup_expired_documents(session)

        purged_count = asyncio.run(_run())
        return {"success": True, "purged_count": purged_count}
    except Exception as exc:
        logger.error("Cleanup task encountered an error: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}

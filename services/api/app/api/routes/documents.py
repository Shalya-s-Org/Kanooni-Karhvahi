"""
Document intake and management routes (Future Phase).
"""

from fastapi import APIRouter
from app.schemas.base import ApiResponse

router = APIRouter(prefix="/documents", tags=["Documents"])

# TODO (Phase 2): Implement POST /upload (enforce 25MB limit, calculate TTL, store file, enqueue Celery task)
# TODO (Phase 2): Implement GET /{document_id} (fetch document processing status)
# TODO (Phase 2): Implement DELETE /{document_id} (immediate cryptographic and database purge)

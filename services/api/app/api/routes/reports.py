"""
Document plain-language report export routes (Future Phase).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["Reports"])

# TODO (Phase 5): Implement POST /{document_id}/export (export simplified plain-language summary PDF)

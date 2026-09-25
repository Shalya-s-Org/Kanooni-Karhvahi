"""
Document-grounded Q&A and verification chat routes (Future Phase).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["Chat"])

# TODO (Phase 4): Implement POST /query (document-grounded RAG query with strict clause citations)
# TODO (Phase 4): Implement GET /{document_id}/history (retrieve session chat history)

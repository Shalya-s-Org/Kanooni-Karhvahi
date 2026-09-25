"""
Document-scoped pgvector semantic retrieval.

Every search is strictly filtered by document_id before ranking.
A query against document A can never retrieve chunks from document B.
"""
from app.rag.retrieval.service import (
    RetrievalResult,
    DocumentRetrievalService,
    document_retrieval_service,
)

__all__ = [
    "RetrievalResult",
    "DocumentRetrievalService",
    "document_retrieval_service",
]

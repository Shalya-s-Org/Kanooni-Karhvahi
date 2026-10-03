"""
Verified Legal-Source RAG package (Phase 6).
"""

from app.legal_sources.chunking import LegalSourceChunker, RawLegalChunk, legal_source_chunker
from app.legal_sources.embeddings import LegalSourceEmbeddingService, legal_source_embedding_service
from app.legal_sources.ingestion import LegalSourceIngestionService, legal_source_ingestion_service
from app.legal_sources.retrieval import LegalSourceRetrievalService, legal_source_retrieval_service

__all__ = [
    "LegalSourceChunker",
    "RawLegalChunk",
    "legal_source_chunker",
    "LegalSourceEmbeddingService",
    "legal_source_embedding_service",
    "LegalSourceIngestionService",
    "legal_source_ingestion_service",
    "LegalSourceRetrievalService",
    "legal_source_retrieval_service",
]

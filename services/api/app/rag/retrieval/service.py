"""
Document-scoped semantic retrieval service.

Critical invariant:
  Every search filters by document_id at the database level BEFORE ranking.
  A query against document A will NEVER return chunks from document B.
  The WHERE clause is applied in SQL — not after fetching results in Python.

Retrieval flow:
  query_text
    → embed_text (embedding provider)
    → pgvector cosine similarity search (filtered by document_id + top-k)
    → metadata enrichment (clause, page)
    → List[RetrievalResult]

The service does NOT:
  - Generate an answer.
  - Summarise clause text.
  - Provide legal advice.
  It only retrieves evidence so that a future LLM layer can cite sources.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document, DocumentChunk, DocumentClause
from app.rag.embeddings.base import BaseEmbeddingProvider, EmbeddingProviderError
from app.rag.embeddings.factory import get_embedding_provider


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """
    A single ranked retrieval result with full source traceability.

    Fields::

        chunk_id      – UUID of the DocumentChunk record
        text          – verbatim chunk text (do NOT modify for display)
        score         – cosine similarity [0, 1]; higher is more similar
        page_number   – 1-based page number where the chunk originates
        page_id       – UUID of the DocumentPage record (nullable)
        clause_id     – UUID of the DocumentClause record (nullable)
        clause_number – human-readable clause number e.g. "7", "3.1" (nullable)
        document_id   – UUID of the source document
        retrieval_method – "semantic" | "lexical" | "hybrid"
        source_type   – always "uploaded_document" in Phase 4
    """

    chunk_id: uuid.UUID
    text: str
    score: float
    page_number: int
    page_id: Optional[uuid.UUID]
    clause_id: Optional[uuid.UUID]
    clause_number: Optional[str]
    document_id: uuid.UUID
    retrieval_method: str = "semantic"
    source_type: str = "uploaded_document"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DocumentRetrievalService:
    """
    Retrieve semantically similar chunks from a single document.

    Usage::

        results = await retrieval_service.retrieve(
            document_id=doc_id,
            query="What is the payment deadline?",
            top_k=5,
            db=session,
        )
    """

    async def retrieve(
        self,
        document_id: uuid.UUID,
        query: str,
        top_k: int,
        db: AsyncSession,
        provider: Optional[BaseEmbeddingProvider] = None,
    ) -> List[RetrievalResult]:
        """
        Perform semantic similarity search within a single document.

        Args:
            document_id: The document to search.  Chunks outside this document
                         are NEVER returned (enforced at SQL level).
            query:       Natural-language search query.
            top_k:       Maximum number of results to return (1–50).
            db:          Active async database session.
            provider:    Optional embedding provider override (used in tests).

        Returns:
            List of RetrievalResult ordered by descending similarity score.

        Raises:
            ValueError: If query is empty or document does not exist.
            EmbeddingProviderError: If the configured provider cannot produce
                an embedding (e.g. missing credentials, provider not configured).
        """
        query = query.strip()
        if not query:
            raise ValueError("Query must not be empty.")

        top_k = max(1, min(top_k, 50))  # Clamp to [1, 50]

        # Verify the document exists and has not been deleted.
        doc_result = await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
        )
        doc = doc_result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found or has been deleted.")

        # Resolve embedding provider.
        emb_provider = provider or get_embedding_provider()

        # Embed the query using the same provider and model used for indexing.
        query_vector = await emb_provider.embed_text(query)

        # Check if the database supports pgvector (not SQLite test environment).
        try:
            results = await self._vector_search(
                document_id=document_id,
                query_vector=query_vector,
                top_k=top_k,
                db=db,
            )
        except Exception as e:
            # Detect SQLite / missing pgvector — fall back to lexical search.
            err_str = str(e).lower()
            if "vector" in err_str or "no such function" in err_str or "operationalerror" in err_str.lower():
                logger.warning(
                    "pgvector not available (likely SQLite test environment). "
                    "Falling back to lexical search for document %s.", document_id
                )
                results = await self._lexical_search(
                    document_id=document_id,
                    query=query,
                    top_k=top_k,
                    db=db,
                )
            else:
                raise

        return results

    async def _vector_search(
        self,
        document_id: uuid.UUID,
        query_vector: List[float],
        top_k: int,
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """
        pgvector cosine similarity search, STRICTLY filtered by document_id.

        The WHERE clause on document_id is applied in SQL before the ORDER BY
        distance, so only chunks belonging to this document are ever ranked.
        """
        # Build vector literal string for pgvector operators.
        # pgvector expects: '[0.1,0.2,...]'
        vector_str = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"

        # Use pgvector's <=> operator (cosine distance: 0 = identical, 2 = opposite).
        # Similarity score = 1 - distance, clipped to [0, 1].
        sql = text(
            """
            SELECT
                dc.id          AS chunk_id,
                dc.text        AS chunk_text,
                dc.page_number,
                dc.page_id,
                dc.clause_id,
                dc.document_id,
                dc.chunk_metadata,
                1 - (dc.embedding <=> CAST(:vec AS vector)) AS score
            FROM document_chunks dc
            WHERE dc.document_id = :doc_id
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
            """
        )

        rows = await db.execute(
            sql,
            {"vec": vector_str, "doc_id": str(document_id), "top_k": top_k},
        )
        rows = rows.fetchall()

        return [
            RetrievalResult(
                chunk_id=uuid.UUID(str(row.chunk_id)),
                text=row.chunk_text,
                score=float(row.score),
                page_number=row.page_number,
                page_id=uuid.UUID(str(row.page_id)) if row.page_id else None,
                clause_id=uuid.UUID(str(row.clause_id)) if row.clause_id else None,
                clause_number=(row.chunk_metadata or {}).get("clause_number"),
                document_id=uuid.UUID(str(row.document_id)),
                retrieval_method="semantic",
            )
            for row in rows
        ]

    async def _lexical_search(
        self,
        document_id: uuid.UUID,
        query: str,
        top_k: int,
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """
        Simple ILIKE-based lexical fallback when pgvector is not available.

        Used in:
          - Automated tests running on SQLite
          - Development environments without pgvector

        Results are labelled retrieval_method="lexical" so callers know the
        difference.  This is NOT semantic similarity.
        """
        query_terms = [t.strip() for t in query.split() if len(t.strip()) >= 3]

        if not query_terms:
            return []

        # Build a query that scores chunks by keyword hits.
        chunks_result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(200)  # Candidate pool
        )
        chunks = list(chunks_result.scalars().all())

        scored: List[tuple] = []
        for chunk in chunks:
            text_lower = chunk.text.lower()
            hits = sum(1 for term in query_terms if term.lower() in text_lower)
            if hits > 0:
                score = hits / len(query_terms)
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        return [
            RetrievalResult(
                chunk_id=chunk.id,
                text=chunk.text,
                score=float(score),
                page_number=chunk.page_number,
                page_id=chunk.page_id,
                clause_id=chunk.clause_id,
                clause_number=(chunk.chunk_metadata or {}).get("clause_number"),
                document_id=chunk.document_id,
                retrieval_method="lexical",
            )
            for chunk, score in top
        ]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

document_retrieval_service = DocumentRetrievalService()

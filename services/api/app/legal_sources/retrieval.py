"""
Legal source retrieval service for Phase 6 — Verified Legal-Source RAG.

Provides point-in-time version-aware search across authoritative legal sources.
Generates structured citations for every retrieved legal chunk.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.legal_source import (
    LegalSource,
    LegalSourceChunk,
    LegalSourceVersion,
)
from app.rag.embeddings.base import BaseEmbeddingProvider, EmbeddingProviderError
from app.rag.embeddings.factory import get_embedding_provider
from app.schemas.legal_source import LegalCitation, LegalRetrievalResultItem


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """In-memory cosine similarity fallback for SQLite test environments."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class LegalSourceRetrievalService:
    """
    Retrieves relevant statutory sections and legal authority chunks
    with point-in-time version awareness and citation generation.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        self._provider = provider

    def _get_provider(self) -> BaseEmbeddingProvider:
        return self._provider or get_embedding_provider()

    async def retrieve(
        self,
        query: str,
        db: AsyncSession,
        jurisdiction: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        effective_date: Optional[datetime] = None,
        legal_source_id: Optional[uuid.UUID] = None,
        top_k: int = 5,
        provider: Optional[BaseEmbeddingProvider] = None,
    ) -> List[LegalRetrievalResultItem]:
        """
        Search verified legal sources.

        Args:
            query:           Search query or legal proposition.
            db:              Async database session.
            jurisdiction:    Optional jurisdiction filter (e.g. 'India').
            source_types:    List of allowed types (e.g. ['ACT', 'RULE']).
            effective_date:  Point-in-time date for temporal versioning.
            legal_source_id: Specific source filter.
            top_k:           Number of top results to return (1-50).
            provider:        Embedding provider override.
        """
        query = query.strip()
        if not query:
            raise ValueError("Query must not be empty.")

        top_k = max(1, min(top_k, 50))
        emb_provider = provider or self._get_provider()

        # Generate query vector
        query_vector = await emb_provider.embed_text(query)

        # First attempt pgvector search; on SQLite/no-pgvector fall back to in-memory cosine / lexical
        try:
            results = await self._pgvector_search(
                query_vector=query_vector,
                jurisdiction=jurisdiction,
                source_types=source_types,
                effective_date=effective_date,
                legal_source_id=legal_source_id,
                top_k=top_k,
                db=db,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "vector" in err_str or "no such function" in err_str or "operationalerror" in err_str:
                logger.warning(
                    "pgvector not available for legal search (SQLite test environment). Falling back to in-memory cosine search."
                )
                results = await self._fallback_search(
                    query=query,
                    query_vector=query_vector,
                    jurisdiction=jurisdiction,
                    source_types=source_types,
                    effective_date=effective_date,
                    legal_source_id=legal_source_id,
                    top_k=top_k,
                    db=db,
                )
            else:
                raise

        return results

    async def _pgvector_search(
        self,
        query_vector: List[float],
        jurisdiction: Optional[str],
        source_types: Optional[List[str]],
        effective_date: Optional[datetime],
        legal_source_id: Optional[uuid.UUID],
        top_k: int,
        db: AsyncSession,
    ) -> List[LegalRetrievalResultItem]:
        """pgvector cosine distance query with full join and version filtering."""
        vector_str = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"

        # Build dynamic WHERE clause
        conditions = [
            "ls.active = TRUE",
            "lsv.status = 'ACTIVE'",
            "lsc.embedding IS NOT NULL",
        ]
        params: dict[str, Any] = {
            "vec": vector_str,
            "top_k": top_k,
        }

        if jurisdiction:
            conditions.append("ls.jurisdiction = :jurisdiction")
            params["jurisdiction"] = jurisdiction

        if legal_source_id:
            conditions.append("ls.id = :legal_source_id")
            params["legal_source_id"] = str(legal_source_id)

        if source_types:
            placeholders = []
            for idx, st in enumerate(source_types):
                p_name = f"st_{idx}"
                placeholders.append(f":{p_name}")
                params[p_name] = st.upper()
            conditions.append(f"ls.source_type IN ({','.join(placeholders)})")

        if effective_date:
            conditions.append("(lsv.effective_from IS NULL OR lsv.effective_from <= :effective_date)")
            conditions.append("(lsv.effective_to IS NULL OR lsv.effective_to >= :effective_date)")
            params["effective_date"] = effective_date

        where_clause = " AND ".join(conditions)

        raw_sql = f"""
            SELECT
                lsc.id AS chunk_id,
                lsc.text AS source_text,
                lsc.section,
                lsc.subsection,
                lsc.page_or_reference,
                lsv.id AS version_id,
                lsv.version_identifier,
                lsv.effective_from,
                lsv.effective_to,
                lsv.retrieved_at,
                ls.id AS source_id,
                ls.name AS source_name,
                ls.authority,
                ls.source_type,
                ls.official_url,
                1 - (lsc.embedding <=> CAST(:vec AS vector)) AS score
            FROM legal_source_chunks lsc
            JOIN legal_source_versions lsv ON lsc.legal_source_version_id = lsv.id
            JOIN legal_sources ls ON lsv.legal_source_id = ls.id
            WHERE {where_clause}
            ORDER BY lsc.embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """

        rows = (await db.execute(text(raw_sql), params)).fetchall()

        results: List[LegalRetrievalResultItem] = []
        for r in rows:
            clean_sec = re.sub(r"[^A-Za-z0-9]", "", r.section or "sec")[:12]
            citation_id = f"cite-{r.source_type.lower()}-{clean_sec}-{str(r.chunk_id)[:8]}"
            effective_str = r.effective_from.isoformat() if r.effective_from else None

            citation = LegalCitation(
                citation_id=citation_id,
                source_name=r.source_name,
                authority=r.authority,
                source_type=r.source_type,
                section=r.section,
                subsection=r.subsection,
                version=r.version_identifier,
                effective_date=effective_str,
                official_url=r.official_url,
                retrieved_at=r.retrieved_at.isoformat() if hasattr(r.retrieved_at, "isoformat") else str(r.retrieved_at),
            )

            results.append(
                LegalRetrievalResultItem(
                    chunk_id=uuid.UUID(str(r.chunk_id)),
                    legal_source_id=uuid.UUID(str(r.source_id)),
                    legal_source_name=r.source_name,
                    authority=r.authority,
                    source_type=r.source_type,
                    official_url=r.official_url,
                    version_id=uuid.UUID(str(r.version_id)),
                    version_identifier=r.version_identifier,
                    effective_from=r.effective_from,
                    effective_to=r.effective_to,
                    section=r.section,
                    subsection=r.subsection,
                    page_or_reference=r.page_or_reference,
                    source_text=r.source_text,
                    score=float(r.score),
                    retrieval_method="semantic",
                    citation=citation,
                )
            )

        return results

    async def _fallback_search(
        self,
        query: str,
        query_vector: List[float],
        jurisdiction: Optional[str],
        source_types: Optional[List[str]],
        effective_date: Optional[datetime],
        legal_source_id: Optional[uuid.UUID],
        top_k: int,
        db: AsyncSession,
    ) -> List[LegalRetrievalResultItem]:
        """In-memory cosine similarity and lexical search for SQLite testing."""
        stmt = (
            select(LegalSourceChunk)
            .join(LegalSourceVersion)
            .join(LegalSource)
            .options(
                selectinload(LegalSourceChunk.version).selectinload(LegalSourceVersion.source)
            )
            .where(
                LegalSource.active.is_(True),
                LegalSourceVersion.status == "ACTIVE",
            )
        )

        if jurisdiction:
            stmt = stmt.where(LegalSource.jurisdiction == jurisdiction)

        if legal_source_id:
            stmt = stmt.where(LegalSource.id == legal_source_id)

        if source_types:
            stmt = stmt.where(LegalSource.source_type.in_([st.upper() for st in source_types]))

        if effective_date:
            stmt = stmt.where(
                (LegalSourceVersion.effective_from.is_(None) | (LegalSourceVersion.effective_from <= effective_date))
                & (LegalSourceVersion.effective_to.is_(None) | (LegalSourceVersion.effective_to >= effective_date))
            )

        candidates = (await db.execute(stmt)).scalars().all()
        scored: List[Tuple[float, str, LegalSourceChunk]] = []

        query_terms = [t.lower() for t in query.split() if len(t) >= 3]

        for chunk in candidates:
            version = chunk.version
            source = version.source if version else None
            if not source or not source.active:
                continue

            # If embedding exists (stored as JSON array in SQLite)
            if chunk.embedding and isinstance(chunk.embedding, list):
                score = _cosine_similarity(query_vector, chunk.embedding)
                scored.append((score, "semantic", chunk))
            else:
                # Lexical scoring
                text_lower = chunk.text.lower()
                hits = sum(1 for term in query_terms if term in text_lower)
                if hits > 0 or not query_terms:
                    score = hits / max(1, len(query_terms))
                    scored.append((score, "lexical", chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored[:top_k]

        results: List[LegalRetrievalResultItem] = []
        for score, method, chunk in top_matches:
            version = chunk.version
            source = version.source

            clean_sec = re.sub(r"[^A-Za-z0-9]", "", chunk.section or "sec")[:12]
            citation_id = f"cite-{source.source_type.lower()}-{clean_sec}-{str(chunk.id)[:8]}"
            effective_str = version.effective_from.isoformat() if version.effective_from else None

            citation = LegalCitation(
                citation_id=citation_id,
                source_name=source.name,
                authority=source.authority,
                source_type=source.source_type,
                section=chunk.section,
                subsection=chunk.subsection,
                version=version.version_identifier,
                effective_date=effective_str,
                official_url=source.official_url,
                retrieved_at=version.retrieved_at.isoformat() if hasattr(version.retrieved_at, "isoformat") else str(version.retrieved_at),
            )

            results.append(
                LegalRetrievalResultItem(
                    chunk_id=chunk.id,
                    legal_source_id=source.id,
                    legal_source_name=source.name,
                    authority=source.authority,
                    source_type=source.source_type,
                    official_url=source.official_url,
                    version_id=version.id,
                    version_identifier=version.version_identifier,
                    effective_from=version.effective_from,
                    effective_to=version.effective_to,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    page_or_reference=chunk.page_or_reference,
                    source_text=chunk.text,
                    score=float(score),
                    retrieval_method=method,
                    citation=citation,
                )
            )

        return results


legal_source_retrieval_service = LegalSourceRetrievalService()

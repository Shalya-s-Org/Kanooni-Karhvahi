"""
Controlled ingestion service for verified legal sources (Phase 6).

Principles:
  - NO unrestricted web crawling.
  - Curated, explicit ingestion of authoritative sources only.
  - Cryptographic content hash (SHA-256) per version for tamper detection.
  - Structure-aware hierarchy chunking preserving legal numbering.
  - Complete traceability: authority, publication date, effective dates, source URL.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.legal_sources.chunking import LegalSourceChunker, legal_source_chunker
from app.legal_sources.embeddings import LegalSourceEmbeddingService, legal_source_embedding_service
from app.models.legal_source import (
    LegalSource,
    LegalSourceChunk,
    LegalSourceType,
    LegalSourceVersion,
)
from app.schemas.legal_source import LegalSourceIngestRequest, LegalSourceIngestResponse


class LegalSourceIngestionService:
    """
    Manages the controlled ingestion and lifecycle of authoritative legal sources.
    """

    def __init__(
        self,
        chunker: Optional[LegalSourceChunker] = None,
        embedding_service: Optional[LegalSourceEmbeddingService] = None,
    ):
        self.chunker = chunker or legal_source_chunker
        self.embedding_service = embedding_service or legal_source_embedding_service

    async def ingest_source(
        self,
        req: LegalSourceIngestRequest,
        db: AsyncSession,
        generate_embeddings: bool = True,
    ) -> LegalSourceIngestResponse:
        """
        Ingest a new legal source or a new version of an existing source.
        """
        # Validate source type
        allowed_types = {t.value for t in LegalSourceType}
        if req.source_type.upper() not in allowed_types:
            raise ValueError(
                f"Invalid source_type '{req.source_type}'. Must be one of: {sorted(allowed_types)}"
            )

        # 1. Compute SHA-256 content hash
        content_bytes = req.raw_text.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # 2. Check if source already exists by name
        res = await db.execute(
            select(LegalSource).where(LegalSource.name == req.name)
        )
        source = res.scalars().first()

        now = datetime.now(timezone.utc)

        if not source:
            source = LegalSource(
                id=uuid.uuid4(),
                name=req.name,
                source_type=req.source_type.upper(),
                authority=req.authority,
                official_url=req.official_url,
                description=req.description,
                jurisdiction=req.jurisdiction,
                language=req.language,
                active=True,
                trust_level=req.trust_level,
                created_at=now,
                updated_at=now,
            )
            db.add(source)
            await db.flush()
        else:
            # Update authority and URL if changed
            source.authority = req.authority
            source.official_url = req.official_url
            source.updated_at = now

        # 3. Create version record
        version_id = uuid.uuid4()
        version = LegalSourceVersion(
            id=version_id,
            legal_source_id=source.id,
            version_identifier=req.version_identifier,
            effective_from=req.effective_from,
            effective_to=req.effective_to,
            publication_date=req.publication_date,
            retrieved_at=now,
            content_hash=content_hash,
            source_url=req.official_url,
            status="ACTIVE",
            metadata_json=req.metadata,
            created_at=now,
            updated_at=now,
        )
        db.add(version)
        await db.flush()

        # 4. Perform structure-aware chunking
        raw_chunks = self.chunker.chunk_text(req.raw_text)

        # 5. Persist chunk records
        for rc in raw_chunks:
            chunk = LegalSourceChunk(
                id=uuid.uuid4(),
                legal_source_version_id=version_id,
                text=rc.text,
                section=rc.section,
                subsection=rc.subsection,
                page_or_reference=rc.page_or_reference,
                token_count=rc.token_count,
                chunk_index=rc.chunk_index,
                chunk_metadata=rc.metadata,
                embedding=None,
            )
            db.add(chunk)

        await db.flush()

        # 6. Generate embeddings if requested
        embeddings_count = 0
        if generate_embeddings:
            try:
                embeddings_count = await self.embedding_service.embed_version_chunks(
                    version_id=version_id,
                    db=db,
                )
            except Exception as e:
                logger.warning(
                    "Embeddings could not be generated during ingestion of version %s: %s. "
                    "Version remains available for lexical retrieval.",
                    version_id,
                    e,
                )

        await db.commit()

        logger.info(
            "Ingested legal source '%s' (version '%s'): %d chunks created, %d embedded.",
            source.name,
            version.version_identifier,
            len(raw_chunks),
            embeddings_count,
        )

        return LegalSourceIngestResponse(
            legal_source_id=source.id,
            version_id=version_id,
            name=source.name,
            version_identifier=version.version_identifier,
            content_hash=content_hash,
            chunks_created=len(raw_chunks),
            embeddings_generated=embeddings_count,
        )

    async def deactivate_source(self, source_id: uuid.UUID, db: AsyncSession) -> bool:
        """Deactivate a source so it is excluded from future retrieval."""
        res = await db.execute(select(LegalSource).where(LegalSource.id == source_id))
        source = res.scalars().first()
        if not source:
            return False
        source.active = False
        source.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True


legal_source_ingestion_service = LegalSourceIngestionService()

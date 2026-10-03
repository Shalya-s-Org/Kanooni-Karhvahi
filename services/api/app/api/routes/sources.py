"""
Legal Source and Verified Legal-Source RAG routes for Phase 6.

Endpoints:
  - GET  /api/v1/legal-sources            (List curated legal sources)
  - GET  /api/v1/legal-sources/{id}       (Get legal source details)
  - GET  /api/v1/legal-sources/{id}/versions (Get legal source versions)
  - POST /api/v1/legal-sources/retrieve   (Point-in-time semantic/lexical legal retrieval)
  - POST /api/v1/legal-sources/ingest     (Controlled admin ingestion)
"""

from __future__ import annotations

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.database.session import get_db
from app.legal_sources.ingestion import legal_source_ingestion_service
from app.legal_sources.retrieval import legal_source_retrieval_service
from app.models.legal_source import LegalSource, LegalSourceVersion
from app.schemas.base import ApiResponse
from app.schemas.legal_source import (
    LegalSourceDetailResponse,
    LegalSourceIngestRequest,
    LegalSourceIngestResponse,
    LegalSourceResponse,
    LegalSourceRetrieveRequest,
    LegalSourceRetrieveResponse,
    LegalSourceVersionResponse,
)

router = APIRouter(prefix="/legal-sources", tags=["Legal Sources"])


# ---------------------------------------------------------------------------
# Public Catalog & Retrieval
# ---------------------------------------------------------------------------

@router.get("", response_model=ApiResponse[List[LegalSourceResponse]])
async def list_legal_sources(
    jurisdiction: Optional[str] = Query(None, description="Filter by jurisdiction, e.g. 'India'"),
    source_type: Optional[str] = Query(None, description="Filter by source type, e.g. 'ACT'"),
    active_only: bool = Query(True, description="Only return active sources"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[List[LegalSourceResponse]]:
    """
    List curated authoritative legal sources available for grounding and citations.
    """
    stmt = select(LegalSource).offset(offset).limit(limit).order_by(LegalSource.name)

    if active_only:
        stmt = stmt.where(LegalSource.active.is_(True))
    if jurisdiction:
        stmt = stmt.where(LegalSource.jurisdiction == jurisdiction)
    if source_type:
        stmt = stmt.where(LegalSource.source_type == source_type.upper())

    result = await db.execute(stmt)
    sources = list(result.scalars().all())

    data = [LegalSourceResponse.model_validate(s) for s in sources]
    return ApiResponse.ok(data)


@router.get("/{id}", response_model=ApiResponse[LegalSourceDetailResponse])
async def get_legal_source(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LegalSourceDetailResponse]:
    """
    Get full metadata and version list for a legal source.
    """
    stmt = (
        select(LegalSource)
        .where(LegalSource.id == id)
        .options(selectinload(LegalSource.versions))
    )
    result = await db.execute(stmt)
    source = result.scalars().first()

    if not source:
        return ApiResponse.fail(
            code="SOURCE_NOT_FOUND",
            message=f"Legal source with id '{id}' was not found.",
        )

    versions = [LegalSourceVersionResponse.model_validate(v) for v in source.versions]
    data = LegalSourceDetailResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        authority=source.authority,
        official_url=source.official_url,
        description=source.description,
        jurisdiction=source.jurisdiction,
        language=source.language,
        active=source.active,
        trust_level=source.trust_level,
        created_at=source.created_at,
        updated_at=source.updated_at,
        versions=versions,
    )
    return ApiResponse.ok(data)


@router.get("/{id}/versions", response_model=ApiResponse[List[LegalSourceVersionResponse]])
async def get_legal_source_versions(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[List[LegalSourceVersionResponse]]:
    """
    Get historical and active versions for a legal source.
    """
    # Verify source exists
    res = await db.execute(select(LegalSource).where(LegalSource.id == id))
    if not res.scalars().first():
        return ApiResponse.fail(
            code="SOURCE_NOT_FOUND",
            message=f"Legal source with id '{id}' was not found.",
        )

    v_stmt = (
        select(LegalSourceVersion)
        .where(LegalSourceVersion.legal_source_id == id)
        .order_by(LegalSourceVersion.retrieved_at.desc())
    )
    v_res = await db.execute(v_stmt)
    versions = list(v_res.scalars().all())

    data = [LegalSourceVersionResponse.model_validate(v) for v in versions]
    return ApiResponse.ok(data)


@router.post("/retrieve", response_model=ApiResponse[LegalSourceRetrieveResponse])
async def retrieve_legal_sources(
    body: LegalSourceRetrieveRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[LegalSourceRetrieveResponse]:
    """
    Search verified legal sources.
    Respects point-in-time versioning, jurisdiction, and source types.
    Returns ranked excerpts with verifiable citations.
    """
    try:
        results = await legal_source_retrieval_service.retrieve(
            query=body.query,
            db=db,
            jurisdiction=body.jurisdiction,
            source_types=body.source_types,
            effective_date=body.effective_date,
            legal_source_id=body.legal_source_id,
            top_k=body.top_k,
        )
        citations = [r.citation for r in results]
        data = LegalSourceRetrieveResponse(
            query=body.query,
            results=results,
            citations=citations,
        )
        return ApiResponse.ok(data)
    except ValueError as e:
        return ApiResponse.fail(
            code="INVALID_QUERY",
            message=str(e),
        )
    except Exception as e:
        logger.error("Legal retrieval failed: %s", e, exc_info=True)
        return ApiResponse.fail(
            code="LEGAL_RETRIEVAL_FAILED",
            message=f"Failed to retrieve legal sources: {str(e)}",
            retryable=True,
        )


# ---------------------------------------------------------------------------
# Controlled Admin Ingestion (Protected)
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=ApiResponse[LegalSourceIngestResponse])
async def ingest_legal_source(
    body: LegalSourceIngestRequest,
    db: AsyncSession = Depends(get_db),
    x_admin_key: Optional[str] = Header(None),
) -> ApiResponse[LegalSourceIngestResponse]:
    """
    Controlled administrative ingestion endpoint.
    Not exposed to public end-users; requires validation or dev environment.
    """
    expected_key = os.getenv("ADMIN_INGEST_KEY")
    if expected_key and x_admin_key != expected_key:
        return ApiResponse.fail(
            code="UNAUTHORIZED_INGESTION",
            message="Valid administrative authorization required for legal source ingestion.",
        )

    try:
        resp = await legal_source_ingestion_service.ingest_source(
            req=body,
            db=db,
            generate_embeddings=True,
        )
        return ApiResponse.ok(resp)
    except ValueError as e:
        return ApiResponse.fail(
            code="INVALID_SOURCE_DATA",
            message=str(e),
        )
    except Exception as e:
        logger.error("Legal source ingestion failed: %s", e, exc_info=True)
        return ApiResponse.fail(
            code="INGESTION_FAILED",
            message=f"Ingestion failed: {str(e)}",
            retryable=True,
        )

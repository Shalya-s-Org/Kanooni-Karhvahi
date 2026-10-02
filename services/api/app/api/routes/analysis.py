"""
Phase 5 — AI Comprehension analysis routes.

Endpoints:
  POST /analysis/{document_id}/summary          — generate document summary
  GET  /analysis/{document_id}/summary          — retrieve existing summary
  POST /analysis/{document_id}/clauses/{cid}/explain — generate clause explanation
  GET  /analysis/{document_id}/clauses/{cid}/explain — retrieve existing explanation

Design principles:
  - Analysis is on-demand (never auto-generated).
  - Every response carries full source traceability.
  - Provider unavailability is surfaced explicitly, never silenced.
  - Cross-document clause access is blocked at the service layer.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMProviderError
from app.analysis.clause_explanation import clause_explanation_service
from app.analysis.document_summary import document_summary_service
from app.core.logging import logger
from app.database.session import get_db
from app.models.analysis import AnalysisStatus
from app.schemas.analysis import (
    CheckSignalSchema,
    ClauseExplanationResponseData,
    DocumentSummaryResponseData,
    ImportantTermSchema,
    KeyPointSchema,
)
from app.schemas.base import ApiResponse

router = APIRouter(prefix="/analysis", tags=["Analysis"])

# ---------------------------------------------------------------------------
# Safety notice injected into every analysis response.
# ---------------------------------------------------------------------------
_AI_DISCLAIMER = (
    "AI-generated information is based on this document and is not legal advice. "
    "Verify important matters with the relevant official source or a qualified lawyer."
)


# ---------------------------------------------------------------------------
# Document Summary
# ---------------------------------------------------------------------------

@router.post(
    "/{document_id}/summary",
    response_model=ApiResponse[DocumentSummaryResponseData],
    summary="Generate AI Document Summary (Phase 5)",
    description=(
        "Generates an AI-powered plain-language summary of the document. "
        "Every claim is traced to source evidence (page, clause, chunk). "
        "This is not legal advice."
    ),
)
async def generate_document_summary(
    document_id: uuid.UUID,
    response: Response,
    force_regenerate: bool = Query(default=False, description="Re-generate even if a completed summary exists."),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentSummaryResponseData]:
    try:
        analysis = await document_summary_service.generate_summary(
            document_id=document_id,
            db=db,
            force_regenerate=force_regenerate,
        )
        if analysis.status == AnalysisStatus.PROVIDER_UNAVAILABLE:
            return ApiResponse.fail(
                code="AI_PROVIDER_UNAVAILABLE",
                message=analysis.error_message or "AI provider is not configured or unavailable.",
                retryable=True,
            )
        if analysis.status == AnalysisStatus.VALIDATION_FAILED:
            return ApiResponse.fail(
                code="AI_OUTPUT_VALIDATION_FAILED",
                message=analysis.error_message or "AI output failed hallucination guard validation.",
                retryable=False,
            )
        if analysis.status == AnalysisStatus.FAILED:
            return ApiResponse.fail(
                code="ANALYSIS_FAILED",
                message=analysis.error_message or "Document summary generation failed.",
                retryable=True,
            )
        return ApiResponse.ok(data=_summary_to_response(analysis))

    except ValueError as ve:
        msg = str(ve)
        if "not ready" in msg.lower():
            return ApiResponse.fail(
                code="DOCUMENT_NOT_READY",
                message=msg,
                retryable=True,
            )
        if "not found" in msg.lower():
            return ApiResponse.fail(
                code="DOCUMENT_NOT_FOUND",
                message=msg,
                retryable=False,
            )
        return ApiResponse.fail(code="ANALYSIS_ERROR", message=msg, retryable=False)

    except Exception as exc:
        logger.error("Summary generation error for %s: %s", document_id, exc, exc_info=True)
        return ApiResponse.fail(
            code="ANALYSIS_FAILED",
            message="An unexpected error occurred during summary generation.",
            retryable=True,
        )


@router.get(
    "/{document_id}/summary",
    response_model=ApiResponse[DocumentSummaryResponseData],
    summary="Retrieve AI Document Summary",
    description="Returns an existing AI document summary if one has been generated.",
)
async def get_document_summary(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DocumentSummaryResponseData]:
    try:
        analysis = await document_summary_service.get_summary(document_id, db)
        if not analysis:
            return ApiResponse.fail(
                code="ANALYSIS_NOT_FOUND",
                message="No summary has been generated for this document yet. "
                        "Use POST to generate one.",
                retryable=False,
            )
        if analysis.status == AnalysisStatus.PROVIDER_UNAVAILABLE:
            return ApiResponse.fail(
                code="AI_PROVIDER_UNAVAILABLE",
                message=analysis.error_message or "AI provider is not configured or unavailable.",
                retryable=True,
            )
        if analysis.status == AnalysisStatus.VALIDATION_FAILED:
            return ApiResponse.fail(
                code="AI_OUTPUT_VALIDATION_FAILED",
                message=analysis.error_message or "AI output failed verification guard.",
                retryable=False,
            )
        return ApiResponse.ok(data=_summary_to_response(analysis))
    except Exception as exc:
        logger.error("Summary retrieval error for %s: %s", document_id, exc, exc_info=True)
        return ApiResponse.fail(
            code="ANALYSIS_FAILED",
            message="Failed to retrieve document summary.",
            retryable=True,
        )


# ---------------------------------------------------------------------------
# Clause Explanation
# ---------------------------------------------------------------------------

@router.post(
    "/{document_id}/clauses/{clause_id}/explain",
    response_model=ApiResponse[ClauseExplanationResponseData],
    summary="Generate AI Clause Explanation (Phase 5)",
    description=(
        "Generates a plain-language AI explanation of a specific clause. "
        "The original clause text is always preserved alongside the explanation. "
        "This is not legal advice."
    ),
)
async def generate_clause_explanation(
    document_id: uuid.UUID,
    clause_id: uuid.UUID,
    response: Response,
    force_regenerate: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ClauseExplanationResponseData]:
    try:
        analysis = await clause_explanation_service.explain_clause(
            document_id=document_id,
            clause_id=clause_id,
            db=db,
            force_regenerate=force_regenerate,
        )
        if analysis.status == AnalysisStatus.PROVIDER_UNAVAILABLE:
            return ApiResponse.fail(
                code="AI_PROVIDER_UNAVAILABLE",
                message=analysis.error_message or "AI provider is not configured or unavailable.",
                retryable=True,
            )
        if analysis.status == AnalysisStatus.VALIDATION_FAILED:
            return ApiResponse.fail(
                code="AI_OUTPUT_VALIDATION_FAILED",
                message=analysis.error_message or "Clause explanation failed hallucination guard validation.",
                retryable=False,
            )
        if analysis.status == AnalysisStatus.FAILED:
            return ApiResponse.fail(
                code="ANALYSIS_FAILED",
                message=analysis.error_message or "Clause explanation generation failed.",
                retryable=True,
            )

        # Load the clause for original_text in the response.
        from sqlalchemy import select
        from app.models.document import DocumentClause

        clause_result = await db.execute(
            select(DocumentClause).where(
                DocumentClause.id == clause_id,
                DocumentClause.document_id == document_id,
            )
        )
        clause = clause_result.scalars().first()
        return ApiResponse.ok(data=_explanation_to_response(analysis, clause))

    except ValueError as ve:
        msg = str(ve)
        if "not found or does not belong" in msg:
            return ApiResponse.fail(
                code="CLAUSE_DOCUMENT_MISMATCH",
                message=msg,
                retryable=False,
            )
        if "not ready" in msg.lower():
            return ApiResponse.fail(code="DOCUMENT_NOT_READY", message=msg, retryable=True)
        if "not found" in msg.lower():
            return ApiResponse.fail(code="CLAUSE_NOT_FOUND", message=msg, retryable=False)
        return ApiResponse.fail(code="ANALYSIS_ERROR", message=msg, retryable=False)

    except Exception as exc:
        logger.error(
            "Clause explanation error doc=%s clause=%s: %s",
            document_id, clause_id, exc, exc_info=True,
        )
        return ApiResponse.fail(
            code="ANALYSIS_FAILED",
            message="An unexpected error occurred during clause explanation.",
            retryable=True,
        )


@router.get(
    "/{document_id}/clauses/{clause_id}/explain",
    response_model=ApiResponse[ClauseExplanationResponseData],
    summary="Retrieve AI Clause Explanation",
    description="Returns an existing clause explanation if one has been generated.",
)
async def get_clause_explanation(
    document_id: uuid.UUID,
    clause_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ClauseExplanationResponseData]:
    try:
        from sqlalchemy import select
        from app.models.document import DocumentClause

        analysis = await clause_explanation_service.get_explanation(document_id, clause_id, db)
        if not analysis:
            return ApiResponse.fail(
                code="ANALYSIS_NOT_FOUND",
                message="No explanation has been generated for this clause yet. "
                        "Use POST to generate one.",
                retryable=False,
            )
        if analysis.status == AnalysisStatus.PROVIDER_UNAVAILABLE:
            return ApiResponse.fail(
                code="AI_PROVIDER_UNAVAILABLE",
                message=analysis.error_message or "AI provider is not configured or unavailable.",
                retryable=True,
            )
        if analysis.status == AnalysisStatus.VALIDATION_FAILED:
            return ApiResponse.fail(
                code="AI_OUTPUT_VALIDATION_FAILED",
                message=analysis.error_message or "Clause explanation failed verification guard.",
                retryable=False,
            )

        clause_result = await db.execute(
            select(DocumentClause).where(
                DocumentClause.id == clause_id,
                DocumentClause.document_id == document_id,
            )
        )
        clause = clause_result.scalars().first()
        return ApiResponse.ok(data=_explanation_to_response(analysis, clause))
    except Exception as exc:
        logger.error(
            "Clause explanation retrieval error doc=%s clause=%s: %s",
            document_id, clause_id, exc, exc_info=True,
        )
        return ApiResponse.fail(
            code="ANALYSIS_FAILED",
            message="Failed to retrieve clause explanation.",
            retryable=True,
        )


# ---------------------------------------------------------------------------
# Response mappers
# ---------------------------------------------------------------------------

def _summary_to_response(analysis) -> DocumentSummaryResponseData:
    """Map a DocumentAnalysis DB record to the API response schema."""
    out = analysis.output_json or {}

    key_points = [
        KeyPointSchema(
            text=kp.get("text", ""),
            evidence_refs=kp.get("evidence_refs", []),
        )
        for kp in out.get("key_points", [])
    ]
    check_signals = [
        CheckSignalSchema(
            category=cs.get("category", ""),
            message=cs.get("message", ""),
            severity=cs.get("severity", "INFO"),
            evidence_refs=cs.get("evidence_refs", []),
            explanation=cs.get("explanation", ""),
        )
        for cs in out.get("check_signals", [])
    ]

    return DocumentSummaryResponseData(
        analysis_id=analysis.id,
        document_id=analysis.document_id,
        status=analysis.status,
        summary=out.get("summary"),
        purpose=out.get("purpose"),
        document_type=out.get("document_type"),
        key_points=key_points,
        important_dates=out.get("important_dates", []),
        important_amounts=out.get("important_amounts", []),
        important_parties=out.get("important_parties", []),
        obligations=out.get("obligations", []),
        check_signals=check_signals,
        uncertainty_notes=out.get("uncertainty_notes", []),
        evidence_refs=out.get("evidence_refs", []),
        provider=analysis.provider,
        model=analysis.model,
        prompt_version=analysis.prompt_version,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


def _explanation_to_response(analysis, clause=None) -> ClauseExplanationResponseData:
    """Map a ClauseAnalysis DB record to the API response schema."""
    out = analysis.output_json or {}

    important_terms = [
        ImportantTermSchema(
            term=t.get("term", ""),
            explanation=t.get("explanation", ""),
        )
        for t in out.get("important_terms", [])
    ]
    check_signals = [
        CheckSignalSchema(
            category=cs.get("category", ""),
            message=cs.get("message", ""),
            severity=cs.get("severity", "INFO"),
            evidence_refs=cs.get("evidence_refs", []),
            explanation=cs.get("explanation", ""),
        )
        for cs in out.get("check_signals", [])
    ]

    return ClauseExplanationResponseData(
        analysis_id=analysis.id,
        document_id=analysis.document_id,
        clause_id=analysis.clause_id,
        status=analysis.status,
        original_text=clause.original_text if clause else None,
        clause_number=clause.clause_number if clause else None,
        clause_title=clause.title if clause else None,
        page_start=clause.page_start if clause else None,
        plain_meaning=out.get("plain_meaning"),
        why_it_matters=out.get("why_it_matters"),
        important_terms=important_terms,
        obligations=out.get("obligations", []),
        dates=out.get("dates", []),
        amounts=out.get("amounts", []),
        check_signals=check_signals,
        uncertainty_notes=out.get("uncertainty_notes", []),
        evidence_refs=out.get("evidence_refs", []),
        provider=analysis.provider,
        model=analysis.model,
        prompt_version=analysis.prompt_version,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )

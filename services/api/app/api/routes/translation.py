"""
Phase 7 — Translation API Routes

Endpoints:
  GET  /api/v1/translate/languages
       List all supported Indian languages.

  POST /api/v1/translate
       Translate an arbitrary snippet of English legal text.

  POST /api/v1/documents/{document_id}/translate/summary
       Translate a document's AI summary into a target language.
       (Fetches summary from analysis model via DB if available.)

  POST /api/v1/documents/{document_id}/clauses/{clause_id}/translate
       Translate a specific clause's plain-meaning explanation.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query, status

from app.core.logging import logger
from app.schemas.base import ApiResponse
from app.schemas.translation import (
    SupportedLanguageItem,
    SupportedLanguagesResponse,
    TranslationRequest,
    TranslationResponseData,
)
from app.translation.service import SUPPORTED_LANGUAGES, get_translation_service

router = APIRouter(prefix="/translate", tags=["Translation (Phase 7)"])


def _result_to_schema(result) -> TranslationResponseData:
    return TranslationResponseData(
        translation_id=result.translation_id,
        document_id=result.document_id,
        source_language=result.source_language,
        target_language=result.target_language,
        target_language_name=result.target_language_name,
        content_type=result.content_type,
        clause_id=result.clause_id,
        original_text=result.original_text,
        translated_text=result.translated_text,
        preserved_terms=result.preserved_terms,
        provider=result.provider,
        model=result.model,
        created_at=result.created_at,
        status=result.status,
        error_message=result.error_message,
    )


@router.get(
    "/languages",
    response_model=ApiResponse[SupportedLanguagesResponse],
    summary="List supported Indian languages",
)
async def list_supported_languages() -> ApiResponse[SupportedLanguagesResponse]:
    """
    Returns all Indian languages supported for legal document translation.
    """
    items = [
        SupportedLanguageItem(code=code, name=name)
        for code, name in SUPPORTED_LANGUAGES.items()
    ]
    return ApiResponse.ok(SupportedLanguagesResponse(languages=items))


@router.post(
    "",
    response_model=ApiResponse[TranslationResponseData],
    summary="Translate a legal text snippet",
)
async def translate_snippet(body: TranslationRequest) -> ApiResponse[TranslationResponseData]:
    """
    Translate an arbitrary English legal text snippet into an Indian regional language.

    Legal terms (Section numbers, IPC, CrPC, Act names, etc.) are preserved in English.
    """
    if body.target_language not in SUPPORTED_LANGUAGES:
        return ApiResponse.fail(
            code="UNSUPPORTED_LANGUAGE",
            message=(
                f"Language '{body.target_language}' is not supported. "
                f"Supported codes: {sorted(SUPPORTED_LANGUAGES.keys())}."
            ),
            retryable=False,
        )

    service = get_translation_service()
    result = await service.translate_text(
        text=body.text,
        target_language=body.target_language,
        content_type=body.content_type,
    )

    if result.status == "FAILED":
        return ApiResponse.fail(
            code="TRANSLATION_FAILED",
            message=result.error_message or "Translation failed.",
            retryable=True,
        )

    return ApiResponse.ok(_result_to_schema(result))


# ---------------------------------------------------------------------------
# Document-scoped translation router (registered separately in __init__)
# ---------------------------------------------------------------------------

doc_translation_router = APIRouter(
    prefix="/documents/{document_id}",
    tags=["Translation (Phase 7)"],
)


@doc_translation_router.post(
    "/translate/summary",
    response_model=ApiResponse[TranslationResponseData],
    summary="Translate document AI summary",
)
async def translate_document_summary(
    document_id: str,
    target_language: str = Query(..., description="BCP-47 language code, e.g. 'hi', 'ta'."),
    force: bool = Query(False, description="Force re-translation even if cached."),
) -> ApiResponse[TranslationResponseData]:
    """
    Translate the AI-generated document summary into a regional Indian language.

    Requires that a summary has been generated first
    (POST /documents/{id}/summary). Legal terminology is preserved in English.
    """
    if target_language not in SUPPORTED_LANGUAGES:
        return ApiResponse.fail(
            code="UNSUPPORTED_LANGUAGE",
            message=f"Language '{target_language}' is not supported.",
            retryable=False,
        )

    # Attempt to retrieve the existing summary text from the analysis model
    summary_text: Optional[str] = None
    try:
        import uuid as _uuid
        from sqlalchemy import select
        from app.database.session import AsyncSessionLocal
        from app.models.analysis import DocumentAnalysis, AnalysisType, AnalysisStatus

        async with AsyncSessionLocal() as db:
            result_db = await db.execute(
                select(DocumentAnalysis)
                .where(
                    DocumentAnalysis.document_id == _uuid.UUID(document_id),
                    DocumentAnalysis.analysis_type == AnalysisType.DOCUMENT_SUMMARY,
                    DocumentAnalysis.status == AnalysisStatus.COMPLETED,
                )
                .order_by(DocumentAnalysis.created_at.desc())
                .limit(1)
            )
            record = result_db.scalar_one_or_none()
            if record and record.output_data:
                summary_text = record.output_data.get("summary")
    except Exception as exc:
        logger.warning("Could not fetch summary for translation: %s", exc)

    if not summary_text:
        return ApiResponse.fail(
            code="SUMMARY_NOT_FOUND",
            message=(
                "No completed AI summary found for this document. "
                "Generate a summary first (POST /documents/{id}/summary) then translate it."
            ),
            retryable=False,
        )

    service = get_translation_service()
    result = await service.translate_text(
        text=summary_text,
        target_language=target_language,
        document_id=document_id,
        content_type="summary",
        force=force,
    )

    if result.status == "FAILED":
        return ApiResponse.fail(
            code="TRANSLATION_FAILED",
            message=result.error_message or "Translation failed.",
            retryable=True,
        )

    return ApiResponse.ok(_result_to_schema(result))


@doc_translation_router.post(
    "/clauses/{clause_id}/translate",
    response_model=ApiResponse[TranslationResponseData],
    summary="Translate a clause explanation",
)
async def translate_clause_explanation(
    document_id: str,
    clause_id: str,
    target_language: str = Query(..., description="BCP-47 language code, e.g. 'hi', 'ta'."),
    force: bool = Query(False, description="Force re-translation even if cached."),
) -> ApiResponse[TranslationResponseData]:
    """
    Translate the AI-generated plain-language explanation of a specific clause.

    Requires that a clause explanation has already been generated
    (POST /documents/{id}/clauses/{clause_id}/explain).
    """
    if target_language not in SUPPORTED_LANGUAGES:
        return ApiResponse.fail(
            code="UNSUPPORTED_LANGUAGE",
            message=f"Language '{target_language}' is not supported.",
            retryable=False,
        )

    clause_text: Optional[str] = None
    try:
        import uuid as _uuid
        from sqlalchemy import select
        from app.database.session import AsyncSessionLocal
        from app.models.analysis import DocumentAnalysis, AnalysisType, AnalysisStatus

        async with AsyncSessionLocal() as db:
            result_db = await db.execute(
                select(DocumentAnalysis)
                .where(
                    DocumentAnalysis.document_id == _uuid.UUID(document_id),
                    DocumentAnalysis.analysis_type == AnalysisType.CLAUSE_EXPLANATION,
                    DocumentAnalysis.status == AnalysisStatus.COMPLETED,
                )
                .order_by(DocumentAnalysis.created_at.desc())
                .limit(1)
            )
            record = result_db.scalar_one_or_none()
            if record and record.output_data:
                clause_text = record.output_data.get("plain_meaning")
    except Exception as exc:
        logger.warning("Could not fetch clause explanation for translation: %s", exc)

    if not clause_text:
        return ApiResponse.fail(
            code="CLAUSE_EXPLANATION_NOT_FOUND",
            message=(
                "No completed clause explanation found. "
                "Generate it first (POST /documents/{id}/clauses/{clause_id}/explain) then translate."
            ),
            retryable=False,
        )

    service = get_translation_service()
    result = await service.translate_text(
        text=clause_text,
        target_language=target_language,
        document_id=document_id,
        content_type="clause",
        clause_id=clause_id,
        force=force,
    )

    if result.status == "FAILED":
        return ApiResponse.fail(
            code="TRANSLATION_FAILED",
            message=result.error_message or "Translation failed.",
            retryable=True,
        )

    return ApiResponse.ok(_result_to_schema(result))

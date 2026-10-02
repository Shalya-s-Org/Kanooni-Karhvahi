"""
Document summary generation service — Phase 5.

Orchestrates the full evidence → LLM → validation → persistence pipeline
for document-level AI summaries.

The document must be in READY or READY_WITHOUT_EMBEDDINGS status.
AI comprehension is invoked on-demand (not automatically after upload).

Summary lifecycle
-----------------
PENDING → GENERATING → COMPLETED
                     ↘ VALIDATION_FAILED
                     ↘ FAILED
                     ↘ PROVIDER_UNAVAILABLE
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_document_summary_prompt,
)
from app.ai.providers.base import LLMProviderError, LLMOutputParseError
from app.ai.providers.factory import get_llm_provider
from app.ai.structured_output.schemas import (
    DOCUMENT_SUMMARY_JSON_SCHEMA,
    DocumentSummaryOutput,
)
from app.analysis.evidence import EvidencePack, evidence_pack_builder
from app.analysis.guard import hallucination_guard
from app.core.config import settings
from app.core.logging import logger
from app.models.analysis import AnalysisStatus, AnalysisType, DocumentAnalysis
from app.models.document import Document

# Statuses that allow generating a summary.
READY_STATUSES = {"READY", "READY_WITHOUT_EMBEDDINGS"}


class DocumentSummaryService:
    """
    Generates and persists AI document summaries.

    Usage::

        service = DocumentSummaryService()
        analysis = await service.generate_summary(document_id, db)
    """

    async def generate_summary(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
        force_regenerate: bool = False,
    ) -> DocumentAnalysis:
        """
        Generate (or retrieve existing) AI summary for a document.

        Args:
            document_id:       Target document UUID.
            db:                Active async session.
            force_regenerate:  If True, overwrites any existing COMPLETED analysis.

        Returns:
            DocumentAnalysis record with status COMPLETED (or FAILED/*).

        Raises:
            ValueError: If the document does not exist or is not yet ready.
        """
        # 1. Verify document exists and is in a ready state.
        doc = await self._get_ready_document(document_id, db)

        # 2. Return cached analysis if available (and not forced).
        if not force_regenerate:
            existing = await self._get_existing_summary(document_id, db)
            if existing and existing.status == AnalysisStatus.COMPLETED:
                logger.info("Returning cached summary for document %s", document_id)
                return existing

        # 3. Create or update the analysis record.
        analysis = await self._upsert_analysis_record(document_id, db)

        try:
            # 4. Set status to GENERATING and commit.
            analysis.status = AnalysisStatus.GENERATING
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 5. Resolve LLM provider — fail early if not configured.
            try:
                provider = get_llm_provider()
            except LLMProviderError as exc:
                logger.warning("LLM provider unavailable for document %s: %s", document_id, exc)
                return await self._fail_analysis(
                    analysis, AnalysisStatus.PROVIDER_UNAVAILABLE, str(exc), db
                )

            # 6. Build evidence pack.
            pack = await evidence_pack_builder.build_for_document(document_id, db)

            # 7. Build prompt.
            prompt = build_document_summary_prompt(
                document_filename=doc.original_filename,
                document_type=pack.document_type,
                evidence_items=pack.to_list_of_dicts(),
                total_pages=pack.total_pages,
                is_evidence_partial=pack.is_partial,
            )

            # 8. Call LLM.
            try:
                raw_output = await provider.generate_structured(
                    prompt=prompt,
                    schema=DOCUMENT_SUMMARY_JSON_SCHEMA,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
            except LLMOutputParseError as exc:
                logger.error("LLM output parse error for document %s: %s", document_id, exc)
                return await self._fail_analysis(
                    analysis, AnalysisStatus.VALIDATION_FAILED, str(exc), db
                )
            except LLMProviderError as exc:
                logger.error("LLM provider error for document %s: %s", document_id, exc)
                return await self._fail_analysis(
                    analysis, AnalysisStatus.PROVIDER_UNAVAILABLE, str(exc), db
                )

            # 9. Stamp provider/model into raw output before validation.
            raw_output["provider"] = provider.provider_name
            raw_output["model"] = provider.model_name

            # 10. Validate with hallucination guard.
            guard_result = hallucination_guard.validate_summary(
                raw_output, pack.valid_ids
            )
            if not guard_result.passed:
                errors_str = "; ".join(guard_result.errors)
                logger.warning(
                    "Hallucination guard failed for document %s: %s",
                    document_id,
                    errors_str,
                )
                return await self._fail_analysis(
                    analysis, AnalysisStatus.VALIDATION_FAILED, errors_str, db
                )

            validated: DocumentSummaryOutput = guard_result.sanitised_output

            # 11. Persist.
            analysis.status = AnalysisStatus.COMPLETED
            analysis.output_json = validated.model_dump()
            analysis.evidence_json = pack.to_list_of_dicts()
            analysis.provider = provider.provider_name
            analysis.model = provider.model_name
            analysis.prompt_version = settings.AI_PROMPT_VERSION
            analysis.error_message = None
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(analysis)
            logger.info("Document summary completed for %s", document_id)
            return analysis

        except Exception as exc:
            logger.error(
                "Unexpected error generating summary for document %s: %s",
                document_id,
                exc,
                exc_info=True,
            )
            return await self._fail_analysis(
                analysis, AnalysisStatus.FAILED, str(exc), db
            )

    async def get_summary(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[DocumentAnalysis]:
        """Retrieve an existing summary without regenerating."""
        return await self._get_existing_summary(document_id, db)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_ready_document(
        self, document_id: uuid.UUID, db: AsyncSession
    ) -> Document:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")
        if doc.status not in READY_STATUSES:
            raise ValueError(
                f"Document {document_id} is not ready for analysis "
                f"(current status: {doc.status})."
            )
        return doc

    async def _get_existing_summary(
        self, document_id: uuid.UUID, db: AsyncSession
    ) -> Optional[DocumentAnalysis]:
        result = await db.execute(
            select(DocumentAnalysis).where(
                DocumentAnalysis.document_id == document_id,
                DocumentAnalysis.analysis_type == AnalysisType.DOCUMENT_SUMMARY,
            )
        )
        return result.scalars().first()

    async def _upsert_analysis_record(
        self, document_id: uuid.UUID, db: AsyncSession
    ) -> DocumentAnalysis:
        """Get existing record or create new PENDING one."""
        existing = await self._get_existing_summary(document_id, db)
        if existing:
            # Reset for regeneration.
            existing.status = AnalysisStatus.PENDING
            existing.output_json = None
            existing.evidence_json = None
            existing.error_message = None
            existing.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return existing

        now = datetime.now(timezone.utc)
        analysis = DocumentAnalysis(
            id=uuid.uuid4(),
            document_id=document_id,
            analysis_type=AnalysisType.DOCUMENT_SUMMARY,
            status=AnalysisStatus.PENDING,
            prompt_version=settings.AI_PROMPT_VERSION,
            created_at=now,
            updated_at=now,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis

    async def _fail_analysis(
        self,
        analysis: DocumentAnalysis,
        status: str,
        error_message: str,
        db: AsyncSession,
    ) -> DocumentAnalysis:
        analysis.status = status
        analysis.error_message = error_message[:1000]  # Cap length
        analysis.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(analysis)
        return analysis


document_summary_service = DocumentSummaryService()

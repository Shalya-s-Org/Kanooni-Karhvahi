"""
Clause explanation generation service — Phase 5.

Generates and persists AI explanations for individual document clauses.

Security invariant: clause_id is always validated against document_id at
the database level.  A caller cannot explain a clause from a different
document by manipulating IDs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_clause_explanation_prompt,
)
from app.ai.providers.base import LLMOutputParseError, LLMProviderError
from app.ai.providers.factory import get_llm_provider
from app.ai.structured_output.schemas import (
    CLAUSE_EXPLANATION_JSON_SCHEMA,
    ClauseExplanationOutput,
)
from app.analysis.evidence import evidence_pack_builder
from app.analysis.guard import hallucination_guard
from app.core.config import settings
from app.core.logging import logger
from app.models.analysis import AnalysisStatus, ClauseAnalysis
from app.models.document import Document, DocumentClause

READY_STATUSES = {"READY", "READY_WITHOUT_EMBEDDINGS"}


class ClauseExplanationService:
    """
    Generates and persists AI clause explanations.

    Usage::

        service = ClauseExplanationService()
        analysis = await service.explain_clause(document_id, clause_id, db)
    """

    async def explain_clause(
        self,
        document_id: uuid.UUID,
        clause_id: uuid.UUID,
        db: AsyncSession,
        force_regenerate: bool = False,
    ) -> ClauseAnalysis:
        """
        Generate (or retrieve existing) AI explanation for a clause.

        Security: clause_id is verified to belong to document_id in the DB.
        A CLAUSE_DOCUMENT_MISMATCH error is raised if they don't match.

        Args:
            document_id:      Parent document UUID.
            clause_id:        Target clause UUID.
            db:               Active async session.
            force_regenerate: If True, overwrites any existing COMPLETED analysis.

        Returns:
            ClauseAnalysis record.
        """
        # 1. Verify document is ready.
        doc = await self._get_ready_document(document_id, db)

        # 2. Verify clause belongs to document.
        clause = await self._get_clause(document_id, clause_id, db)

        # 3. Return cached if available.
        if not force_regenerate:
            existing = await self._get_existing(document_id, clause_id, db)
            if existing and existing.status == AnalysisStatus.COMPLETED:
                logger.info("Returning cached explanation for clause %s", clause_id)
                return existing

        # 4. Upsert analysis record.
        analysis = await self._upsert_record(document_id, clause_id, db)

        try:
            # 5. GENERATING
            analysis.status = AnalysisStatus.GENERATING
            analysis.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 6. Resolve provider.
            try:
                provider = get_llm_provider()
            except LLMProviderError as exc:
                logger.warning("LLM provider unavailable for clause %s: %s", clause_id, exc)
                return await self._fail(analysis, AnalysisStatus.PROVIDER_UNAVAILABLE, str(exc), db)

            # 7. Build evidence pack for this clause.
            pack = await evidence_pack_builder.build_for_clause(document_id, clause_id, db)

            # 8. Build prompt.
            prompt = build_clause_explanation_prompt(
                clause_number=clause.clause_number,
                clause_title=clause.title,
                clause_text=clause.original_text,
                page_number=clause.page_start,
                evidence_items=pack.to_list_of_dicts(),
                document_type=pack.document_type,
            )

            # 9. Call LLM.
            try:
                raw_output = await provider.generate_structured(
                    prompt=prompt,
                    schema=CLAUSE_EXPLANATION_JSON_SCHEMA,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
            except LLMOutputParseError as exc:
                return await self._fail(analysis, AnalysisStatus.VALIDATION_FAILED, str(exc), db)
            except LLMProviderError as exc:
                return await self._fail(analysis, AnalysisStatus.PROVIDER_UNAVAILABLE, str(exc), db)

            # 10. Stamp provenance.
            raw_output["provider"] = provider.provider_name
            raw_output["model"] = provider.model_name

            # 11. Validate with guard.
            guard_result = hallucination_guard.validate_clause_explanation(
                raw_output, pack.valid_ids
            )
            if not guard_result.passed:
                errors_str = "; ".join(guard_result.errors)
                logger.warning("Guard failed for clause %s: %s", clause_id, errors_str)
                return await self._fail(analysis, AnalysisStatus.VALIDATION_FAILED, errors_str, db)

            validated: ClauseExplanationOutput = guard_result.sanitised_output

            # 12. Persist.
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
            logger.info("Clause explanation completed for %s", clause_id)
            return analysis

        except Exception as exc:
            logger.error(
                "Unexpected error explaining clause %s: %s", clause_id, exc, exc_info=True
            )
            return await self._fail(analysis, AnalysisStatus.FAILED, str(exc), db)

    async def get_explanation(
        self,
        document_id: uuid.UUID,
        clause_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[ClauseAnalysis]:
        """Retrieve existing explanation without regenerating."""
        return await self._get_existing(document_id, clause_id, db)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_ready_document(self, document_id: uuid.UUID, db: AsyncSession) -> Document:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")
        if doc.status not in READY_STATUSES:
            raise ValueError(
                f"Document {document_id} is not ready (status: {doc.status})."
            )
        return doc

    async def _get_clause(
        self, document_id: uuid.UUID, clause_id: uuid.UUID, db: AsyncSession
    ) -> DocumentClause:
        result = await db.execute(
            select(DocumentClause).where(
                DocumentClause.id == clause_id,
                DocumentClause.document_id == document_id,
            )
        )
        clause = result.scalars().first()
        if not clause:
            raise ValueError(
                f"Clause {clause_id} not found or does not belong to document {document_id}."
            )
        return clause

    async def _get_existing(
        self, document_id: uuid.UUID, clause_id: uuid.UUID, db: AsyncSession
    ) -> Optional[ClauseAnalysis]:
        result = await db.execute(
            select(ClauseAnalysis).where(
                ClauseAnalysis.document_id == document_id,
                ClauseAnalysis.clause_id == clause_id,
            )
        )
        return result.scalars().first()

    async def _upsert_record(
        self, document_id: uuid.UUID, clause_id: uuid.UUID, db: AsyncSession
    ) -> ClauseAnalysis:
        existing = await self._get_existing(document_id, clause_id, db)
        if existing:
            existing.status = AnalysisStatus.PENDING
            existing.output_json = None
            existing.evidence_json = None
            existing.error_message = None
            existing.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return existing

        now = datetime.now(timezone.utc)
        analysis = ClauseAnalysis(
            id=uuid.uuid4(),
            document_id=document_id,
            clause_id=clause_id,
            status=AnalysisStatus.PENDING,
            prompt_version=settings.AI_PROMPT_VERSION,
            created_at=now,
            updated_at=now,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis

    async def _fail(
        self,
        analysis: ClauseAnalysis,
        status: str,
        error_message: str,
        db: AsyncSession,
    ) -> ClauseAnalysis:
        analysis.status = status
        analysis.error_message = error_message[:1000]
        analysis.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(analysis)
        return analysis


clause_explanation_service = ClauseExplanationService()

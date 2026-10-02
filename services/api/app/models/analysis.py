"""
Phase 5 — AI Comprehension analysis persistence models.

DocumentAnalysis  — stores one generated AI summary per document.
ClauseAnalysis    — stores one AI explanation per clause.

Both models cascade-delete with their parent document so that the
24-hour TTL purge removes all AI-generated content automatically.
Neither model stores API credentials, raw embeddings, or the
document's binary content — only the structured JSON output and
the evidence snapshot used to generate it.

Analysis lifecycle states
-------------------------
PENDING           — record created, generation not yet started
GENERATING        — LLM call in progress
COMPLETED         — validated output stored in output_json
VALIDATION_FAILED — output failed hallucination/schema guard
FAILED            — unexpected error during generation
PROVIDER_UNAVAILABLE — LLM provider not configured or no credentials
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# ---------------------------------------------------------------------------
# Analysis status constants (string literals, not Enum, for SQLite compat)
# ---------------------------------------------------------------------------

class AnalysisStatus:
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    FAILED = "FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class AnalysisType:
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    CLAUSE_EXPLANATION = "CLAUSE_EXPLANATION"


# ---------------------------------------------------------------------------
# DocumentAnalysis
# ---------------------------------------------------------------------------

class DocumentAnalysis(Base):
    """
    Persists one AI-generated document summary per document.

    The ``output_json`` column holds a validated ``DocumentSummaryOutput``
    instance serialised to JSON.  The ``evidence_json`` column stores the
    evidence snapshot that was submitted to the LLM so that audits can
    verify the provenance of every generated claim.

    ``prompt_version`` allows regeneration when prompts change without
    invalidating the schema of older analyses.
    """

    __tablename__ = "document_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=AnalysisType.DOCUMENT_SUMMARY,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AnalysisStatus.PENDING,
        index=True,
    )
    # Validated structured output from the LLM (DocumentSummaryOutput JSON).
    output_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # Evidence snapshot submitted to the LLM.
    evidence_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # Provider / model metadata for reproducibility and auditing.
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Optional diagnostics (never contains sensitive user data).
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(  # type: ignore[name-defined]
        "Document",
        back_populates="analyses",
    )


# ---------------------------------------------------------------------------
# ClauseAnalysis
# ---------------------------------------------------------------------------

class ClauseAnalysis(Base):
    """
    Persists one AI-generated clause explanation per clause.

    ``output_json`` holds a validated ``ClauseExplanationOutput`` instance.
    The original clause text is NOT duplicated here — callers must join to
    ``DocumentClause`` to retrieve ``original_text``.

    The ``document_id`` column is denormalised (redundant with
    ``clause.document_id``) for fast index-based isolation: every query
    that accesses a ClauseAnalysis can assert ``document_id = :doc_id``
    without an extra JOIN.
    """

    __tablename__ = "clause_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clause_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_clauses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AnalysisStatus.PENDING,
        index=True,
    )
    output_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(  # type: ignore[name-defined]
        "Document",
        back_populates="clause_analyses",
    )
    clause: Mapped["DocumentClause"] = relationship(  # type: ignore[name-defined]
        "DocumentClause",
        back_populates="analyses",
    )

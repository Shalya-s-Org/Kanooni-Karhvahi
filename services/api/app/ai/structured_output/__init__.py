"""
Phase 5 — Structured Pydantic output schemas for AI-generated legal analysis.

Every LLM response is validated against these schemas before being stored
or returned to the client.  A response that fails validation is rejected
and the analysis is marked VALIDATION_FAILED rather than silently accepted.

Key design invariants:
  - Every factual claim carries at least one evidence_ref.
  - provider and model fields trace which AI system produced the output.
  - Check signals use conservative severity levels (INFO / ATTENTION / HIGH_ATTENTION).
  - uncertainty_notes explicitly surfaces what the AI could not determine.
"""

from app.ai.structured_output.schemas import (
    CheckSignal,
    CheckSignalSeverity,
    EvidenceRef,
    KeyPoint,
    ImportantTerm,
    DocumentSummaryOutput,
    ClauseExplanationOutput,
    DOCUMENT_SUMMARY_JSON_SCHEMA,
    CLAUSE_EXPLANATION_JSON_SCHEMA,
)

__all__ = [
    "CheckSignal",
    "CheckSignalSeverity",
    "EvidenceRef",
    "KeyPoint",
    "ImportantTerm",
    "DocumentSummaryOutput",
    "ClauseExplanationOutput",
    "DOCUMENT_SUMMARY_JSON_SCHEMA",
    "CLAUSE_EXPLANATION_JSON_SCHEMA",
]

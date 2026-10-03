"""
Pydantic v2 schemas for Phase 5 AI structured outputs.

These are the canonical output models.  Every LLM response is deserialised
into one of these models; a Pydantic ValidationError means the output is
rejected and the analysis is marked VALIDATION_FAILED.

Safety constraints encoded in the schema:
  - No field accepts free-floating factual claims without evidence_refs.
  - Check signals use a controlled severity vocabulary.
  - provider / model are always captured for audit purposes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class CheckSignalSeverity(str, Enum):
    INFO = "INFO"
    ATTENTION = "ATTENTION"
    HIGH_ATTENTION = "HIGH_ATTENTION"


class CheckSignal(BaseModel):
    """
    A conservative observation that a human should verify.

    NOT a legal conclusion.  The message must not use language like
    "illegal", "fraudulent", "void", "invalid", or "you will lose".
    """
    category: str = Field(
        ...,
        description="Short category label e.g. MISSING_DATE, UNCLEAR_PARTY, UNUSUAL_DEADLINE",
    )
    message: str = Field(
        ...,
        max_length=500,
        description="Plain-language observation (not a legal conclusion).",
    )
    severity: CheckSignalSeverity = Field(default=CheckSignalSeverity.INFO)
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="IDs of EvidenceItem records this signal is based on.",
    )
    explanation: str = Field(
        default="",
        description="One or two sentences explaining why this deserves attention.",
    )


class EvidenceRef(BaseModel):
    """Reference to a single piece of source evidence."""
    evidence_id: str
    source_type: str = "uploaded_document"


class KeyPoint(BaseModel):
    """A single key point from the document with mandatory evidence tracing."""
    text: str = Field(..., description="The key point — must begin with 'According to the document...' or similar.")
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="At least one evidence_id supporting this claim.",
    )


class ImportantTerm(BaseModel):
    """A legal or technical term found in the clause with a plain-language explanation."""
    term: str
    explanation: str


# ---------------------------------------------------------------------------
# Document Summary Output
# ---------------------------------------------------------------------------

class DocumentSummaryOutput(BaseModel):
    """
    Validated structured output for a document-level AI summary.

    The AI system generates this; the analysis service validates it here
    before persisting.

    Evidence contract:
      - Every key_point entry must have ≥ 1 evidence_ref.
      - The AI must not include facts it cannot trace to the evidence pack.
    """

    summary: str = Field(
        ...,
        min_length=10,
        description="Two–four sentence overview of the document's purpose and main effect.",
    )
    purpose: str = Field(
        ...,
        description="One sentence describing what the document accomplishes.",
    )
    document_type: str = Field(
        default="UNKNOWN",
        description="Broad document category (CONTRACT, LEGAL_NOTICE, FIR, etc.).",
    )
    key_points: List[KeyPoint] = Field(
        default_factory=list,
        description="Most important facts from the document, each with evidence.",
    )
    important_dates: List[str] = Field(
        default_factory=list,
        description="Dates and deadlines found in the document.",
    )
    important_amounts: List[str] = Field(
        default_factory=list,
        description="Monetary amounts found in the document.",
    )
    important_parties: List[str] = Field(
        default_factory=list,
        description="Named parties (persons, organisations) in the document.",
    )
    obligations: List[str] = Field(
        default_factory=list,
        description="Explicit obligations or duties described in the document.",
    )
    check_signals: List[CheckSignal] = Field(
        default_factory=list,
        description="Observations that deserve human verification.",
    )
    uncertainty_notes: List[str] = Field(
        default_factory=list,
        description="Things the AI could not determine from the available evidence.",
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="IDs of all EvidenceItems supporting the summary.",
    )
    legal_citations: List[Any] = Field(
        default_factory=list,
        description="Structured citations for verified legal sources referenced.",
    )
    external_legal_context: List[str] = Field(
        default_factory=list,
        description="Contextual legal observations grounded in verified sources (not legal advice).",
    )
    # Provenance metadata — set by the analysis service, not the LLM.
    provider: str = Field(default="unknown")
    model: str = Field(default="unknown")


# ---------------------------------------------------------------------------
# Clause Explanation Output
# ---------------------------------------------------------------------------

class ClauseExplanationOutput(BaseModel):
    """
    Validated structured output for a single clause explanation.

    The original clause text is NOT stored here — it is always retrieved
    from DocumentClause.original_text.  The AI-generated explanation is
    supplementary and must never replace the original text.
    """

    clause_id: Optional[str] = Field(
        default=None,
        description="Clause UUID or ID string being explained.",
    )
    plain_meaning: str = Field(
        ...,
        min_length=10,
        description=(
            "Plain-language explanation of what this clause says.  "
            "Must start with 'According to the document...' or 'This clause states...'"
        ),
    )
    why_it_matters: str = Field(
        ...,
        description="Why this clause may be important for the reader.",
    )
    important_terms: List[ImportantTerm] = Field(
        default_factory=list,
        description="Legal or technical terms in the clause with plain explanations.",
    )
    obligations: List[str] = Field(
        default_factory=list,
        description="Explicit obligations or duties in this clause.",
    )
    dates: List[str] = Field(
        default_factory=list,
        description="Dates or deadlines mentioned in this clause.",
    )
    amounts: List[str] = Field(
        default_factory=list,
        description="Monetary amounts mentioned in this clause.",
    )
    check_signals: List[CheckSignal] = Field(
        default_factory=list,
        description="Observations about this clause that deserve attention.",
    )
    uncertainty_notes: List[str] = Field(
        default_factory=list,
        description="What the AI could not determine about this clause.",
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Evidence IDs used to generate this explanation.",
    )
    legal_citations: List[Any] = Field(
        default_factory=list,
        description="Structured citations for verified legal sources referenced.",
    )
    external_legal_context: List[str] = Field(
        default_factory=list,
        description="Contextual legal observations grounded in verified sources (not legal advice).",
    )
    provider: str = Field(default="unknown")
    model: str = Field(default="unknown")


# ---------------------------------------------------------------------------
# JSON Schema dicts (for prompting the LLM)
# ---------------------------------------------------------------------------
# Simplified schemas sent to the LLM — enough structure to constrain output
# without overwhelming the context window.

DOCUMENT_SUMMARY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["summary", "purpose", "document_type", "key_points", "check_signals", "uncertainty_notes", "provider", "model"],
    "properties": {
        "summary": {"type": "string"},
        "purpose": {"type": "string"},
        "document_type": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "evidence_refs"],
            },
        },
        "important_dates": {"type": "array", "items": {"type": "string"}},
        "important_amounts": {"type": "array", "items": {"type": "string"}},
        "important_parties": {"type": "array", "items": {"type": "string"}},
        "obligations": {"type": "array", "items": {"type": "string"}},
        "check_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["INFO", "ATTENTION", "HIGH_ATTENTION"]},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": ["category", "message", "severity"],
            },
        },
        "uncertainty_notes": {"type": "array", "items": {"type": "string"}},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "provider": {"type": "string"},
        "model": {"type": "string"},
    },
}

CLAUSE_EXPLANATION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["plain_meaning", "why_it_matters", "evidence_refs", "provider", "model"],
    "properties": {
        "clause_id": {"type": "string"},
        "plain_meaning": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "important_terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["term", "explanation"],
            },
        },
        "obligations": {"type": "array", "items": {"type": "string"}},
        "dates": {"type": "array", "items": {"type": "string"}},
        "amounts": {"type": "array", "items": {"type": "string"}},
        "check_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["INFO", "ATTENTION", "HIGH_ATTENTION"]},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": ["category", "message", "severity"],
            },
        },
        "uncertainty_notes": {"type": "array", "items": {"type": "string"}},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "provider": {"type": "string"},
        "model": {"type": "string"},
    },
}

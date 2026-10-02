"""
Phase 5 — API-layer Pydantic schemas for analysis endpoints.

These schemas translate between the database/service layer and the JSON
response sent to clients.  They do NOT expose raw LLM output; they present
a clean, validated representation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------

class CheckSignalSchema(BaseModel):
    category: str
    message: str
    severity: str  # INFO | ATTENTION | HIGH_ATTENTION
    evidence_refs: List[str] = Field(default_factory=list)
    explanation: str = ""


class KeyPointSchema(BaseModel):
    text: str
    evidence_refs: List[str] = Field(default_factory=list)


class ImportantTermSchema(BaseModel):
    term: str
    explanation: str


class EvidenceItemSchema(BaseModel):
    """Compact evidence reference for frontend display."""
    evidence_id: str
    source_type: str
    page_number: int
    source_text: str
    clause_number: Optional[str] = None
    clause_id: Optional[UUID] = None
    chunk_id: Optional[UUID] = None


# ---------------------------------------------------------------------------
# Document Summary
# ---------------------------------------------------------------------------

class DocumentSummaryResponseData(BaseModel):
    """Response data for GET/POST /documents/{id}/summary."""
    analysis_id: UUID
    document_id: UUID
    status: str
    # Present only when status == COMPLETED
    summary: Optional[str] = None
    purpose: Optional[str] = None
    document_type: Optional[str] = None
    key_points: List[KeyPointSchema] = Field(default_factory=list)
    important_dates: List[str] = Field(default_factory=list)
    important_amounts: List[str] = Field(default_factory=list)
    important_parties: List[str] = Field(default_factory=list)
    obligations: List[str] = Field(default_factory=list)
    check_signals: List[CheckSignalSchema] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Clause Explanation
# ---------------------------------------------------------------------------

class ClauseExplanationResponseData(BaseModel):
    """Response data for GET/POST /documents/{doc_id}/clauses/{clause_id}/explain."""
    analysis_id: UUID
    document_id: UUID
    clause_id: UUID
    status: str
    # Original clause — always present (fetched from DocumentClause, not AI output)
    original_text: Optional[str] = None
    clause_number: Optional[str] = None
    clause_title: Optional[str] = None
    page_start: Optional[int] = None
    # AI-generated fields — present only when status == COMPLETED
    plain_meaning: Optional[str] = None
    why_it_matters: Optional[str] = None
    important_terms: List[ImportantTermSchema] = Field(default_factory=list)
    obligations: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    check_signals: List[CheckSignalSchema] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

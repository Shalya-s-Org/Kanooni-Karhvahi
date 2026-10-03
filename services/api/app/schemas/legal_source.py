"""
Pydantic v2 schemas for Legal Sources and Verified Legal-Source RAG (Phase 6).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LegalCitation(BaseModel):
    """
    Structured legal citation required for every external legal claim.
    Provides complete auditability back to official source and version.
    """
    model_config = ConfigDict(from_attributes=True)

    citation_id: str = Field(
        ...,
        description="Unique reference identifier used in AI responses (e.g. 'cite-act-sec73-a1b2c3d4')",
    )
    source_name: str = Field(
        ...,
        description="Official title of the statute, court judgment, or regulation",
    )
    authority: str = Field(
        ...,
        description="Promulgating body e.g. 'Parliament of India', 'Supreme Court of India'",
    )
    source_type: str = Field(
        ...,
        description="ACT | RULE | REGULATION | OFFICIAL_NOTIFICATION | COURT_JUDGMENT | etc.",
    )
    section: Optional[str] = Field(
        default=None,
        description="Numbered section or article, e.g. 'Section 73', 'Article 21'",
    )
    subsection: Optional[str] = Field(
        default=None,
        description="Subsection or clause, e.g. '(1)', '(2)(a)'",
    )
    version: str = Field(
        ...,
        description="Version identifier e.g. '1872-orig', '2015-amendment'",
    )
    effective_date: Optional[str] = Field(
        default=None,
        description="Effective date string if known",
    )
    official_url: str = Field(
        ...,
        description="Verifiable official portal URL",
    )
    retrieved_at: str = Field(
        ...,
        description="ISO timestamp when the source was retrieved/indexed",
    )


class LegalSourceVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legal_source_id: uuid.UUID
    version_identifier: str
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    publication_date: Optional[datetime] = None
    retrieved_at: datetime
    content_hash: str
    source_url: str
    status: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class LegalSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_type: str
    authority: str
    official_url: str
    description: Optional[str] = None
    jurisdiction: str
    language: str
    active: bool
    trust_level: str
    created_at: datetime
    updated_at: datetime


class LegalSourceDetailResponse(LegalSourceResponse):
    versions: List[LegalSourceVersionResponse] = Field(default_factory=list)


class LegalRetrievalResultItem(BaseModel):
    chunk_id: uuid.UUID
    legal_source_id: uuid.UUID
    legal_source_name: str
    authority: str
    source_type: str
    official_url: str
    version_id: uuid.UUID
    version_identifier: str
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    page_or_reference: Optional[str] = None
    source_text: str
    score: float
    retrieval_method: str = "semantic"
    citation: LegalCitation


class LegalSourceRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Legal query or proposition")
    jurisdiction: Optional[str] = Field(default=None, description="Optional jurisdiction filter e.g. 'India'")
    source_types: Optional[List[str]] = Field(default=None, description="Filter by source types e.g. ['ACT', 'RULE']")
    effective_date: Optional[datetime] = Field(default=None, description="Point-in-time date for version selection")
    legal_source_id: Optional[uuid.UUID] = Field(default=None, description="Filter to a specific source")
    top_k: int = Field(default=5, ge=1, le=50, description="Max results to return")


class LegalSourceRetrieveResponse(BaseModel):
    query: str
    results: List[LegalRetrievalResultItem]
    citations: List[LegalCitation]


class LegalSourceIngestRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    source_type: str = Field(default="ACT", description="ACT, RULE, REGULATION, COURT_JUDGMENT, etc.")
    authority: str = Field(..., min_length=2, max_length=255)
    official_url: str = Field(..., min_length=5, max_length=1024)
    version_identifier: str = Field(..., min_length=1, max_length=128)
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    publication_date: Optional[datetime] = None
    raw_text: str = Field(..., min_length=10, description="Full text to be structure-chunked and embedded")
    jurisdiction: str = Field(default="India", max_length=64)
    language: str = Field(default="en", max_length=10)
    trust_level: str = Field(default="STATUTORY", max_length=32)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LegalSourceIngestResponse(BaseModel):
    legal_source_id: uuid.UUID
    version_id: uuid.UUID
    name: str
    version_identifier: str
    content_hash: str
    chunks_created: int
    embeddings_generated: int

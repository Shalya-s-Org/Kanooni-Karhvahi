from datetime import datetime
from typing import List, Optional, Any, Dict
from uuid import UUID
from pydantic import BaseModel, Field


class ClassificationEvidenceSchema(BaseModel):
    page: int = Field(..., ge=1, description="1-indexed source page number")
    text: str = Field(..., description="Evidence text excerpt demonstrating category indicators")


class ClassificationResponse(BaseModel):
    document_type: str = Field(..., description="Broad document classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    evidence: List[ClassificationEvidenceSchema] = Field(default_factory=list, description="Traceable evidence items")


class EntityResponse(BaseModel):
    id: UUID = Field(..., description="Unique entity ID")
    document_id: UUID = Field(..., description="Associated document ID")
    page_id: Optional[UUID] = Field(default=None, description="Source page ID")
    page_number: int = Field(..., ge=1, description="Source page number")
    entity_type: str = Field(..., description="Entity category (DATE, DEADLINE, AMOUNT, etc.)")
    value: str = Field(..., description="Raw text value as extracted")
    normalized_value: Optional[str] = Field(default=None, description="Standardized normalized value")
    entity_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra semantic metadata")
    source_text: str = Field(..., description="Verbatim source sentence or context")
    start_offset: Optional[int] = Field(default=None, description="Start character offset")
    end_offset: Optional[int] = Field(default=None, description="End character offset")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    created_at: datetime = Field(..., description="Extraction timestamp")


class EntityListResponse(BaseModel):
    document_id: UUID = Field(..., description="Associated document ID")
    total_count: int = Field(..., ge=0, description="Total entity count")
    entities: List[EntityResponse] = Field(default_factory=list, description="Extracted entities")


class ClauseResponse(BaseModel):
    id: UUID = Field(..., description="Unique clause ID")
    document_id: UUID = Field(..., description="Associated document ID")
    page_id: Optional[UUID] = Field(default=None, description="Source start page ID")
    clause_number: Optional[str] = Field(default=None, description="Clause numbering e.g. 1.1")
    title: Optional[str] = Field(default=None, description="Clause title/heading")
    original_text: str = Field(..., description="Verbatim clause text")
    page_start: int = Field(..., ge=1, description="Starting page number")
    page_end: int = Field(..., ge=1, description="Ending page number")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Segmentation confidence score")
    created_at: datetime = Field(..., description="Segmentation timestamp")


class ClauseListResponse(BaseModel):
    document_id: UUID = Field(..., description="Associated document ID")
    total_count: int = Field(..., ge=0, description="Total clause count")
    clauses: List[ClauseResponse] = Field(default_factory=list, description="Extracted clauses")

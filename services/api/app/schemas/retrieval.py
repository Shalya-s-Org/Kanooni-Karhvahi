"""
Pydantic schemas for the Phase 4 semantic retrieval API.

The retrieve endpoint returns evidence chunks — it does NOT return an answer
or any AI-generated text.  Every result carries full source traceability.
"""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    """Request body for POST /documents/{document_id}/retrieve."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language search query (e.g. 'What is the payment deadline?')",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of results to return (1–50).",
    )


class RetrievalResultSchema(BaseModel):
    """A single ranked retrieval result with full source traceability."""

    chunk_id: UUID = Field(..., description="UUID of the DocumentChunk record")
    text: str = Field(..., description="Verbatim source text from the chunk")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0–1, higher = more similar)")
    page_number: int = Field(..., ge=1, description="1-based source page number")
    page_id: Optional[UUID] = Field(default=None, description="UUID of the source DocumentPage")
    clause_id: Optional[UUID] = Field(default=None, description="UUID of the source DocumentClause")
    clause_number: Optional[str] = Field(default=None, description="Human-readable clause number e.g. '7', '3.1'")
    document_id: UUID = Field(..., description="UUID of the source document")
    retrieval_method: str = Field(
        default="semantic",
        description="How results were retrieved: 'semantic' | 'lexical' | 'hybrid'",
    )
    source_type: str = Field(
        default="uploaded_document",
        description="Source origin — always 'uploaded_document' in Phase 4",
    )


class RetrievalResponseData(BaseModel):
    """Payload returned by the retrieval endpoint."""

    document_id: UUID = Field(..., description="The document that was searched")
    query: str = Field(..., description="The query that was submitted")
    results: List[RetrievalResultSchema] = Field(
        default_factory=list,
        description="Ranked results ordered by descending similarity score",
    )
    total_results: int = Field(..., ge=0, description="Number of results returned")
    retrieval_method: str = Field(
        default="semantic",
        description="Retrieval method used for this response",
    )

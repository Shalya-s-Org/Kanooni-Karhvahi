from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: UUID = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Initial processing state")
    filename: str = Field(..., description="Original filename")
    expires_at: datetime = Field(..., description="Ephemeral expiration UTC timestamp")


class DocumentStatusResponse(BaseModel):
    document_id: UUID = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Current processing state")
    progress: int = Field(..., ge=0, le=100, description="Processing percentage (0-100)")
    stage: str = Field(..., description="Human-readable processing stage")
    error: Optional[str] = Field(default=None, description="Diagnostic error details if failed")
    retryable: bool = Field(default=False, description="Whether failed processing can be retried")


class DocumentMetadataResponse(BaseModel):
    id: UUID = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="Detected MIME type")
    size: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Total pages")
    status: str = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Created UTC timestamp")
    expires_at: datetime = Field(..., description="Expiration UTC timestamp")


class DocumentPageResponse(BaseModel):
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str = Field(..., description="Extracted text content")
    ocr_used: bool = Field(..., description="Whether OCR was required for this page")
    ocr_confidence: Optional[float] = Field(default=None, description="OCR confidence score (0-1)")
    width: Optional[int] = Field(default=None, description="Page width in pixels/points")
    height: Optional[int] = Field(default=None, description="Page height in pixels/points")


class DocumentPagesListResponse(BaseModel):
    document_id: UUID = Field(..., description="Document identifier")
    page_count: int = Field(..., description="Total count of pages")
    pages: List[DocumentPageResponse] = Field(..., description="Page breakdown")


class PastedTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500000, description="Raw legal text to process")
    filename: Optional[str] = Field(default="pasted-legal-document.txt", description="Display filename")

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class RawExtractedEntity(BaseModel):
    """
    Standard representation returned by individual modular entity extractors.
    """
    entity_type: str = Field(..., description="High-level entity category (DATE, DEADLINE, AMOUNT, etc.)")
    value: str = Field(..., description="Exact textual value extracted from document")
    normalized_value: Optional[str] = Field(default=None, description="Standardized format (ISO date, numeric amount, etc.)")
    source_text: str = Field(..., description="Sentence or excerpt containing the entity for traceability")
    start_offset: Optional[int] = Field(default=None, description="Starting character offset in source text or page")
    end_offset: Optional[int] = Field(default=None, description="Ending character offset in source text or page")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0, description="Confidence score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Semantic metadata (e.g. role, date_type, amount_type, currency)")

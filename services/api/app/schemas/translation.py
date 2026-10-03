"""
Phase 7 — Pydantic schemas for the translation API.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class TranslationRequest(BaseModel):
    """Request body for ad-hoc text translation."""
    text: str = Field(..., min_length=1, max_length=20000, description="English legal text to translate.")
    target_language: str = Field(..., description="BCP-47 language code, e.g. 'hi', 'ta'.")
    content_type: str = Field(default="snippet", description="snippet | summary | clause | raw_text")


class TranslationResponseData(BaseModel):
    """Serialized response for a single translation."""
    translation_id: str
    document_id: Optional[str] = None
    source_language: str
    target_language: str
    target_language_name: str
    content_type: str
    clause_id: Optional[str] = None
    original_text: str
    translated_text: str
    preserved_terms: List[str] = Field(default_factory=list)
    provider: str
    model: str
    created_at: str
    status: str
    error_message: Optional[str] = None


class SupportedLanguageItem(BaseModel):
    code: str
    name: str


class SupportedLanguagesResponse(BaseModel):
    languages: List[SupportedLanguageItem]
    preserve_terms_note: str = (
        "Legal terms such as Section numbers, Act names, IPC, CrPC, FIR, etc. "
        "are preserved in English across all translations."
    )

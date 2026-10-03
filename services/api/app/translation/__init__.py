"""
Phase 7: Multilingual translation module for Indian regional languages.

Supports: Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada,
Malayalam, Punjabi, Odia, Urdu, Assamese.

Legal terms (Section numbers, IPC, CrPC, Act names) are preserved in English
across all translations to maintain legal precision.
"""
from app.translation.service import (
    TranslationService,
    TranslationResult,
    SUPPORTED_LANGUAGES,
    get_translation_service,
)

__all__ = [
    "TranslationService",
    "TranslationResult",
    "SUPPORTED_LANGUAGES",
    "get_translation_service",
]


"""
Phase 7: Multilingual Translation Service
Translates legal document summaries, clause explanations, and raw text
into Indian regional languages while preserving legal terminology.

Supported languages:
  - Hindi (hi)
  - Tamil (ta)
  - Telugu (te)
  - Bengali (bn)
  - Marathi (mr)
  - Gujarati (gu)
  - Kannada (kn)
  - Malayalam (ml)
  - Punjabi (pa)
  - Odia (or)
  - Urdu (ur)
  - Assamese (as)

Design principles:
  - Legal terms (Section 138, IPC, CrPC, MoU, etc.) are preserved UNTRANSLATED.
  - Each translation carries full provenance: provider, model, source_language, target_language.
  - Translations are stored in-memory keyed by (document_id, target_language, content_type).
  - Translation is CONSERVATIVE: when uncertain, the original English is appended in parentheses.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.logging import logger


# ---------------------------------------------------------------------------
# Language Registry
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
    "as": "Assamese",
}

# Legal terms to preserve verbatim across all translations
PRESERVE_TERMS = [
    "IPC", "CrPC", "Section", "Article", "Act", "Court", "FIR",
    "PIL", "MoU", "NDA", "LOC", "Writ", "Habeas Corpus", "Mandamus",
    "Certiorari", "High Court", "Supreme Court", "District Court",
    "Lok Adalat", "NCLT", "NCLAT", "RERA", "GST", "PAN", "Aadhaar",
    "RTI", "CBI", "ED", "EOW", "SFIO", "SEBI", "RBI",
]


# ---------------------------------------------------------------------------
# Translation Data Models
# ---------------------------------------------------------------------------

@dataclass
class TranslationResult:
    translation_id: str
    document_id: Optional[str]
    source_language: str
    target_language: str
    target_language_name: str
    content_type: str              # "summary" | "clause" | "raw_text" | "snippet"
    clause_id: Optional[str]
    original_text: str
    translated_text: str
    preserved_terms: List[str]
    provider: str
    model: str
    created_at: str
    status: str = "COMPLETED"      # COMPLETED | FAILED
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# In-memory translation cache
# ---------------------------------------------------------------------------
_translation_cache: Dict[str, TranslationResult] = {}


def _cache_key(
    document_id: Optional[str],
    target_language: str,
    content_type: str,
    clause_id: Optional[str],
    text_hash: str,
) -> str:
    parts = [
        document_id or "none",
        target_language,
        content_type,
        clause_id or "none",
        text_hash[:16],
    ]
    return ":".join(parts)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(target_language: str, target_language_name: str) -> str:
    preserve_list = ", ".join(PRESERVE_TERMS[:20])
    return (
        f"You are a professional legal document translator specialising in Indian law. "
        f"Your task is to translate the provided legal text into {target_language_name} "
        f"({target_language}) accurately.\n\n"
        f"CRITICAL RULES:\n"
        f"1. Preserve the following legal terms exactly in English without translating them: "
        f"{preserve_list}, and any Section numbers, Article numbers, and Act names.\n"
        f"2. When you are uncertain about a specific legal term's translation, keep the "
        f"original English term and add the translation attempt in parentheses.\n"
        f"3. Translate to plain, accessible language that a non-lawyer can understand.\n"
        f"4. Do NOT add any legal advice. Translate only what is written.\n"
        f"5. Return ONLY the translated text. Do not include explanations or commentary.\n"
        f"6. Preserve paragraph structure and bullet point formatting.\n"
    )


def _build_translation_prompt(text: str, target_language_name: str) -> str:
    return (
        f"Translate the following legal text into {target_language_name}. "
        f"Preserve all legal terms, Section numbers, and Act names in English.\n\n"
        f"TEXT TO TRANSLATE:\n{text}"
    )


# ---------------------------------------------------------------------------
# Mock translation engine (when LLM provider is mock or unavailable)
# ---------------------------------------------------------------------------

_MOCK_TRANSLATIONS: Dict[str, str] = {
    "hi": "हिंदी",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "bn": "বাংলা",
    "mr": "मराठी",
    "gu": "ગુજરાતી",
    "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം",
    "pa": "ਪੰਜਾਬੀ",
    "or": "ଓଡ଼ିଆ",
    "ur": "اردو",
    "as": "অসমীয়া",
}


def _mock_translate(text: str, target_lang: str) -> str:
    """Produce a mock translation clearly marked as demo content."""
    lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    script_marker = _MOCK_TRANSLATIONS.get(target_lang, lang_name)
    digest = hashlib.sha256(text.encode()).hexdigest()[:6]
    # Return truncated original with mock marker for demo/test purposes
    preview = text[:200] + ("..." if len(text) > 200 else "")
    return (
        f"[{script_marker} — DEMO अनुवाद / Translation — {digest}]\n\n"
        f"{preview}\n\n"
        f"(यह प्रदर्शन अनुवाद है / This is a demo translation. "
        f"Configure AI_PROVIDER to enable real {lang_name} translation.)"
    )


# ---------------------------------------------------------------------------
# Translation Service
# ---------------------------------------------------------------------------

class TranslationService:
    """
    Phase 7 multilingual translation service.

    Uses the application's LLM provider to translate legal text into
    Indian regional languages while preserving legal terminology.
    """

    def __init__(self, provider: Any = None) -> None:
        """
        Args:
            provider: BaseLLMProvider instance.  If None, mock translations are used.
        """
        self._provider = provider

    async def translate_text(
        self,
        text: str,
        target_language: str,
        document_id: Optional[str] = None,
        content_type: str = "snippet",
        clause_id: Optional[str] = None,
        force: bool = False,
    ) -> TranslationResult:
        """
        Translate text into the target language.

        Args:
            text: Source text to translate (expected to be in English).
            target_language: BCP-47 language code (e.g. "hi", "ta").
            document_id: Associated document ID for caching.
            content_type: Classification of content ("summary", "clause", "raw_text", "snippet").
            clause_id: Clause UUID when translating a specific clause.
            force: Skip cache and regenerate.

        Returns:
            TranslationResult dataclass.
        """
        if target_language not in SUPPORTED_LANGUAGES:
            return TranslationResult(
                translation_id=str(uuid4()),
                document_id=document_id,
                source_language="en",
                target_language=target_language,
                target_language_name=target_language,
                content_type=content_type,
                clause_id=clause_id,
                original_text=text,
                translated_text="",
                preserved_terms=[],
                provider="none",
                model="none",
                created_at=datetime.now(timezone.utc).isoformat(),
                status="FAILED",
                error_message=f"Language '{target_language}' is not supported.",
            )

        target_language_name = SUPPORTED_LANGUAGES[target_language]
        text_hash = _text_hash(text)
        cache_key = _cache_key(document_id, target_language, content_type, clause_id, text_hash)

        # Return cached unless force=True
        if not force and cache_key in _translation_cache:
            logger.info("Translation cache hit for key=%s", cache_key)
            return _translation_cache[cache_key]

        # Determine preserved terms found in this text
        preserved = [term for term in PRESERVE_TERMS if term in text]

        try:
            if self._provider is None or getattr(self._provider, "provider_name", "mock") == "mock":
                translated = _mock_translate(text, target_language)
                provider_name = "mock"
                model_name = "mock-translator-v1"
            else:
                system_prompt = _build_system_prompt(target_language, target_language_name)
                translation_prompt = _build_translation_prompt(text, target_language_name)
                translated = await self._provider.generate_text(
                    prompt=translation_prompt,
                    system_instruction=system_prompt,
                    temperature=0.05,   # Very low — translation is deterministic
                    max_tokens=4096,
                )
                provider_name = getattr(self._provider, "provider_name", "unknown")
                model_name = getattr(self._provider, "model_name", "unknown")

            result = TranslationResult(
                translation_id=str(uuid4()),
                document_id=document_id,
                source_language="en",
                target_language=target_language,
                target_language_name=target_language_name,
                content_type=content_type,
                clause_id=clause_id,
                original_text=text,
                translated_text=translated,
                preserved_terms=preserved,
                provider=provider_name,
                model=model_name,
                created_at=datetime.now(timezone.utc).isoformat(),
                status="COMPLETED",
            )

        except Exception as exc:
            logger.error("Translation failed for lang=%s: %s", target_language, exc)
            result = TranslationResult(
                translation_id=str(uuid4()),
                document_id=document_id,
                source_language="en",
                target_language=target_language,
                target_language_name=target_language_name,
                content_type=content_type,
                clause_id=clause_id,
                original_text=text,
                translated_text="",
                preserved_terms=preserved,
                provider="error",
                model="error",
                created_at=datetime.now(timezone.utc).isoformat(),
                status="FAILED",
                error_message=str(exc),
            )

        _translation_cache[cache_key] = result
        return result

    async def translate_summary_fields(
        self,
        summary_data: Dict[str, Any],
        target_language: str,
        document_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Translate the key fields of a document summary into the target language.

        Returns a dict mirroring the original structure with translated values.
        All non-translatable fields (IDs, dates, providers) are passed through unchanged.
        """
        translated: Dict[str, Any] = dict(summary_data)
        translated["target_language"] = target_language
        translated["target_language_name"] = SUPPORTED_LANGUAGES.get(target_language, target_language)

        async def _t(text: Optional[str], ctype: str = "summary") -> Optional[str]:
            if not text:
                return text
            r = await self.translate_text(text, target_language, document_id, ctype, force=force)
            return r.translated_text if r.status == "COMPLETED" else text

        # Core prose fields
        translated["summary"] = await _t(summary_data.get("summary"), "summary")
        translated["purpose"] = await _t(summary_data.get("purpose"), "summary")

        # Lists of strings
        for list_key in ("important_dates", "important_amounts", "important_parties", "obligations", "uncertainty_notes"):
            items = summary_data.get(list_key) or []
            translated[list_key] = [
                (await _t(item, "summary")) or item for item in items if isinstance(item, str)
            ]

        # Key points — translate .text field only
        kps = summary_data.get("key_points") or []
        translated_kps = []
        for kp in kps:
            t_kp = dict(kp)
            if isinstance(kp.get("text"), str):
                t_kp["text"] = (await _t(kp["text"], "summary")) or kp["text"]
            translated_kps.append(t_kp)
        translated["key_points"] = translated_kps

        # Check signals — translate message and explanation
        signals = summary_data.get("check_signals") or []
        translated_signals = []
        for sig in signals:
            t_sig = dict(sig)
            if isinstance(sig.get("message"), str):
                t_sig["message"] = (await _t(sig["message"], "summary")) or sig["message"]
            if isinstance(sig.get("explanation"), str):
                t_sig["explanation"] = (await _t(sig["explanation"], "summary")) or sig["explanation"]
            translated_signals.append(t_sig)
        translated["check_signals"] = translated_signals

        # External legal context strings (from Phase 6)
        ext_ctx = summary_data.get("external_legal_context") or []
        translated["external_legal_context"] = [
            (await _t(c, "summary")) or c for c in ext_ctx if isinstance(c, str)
        ]

        return translated


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_service_instance: Optional[TranslationService] = None


def get_translation_service(provider: Any = None) -> TranslationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = TranslationService(provider=provider)
    return _service_instance

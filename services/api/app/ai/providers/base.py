"""
AI LLM provider abstraction.

All LLM calls in the application go through BaseLLMProvider.
No vendor SDK is ever called directly outside a concrete provider subclass.

Interface
---------
BaseLLMProvider.generate_text(prompt, system_instruction, temperature, max_tokens)
    → str

BaseLLMProvider.generate_structured(prompt, schema, system_instruction)
    → Dict[str, Any]  (validated against schema before returning)

Safety contract
---------------
Every concrete provider implementation MUST:
  - Return only what the document evidence supplies.
  - Never invent facts, citations, or legal conclusions.
  - Propagate LLMProviderError on credentials failure rather than silently
    returning a mock-like response.
"""

from __future__ import annotations

import json
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM text and structured-output generation.

    Subclasses MUST implement ``generate_text`` and ``generate_structured``.
    """

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

    @property
    def model_name(self) -> str:
        return "unknown"

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a text completion.

        Args:
            prompt: The user/evidence prompt.
            system_instruction: Optional system-level instructions (safety guardrails go here).
            temperature: Sampling temperature.  Keep low (0.1) for legal analysis.
            max_tokens: Maximum output tokens.

        Returns:
            Raw text string from the model.

        Raises:
            LLMProviderError: On credential failure, quota exhaustion, or network error.
        """

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON-structured response that conforms to *schema*.

        The implementation must:
          1. Ask the model to respond only with valid JSON.
          2. Parse the response.
          3. Return the parsed dict.

        The caller (analysis service) is responsible for Pydantic validation
        of the returned dict against the full output model.

        Args:
            prompt: The user/evidence prompt.
            schema: JSON Schema dict describing expected output shape.
            system_instruction: Optional system-level instructions.

        Returns:
            Parsed JSON dict from the model.

        Raises:
            LLMProviderError: On credential failure or irrecoverable generation error.
            LLMOutputParseError: If the model returns non-JSON or malformed JSON.
        """


# ---------------------------------------------------------------------------
# Backward-compatible alias (Phase 1–4 code imports LLMProvider)
# ---------------------------------------------------------------------------
LLMProvider = BaseLLMProvider


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class LLMProviderError(Exception):
    """
    Raised when the LLM provider is unavailable, misconfigured, or returns
    an irrecoverable error (e.g. invalid API key, quota exceeded).

    This is a configuration/infrastructure error, not a generation error.
    The application should surface this as PROVIDER_UNAVAILABLE to the caller.
    """

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"LLM provider '{provider}' error: {reason}")
        self.provider = provider
        self.reason = reason


class LLMOutputParseError(Exception):
    """
    Raised when the LLM returns output that cannot be parsed as valid JSON
    or does not match the expected schema.

    This is a generation-quality error, not a configuration error.
    The analysis should be marked VALIDATION_FAILED rather than PROVIDER_UNAVAILABLE.
    """

    def __init__(self, provider: str, raw_output: str, reason: str) -> None:
        super().__init__(f"LLM output parse error from '{provider}': {reason}")
        self.provider = provider
        self.raw_output = raw_output
        self.reason = reason


# ---------------------------------------------------------------------------
# Deterministic Mock Provider (tests only)
# ---------------------------------------------------------------------------

class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for automated tests.

    Properties:
      - Never calls the internet or requires credentials.
      - Returns schema-valid structured output.
      - Text output is deterministic by input hash.
      - Clearly identifies itself as mock output in every response.
      - MUST NOT be used in production.

    The mock summary and explanation outputs are structurally valid but
    semantically meaningless.  Tests should validate orchestration and
    schema behaviour, not AI response quality.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-llm-v1"

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        return (
            f"[MOCK OUTPUT — NOT REAL AI — digest:{digest}] "
            "According to the uploaded document, this is a deterministic test response. "
            "This is not legal advice."
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return a structurally valid mock payload that satisfies the
        DocumentSummaryOutput and ClauseExplanationOutput schemas.

        The shape is inferred from the ``schema`` dict's ``properties`` keys.
        If neither summary-specific nor clause-specific keys are detected,
        a generic mock payload is returned.
        """
        import re
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        props = schema.get("properties", {})

        # Extract evidence IDs from prompt so mock cites valid evidence supplied in the prompt
        extracted_eids = re.findall(r"\[([a-zA-Z0-9_\-]+)\]\s+Source:", prompt)
        mock_evidence_refs = extracted_eids[:3] if extracted_eids else ["mock-evidence-ref-0000"]
        mock_evidence_ref = mock_evidence_refs[0]

        mock_check_signal = {
            "category": "MISSING_INFORMATION",
            "message": "According to the uploaded document, check signal: verify detail with official source.",
            "severity": "INFO",
            "evidence_refs": [mock_evidence_ref],
            "explanation": "This is a conservative check signal indicating that this detail should be verified.",
        }

        # Document summary shape
        if "summary" in props:
            return {
                "summary": f"[MOCK:{digest}] According to the uploaded document, this is a test summary. This is not legal advice.",
                "purpose": f"[MOCK:{digest}] The purpose of the document is for testing.",
                "document_type": "UNKNOWN",
                "key_points": [
                    {
                        "text": f"[MOCK:{digest}] According to the document, key point one.",
                        "evidence_refs": [mock_evidence_ref],
                    }
                ],
                "important_dates": [],
                "important_amounts": [],
                "important_parties": [],
                "obligations": [],
                "check_signals": [mock_check_signal],
                "evidence_refs": mock_evidence_refs,
                "uncertainty_notes": [
                    f"[MOCK:{digest}] The document does not provide enough information to determine all details. Verify with a qualified lawyer."
                ],
                "provider": "mock",
                "model": "mock-llm-v1",
            }

        # Clause explanation shape
        if "plain_meaning" in props:
            clause_id_match = re.search(r"clause-([a-f0-9\-]+)", prompt)
            clause_id_str = clause_id_match.group(0) if clause_id_match else None
            return {
                "clause_id": clause_id_str,
                "plain_meaning": f"[MOCK:{digest}] According to the uploaded document, this clause states the terms agreed upon. This is not legal advice.",
                "why_it_matters": f"[MOCK:{digest}] This may be important because it sets forth operative conditions under the document.",
                "important_terms": [
                    {"term": "mock_term", "explanation": "A term used in this clause."}
                ],
                "obligations": [],
                "dates": [],
                "amounts": [],
                "check_signals": [mock_check_signal],
                "uncertainty_notes": [
                    f"[MOCK:{digest}] The document does not provide enough information to determine complete legal implications."
                ],
                "evidence_refs": mock_evidence_refs,
                "provider": "mock",
                "model": "mock-llm-v1",
            }

        # Generic fallback
        return {
            "mock": True,
            "digest": digest,
            "note": "Mock structured output — not real AI analysis.",
            "provider": "mock",
            "model": "mock-llm-v1",
        }

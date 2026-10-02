"""
Google Gemini LLM provider.

Requires:
    pip install google-generativeai>=0.8.0

Configuration:
    LLM_PROVIDER=gemini
    LLM_API_KEY=your_gemini_api_key
    LLM_MODEL=gemini-1.5-flash   (or gemini-1.5-pro for higher quality)

This module is imported lazily by the factory.  If google-generativeai is
not installed, the factory simply skips registration and Gemini is unavailable.

Safety note: API key is read from settings at call time and never logged.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from app.ai.providers.base import BaseLLMProvider, LLMProviderError, LLMOutputParseError
from app.core.logging import logger


class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini text generation provider.

    Uses the ``google-generativeai`` Python SDK.
    The model is instantiated lazily on first call so that import-time
    failures (missing API key) raise LLMProviderError with a clear message
    rather than crashing the application at startup.
    """

    def __init__(self) -> None:
        self._client = None  # lazy init

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        from app.core.config import settings
        return settings.LLM_MODEL

    def _get_client(self):
        """Lazily initialise the Gemini SDK client."""
        if self._client is not None:
            return self._client

        try:
            import google.generativeai as genai  # type: ignore[import]
        except ImportError as exc:
            raise LLMProviderError(
                provider="gemini",
                reason="google-generativeai SDK is not installed. Run: pip install google-generativeai>=0.8.0",
            ) from exc

        from app.core.config import settings
        api_key = settings.LLM_API_KEY
        if not api_key:
            raise LLMProviderError(
                provider="gemini",
                reason="LLM_API_KEY is not set. Configure it in your .env file.",
            )

        try:
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(model_name=settings.LLM_MODEL)
            logger.info("Gemini client initialised with model: %s", settings.LLM_MODEL)
        except Exception as exc:
            raise LLMProviderError(provider="gemini", reason=str(exc)) from exc

        return self._client

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        try:
            import google.generativeai as genai  # type: ignore[import]

            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            response = client.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            return response.text
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(provider="gemini", reason=str(exc)) from exc

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Instructs Gemini to respond with valid JSON only, then parses the
        response.  Falls back to extracting the first JSON block if the model
        wraps the output in markdown code fences.
        """
        from app.core.config import settings

        client = self._get_client()

        json_instruction = (
            "You MUST respond with ONLY valid JSON — no markdown fences, "
            "no prose, no comments.  The JSON must conform exactly to the "
            "provided schema.\n\n"
            f"Schema:\n{json.dumps(schema, indent=2)}"
        )

        full_system = (
            f"{system_instruction}\n\n{json_instruction}"
            if system_instruction
            else json_instruction
        )
        full_prompt = f"{full_system}\n\n{prompt}"

        try:
            import google.generativeai as genai  # type: ignore[import]

            generation_config = genai.types.GenerationConfig(
                temperature=settings.AI_TEMPERATURE,
                max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                response_mime_type="application/json",
            )
            response = client.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            raw = response.text.strip()
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(provider="gemini", reason=str(exc)) from exc

        # Parse JSON — strip markdown fences if present.
        raw = _strip_markdown_fences(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMOutputParseError(
                provider="gemini",
                raw_output=raw[:500],
                reason=f"JSON parse failed: {exc}",
            ) from exc


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    # Match code fence with optional language tag
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

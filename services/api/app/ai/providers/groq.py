"""
GroqCloud LLM provider (OpenAI-compatible chat completions API).

Requires no additional SDK — uses ``httpx`` which is already a project
dependency.  Communicates with the Groq OpenAI-compatible endpoint.

Configuration:
    LLM_PROVIDER=groq
    LLM_API_KEY=<your GroqCloud API key>
    LLM_MODEL=openai/gpt-oss-20b   (or any model listed at console.groq.com/docs/models)
    LLM_BASE_URL=https://api.groq.com/openai/v1

Safety note: The API key is read from settings at call time and is never
logged or included in exception messages.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import httpx

from app.ai.providers.base import BaseLLMProvider, LLMProviderError, LLMOutputParseError
from app.core.logging import logger

_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMProvider(BaseLLMProvider):
    """
    GroqCloud chat-completion provider.

    Uses the OpenAI-compatible ``/chat/completions`` endpoint so the
    implementation is straightforward and requires no Groq-specific SDK.
    The client is initialised lazily on the first call.
    """

    def __init__(self) -> None:
        self._api_key: Optional[str] = None
        self._base_url: str = _DEFAULT_BASE_URL
        self._model: str = "openai/gpt-oss-20b"

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def _init(self) -> None:
        """Read configuration from settings (deferred to first call)."""
        from app.core.config import settings

        api_key = settings.LLM_API_KEY
        if not api_key:
            raise LLMProviderError(
                provider="groq",
                reason=(
                    "LLM_API_KEY is not set. "
                    "Obtain a key from console.groq.com and add it to your .env file."
                ),
            )

        self._api_key = api_key
        self._model = settings.LLM_MODEL or "openai/gpt-oss-20b"
        self._base_url = (settings.LLM_BASE_URL or _DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _chat(
        self,
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        """Send a chat-completions request and return the assistant message text."""
        self._init()

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        url = f"{self._base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Avoid leaking the response body (may contain quota details).
            raise LLMProviderError(
                provider="groq",
                reason=f"HTTP {exc.response.status_code} from Groq API.",
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                provider="groq",
                reason=f"Network error contacting Groq API: {type(exc).__name__}",
            ) from exc

        data = resp.json()
        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(
                provider="groq",
                reason=f"Unexpected Groq API response shape: {exc}",
            ) from exc

        return content

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        messages: list[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        text = await self._chat(messages, temperature=temperature, max_tokens=max_tokens)
        logger.debug("Groq generate_text completed (model=%s).", self._model)
        return text

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.core.config import settings

        json_instruction = (
            "You MUST respond with ONLY valid JSON — no markdown fences, "
            "no prose, no comments.  The JSON must conform exactly to the "
            "provided schema.\n\n"
            f"Schema:\n{json.dumps(schema, indent=2)}"
        )

        system = (
            f"{system_instruction}\n\n{json_instruction}"
            if system_instruction
            else json_instruction
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        raw = await self._chat(
            messages,
            temperature=settings.AI_TEMPERATURE,
            max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            response_format={"type": "json_object"},
        )

        raw = _strip_markdown_fences(raw.strip())
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMOutputParseError(
                provider="groq",
                raw_output=raw[:500],
                reason=f"JSON parse failed: {exc}",
            ) from exc

        logger.debug("Groq generate_structured completed (model=%s).", self._model)
        return result


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` wrappers if present."""
    text = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

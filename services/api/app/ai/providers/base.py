from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator


class LLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    Enables swapping between Gemini, Anthropic, OpenAI, local Ollama, etc. without modifying business logic.
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generates text completion based on prompt and system constraints.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates strictly schema-conforming JSON structure.
        """
        pass


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for local testing and offline execution.
    """

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        return "[MOCK LLM RESPONSE]: Kanooni Karhvahi mock response for testing."

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {"mock": True, "status": "simulated_structured_output"}

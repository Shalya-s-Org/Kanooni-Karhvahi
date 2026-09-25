from typing import Dict, Type
from app.ai.providers.base import LLMProvider, MockLLMProvider
from app.core.config import settings
from app.core.logging import logger

_PROVIDERS: Dict[str, Type[LLMProvider]] = {
    "mock": MockLLMProvider,
}


def get_llm_provider(name: str = None) -> LLMProvider:
    """
    Factory function to instantiate the configured LLM provider.
    """
    provider_name = (name or settings.LLM_PROVIDER).lower()

    if provider_name in _PROVIDERS:
        return _PROVIDERS[provider_name]()

    logger.warning("Provider '%s' not registered yet. Falling back to MockLLMProvider.", provider_name)
    return MockLLMProvider()

"""Central list of providers. To add a provider: implement `Provider` and append it here."""
from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import Provider
from .openai_compat import (CustomCompatProvider, GeminiProvider, LlamaCppProvider, LMStudioProvider,
                            OllamaProvider, OpenAICompatProvider)

PROVIDERS: dict[str, type[Provider]] = {
    cls.info.id: cls
    for cls in (AnthropicProvider, OpenAICompatProvider, GeminiProvider, OllamaProvider,
                LlamaCppProvider, LMStudioProvider, CustomCompatProvider)
}


def create(provider_id: str, api_key: str = "", base_url: str = "") -> Provider:
    cls = PROVIDERS.get(provider_id)
    if cls is None:
        raise KeyError(provider_id)
    return cls(api_key=api_key, base_url=base_url)

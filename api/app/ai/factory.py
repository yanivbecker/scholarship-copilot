"""Pick the configured AI provider (SCHOLARSHIP_AI_PROVIDER)."""

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider, NoAIProvider
from app.ai.ollama_provider import OllamaProvider
from app.core.config import Settings, get_settings


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    match settings.ai_provider:
        case "anthropic":
            key = settings.anthropic_api_key
            return AnthropicProvider(
                model=settings.anthropic_model,
                effort=settings.anthropic_effort,
                api_key=key.get_secret_value() if key else None,
            )
        case "ollama":
            return OllamaProvider(url=settings.ollama_url, model=settings.ollama_model)
        case _:
            return NoAIProvider()

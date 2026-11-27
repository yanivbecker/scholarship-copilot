"""Pick the configured AI provider (SCHOLARSHIP_AI_PROVIDER).

Settings come only from the environment / .env, never from a request.
`get_ai_provider` is a FastAPI dependency, so it must take no parameters:
any parameter there becomes something an API caller can fill in.
"""

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider, NoAIProvider
from app.ai.ollama_provider import OllamaProvider
from app.core.config import Settings, get_settings


def build_ai_provider(settings: Settings) -> AIProvider:
    """The provider described by `settings` (used by jobs and tests)."""
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


def get_ai_provider() -> AIProvider:
    """FastAPI dependency: the provider from the server's own configuration."""
    return build_ai_provider(get_settings())

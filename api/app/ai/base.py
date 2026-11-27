"""The AI provider interface (ARCHITECTURE.md: none / ollama / anthropic).

AI is optional (NFR-6): with provider "none" the app still works; anything
that needs AI says so and the student can enter or paste data by hand.

Providers only turn a prompt into JSON text. Validating that JSON against a
schema, retrying, and deciding what to trust is done once, for every
provider, in app/ai/structured.py.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class AIError(Exception):
    """Base class. Messages are user-facing."""


class AIUnavailableError(AIError):
    """No provider is configured, or it can't be reached."""


class AIRefusalError(AIError):
    """The model declined the request (e.g. a safety refusal)."""


class AIOutputError(AIError):
    """The output was incomplete or didn't match the schema, even after a retry.

    Callers mark the item for manual review (NFR-5).
    """


@dataclass(frozen=True)
class AIReply:
    """Raw JSON text from a provider, plus what it cost."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class AIProvider(Protocol):
    """Anything that can answer a prompt with JSON matching a schema."""

    name: str

    def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any]
    ) -> AIReply:
        """Return JSON text. Raise AIError subclasses for known failures."""
        ...  # pylint: disable=unnecessary-ellipsis


class NoAIProvider:
    """Provider "none": the default. Every request explains how to proceed."""

    name = "none"

    def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any]
    ) -> AIReply:
        raise AIUnavailableError(
            "AI is turned off (SCHOLARSHIP_AI_PROVIDER=none). You can add "
            "scholarship details by hand, or set the provider to ollama or "
            "anthropic."
        )

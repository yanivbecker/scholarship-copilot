"""Claude via the official Anthropic SDK (ARCHITECTURE.md AI provider).

* Structured outputs (`output_config.format`) constrain the reply to our JSON
  schema; app/ai/structured.py still validates it with Pydantic.
* Server-side refusal fallbacks (`fallbacks="default"`) let the API retry a
  declined request on a suitable model within the same call.
* No tools are offered, so untrusted page text can't trigger any action.
* The SDK retries connection errors, 429 and 5xx itself (max_retries).
"""

from typing import Any, Literal

import anthropic
from anthropic.types.beta import BetaOutputConfigParam

from app.ai.base import AIOutputError, AIRefusalError, AIReply, AIUnavailableError

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000  # non-streaming default: stays under SDK HTTP timeouts
TIMEOUT_SECONDS = 120.0

type Effort = Literal["low", "medium", "high"]


class AnthropicProvider:
    """Generates JSON with Claude. The client is injectable for tests."""

    name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        effort: Effort = "medium",
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        # api_key=None lets the SDK use ANTHROPIC_API_KEY or an `ant` profile.
        self.client = client or anthropic.Anthropic(
            api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=2
        )

    def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any]
    ) -> AIReply:
        output_config: BetaOutputConfigParam = {
            "effort": self.effort,
            "format": {"type": "json_schema", "schema": json_schema},
        }
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
            )
        except anthropic.AuthenticationError:
            raise AIUnavailableError(
                "The Anthropic API key was rejected. Check ANTHROPIC_API_KEY."
            ) from None
        except anthropic.PermissionDeniedError:
            raise AIUnavailableError(
                "This Anthropic API key isn't allowed to use that model."
            ) from None
        except anthropic.NotFoundError:
            raise AIUnavailableError(
                f"The model {self.model!r} wasn't found. "
                "Check SCHOLARSHIP_ANTHROPIC_MODEL."
            ) from None
        except anthropic.RateLimitError:
            raise AIUnavailableError(
                "Anthropic's rate limit was reached. Try again later."
            ) from None
        except anthropic.APIStatusError as exc:
            raise AIUnavailableError(
                f"The Anthropic API returned an error ({exc.status_code})."
            ) from None
        except anthropic.APIConnectionError:
            raise AIUnavailableError("Couldn't reach the Anthropic API.") from None

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise AIRefusalError(
                "The model declined to process this page"
                + (f" ({category})." if category else ".")
            )
        if response.stop_reason == "max_tokens":
            raise AIOutputError("The AI's answer was cut off before it finished.")

        text = "".join(b.text for b in response.content if b.type == "text")
        return AIReply(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

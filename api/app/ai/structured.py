"""Ask a provider for JSON and validate it against a Pydantic model (NFR-5).

One retry: if the first answer doesn't validate, the provider is told exactly
what was wrong and asked again. If the second answer also fails, we give up
with AIOutputError and the caller marks the item for manual review.
"""

from dataclasses import dataclass

from anthropic import transform_schema
from pydantic import BaseModel, ValidationError

from app.ai.base import AIOutputError, AIProvider, AIReply

MAX_ERROR_CHARS = 2000


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    """The validated output and every reply it took to get it."""

    value: T
    replies: tuple[AIReply, ...]

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.replies)

    @property
    def output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.replies)


def json_schema_for(model: type[BaseModel]) -> dict[str, object]:
    """A JSON schema providers can enforce. Constraints they can't (like
    number ranges) move into descriptions; Pydantic still checks them here."""
    return transform_schema(model)


def ask_structured[T: BaseModel](
    provider: AIProvider, *, system: str, user: str, output: type[T]
) -> StructuredResult[T]:
    """Get a validated `output` instance, retrying once on invalid JSON."""
    schema = json_schema_for(output)
    first = provider.generate_json(system=system, user=user, json_schema=schema)
    try:
        return StructuredResult(output.model_validate_json(first.text), (first,))
    except ValidationError as exc:
        problem = _describe(exc)

    retry_user = (
        f"{user}\n\nYour previous answer was not valid for the required "
        f"JSON schema. Problems:\n{problem}\n\nAnswer again with corrected JSON only."
    )
    second = provider.generate_json(system=system, user=retry_user, json_schema=schema)
    try:
        return StructuredResult(
            output.model_validate_json(second.text), (first, second)
        )
    except ValidationError as exc:
        raise AIOutputError(
            "The AI's answer didn't match the expected format twice, so it "
            f"needs a manual review. ({_describe(exc)[:300]})"
        ) from None


def _describe(exc: ValidationError) -> str:
    """Short, model-readable list of what failed validation."""
    lines = [
        f"- {'.'.join(str(p) for p in error['loc']) or '(root)'}: {error['msg']}"
        for error in exc.errors(include_url=False, include_input=False)
    ]
    return "\n".join(lines)[:MAX_ERROR_CHARS] or "- (no details)"

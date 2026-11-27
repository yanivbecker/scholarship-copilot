"""Test doubles shared across test files. All data is fictional."""

import json
from typing import Any

from app.ai.base import AIReply


class ScriptedProvider:
    """An AI provider that returns prepared answers in order and records prompts."""

    name = "scripted"

    def __init__(
        self, *answers: str | dict[str, Any], model: str = "scripted-model"
    ) -> None:
        self.answers = [a if isinstance(a, str) else json.dumps(a) for a in answers]
        self.model = model
        self.systems: list[str] = []
        self.prompts: list[str] = []

    def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any]
    ) -> AIReply:
        del json_schema  # same signature as AIProvider; not needed here
        self.systems.append(system)
        self.prompts.append(user)
        return AIReply(self.answers.pop(0), self.model, 1000, 200)

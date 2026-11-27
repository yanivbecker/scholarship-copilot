"""A local model through Ollama's HTTP API (optional, free, offline).

Only loopback addresses are accepted, so scraped text and profile data never
leave this computer through this provider.
"""

import ipaddress
from typing import Any
from urllib.parse import urlsplit

import httpx2

from app.ai.base import AIOutputError, AIReply, AIUnavailableError

TIMEOUT = httpx2.Timeout(300.0, connect=5.0)  # local models can be slow


def _require_loopback(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    try:
        is_loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise AIUnavailableError(
            "SCHOLARSHIP_OLLAMA_URL must point to this computer "
            "(127.0.0.1 or localhost)."
        )
    return url.rstrip("/")


class OllamaProvider:
    """Generates JSON with a local Ollama model."""

    name = "ollama"

    def __init__(
        self,
        *,
        url: str,
        model: str,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self.url = _require_loopback(url)
        self.model = model
        self._transport = transport

    def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any]
    ) -> AIReply:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": json_schema,  # Ollama structured outputs
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            with httpx2.Client(
                transport=self._transport, timeout=TIMEOUT, trust_env=False
            ) as client:
                response = client.post(f"{self.url}/api/chat", json=body)
        except httpx2.HTTPError:
            raise AIUnavailableError(
                "Couldn't reach Ollama. Is it running (`ollama serve`)?"
            ) from None
        if response.status_code == 404:
            raise AIUnavailableError(
                f"Ollama doesn't have the model {self.model!r}. "
                f"Run `ollama pull {self.model}`."
            )
        if response.status_code != 200:
            raise AIUnavailableError(
                f"Ollama returned an error ({response.status_code})."
            )
        data = response.json()
        if data.get("done_reason") == "length":
            raise AIOutputError("The AI's answer was cut off before it finished.")
        message = data.get("message") or {}
        return AIReply(
            text=str(message.get("content", "")),
            model=str(data.get("model", self.model)),
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
        )

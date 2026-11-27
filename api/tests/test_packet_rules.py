"""The AI-use rules check before any writing help (FR-A1, FR-A2).

All listing text is fictional.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.packets.models import RulesStatus
from app.modules.packets.rules import find_policy_sentences, suggest_status
from tests.sample_listing import PAGE

V1 = "/api/v1"
BAN = "The use of AI tools such as ChatGPT is not permitted."
ALLOW = "Applicants may use AI writing tools to help edit their essays."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"Essays must be your own original work. {BAN}", RulesStatus.PROHIBITED),
        ("Do not use generative tools when writing.", RulesStatus.PROHIBITED),
        (ALLOW, RulesStatus.ALLOWED),
        # A permission with conditions is for the student to read, not for code.
        (
            "You may use AI for brainstorming, but the essay must be written by you.",
            RulesStatus.UNCLEAR,
        ),
        # Silence about AI is not permission.
        (PAGE, RulesStatus.UNCLEAR),
        # Plagiarism rules are shown, but aren't an AI policy.
        ("Plagiarism will result in disqualification.", RulesStatus.UNCLEAR),
    ],
)
def test_suggestion_from_the_sponsors_words(text: str, expected: RulesStatus) -> None:
    assert suggest_status(find_policy_sentences(text)) is expected


def test_words_that_merely_contain_ai_are_ignored() -> None:
    assert not find_policy_sentences("Said the CHAIRMAN: we maintain our standards.")


def packet_for(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    body: dict[str, Any] = client.get(
        f"{V1}/scholarships/{scholarship_id}/packet"
    ).json()
    return body


def repaste(client: TestClient, extra: str) -> None:
    """A newer snapshot of the same source page, now with an AI policy."""
    [source] = client.get(f"{V1}/sources").json()
    response = client.post(
        f"{V1}/sources/{source['id']}/paste", json={"text": PAGE + extra}
    )
    assert response.status_code in (200, 201), response.text


def test_scan_reads_the_latest_source_text(
    client: TestClient, scholarship_id: int
) -> None:
    packet = packet_for(client, scholarship_id)
    url = f"{V1}/packets/{packet['id']}/rules/scan"
    before = client.get(url).json()
    repaste(client, f"Essays must be your own original work.\n{BAN}\n")

    after = client.get(url).json()

    assert before["suggested"] == "unclear" and before["candidates"] == []
    assert after["suggested"] == "prohibited"
    assert BAN in after["candidates"]
    assert after["source_url"] == "https://example.org/awards"
    # Scanning changes nothing; only the student's confirmation does.
    assert packet_for(client, scholarship_id)["rules_status"] == "unchecked"


def test_allowed_needs_a_quote_from_the_source(
    client: TestClient, scholarship_id: int
) -> None:
    repaste(client, ALLOW + "\n")
    packet = packet_for(client, scholarship_id)
    url = f"{V1}/packets/{packet['id']}/rules"

    no_quote = client.put(url, json={"status": "allowed"})
    made_up = client.put(
        url, json={"status": "allowed", "quote": "AI tools are fully welcome here."}
    )
    real = client.put(url, json={"status": "allowed", "quote": f"  {ALLOW}  "})

    assert no_quote.status_code == 422 and "quote" in no_quote.json()["detail"]
    assert made_up.status_code == 422 and "isn't on" in made_up.json()["detail"]
    assert real.status_code == 200, real.text
    body = real.json()
    assert body["rules_status"] == "allowed" and body["ai_writing_allowed"] is True
    assert body["rules_quote"] == ALLOW
    history = client.get(f"{V1}/scholarships/{scholarship_id}/status").json()
    assert "rules_confirmed" in [h["action"] for h in history["history"]]


@pytest.mark.parametrize("status", ["prohibited", "unclear"])
def test_anything_but_allowed_keeps_ai_help_off(
    client: TestClient, scholarship_id: int, status: str
) -> None:
    packet = packet_for(client, scholarship_id)

    body = client.put(
        f"{V1}/packets/{packet['id']}/rules", json={"status": status}
    ).json()

    assert body["rules_status"] == status
    assert body["rules_confirmed_at"] is not None
    assert body["ai_writing_allowed"] is False


def test_unchecked_cannot_be_confirmed(client: TestClient, scholarship_id: int) -> None:
    packet = packet_for(client, scholarship_id)

    response = client.put(
        f"{V1}/packets/{packet['id']}/rules", json={"status": "unchecked"}
    )

    assert response.status_code == 422

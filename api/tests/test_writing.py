"""AI writing help: gated by the rules check, verified by code (FR-A3-A5).

Every AI answer here is scripted, and the student, story and listing are
fictional. No real AI is called.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.base import NoAIProvider
from app.ai.factory import get_ai_provider
from app.modules.packets.provenance import claims_in
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE

V1 = "/api/v1"
ALLOW = "Applicants may use AI writing tools to help edit their essays."
PROMPT = "Describe a time you helped others learn. What did you take away from it?"
STORY = (
    "I started a peer tutoring club at Lincoln High School. Every week I "
    "tutored freshmen in algebra. By spring, 12 students had joined the club."
)
PRIVATE_STORY = "My grandmother taught me to bake bread in her kitchen."


def use(client: TestClient, provider: object) -> None:
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]


def make_item(
    client: TestClient, scholarship_id: int, *, allow: bool
) -> dict[str, Any]:
    if allow:
        [source] = client.get(f"{V1}/sources").json()
        client.post(f"{V1}/sources/{source['id']}/paste", json={"text": PAGE + ALLOW})
    packet = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()
    if allow:
        confirmed = client.put(
            f"{V1}/packets/{packet['id']}/rules",
            json={"status": "allowed", "quote": ALLOW},
        )
        assert confirmed.status_code == 200, confirmed.text
    body = client.post(
        f"{V1}/packets/{packet['id']}/items",
        json={
            "kind": "essay",
            "title": "Helping others",
            "prompt": PROMPT,
            "limit_value": 120,
            "limit_unit": "words",
        },
    ).json()
    item: dict[str, Any] = body["items"][0]
    return item


def story(client: TestClient, title: str, body: str) -> int:
    response = client.post(f"{V1}/stories", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.fixture(name="item")
def fixture_item(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    return make_item(client, scholarship_id, allow=True)


def set_rules(client: TestClient, scholarship_id: int, status: str) -> None:
    packet = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()
    client.put(f"{V1}/packets/{packet['id']}/rules", json={"status": status})


def coaching_calls(client: TestClient, item_id: int) -> list[int]:
    base = f"{V1}/packet-items/{item_id}/coach"
    return [
        client.post(f"{base}/breakdown").status_code,
        client.post(f"{base}/questions").status_code,
        client.post(f"{base}/outline", json={"answers": []}).status_code,
        client.post(f"{base}/feedback", json={"version_id": 1}).status_code,
    ]


@pytest.mark.parametrize("rules", [None, "unclear"])
def test_coaching_is_on_but_drafting_off_until_rules_allow_it(
    client: TestClient, scholarship_id: int, rules: str | None
) -> None:
    """Owner decision: coaching never writes the answer, so it's the default."""
    item = make_item(client, scholarship_id, allow=False)
    if rules:
        set_rules(client, scholarship_id, rules)
    provider = ScriptedProvider({"questions": ["Who did you help?"]})
    use(client, provider)

    questions = client.post(f"{V1}/packet-items/{item['id']}/coach/questions")
    drafted = client.post(
        f"{V1}/packet-items/{item['id']}/draft", json={"fact_keys": ["gpa"]}
    )

    assert questions.status_code == 200
    assert drafted.status_code == 403
    assert "Unclear rules count as not allowed" in drafted.json()["detail"]
    assert len(provider.prompts) == 1  # the draft request never reached the AI
    packet = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()
    assert packet["ai_coaching_allowed"] is True
    assert packet["ai_writing_allowed"] is False


def test_prohibited_rules_turn_every_kind_of_help_off(
    client: TestClient, scholarship_id: int
) -> None:
    item = make_item(client, scholarship_id, allow=False)
    set_rules(client, scholarship_id, "prohibited")
    provider = ScriptedProvider()
    use(client, provider)

    statuses = coaching_calls(client, item["id"])
    drafted = client.post(f"{V1}/packet-items/{item['id']}/draft", json={})

    assert statuses == [403] * 4 and drafted.status_code == 403
    assert not provider.prompts  # nothing was sent anywhere


def test_breakdown_keeps_only_parts_quoted_from_the_prompt(
    client: TestClient, item: dict[str, Any]
) -> None:
    provider = ScriptedProvider(
        {
            "parts": [
                {"quote": "Describe a time you helped others learn", "ask": "A story."},
                {"quote": "Explain your career goals", "ask": "Invented part."},
            ],
            "themes": ["service"],
        }
    )
    use(client, provider)

    body = client.post(f"{V1}/packet-items/{item['id']}/coach/breakdown").json()

    assert [p["ask"] for p in body["parts"]] == ["A story."]
    # The prompt may come from a web page, so it's sent as untrusted text.
    assert "<untrusted_page_text" in provider.prompts[0]


def test_interview_questions_are_returned(
    client: TestClient, item: dict[str, Any]
) -> None:
    use(client, ScriptedProvider({"questions": ["Who did you help, and how?"]}))

    body = client.post(f"{V1}/packet-items/{item['id']}/coach/questions").json()

    assert body == {"questions": ["Who did you help, and how?"]}


def test_outline_points_must_come_from_the_students_input(
    client: TestClient, item: dict[str, Any]
) -> None:
    story_id = story(client, "Tutoring club", STORY)
    use(
        client,
        ScriptedProvider(
            {
                "points": [
                    {
                        "point": "Open with the first tutoring session.",
                        "answer_number": 1,
                    },
                    {"point": "The club grew.", "story_id": story_id},
                    {"point": "Mention winning a national award.", "answer_number": 7},
                    {"point": "An unsourced point."},
                ]
            }
        ),
    )

    body = client.post(
        f"{V1}/packet-items/{item['id']}/coach/outline",
        json={
            "answers": [{"question": "Who did you help?", "answer": "Freshmen."}],
            "story_ids": [story_id],
        },
    ).json()

    assert [p["point"] for p in body["points"]] == [
        "Open with the first tutoring session.",
        "The club grew.",
    ]


def test_outline_rejects_stories_that_are_not_yours(
    client: TestClient, item: dict[str, Any]
) -> None:
    use(client, ScriptedProvider())

    response = client.post(
        f"{V1}/packet-items/{item['id']}/coach/outline", json={"story_ids": [999]}
    )

    assert response.status_code == 422


def test_feedback_drops_quotes_that_are_not_in_the_text(
    client: TestClient, item: dict[str, Any]
) -> None:
    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions",
        json={"text": "I helped freshmen with algebra every week."},
    ).json()
    version_id = body["items"][0]["versions"][0]["id"]
    use(
        client,
        ScriptedProvider(
            {
                "notes": [
                    {
                        "aspect": "specific details",
                        "comment": "Good detail.",
                        "quote": "freshmen with algebra",
                    },
                    {
                        "aspect": "voice",
                        "comment": "Invented quote.",
                        "quote": "I changed the world",
                    },
                ]
            }
        ),
    )

    out = client.post(
        f"{V1}/packet-items/{item['id']}/coach/feedback",
        json={"version_id": version_id},
    ).json()

    assert [n["quote"] for n in out["notes"]] == ["freshmen with algebra", None]
    assert out["length_note"] == "7 of 120 words."


def test_draft_keeps_only_sentences_backed_by_chosen_material(
    client: TestClient, item: dict[str, Any]
) -> None:
    client.put(f"{V1}/facts/gpa", json={"value": 3.8})
    tutoring = story(client, "Tutoring club", STORY)
    story(client, "Baking", PRIVATE_STORY)  # not chosen
    quote = {"story_id": tutoring, "quote": "I started a peer tutoring club"}
    provider = ScriptedProvider(
        {
            "sentences": [
                {
                    "text": "I started a peer tutoring club at Lincoln High School.",
                    "story_quotes": [quote],
                },
                {
                    "text": "By spring, 12 students had joined.",
                    "story_quotes": [
                        {
                            "story_id": tutoring,
                            "quote": "12 students had joined the club",
                        }
                    ],
                    "new_paragraph": True,
                },
                {"text": "It taught me patience."},  # cites nothing
                {
                    "text": "I tutored 40 students.",  # invented number
                    "story_quotes": [quote],
                },
                {
                    "text": "I tutored at Riverside Library.",  # invented place
                    "story_quotes": [quote],
                },
                {
                    "text": "I won the tutoring award.",
                    "story_quotes": [{"story_id": tutoring, "quote": "I won an award"}],
                },
                {"text": "My GPA is 3.8.", "fact_keys": ["gpa"]},  # gpa not chosen
            ]
        }
    )
    use(client, provider)

    response = client.post(
        f"{V1}/packet-items/{item['id']}/draft", json={"story_ids": [tutoring]}
    )

    assert response.status_code == 200, response.text
    out = response.json()
    assert out["kept"] == 2 and len(out["removed"]) == 5
    reasons = " | ".join(r["reason"] for r in out["removed"])
    assert "doesn't cite" in reasons and "40" in reasons
    assert "Riverside Library" in reasons and "isn't in your story" in reasons
    assert "a fact you didn't choose" in reasons
    [version] = out["packet"]["items"][0]["versions"]
    assert version["id"] == out["version_id"]
    assert version["origin"] == "ai_draft" and version["approved_at"] is None
    assert version["text"] == (
        "I started a peer tutoring club at Lincoln High School.\n\n"
        "By spring, 12 students had joined."
    )
    assert version["provenance"][0]["stories"][0]["title"] == "Tutoring club"
    # Only what the student chose was sent.
    sent = provider.prompts[0]
    assert "peer tutoring club" in sent
    assert "bake bread" not in sent and "3.8" not in sent


def test_a_draft_with_nothing_traceable_is_not_saved(
    client: TestClient, scholarship_id: int, item: dict[str, Any]
) -> None:
    tutoring = story(client, "Tutoring club", STORY)
    use(client, ScriptedProvider({"sentences": [{"text": "I am a natural leader."}]}))

    response = client.post(
        f"{V1}/packet-items/{item['id']}/draft", json={"story_ids": [tutoring]}
    )

    assert response.status_code == 422
    assert "could be traced" in response.json()["detail"]
    packet = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()
    assert packet["items"][0]["versions"] == []


def test_claim_check_highlights_details_not_in_facts_or_stories(
    client: TestClient, item: dict[str, Any]
) -> None:
    story(client, "Tutoring club", STORY)
    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions",
        json={
            "text": "I tutored at Lincoln High School. I helped 40 students at "
            "Riverside Library. I learned a lot."
        },
    ).json()
    version_id = body["items"][0]["versions"][0]["id"]

    out = client.get(
        f"{V1}/packet-items/{item['id']}/versions/{version_id}/claims"
    ).json()

    assert [s["unsupported"] for s in out["sentences"]] == [
        [],
        ["40", "Riverside Library"],
        [],
    ]
    assert out["unsupported_count"] == 2


def test_ai_turned_off_says_how_to_proceed(
    client: TestClient, item: dict[str, Any]
) -> None:
    use(client, NoAIProvider())

    response = client.post(f"{V1}/packet-items/{item['id']}/coach/questions")

    assert response.status_code == 503
    assert "AI is turned off" in response.json()["detail"]


@pytest.mark.parametrize(
    ("sentence", "claims"),
    [
        # Found in the browser check: a joining word was kept on the end.
        ("I tutored at Lincoln High School and the library.", ["Lincoln High School"]),
        ("I volunteered at the Bank of America office.", ["Bank of America"]),
        ("My GPA is 3.80.", ["GPA", "3.80"]),
        ("When I joined, I learned a lot.", []),
    ],
)
def test_claims_are_names_and_numbers(sentence: str, claims: list[str]) -> None:
    assert sorted(claims_in(sentence)) == sorted(claims)

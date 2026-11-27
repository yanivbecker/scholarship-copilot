"""Eligibility through the API: verdicts follow the profile (FR-E1-E6).

A fictional scholarship is extracted with a scripted AI, then the student's
facts and answers change and the verdict follows immediately.
"""

from typing import Any

from fastapi.testclient import TestClient

from app.ai.factory import get_ai_provider
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award

V1 = "/api/v1"


def eligibility(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    response = client.get(f"{V1}/scholarships/{scholarship_id}/eligibility")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def set_facts(client: TestClient, **facts: Any) -> None:
    for key, value in facts.items():
        assert client.put(f"{V1}/facts/{key}", json={"value": value}).status_code == 200


def free_text_id(body: dict[str, Any], words: str) -> int:
    matches = [
        int(c["criterion_id"])
        for c in body["criteria"]
        if c["confirmable"] and words in c["quote"]
    ]
    return matches[0]


def test_empty_profile_needs_info_with_exact_questions(
    client: TestClient, scholarship_id: int
) -> None:
    body = eligibility(client, scholarship_id)

    assert body["verdict"] == "needs_info"
    fact_questions = [q["fact_key"] for q in body["questions"] if q["fact_key"]]
    assert fact_questions == [
        "gpa",
        "state_of_residence",
        "enrollment_status",
        "education_level",
    ]
    assert all(c["quote"] in PAGE for c in body["criteria"])  # evidence travels along


def test_verdict_follows_the_profile_immediately(
    client: TestClient, scholarship_id: int
) -> None:
    set_facts(
        client,
        gpa=3.5,
        state_of_residence="OH",
        enrollment_status="full_time",
        education_level="undergraduate",
    )
    body = eligibility(client, scholarship_id)
    assert body["verdict"] == "needs_info"  # only the free-text items remain

    for words in ("leadership",):
        cid = free_text_id(body, words)
        put = client.put(
            f"{V1}/scholarships/{scholarship_id}/criteria/{cid}/confirmation",
            json={"answer": True},
        )
        assert put.status_code == 200
    assert eligibility(client, scholarship_id)["verdict"] == "eligible"

    set_facts(client, gpa=2.5)  # FR-E4: a profile change re-decides at once
    body = eligibility(client, scholarship_id)
    assert body["verdict"] == "ineligible"
    gpa = next(c for c in body["criteria"] if c["kind"] == "gpa_min")
    assert gpa["outcome"] == "not_met" and "2.5" in gpa["reason"]


def test_saying_no_to_a_free_text_requirement(
    client: TestClient, scholarship_id: int
) -> None:
    cid = free_text_id(eligibility(client, scholarship_id), "leadership")

    body = client.put(
        f"{V1}/scholarships/{scholarship_id}/criteria/{cid}/confirmation",
        json={"answer": False},
    ).json()

    assert body["verdict"] == "ineligible"
    cleared = client.put(
        f"{V1}/scholarships/{scholarship_id}/criteria/{cid}/confirmation",
        json={"answer": None},
    ).json()
    assert cleared["verdict"] == "needs_info"


def test_answers_survive_re_extraction_of_the_same_wording(
    client: TestClient, scholarship_id: int
) -> None:
    cid = free_text_id(eligibility(client, scholarship_id), "leadership")
    client.put(
        f"{V1}/scholarships/{scholarship_id}/criteria/{cid}/confirmation",
        json={"answer": True},
    )
    provider = ScriptedProvider(answer(award()))
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]
    [source] = client.get(f"{V1}/sources").json()

    client.post(f"{V1}/sources/{source['id']}/extract")  # new criterion rows

    body = eligibility(client, scholarship_id)
    leadership = next(c for c in body["criteria"] if "leadership" in c["quote"])
    assert leadership["outcome"] == "met"


def test_profile_criteria_cannot_be_confirmed_by_hand(
    client: TestClient, scholarship_id: int
) -> None:
    gpa = next(
        c
        for c in eligibility(client, scholarship_id)["criteria"]
        if c["kind"] == "gpa_min"
    )

    url = f"{V1}/scholarships/{scholarship_id}/criteria/{gpa['criterion_id']}"
    response = client.put(f"{url}/confirmation", json={"answer": True})

    assert response.status_code == 422
    assert "Update your profile" in response.json()["detail"]


def test_unknown_criterion_is_404(client: TestClient, scholarship_id: int) -> None:
    response = client.put(
        f"{V1}/scholarships/{scholarship_id}/criteria/9999/confirmation",
        json={"answer": True},
    )

    assert response.status_code == 404


def test_list_includes_score_with_labeled_parts(
    client: TestClient, scholarship_id: int
) -> None:
    [item] = client.get(f"{V1}/eligibility").json()

    assert item["scholarship_id"] == scholarship_id
    assert item["deadline"] == "2027-03-01"
    bases = {p["name"]: p["basis"] for p in item["score"]["parts"]}
    assert bases["fit"] == "estimate" and bases["amount"] == "listing"
    assert "not your chances" in item["score"]["note"]

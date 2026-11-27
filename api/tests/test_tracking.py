"""Status tracking (FR-UI4) and the audit log (FR-A7). Fictional data."""

from typing import Any

from fastapi.testclient import TestClient

from app.ai.factory import get_ai_provider
from tests.fakes import ScriptedProvider
from tests.sample_listing import PAGE, answer, award

V1 = "/api/v1"


def status(client: TestClient, sid: int) -> dict[str, Any]:
    body: dict[str, Any] = client.get(f"{V1}/scholarships/{sid}/status").json()
    return body


def move(client: TestClient, sid: int, to: str, **extra: Any) -> Any:
    return client.post(f"{V1}/scholarships/{sid}/status", json={"status": to, **extra})


def make_eligible(client: TestClient, sid: int) -> None:
    facts = {
        "gpa": 3.5,
        "state_of_residence": "OH",
        "enrollment_status": "full_time",
        "education_level": "undergraduate",
    }
    for key, value in facts.items():
        client.put(f"{V1}/facts/{key}", json={"value": value})
    body = client.get(f"{V1}/scholarships/{sid}/eligibility").json()
    for c in body["criteria"]:
        if c["confirmable"]:
            client.put(
                f"{V1}/scholarships/{sid}/criteria/{c['criterion_id']}/confirmation",
                json={"answer": True},
            )


def finished_packet(client: TestClient, sid: int) -> dict[str, Any]:
    """A packet whose one required item (a document) is ticked off."""
    packet: dict[str, Any] = client.get(f"{V1}/scholarships/{sid}/packet").json()
    body = client.post(
        f"{V1}/packets/{packet['id']}/items",
        json={"kind": "document", "title": "Transcript"},
    ).json()
    item = body["items"][0]
    client.put(
        f"{V1}/packet-items/{item['id']}",
        json={"kind": "document", "title": "Transcript", "done": True},
    )
    return packet


def test_new_scholarships_start_as_discovered(
    client: TestClient, scholarship_id: int
) -> None:
    body = status(client, scholarship_id)

    assert body["status"] == "discovered" and body["label"] == "Discovered"
    [step] = body["next_steps"]
    assert step["status"] == "eligibility_confirmed"
    assert "Answer the open questions" in step["blocked_reason"]  # not eligible yet
    assert body["history"] == []


def test_eligibility_confirmation_is_checked_by_the_system(
    client: TestClient, scholarship_id: int
) -> None:
    refused = move(client, scholarship_id, "eligibility_confirmed")
    assert refused.status_code == 422

    make_eligible(client, scholarship_id)
    accepted = move(client, scholarship_id, "eligibility_confirmed")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "eligibility_confirmed"


def test_steps_cannot_be_skipped(client: TestClient, scholarship_id: int) -> None:
    response = move(client, scholarship_id, "submitted", confirmed=True)

    assert response.status_code == 422
    assert "directly" in response.json()["detail"]


def test_full_path_with_explicit_submission_and_audit(
    client: TestClient, scholarship_id: int
) -> None:
    make_eligible(client, scholarship_id)
    for step in ("eligibility_confirmed", "ready_to_apply", "in_progress"):
        assert move(client, scholarship_id, step).status_code == 200
    packet = finished_packet(client, scholarship_id)
    assert move(client, scholarship_id, "awaiting_approval").status_code == 200
    not_approved = move(client, scholarship_id, "submitted", confirmed=True)
    assert not_approved.status_code == 422
    assert "Approve the application packet" in not_approved.json()["detail"]
    client.post(f"{V1}/packets/{packet['id']}/approve")

    unconfirmed = move(client, scholarship_id, "submitted")
    assert unconfirmed.status_code == 422  # FR-A7: the student must say so
    assert "submitted the application yourself" in unconfirmed.json()["detail"]
    steps = {s["status"]: s for s in status(client, scholarship_id)["next_steps"]}
    assert steps["submitted"]["needs_confirmation"] is True

    done = move(
        client, scholarship_id, "submitted", confirmed=True, note="Sent via portal"
    )
    assert done.json()["status"] == "submitted"
    assert move(client, scholarship_id, "won").json()["status"] == "won"

    history = [h for h in status(client, scholarship_id)["history"] if h["to_status"]]
    assert [h["to_status"] for h in history] == [
        "won",
        "submitted",
        "awaiting_approval",
        "in_progress",
        "ready_to_apply",
        "eligibility_confirmed",
    ]
    assert history[1]["note"] == "Sent via portal"


def test_one_step_back_undoes_a_mistake(
    client: TestClient, scholarship_id: int
) -> None:
    make_eligible(client, scholarship_id)
    move(client, scholarship_id, "eligibility_confirmed")

    back = move(client, scholarship_id, "discovered")

    assert back.json()["status"] == "discovered"
    assert len(back.json()["history"]) == 2  # both changes are on record


def test_history_follows_a_merge(client: TestClient, scholarship_id: int) -> None:
    make_eligible(client, scholarship_id)
    move(client, scholarship_id, "eligibility_confirmed")
    # A second, different scholarship to merge in.

    page = PAGE + "\nThe Test Foundation STEM Memorial Award\n"
    provider = ScriptedProvider(
        answer(
            award(
                name="The Test Foundation STEM Memorial Award",
                cycle_year=2028,
                deadline=None,
                deadline_quote=None,
            )
        )
    )
    client.app.dependency_overrides[get_ai_provider] = lambda: provider  # type: ignore[attr-defined]
    source = client.post(
        f"{V1}/sources", json={"url": "https://example.org/memorial"}
    ).json()
    client.post(f"{V1}/sources/{source['id']}/paste", json={"text": page})
    client.post(f"{V1}/sources/{source['id']}/extract")
    other = next(
        s for s in client.get(f"{V1}/scholarships").json() if s["id"] != scholarship_id
    )
    move(
        client, other["id"], "eligibility_confirmed"
    )  # refused: not eligible, no audit

    client.post(
        f"{V1}/scholarships/{other['id']}/merge", json={"other_id": scholarship_id}
    )

    history = status(client, other["id"])["history"]
    assert [h["to_status"] for h in history] == ["eligibility_confirmed"]


def test_approval_waits_for_a_complete_packet(
    client: TestClient, scholarship_id: int
) -> None:
    """FR-A7: in progress -> awaiting approval only when every item is done."""
    make_eligible(client, scholarship_id)
    for step in ("eligibility_confirmed", "ready_to_apply", "in_progress"):
        move(client, scholarship_id, step)
    [step] = [
        s
        for s in status(client, scholarship_id)["next_steps"]
        if s["status"] == "awaiting_approval"
    ]
    assert "Add the application's items" in step["blocked_reason"]

    packet = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()
    client.post(
        f"{V1}/packets/{packet['id']}/items",
        json={"kind": "essay", "title": "Leadership essay"},
    )
    refused = move(client, scholarship_id, "awaiting_approval")

    assert refused.status_code == 422
    assert "Leadership essay" in refused.json()["detail"]

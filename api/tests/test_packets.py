"""Application packets: checklist, versions, approval, library (FR-A6-A8).

All prompts and responses are fictional.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

V1 = "/api/v1"
ESSAY = {
    "kind": "essay",
    "title": "Leadership essay",
    "prompt": "Describe a time you led a group.",
    "limit_value": 10,
    "limit_unit": "words",
}


@pytest.fixture(name="packet")
def fixture_packet(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    response = client.get(f"{V1}/scholarships/{scholarship_id}/packet")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def add(
    client: TestClient, packet: dict[str, Any], item: dict[str, Any]
) -> dict[str, Any]:
    response = client.post(f"{V1}/packets/{packet['id']}/items", json=item)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def approve(client: TestClient, item: dict[str, Any], version: dict[str, Any]) -> None:
    url = f"{V1}/packet-items/{item['id']}/versions/{version['id']}/approve"
    assert client.post(url).status_code == 200


def test_packet_is_created_once_per_cycle(
    client: TestClient, scholarship_id: int, packet: dict[str, Any]
) -> None:
    again = client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()

    assert again["id"] == packet["id"]
    assert packet["rules_status"] == "unchecked"
    assert packet["ai_writing_allowed"] is False  # nothing checked yet
    assert packet["progress"] == {
        "finished": 0,
        "required": 0,
        "missing": [],
        "complete": True,
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "essay", "title": "  "},
        {"kind": "essay", "title": "x", "limit_value": 250},  # number without a unit
        {"kind": "essay", "title": "x", "limit_value": 0, "limit_unit": "words"},
    ],
)
def test_items_are_validated(
    client: TestClient, packet: dict[str, Any], bad: dict[str, Any]
) -> None:
    response = client.post(f"{V1}/packets/{packet['id']}/items", json=bad)

    assert response.status_code == 422


def test_versions_are_never_overwritten(
    client: TestClient, packet: dict[str, Any]
) -> None:
    item = add(client, packet, ESSAY)["items"][0]
    url = f"{V1}/packet-items/{item['id']}/versions"

    client.post(url, json={"text": "First try at the essay."})
    body = client.post(url, json={"text": "  Second try, kept exactly.  "}).json()

    versions = body["items"][0]["versions"]
    assert [(v["number"], v["text"]) for v in versions] == [
        (1, "First try at the essay."),
        (2, "  Second try, kept exactly.  "),
    ]
    assert versions[1]["words"] == 4 and versions[1]["origin"] == "student"


def test_over_limit_version_can_be_saved_but_not_approved(
    client: TestClient, packet: dict[str, Any]
) -> None:
    item = add(client, packet, ESSAY)["items"][0]
    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions",
        json={"text": "one two three four five six seven eight nine ten eleven"},
    ).json()
    version = body["items"][0]["versions"][0]
    assert version["over_limit"] is True  # FR-A6

    response = client.post(
        f"{V1}/packet-items/{item['id']}/versions/{version['id']}/approve"
    )

    assert response.status_code == 422
    assert "longer than the limit" in response.json()["detail"]


def test_approving_finishes_the_item_and_fills_the_library(
    client: TestClient, packet: dict[str, Any]
) -> None:
    item = add(client, packet, ESSAY)["items"][0]
    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions",
        json={"text": "I led our robotics team."},
    ).json()
    version_id = body["items"][0]["versions"][0]["id"]

    approved = client.post(
        f"{V1}/packet-items/{item['id']}/versions/{version_id}/approve"
    ).json()

    assert approved["items"][0]["finished"] is True
    assert approved["items"][0]["approved_version_id"] == version_id
    [entry] = client.get(f"{V1}/library").json()
    assert (
        entry["text"] == "I led our robotics team."
        and entry["title"] == "Leadership essay"
    )


def test_library_text_starts_a_new_unapproved_version(
    client: TestClient, packet: dict[str, Any]
) -> None:
    first = add(client, packet, ESSAY)["items"][0]
    body = client.post(
        f"{V1}/packet-items/{first['id']}/versions", json={"text": "Reusable story."}
    ).json()
    approve(client, first, body["items"][0]["versions"][0])
    second = add(client, packet, {**ESSAY, "title": "Another essay"})["items"][1]
    [entry] = client.get(f"{V1}/library").json()

    body = client.post(
        f"{V1}/packet-items/{second['id']}/use-library", json={"entry_id": entry["id"]}
    ).json()

    copy = body["items"][1]["versions"][0]
    assert copy["origin"] == "library" and copy["text"] == "Reusable story."
    assert copy["approved_at"] is None  # reused text still needs the student's approval


def test_documents_are_ticked_off_but_writing_is_not(
    client: TestClient, packet: dict[str, Any]
) -> None:
    body = add(client, packet, {"kind": "document", "title": "Official transcript"})
    add(client, packet, ESSAY)
    doc, essay = (
        body["items"][0],
        client.get(f"{V1}/scholarships/{packet['scholarship_id']}/packet").json()[
            "items"
        ][1],
    )

    ticked = client.put(
        f"{V1}/packet-items/{doc['id']}",
        json={"kind": "document", "title": "Official transcript", "done": True},
    )
    refused = client.put(
        f"{V1}/packet-items/{essay['id']}", json={**ESSAY, "done": True}
    )

    assert ticked.json()["items"][0]["finished"] is True
    assert refused.status_code == 422
    assert (
        client.post(
            f"{V1}/packet-items/{doc['id']}/versions", json={"text": "x"}
        ).status_code
        == 422
    )


def test_packet_approval_needs_every_required_item(
    client: TestClient, scholarship_id: int, packet: dict[str, Any]
) -> None:
    item = add(client, packet, ESSAY)["items"][0]
    add(
        client,
        packet,
        {"kind": "document", "title": "Optional photo", "required": False},
    )

    refused = client.post(f"{V1}/packets/{packet['id']}/approve")
    assert refused.status_code == 422
    assert "Leadership essay" in refused.json()["detail"]

    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions", json={"text": "Short and done."}
    ).json()
    approve(client, item, body["items"][0]["versions"][0])
    approved = client.post(f"{V1}/packets/{packet['id']}/approve").json()
    assert approved["approved_at"] is not None
    assert approved["progress"]["complete"] is True

    # Approving a new response version means the packet needs approving again.
    body = client.post(
        f"{V1}/packet-items/{item['id']}/versions", json={"text": "A better version."}
    ).json()
    approve(client, item, body["items"][0]["versions"][1])
    assert (
        client.get(f"{V1}/scholarships/{scholarship_id}/packet").json()["approved_at"]
        is None
    )

    history = client.get(f"{V1}/scholarships/{scholarship_id}/status").json()["history"]
    assert [h["action"] for h in history].count("response_approved") == 2
    assert "packet_approved" in [h["action"] for h in history]


def test_other_users_items_are_not_found(client: TestClient) -> None:
    assert (
        client.post(f"{V1}/packet-items/999/versions", json={"text": "x"}).status_code
        == 404
    )

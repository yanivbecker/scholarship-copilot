"""What the browser extension may fill (FR-X1) and the fill record (FR-A7).

All data is fictional.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

V1 = "/api/v1"


def packet_of(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    body: dict[str, Any] = client.get(
        f"{V1}/scholarships/{scholarship_id}/packet"
    ).json()
    return body


def approve_latest(client: TestClient, item: dict[str, Any]) -> None:
    version = item["versions"][-1]
    url = f"{V1}/packet-items/{item['id']}/versions/{version['id']}/approve"
    assert client.post(url).status_code == 200


@pytest.fixture(name="facts")
def fixture_facts(client: TestClient) -> None:
    for key, value in {
        "full_name": "Sam Example",
        "email": "sam@example.org",
        "gpa": 3.8,
        "gender": "nonbinary",  # sensitive: never added as a common field
    }.items():
        assert client.put(f"{V1}/facts/{key}", json={"value": value}).status_code == 200


@pytest.mark.usefixtures("facts")
def test_common_fields_come_from_the_profile_but_need_approval(
    client: TestClient, scholarship_id: int
) -> None:
    packet = packet_of(client, scholarship_id)
    url = f"{V1}/packets/{packet['id']}/common-fields"

    body = client.post(url).json()
    again = client.post(url).json()

    items = {i["title"]: i for i in body["items"]}
    assert list(items) == ["Full name", "Email", "GPA"]  # form order, no gender
    gpa = items["GPA"]
    assert gpa["kind"] == "form_field"
    assert [(v["text"], v["origin"]) for v in gpa["versions"]] == [("3.8", "profile")]
    assert gpa["finished"] is False  # copied, not approved
    assert len(again["items"]) == 3  # not added twice


@pytest.mark.usefixtures("facts")
def test_form_fields_are_finished_by_approving_their_value(
    client: TestClient, scholarship_id: int
) -> None:
    packet = packet_of(client, scholarship_id)
    [name, *_] = client.post(f"{V1}/packets/{packet['id']}/common-fields").json()[
        "items"
    ]

    ticked = client.put(
        f"{V1}/packet-items/{name['id']}",
        json={"kind": "form_field", "title": "Full name", "done": True},
    )
    approve_latest(client, name)

    assert ticked.status_code == 422
    assert packet_of(client, scholarship_id)["items"][0]["finished"] is True


@pytest.mark.usefixtures("facts")
def test_the_extension_only_gets_approved_text_of_an_approved_packet(
    client: TestClient, scholarship_id: int
) -> None:
    packet = packet_of(client, scholarship_id)
    items = client.post(f"{V1}/packets/{packet['id']}/common-fields").json()["items"]
    for item in items:
        approve_latest(client, item)
    client.post(
        f"{V1}/packets/{packet['id']}/items",
        json={"kind": "document", "title": "Transcript", "required": False},
    )
    sheet_url = f"{V1}/autofill/packets/{packet['id']}"

    before = client.get(sheet_url)
    assert before.status_code == 422 and "Approve the packet" in before.json()["detail"]
    assert client.get(f"{V1}/autofill/packets").json() == []

    # A newer, unapproved version must not replace the approved one.
    email = next(i for i in items if i["title"] == "Email")
    client.post(
        f"{V1}/packet-items/{email['id']}/versions", json={"text": "draft@x.org"}
    )
    approve_latest(client, next(i for i in items if i["title"] == "Full name"))
    assert client.post(f"{V1}/packets/{packet['id']}/approve").status_code == 200

    sheet = client.get(sheet_url).json()
    assert {e["title"]: e["text"] for e in sheet["entries"]} == {
        "Full name": "Sam Example",
        "Email": "sam@example.org",
        "GPA": "3.8",
    }  # no document, no unapproved draft
    [listed] = client.get(f"{V1}/autofill/packets").json()
    assert listed["packet_id"] == packet["id"] and listed["hosts"] == ["example.org"]


def _approved_packet(client: TestClient, scholarship_id: int) -> dict[str, Any]:
    packet = packet_of(client, scholarship_id)
    body = client.post(
        f"{V1}/packets/{packet['id']}/items",
        json={"kind": "form_field", "title": "Major"},
    ).json()
    item = body["items"][0]
    client.post(f"{V1}/packet-items/{item['id']}/versions", json={"text": "Biology"})
    approve_latest(client, packet_of(client, scholarship_id)["items"][0])
    assert client.post(f"{V1}/packets/{packet['id']}/approve").status_code == 200
    return packet


def test_withdrawing_approval_takes_the_packet_away_from_the_extension(
    client: TestClient, scholarship_id: int
) -> None:
    packet = _approved_packet(client, scholarship_id)

    client.delete(f"{V1}/packets/{packet['id']}/approve")

    assert client.get(f"{V1}/autofill/packets").json() == []
    assert client.get(f"{V1}/autofill/packets/{packet['id']}").status_code == 422


def test_a_fill_is_recorded_with_counts_and_host_only(
    client: TestClient, scholarship_id: int
) -> None:
    packet = _approved_packet(client, scholarship_id)

    response = client.post(
        f"{V1}/autofill/packets/{packet['id']}/fills",
        json={"host": "apply.example.org", "filled": 4, "unmatched": 2},
    )

    assert response.status_code == 204
    history = client.get(f"{V1}/scholarships/{scholarship_id}/status").json()["history"]
    [event] = [h for h in history if h["action"] == "autofill_used"]
    assert (
        event["note"]
        == "Filled 4 field(s) on apply.example.org; 2 left for you to fill"
    )


def test_fills_of_unapproved_packets_are_refused(
    client: TestClient, scholarship_id: int
) -> None:
    packet = packet_of(client, scholarship_id)

    response = client.post(
        f"{V1}/autofill/packets/{packet['id']}/fills",
        json={"host": "apply.example.org", "filled": 1, "unmatched": 0},
    )

    assert response.status_code == 422

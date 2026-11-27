"""Onboarding and sources API. Fictional test data."""

from fastapi.testclient import TestClient

STEP = "/api/v1/onboarding/steps"


def test_onboarding_state_lists_steps_and_next_step(client: TestClient) -> None:
    body = client.get("/api/v1/onboarding").json()

    assert [s["key"] for s in body["steps"]] == [
        "basics",
        "resume",
        "questionnaire",
        "preferences",
        "sources",
    ]
    basics = body["steps"][0]
    assert "school_name" in basics["fact_keys"]
    assert body["next_step"] == "basics"


def test_submit_step_saves_typed_answers(client: TestClient) -> None:
    response = client.post(
        f"{STEP}/basics", json={"facts": {"expected_graduation_year": 2029}}
    )

    assert response.status_code == 200
    assert response.json()["next_step"] == "resume"
    facts = client.get("/api/v1/facts").json()
    assert facts[0]["value"] == 2029 and facts[0]["origin"] == "questionnaire"


def test_submit_step_reports_field_errors(client: TestClient) -> None:
    response = client.post(
        f"{STEP}/basics",
        json={"facts": {"expected_graduation_year": 3000, "major": "  "}},
    )

    assert response.status_code == 422
    errors = response.json()["field_errors"]
    assert set(errors) == {"expected_graduation_year", "major"}
    assert client.get("/api/v1/facts").json() == []


def test_string_numbers_are_not_coerced(client: TestClient) -> None:
    response = client.post(
        f"{STEP}/basics", json={"facts": {"expected_graduation_year": "2029"}}
    )

    assert response.status_code == 422


def test_preferences_are_saved_on_the_profile(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/profile",
        json={"operating_mode": "discovery", "notifications_enabled": False},
    )

    assert response.json()["notifications_enabled"] is False
    assert response.json()["operating_mode"] == "discovery"


# --- Sources ---


def test_add_list_and_delete_source(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sources",
        json={"url": "HTTPS://Example.org/awards#top", "label": " Test Foundation "},
    )

    assert created.status_code == 201
    source = created.json()
    assert source["url"] == "https://example.org/awards"
    assert source["label"] == "Test Foundation"
    assert source["status"] == "approved"  # added by hand (FR-D1)
    assert len(client.get("/api/v1/sources").json()) == 1

    assert client.delete(f"/api/v1/sources/{source['id']}").status_code == 204
    assert client.get("/api/v1/sources").json() == []


def test_duplicate_source_is_a_conflict(client: TestClient) -> None:
    client.post("/api/v1/sources", json={"url": "https://example.org/a"})

    response = client.post("/api/v1/sources", json={"url": "https://EXAMPLE.org/a#x"})

    assert response.status_code == 409


def test_unsafe_sources_are_rejected_with_a_reason(client: TestClient) -> None:
    private = client.post("/api/v1/sources", json={"url": "http://192.168.0.1/"})
    aggregator = client.post("/api/v1/sources", json={"url": "https://fastweb.com/"})

    assert private.status_code == 422
    assert "Private" in private.json()["detail"]
    assert aggregator.status_code == 422
    assert "Aggregator" in aggregator.json()["detail"]
    assert client.get("/api/v1/sources").json() == []


def test_deleting_a_missing_source_is_404(client: TestClient) -> None:
    assert client.delete("/api/v1/sources/999").status_code == 404

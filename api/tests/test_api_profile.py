"""Profile, facts and story API (FR-P3-P7). All data is fictional test data."""

from fastapi.testclient import TestClient

# --- Profile (FR-P7) --------------------------------------------------------


def test_profile_starts_in_hybrid_mode(client: TestClient) -> None:
    body = client.get("/api/v1/profile").json()

    assert body["operating_mode"] == "hybrid"
    assert body["onboarding_completed_at"] is None


def test_patch_profile_changes_mode_and_name(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/profile",
        json={"operating_mode": "discovery", "display_name": "Test Student"},
    )

    assert response.status_code == 200
    assert response.json()["operating_mode"] == "discovery"
    assert client.get("/api/v1/profile").json()["display_name"] == "Test Student"


def test_patch_profile_rejects_unknown_mode(client: TestClient) -> None:
    response = client.patch("/api/v1/profile", json={"operating_mode": "autopilot"})

    assert response.status_code == 422


# --- Catalog ----------------------------------------------------------------


def test_catalog_lists_sections_with_sensitive_flags(client: TestClient) -> None:
    sections = client.get("/api/v1/facts/catalog").json()["sections"]
    by_key = {s["key"]: s for s in sections}

    assert [s["key"] for s in sections][:2] == ["basics", "education"]
    assert by_key["citizenship"]["sensitive"] is True
    assert by_key["education"]["sensitive"] is False
    gpa = next(f for f in by_key["education"]["facts"] if f["key"] == "gpa")
    assert gpa["type"] == "number" and gpa["max_value"] == 5


# --- Facts (FR-P3, FR-P4, FR-P6) --------------------------------------------


def test_put_then_list_fact(client: TestClient) -> None:
    put = client.put("/api/v1/facts/gpa", json={"value": 3.9})

    assert put.status_code == 200
    assert put.json()["origin"] == "manual"
    facts = client.get("/api/v1/facts").json()
    assert [(f["key"], f["value"]) for f in facts] == [("gpa", 3.9)]


def test_questionnaire_origin_is_accepted(client: TestClient) -> None:
    response = client.put(
        "/api/v1/facts/major", json={"value": "Math", "origin": "questionnaire"}
    )

    assert response.json()["origin"] == "questionnaire"


def test_resume_origin_cannot_be_claimed_through_this_endpoint(
    client: TestClient,
) -> None:
    response = client.put(
        "/api/v1/facts/major", json={"value": "Math", "origin": "resume"}
    )

    assert response.status_code == 422


def test_string_number_is_not_coerced(client: TestClient) -> None:
    response = client.put("/api/v1/facts/gpa", json={"value": "3.9"})

    assert response.status_code == 422
    assert response.json()["detail"] == "GPA must be a number."


def test_out_of_range_value_gives_readable_error(client: TestClient) -> None:
    response = client.put("/api/v1/facts/gpa", json={"value": 9})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("GPA must be between")


def test_unknown_fact_is_rejected(client: TestClient) -> None:
    response = client.put("/api/v1/facts/shoe_size", json={"value": "9"})

    assert response.status_code == 422


def test_delete_fact(client: TestClient) -> None:
    client.put("/api/v1/facts/gender", json={"value": "Prefer to describe"})

    assert client.delete("/api/v1/facts/gender").status_code == 204
    assert client.get("/api/v1/facts").json() == []
    assert client.delete("/api/v1/facts/gender").status_code == 404


def test_missing_facts(client: TestClient) -> None:
    client.put("/api/v1/facts/major", json={"value": "History"})

    response = client.get(
        "/api/v1/facts/missing", params={"keys": ["major", "gpa", "city"]}
    )

    assert response.json() == {"missing": ["gpa", "city"]}


# --- Stories (FR-P5) --------------------------------------------------------


def test_story_crud(client: TestClient) -> None:
    created = client.post(
        "/api/v1/stories",
        json={"title": "Robotics", "body": "We built a robot.", "themes": ["Teamwork"]},
    )
    assert created.status_code == 201
    story_id = created.json()["id"]
    assert created.json()["themes"] == ["teamwork"]

    updated = client.put(
        f"/api/v1/stories/{story_id}",
        json={"title": "Robotics team", "body": "We built two robots."},
    )
    assert updated.json()["title"] == "Robotics team"
    assert updated.json()["themes"] == []

    assert client.delete(f"/api/v1/stories/{story_id}").status_code == 204
    assert client.get("/api/v1/stories").json() == []


def test_story_filter_by_theme(client: TestClient) -> None:
    for title, theme in [("A", "family"), ("B", "leadership")]:
        client.post(
            "/api/v1/stories", json={"title": title, "body": "x", "themes": [theme]}
        )

    stories = client.get("/api/v1/stories", params={"theme": "Leadership"}).json()

    assert [s["title"] for s in stories] == ["B"]


def test_invalid_story_gives_readable_error(client: TestClient) -> None:
    response = client.post("/api/v1/stories", json={"title": "", "body": "x"})

    assert response.status_code == 422
    assert "Title" in response.json()["detail"]


def test_missing_story_is_404(client: TestClient) -> None:
    response = client.put("/api/v1/stories/999", json={"title": "t", "body": "b"})

    assert response.status_code == 404


def test_suggested_themes(client: TestClient) -> None:
    themes = client.get("/api/v1/stories/themes").json()["suggested"]

    assert "leadership" in themes

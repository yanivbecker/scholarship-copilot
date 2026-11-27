"""API-wide safety checks on the OpenAPI schema."""

from typing import Any

from app.main import create_app

SERVER_ONLY_SCHEMAS = {"Settings"}


def _refs(node: Any) -> set[str]:
    """Every schema name referenced anywhere inside `node`."""
    found: set[str] = set()
    if isinstance(node, dict):
        if "$ref" in node:
            found.add(node["$ref"].rsplit("/", 1)[-1])
        children = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        children = []
    for child in children:
        found |= _refs(child)
    return found


def test_no_endpoint_accepts_server_configuration() -> None:
    # A dependency with a Settings parameter would let any caller send
    # their own configuration (provider, model, API key, data paths).
    schema = create_app().openapi()

    assert not SERVER_ONLY_SCHEMAS & set(
        schema.get("components", {}).get("schemas", {})
    )
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            body = operation.get("requestBody", {})
            assert not SERVER_ONLY_SCHEMAS & _refs(body), f"{method.upper()} {path}"


def test_extract_endpoint_takes_no_body() -> None:
    operation = create_app().openapi()["paths"]["/api/v1/sources/{source_id}/extract"][
        "post"
    ]

    assert "requestBody" not in operation

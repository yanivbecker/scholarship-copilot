from fastapi.testclient import TestClient

from app import __main__ as server
from app import __version__
from app.main import create_app


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_server_binds_to_loopback_only() -> None:
    # NFR-3
    assert server.HOST == "127.0.0.1"

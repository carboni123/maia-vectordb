"""Smoke test for health endpoint."""

from fastapi.testclient import TestClient

from maia_vectordb.main import app

client = TestClient(app)


def test_health() -> None:
    """Health endpoint returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

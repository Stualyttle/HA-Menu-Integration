"""Tests for the internal token and the health endpoint."""

from fastapi.testclient import TestClient

from app.auth import TOKEN_HEADER, token_matches
from app.config import load_or_create_token
from app.main import create_app

TOKEN = "test-token-123"


def test_health_requires_token_on_internal_listener() -> None:
    client = TestClient(create_app(require_token=True, token=TOKEN))
    response = client.get("/api/health")
    assert response.status_code == 401


def test_health_rejects_wrong_token() -> None:
    client = TestClient(create_app(require_token=True, token=TOKEN))
    response = client.get("/api/health", headers={TOKEN_HEADER: "nope"})
    assert response.status_code == 401


def test_health_accepts_correct_token() -> None:
    client = TestClient(create_app(require_token=True, token=TOKEN))
    response = client.get("/api/health", headers={TOKEN_HEADER: TOKEN})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingress_listener_needs_no_token() -> None:
    client = TestClient(create_app(require_token=False))
    response = client.get("/api/health")
    assert response.status_code == 200


def test_token_matches_is_strict() -> None:
    assert token_matches(TOKEN, TOKEN)
    assert not token_matches(None, TOKEN)
    assert not token_matches("", TOKEN)
    assert not token_matches(TOKEN + "x", TOKEN)


def test_token_is_created_once_and_persisted(tmp_path) -> None:
    first = load_or_create_token(tmp_path)
    second = load_or_create_token(tmp_path)
    assert first == second
    assert len(first) >= 32
    assert (tmp_path / "internal_token").stat().st_mode & 0o777 == 0o600

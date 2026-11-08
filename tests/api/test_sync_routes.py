"""HTTP tests for POST /api/sync: mounted on a fresh app with a temporary database."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import sync
from app.db import Stores
from app.main import create_app


@pytest.fixture
def stores(tmp_path: Path) -> Iterator[Stores]:
    opened = Stores.open(tmp_path / "menu_planner.db")
    try:
        yield opened
    finally:
        opened.close()


@pytest.fixture
def client(stores: Stores, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TZ", "Europe/Berlin")
    app: FastAPI = create_app(require_token=False, stores=stores)
    app.include_router(sync.router)
    return TestClient(app)


def test_sync_echoes_language_and_time_zone(client: TestClient) -> None:
    response = client.post("/api/sync", json={"language": "de", "time_zone": "Europe/Berlin"})
    assert response.status_code == 200
    assert response.json() == {
        "language": "de",
        "time_zone": "Europe/Berlin",
        "timezone_mismatch": False,
    }


def test_sync_reports_timezone_mismatch(client: TestClient) -> None:
    response = client.post("/api/sync", json={"language": "en", "time_zone": "America/New_York"})
    assert response.status_code == 200
    assert response.json()["timezone_mismatch"] is True


def test_sync_stores_device_values_in_settings(client: TestClient, stores: Stores) -> None:
    client.post("/api/sync", json={"language": "de", "time_zone": "Europe/Berlin"})
    assert stores.settings.get_value(sync.SYNCED_LANGUAGE_KEY) == "de"
    assert stores.settings.get_value(sync.SYNCED_TIME_ZONE_KEY) == "Europe/Berlin"


def test_sync_does_not_overwrite_user_language_setting(client: TestClient, stores: Stores) -> None:
    stores.settings.update({"language": "fr"})
    client.post("/api/sync", json={"language": "de", "time_zone": "Europe/Berlin"})
    assert stores.settings.get_value("language") == "fr"


def test_sync_requires_both_fields(client: TestClient) -> None:
    response = client.post("/api/sync", json={"language": "de"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_sync_rejects_empty_language(client: TestClient) -> None:
    response = client.post("/api/sync", json={"language": "", "time_zone": "Europe/Berlin"})
    assert response.status_code == 400

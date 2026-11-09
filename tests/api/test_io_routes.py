"""HTTP tests for the export and import endpoints (docs/API.md "Import/export")."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import io as io_api
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
def client(stores: Stores) -> TestClient:
    app: FastAPI = create_app(require_token=False, stores=stores)
    if not any(getattr(route, "path", "") == "/api/export" for route in app.routes):
        app.include_router(io_api.router)
    return TestClient(app)


def _document(
    *, items: list[dict[str, Any]], settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    doc: dict[str, Any] = {"schema_version": 1, "items": items, "categories": [], "rules": []}
    if settings is not None:
        doc["settings"] = settings
    return doc


def _error_code(response: Any) -> str:
    return response.json()["error"]["code"]


def test_export_has_schema_version_and_names_not_ids(client: TestClient, stores: Stores) -> None:
    client.post("/api/items", json={"name": "Test tempeh", "type": "protein", "track_stock": False})

    response = client.get("/api/export")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1
    names = [item["name"] for item in body["items"]]
    assert "Test tempeh" in names
    assert all("id" not in item for item in body["items"])


def test_export_excludes_usda_api_key(client: TestClient, stores: Stores) -> None:
    stores.settings.update({"usda_api_key": "secret-key-123", "household_size": 3})

    response = client.get("/api/export")

    assert response.status_code == 200
    assert "usda_api_key" not in response.text
    assert "secret-key-123" not in response.text
    assert response.json()["settings"]["household_size"] == 3


def test_import_preview_counts_added_and_skipped(client: TestClient) -> None:
    client.post("/api/items", json={"name": "Rice test", "type": "carb", "track_stock": False})
    document = _document(
        items=[
            {"name": "Rice test", "type": "carb"},
            {"name": "Jackfruit", "type": "protein"},
            {"name": "Test tempeh", "type": "protein"},
        ]
    )

    response = client.post("/api/import/preview", json=document)

    assert response.status_code == 200
    body = response.json()
    assert body["added"]["items"] == 2
    assert body["skipped"]["items"] == 1
    assert body["settings_available"] is False


def test_import_preview_reports_settings_available(client: TestClient) -> None:
    document = _document(items=[], settings={"household_size": 4})

    response = client.post("/api/import/preview", json=document)

    assert response.status_code == 200
    assert response.json()["settings_available"] is True


def test_import_merges_items(client: TestClient) -> None:
    document = _document(items=[{"name": "Test tempeh", "type": "protein"}])

    response = client.post("/api/import", json={"document": document})

    assert response.status_code == 200
    names = [item["name"] for item in client.get("/api/items").json()]
    assert "Test tempeh" in names


def test_import_without_include_settings_leaves_settings_alone(
    client: TestClient, stores: Stores
) -> None:
    stores.settings.update({"household_size": 2})
    document = _document(items=[], settings={"household_size": 5})

    response = client.post("/api/import", json={"document": document, "include_settings": False})

    assert response.status_code == 200
    assert stores.settings.get_value("household_size") == 2


def test_import_with_include_settings_applies_settings(client: TestClient, stores: Stores) -> None:
    stores.settings.update({"household_size": 2})
    document = _document(items=[], settings={"household_size": 5})

    response = client.post("/api/import", json={"document": document, "include_settings": True})

    assert response.status_code == 200
    assert stores.settings.get_value("household_size") == 5


def test_import_rejects_history(client: TestClient) -> None:
    document = _document(items=[])

    response = client.post("/api/import", json={"document": document, "include_history": True})

    assert response.status_code == 400
    assert _error_code(response) == "unsupported"


def test_import_rejects_wrong_schema_version(client: TestClient) -> None:
    document = {"schema_version": 99, "items": []}

    response = client.post("/api/import/preview", json=document)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "errors" in error["details"]


def test_import_preview_rejects_item_without_type(client: TestClient) -> None:
    document = _document(items=[{"name": "Mystery"}])

    response = client.post("/api/import/preview", json=document)

    assert response.status_code == 400
    assert _error_code(response) == "validation_error"

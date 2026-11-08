"""HTTP tests for POST /api/rules/check. The rules_check router is mounted on a fresh app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import rules_check
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
    app.include_router(rules_check.router)
    return TestClient(app)


def _category_ids(client: TestClient) -> list[int]:
    return [category["id"] for category in client.get("/api/categories").json()]


def _item_id(client: TestClient) -> int:
    return client.get("/api/items").json()[0]["id"]


def _blacklist_all_categories(client: TestClient) -> dict:
    return {
        "kind": "blacklist",
        "scope": "combination",
        "category_ids": _category_ids(client),
    }


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def test_check_returns_documented_shape(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={
            "rule": {"kind": "blacklist", "scope": "item", "item_id": _item_id(client)},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"feasible", "exhausted", "affected_days", "locked_conflicts"}
    assert isinstance(body["feasible"], bool)
    assert isinstance(body["exhausted"], bool)
    assert isinstance(body["affected_days"], list)
    assert isinstance(body["locked_conflicts"], list)


def test_check_single_item_blacklist_is_feasible(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "item", "item_id": _item_id(client)}},
    )
    assert response.status_code == 200
    assert response.json()["feasible"] is True


def test_check_with_rule_id_replaces_stored_rule(client: TestClient) -> None:
    created = client.post(
        "/api/rules",
        json={"kind": "blacklist", "scope": "combination", "category_ids": _category_ids(client)},
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    replaced = client.post(
        "/api/rules/check",
        json={
            "rule": {"kind": "blacklist", "scope": "item", "item_id": _item_id(client)},
            "rule_id": rule_id,
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["feasible"] is True


def test_check_with_unknown_rule_id_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={
            "rule": {"kind": "blacklist", "scope": "item", "item_id": _item_id(client)},
            "rule_id": 999_999,
        },
    )
    assert response.status_code == 404
    assert _error_code(response) == "not_found"


def test_check_rejects_combination_without_categories(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "combination", "category_ids": []}},
    )
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_check_rejects_item_rule_without_item(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "item"}},
    )
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_check_rejects_unknown_item(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "item", "item_id": 999_999}},
    )
    assert response.status_code == 400
    assert _error_code(response) == "unknown_reference"


def test_check_rejects_unknown_category(client: TestClient) -> None:
    response = client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "combination", "category_ids": [999_999]}},
    )
    assert response.status_code == 400
    assert _error_code(response) == "unknown_reference"


def test_check_does_not_persist_rule(client: TestClient) -> None:
    client.post(
        "/api/rules/check",
        json={"rule": {"kind": "blacklist", "scope": "item", "item_id": _item_id(client)}},
    )
    assert client.get("/api/rules").json() == []

"""Stock PUT side effects: replaced and restored days come from MenuPlanner.set_stock."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import menu
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
    app.include_router(menu.router)
    return TestClient(app)


def _planned_dinner_item(client: TestClient) -> tuple[int, str]:
    """An item from the first planned day, and that day's date."""
    days = client.get("/api/menu").json()
    planned = next(day for day in days if day["status"] == "planned")
    return planned["dinner"]["items"][0]["id"], planned["date"]


def _track(client: TestClient, item_id: int) -> None:
    current = next(item for item in client.get("/api/items").json() if item["id"] == item_id)
    body = {
        "name": current["name"],
        "type": current["type"],
        "track_stock": True,
        "category_ids": current.get("category_ids", []),
    }
    response = client.put(f"/api/items/{item_id}", json=body)
    assert response.status_code == 200


def test_out_of_stock_reports_replaced_day(client: TestClient) -> None:
    item_id, day = _planned_dinner_item(client)
    _track(client, item_id)

    response = client.put(f"/api/stock/{item_id}", json={"in_stock": False})
    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item_id
    assert body["in_stock"] is False
    assert day in body["replaced_dates"]
    assert body["restored_dates"] == []
    assert body["shopping"] == []


def test_back_in_stock_reports_restored_day(client: TestClient) -> None:
    item_id, day = _planned_dinner_item(client)
    _track(client, item_id)
    client.put(f"/api/stock/{item_id}", json={"in_stock": False})

    response = client.put(f"/api/stock/{item_id}", json={"in_stock": True})
    assert response.status_code == 200
    body = response.json()
    assert day in body["restored_dates"]
    assert body["replaced_dates"] == []


def test_out_of_stock_replacement_is_visible_on_menu(client: TestClient) -> None:
    item_id, day = _planned_dinner_item(client)
    _track(client, item_id)
    body = client.put(f"/api/stock/{item_id}", json={"in_stock": False}).json()

    day_out = next(d for d in client.get("/api/menu").json() if d["date"] == day)
    assert day in body["replaced_dates"]
    assert day_out["replaced_reason"] == "stock"
    assert item_id not in [item["id"] for item in day_out["dinner"]["items"]]


def test_clearing_answer_restores_replaced_day(client: TestClient) -> None:
    item_id, day = _planned_dinner_item(client)
    _track(client, item_id)
    client.put(f"/api/stock/{item_id}", json={"in_stock": False})

    body = client.put(f"/api/stock/{item_id}", json={"in_stock": None}).json()
    assert body["in_stock"] is None
    assert day in body["restored_dates"]


def test_stock_change_on_untracked_item_has_no_diff(client: TestClient) -> None:
    untracked = client.post(
        "/api/items", json={"name": "Untracked Test", "type": "carb", "track_stock": False}
    ).json()["id"]
    body = client.put(f"/api/stock/{untracked}", json={"in_stock": False}).json()
    assert body["replaced_dates"] == []
    assert body["restored_dates"] == []

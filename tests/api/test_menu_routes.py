"""HTTP tests for /api/menu. The menu router is mounted on a fresh app with a temporary database."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import menu
from app.db import Stores
from app.main import create_app
from app.models import DayStatus, MenuDay


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


def _future_day(client: TestClient, offset: int = 1) -> str:
    """A day inside the window that is after today."""
    today = date.today()
    return (today + timedelta(days=offset)).isoformat()


def _planned_future_day(client: TestClient) -> str:
    """The first future day in the window that already has a planned dinner."""
    today = date.today().isoformat()
    for day in _list(client):
        if day["date"] > today and day["status"] == "planned":
            return day["date"]
    pytest.fail("the starter content should plan at least one future day")


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def _list(client: TestClient) -> list[dict]:
    response = client.get("/api/menu")
    assert response.status_code == 200
    return response.json()


def test_list_menu_returns_bare_array_of_day_objects(client: TestClient) -> None:
    days = _list(client)
    assert isinstance(days, list)
    assert len(days) == 14
    day = days[0]
    assert set(day) == {
        "date",
        "status",
        "dinner",
        "kcal",
        "balance",
        "replaced_reason",
        "warnings",
    }
    assert day["status"] in {"planned", "pinned", "eaten", "empty"}
    assert isinstance(day["warnings"], list)


def test_list_menu_planned_day_has_dinner_items(client: TestClient) -> None:
    planned = [d for d in _list(client) if d["status"] == "planned"]
    assert planned, "the starter content should fill the window"
    dinner = planned[0]["dinner"]
    assert dinner is not None
    assert dinner["id"] > 0
    assert {"id", "name", "type"} <= set(dinner["items"][0])


def test_list_menu_respects_from_and_to(client: TestClient) -> None:
    start = _future_day(client, 1)
    end = _future_day(client, 3)
    response = client.get("/api/menu", params={"from": start, "to": end})
    assert response.status_code == 200
    assert [d["date"] for d in response.json()] == [start, _future_day(client, 2), end]


def test_list_menu_rejects_reversed_range(client: TestClient) -> None:
    response = client.get(
        "/api/menu", params={"from": _future_day(client, 5), "to": _future_day(client, 1)}
    )
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_list_menu_rejects_oversized_range(client: TestClient) -> None:
    response = client.get("/api/menu", params={"from": "2030-01-01", "to": "2032-01-01"})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_today_returns_single_day_object(client: TestClient) -> None:
    response = client.get("/api/menu/today")
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == date.today().isoformat()
    assert "status" in body and "warnings" in body


def test_pin_then_unpin_future_day(client: TestClient) -> None:
    day = _future_day(client)
    planned = next(d for d in _list(client) if d["date"] == day)
    assert planned["dinner"] is not None

    pinned = client.put(f"/api/menu/{day}", json={"pinned": True})
    assert pinned.status_code == 200
    assert pinned.json()["status"] == "pinned"
    assert pinned.json()["dinner"]["id"] == planned["dinner"]["id"]

    unpinned = client.put(f"/api/menu/{day}", json={"pinned": False})
    assert unpinned.status_code == 200
    assert unpinned.json()["status"] == "planned"


def test_put_requires_exactly_one_field(client: TestClient) -> None:
    day = _future_day(client)
    assert client.put(f"/api/menu/{day}", json={}).status_code == 400
    both = client.put(f"/api/menu/{day}", json={"pinned": True, "dinner_id": 1})
    assert both.status_code == 400
    assert _error_code(both) == "validation_error"


def test_put_on_past_day_is_conflict(client: TestClient) -> None:
    past = (date.today() - timedelta(days=3)).isoformat()
    response = client.put(f"/api/menu/{past}", json={"pinned": True})
    assert response.status_code == 409
    assert _error_code(response) == "conflict"


def test_put_on_day_past_window_is_conflict(client: TestClient) -> None:
    far = (date.today() + timedelta(days=400)).isoformat()
    response = client.put(f"/api/menu/{far}", json={"pinned": True})
    assert response.status_code == 409


def test_put_invalid_date_is_400(client: TestClient) -> None:
    response = client.put("/api/menu/not-a-date", json={"pinned": True})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_swap_suggestions_return_up_to_three_dinners(client: TestClient) -> None:
    day = _planned_future_day(client)
    response = client.get(f"/api/menu/{day}/swap")
    assert response.status_code == 200
    suggestions = response.json()
    assert isinstance(suggestions, list)
    assert 0 < len(suggestions) <= 3
    assert {"id", "items"} <= set(suggestions[0])
    assert suggestions[0]["items"]
    assert all("id" in item for item in suggestions[0]["items"])


def test_reading_swap_suggestions_does_not_persist_generated_dinners(
    client: TestClient, stores: Stores
) -> None:
    day = _planned_future_day(client)
    before = asyncio.run(stores.menu.list_dinners())

    response = client.get(f"/api/menu/{day}/swap")

    assert response.status_code == 200
    assert asyncio.run(stores.menu.list_dinners()) == before


def test_swap_suggestions_on_past_day_is_conflict(client: TestClient) -> None:
    past = (date.today() - timedelta(days=1)).isoformat()
    response = client.get(f"/api/menu/{past}/swap")
    assert response.status_code == 409


def test_today_can_be_swapped_before_it_is_eaten(client: TestClient) -> None:
    today = date.today().isoformat()
    current = client.get("/api/menu/today")
    assert current.status_code == 200
    assert current.json()["dinner"] is not None

    suggestions_response = client.get(f"/api/menu/{today}/swap")

    assert suggestions_response.status_code == 200
    suggestions = suggestions_response.json()
    assert suggestions
    item_ids = [item["id"] for item in suggestions[0]["items"]]
    response = client.post(f"/api/menu/{today}/swap", json={"item_ids": item_ids})
    assert response.status_code == 200
    assert response.json()["status"] == "pinned"
    assert [item["id"] for item in response.json()["dinner"]["items"]] == item_ids


def test_today_cannot_be_swapped_after_it_is_eaten(client: TestClient) -> None:
    today = date.today().isoformat()
    assert client.get("/api/menu/today").status_code == 200
    assert client.post(f"/api/menu/{today}/eaten").status_code == 200

    assert client.get(f"/api/menu/{today}/swap").status_code == 409
    assert client.post(f"/api/menu/{today}/swap", json={"dinner_id": 1}).status_code == 409


def test_swap_sets_chosen_dinner_and_pins_it(client: TestClient) -> None:
    day = _planned_future_day(client)
    suggestion = client.get(f"/api/menu/{day}/swap").json()[0]
    item_ids = [item["id"] for item in suggestion["items"]]
    response = client.post(f"/api/menu/{day}/swap", json={"item_ids": item_ids})
    assert response.status_code == 200
    body = response.json()
    assert body["dinner"]["id"] > 0
    assert [item["id"] for item in body["dinner"]["items"]] == item_ids
    assert body["status"] == "pinned"


def test_swap_requires_exactly_one_dinner_target(client: TestClient) -> None:
    day = _planned_future_day(client)

    assert client.post(f"/api/menu/{day}/swap", json={}).status_code == 400
    response = client.post(f"/api/menu/{day}/swap", json={"dinner_id": 1, "item_ids": [1, 10, 20]})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_swap_with_unknown_dinner_is_400(client: TestClient) -> None:
    day = _future_day(client)
    response = client.post(f"/api/menu/{day}/swap", json={"dinner_id": 999_999})
    assert response.status_code == 400
    assert _error_code(response) == "unknown_reference"


def test_put_with_dinner_id_swaps(client: TestClient) -> None:
    day = _planned_future_day(client)
    planned_day = next(entry for entry in _list(client) if entry["date"] == day)
    response = client.put(f"/api/menu/{day}", json={"dinner_id": planned_day["dinner"]["id"]})
    assert response.status_code == 200
    assert response.json()["dinner"]["id"] == planned_day["dinner"]["id"]


def test_eaten_marks_day_and_leaves_stock_unchanged(client: TestClient, stores: Stores) -> None:
    yesterday_date = date.today() - timedelta(days=1)
    yesterday = yesterday_date.isoformat()
    item_ids = [item.id for item in asyncio.run(stores.items.list_items())[:2]]
    dinner_id = asyncio.run(stores.menu.ensure_dinners([item_ids]))[0]
    asyncio.run(
        stores.menu.save_days(
            [MenuDay(day=yesterday_date, dinner_id=dinner_id, status=DayStatus.PLANNED)]
        )
    )
    before = client.get("/api/stock").json()
    response = client.post(f"/api/menu/{yesterday}/eaten")
    assert response.status_code == 200
    assert response.json()["status"] == "eaten"
    assert client.get("/api/stock").json() == before


def test_eaten_on_future_day_is_conflict(client: TestClient) -> None:
    response = client.post(f"/api/menu/{_future_day(client)}/eaten")
    assert response.status_code == 409
    assert _error_code(response) == "conflict"


def test_put_on_eaten_day_is_conflict(client: TestClient) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post(f"/api/menu/{yesterday}/eaten")
    response = client.put(f"/api/menu/{yesterday}", json={"pinned": False})
    assert response.status_code == 409


def test_replan_returns_window_of_days(client: TestClient) -> None:
    response = client.post("/api/menu/replan")
    assert response.status_code == 200
    days = response.json()
    assert isinstance(days, list)
    assert len(days) == 14

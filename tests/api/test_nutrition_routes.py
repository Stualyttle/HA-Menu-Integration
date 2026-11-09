"""HTTP tests for the nutrition endpoints.

Open Food Facts was in maintenance while these routes were designed, so the search payloads
below are hand-modelled from the documented product shape, not recorded from the live API.
The HTTP clients are backed by httpx.MockTransport, so no test touches the network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import nutrition as nutrition_api
from app.db import Stores
from app.main import create_app
from app.models import WarningCode, WarningRecord, WarningSubject

OFF_PRODUCTS = [
    {
        "code": "4006381333931",
        "product_name": "Chicken breast fillet",
        "nutriments": {
            "energy-kcal_100g": 110,
            "proteins_100g": 23.1,
            "carbohydrates_100g": 0.4,
            "fat_100g": 1.9,
            "fiber_100g": 0,
        },
    },
    {
        "code": "2000000000002",
        "product_name": "Chicken soup",
        "nutriments": {"energy-kj_100g": 184, "proteins_100g": 3.0},
    },
    {"code": "2000000000003", "product_name": "", "nutriments": {"energy-kcal_100g": 100}},
]

Handler = Callable[[httpx.Request], httpx.Response]


def _off_ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"count": 3, "products": OFF_PRODUCTS})


def _off_down(_: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={})


@pytest.fixture
def stores(tmp_path: Path) -> Iterator[Stores]:
    opened = Stores.open(tmp_path / "menu_planner.db")
    try:
        yield opened
    finally:
        opened.close()


def _build_client(
    stores: Stores, handler: Handler | None
) -> tuple[TestClient, list[httpx.Request]]:
    app: FastAPI = create_app(require_token=False, stores=stores)
    if not any(getattr(route, "path", "").endswith("/nutrition/lookup") for route in app.routes):
        app.include_router(nutrition_api.router)
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request) if handler is not None else _off_ok(request)

    app.state.nutrition_http = httpx.AsyncClient(transport=httpx.MockTransport(recording))
    return TestClient(app), seen


@pytest.fixture
def client(stores: Stores) -> TestClient:
    test_client, _ = _build_client(stores, None)
    return test_client


def _create_item(client: TestClient, name: str) -> int:
    response = client.post(
        "/api/items", json={"name": name, "type": "protein", "track_stock": False}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _error_code(response: Any) -> str:
    return response.json()["error"]["code"]


# Lookup


def test_lookup_returns_scored_candidates(client: TestClient) -> None:
    item_id = _create_item(client, "Chicken breast fillet")

    response = client.get(f"/api/items/{item_id}/nutrition/lookup")

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item_id
    assert body["failed_sources"] == []
    candidates = body["candidates"]
    assert candidates, "expected at least one candidate"
    best = candidates[0]
    assert best["source"] == "open_food_facts"
    assert best["external_id"] == "4006381333931"
    assert best["matched_name"] == "Chicken breast fillet"
    assert best["score"] == pytest.approx(1.0)
    assert best["kcal"] == pytest.approx(110)
    assert best["protein_g"] == pytest.approx(23.1)
    scores = [candidate["score"] for candidate in candidates]
    assert scores == sorted(scores, reverse=True)
    assert all(candidate["score"] > 0 for candidate in candidates)
    assert all(candidate["matched_name"] for candidate in candidates)


def test_lookup_does_not_persist_anything(client: TestClient) -> None:
    item_id = _create_item(client, "Chicken breast fillet")

    assert client.get(f"/api/items/{item_id}/nutrition/lookup").status_code == 200

    item = client.get(f"/api/items/{item_id}").json()
    assert item.get("nutrition") in (None, {})
    assert client.get(f"/api/items/{item_id}/nutrition/lookup").status_code == 200


def test_lookup_unknown_item_is_404(client: TestClient) -> None:
    response = client.get("/api/items/999999/nutrition/lookup")
    assert response.status_code == 404
    assert _error_code(response) == "not_found"


def test_lookup_returns_503_when_every_source_fails(stores: Stores) -> None:
    test_client, _ = _build_client(stores, _off_down)
    item_id = _create_item(test_client, "Chicken breast fillet")

    response = test_client.get(f"/api/items/{item_id}/nutrition/lookup")

    assert response.status_code == 503
    assert _error_code(response) == "lookup_unavailable"


def test_usda_is_not_queried_without_a_key(stores: Stores) -> None:
    test_client, seen = _build_client(stores, None)
    item_id = _create_item(test_client, "Chicken breast fillet")

    test_client.get(f"/api/items/{item_id}/nutrition/lookup")

    hosts = {request.url.host for request in seen}
    assert "api.nal.usda.gov" not in hosts
    assert "world.openfoodfacts.org" in hosts


# Confirm / store


def test_put_manual_stores_and_is_verified(client: TestClient) -> None:
    item_id = _create_item(client, "Home-cooked stew")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={
            "source": "manual",
            "kcal": 250,
            "protein_g": 12,
            "carbs_g": 20,
            "fat_g": 9,
            "fiber_g": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "manual"
    assert body["verified"] is True
    assert body["kcal"] == pytest.approx(250)
    assert body["fiber_g"] == pytest.approx(3)


def test_put_manual_rejects_incomplete_data(client: TestClient) -> None:
    item_id = _create_item(client, "Home-cooked stew")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={"source": "manual", "protein_g": 12, "carbs_g": 20, "fat_g": 9},
    )

    assert response.status_code == 400
    assert _error_code(response) == "validation_error"
    assert "message" in response.json()["error"]


def test_put_manual_rejects_negative_macro(client: TestClient) -> None:
    item_id = _create_item(client, "Home-cooked stew")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={"source": "manual", "kcal": 250, "protein_g": -1, "carbs_g": 20, "fat_g": 9},
    )

    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_put_rejects_unknown_fields(client: TestClient) -> None:
    item_id = _create_item(client, "Home-cooked stew")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={"source": "manual", "kcal": 1, "protein_g": 1, "carbs_g": 1, "fat_g": 1, "x": 1},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_put_candidate_confirms_a_lookup_result(client: TestClient) -> None:
    item_id = _create_item(client, "Chicken breast fillet")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={
            "source": "open_food_facts",
            "external_id": "4006381333931",
            "matched_name": "Chicken breast fillet",
            "kcal": 110,
            "protein_g": 23.1,
            "carbs_g": 0.4,
            "fat_g": 1.9,
            "fiber_g": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "open_food_facts"
    assert body["external_id"] == "4006381333931"
    assert body["verified"] is True


def test_put_candidate_without_external_id_is_rejected(client: TestClient) -> None:
    item_id = _create_item(client, "Chicken breast fillet")

    response = client.put(
        f"/api/items/{item_id}/nutrition",
        json={
            "source": "open_food_facts",
            "matched_name": "Chicken breast fillet",
            "kcal": 110,
            "protein_g": 23.1,
            "carbs_g": 0.4,
            "fat_g": 1.9,
        },
    )

    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_put_unknown_item_is_404(client: TestClient) -> None:
    response = client.put(
        "/api/items/999999/nutrition",
        json={"source": "manual", "kcal": 1, "protein_g": 1, "carbs_g": 1, "fat_g": 1},
    )
    assert response.status_code == 404
    assert _error_code(response) == "not_found"


# USDA key handling


USDA_KEY = "usda-secret-key-do-not-leak"


def test_usda_key_is_write_only(stores: Stores) -> None:
    stores.settings.update({"usda_api_key": USDA_KEY})
    test_client, seen = _build_client(stores, None)
    item_id = _create_item(test_client, "Chicken breast fillet")

    lookup = test_client.get(f"/api/items/{item_id}/nutrition/lookup")
    put = test_client.put(
        f"/api/items/{item_id}/nutrition",
        json={"source": "manual", "kcal": 1, "protein_g": 1, "carbs_g": 1, "fat_g": 1},
    )
    settings = test_client.get("/api/settings")

    for response in (lookup, put, settings):
        assert USDA_KEY not in response.text
    assert all(USDA_KEY not in str(request.url) for request in seen)
    assert all(USDA_KEY not in request.headers.get("user-agent", "") for request in seen)


def test_retry_endpoint_immediately_retries_open_lookup_failures(stores: Stores) -> None:
    test_client, seen = _build_client(stores, None)
    item_id = _create_item(test_client, "Chicken breast fillet")
    asyncio.run(
        stores.warnings.open_warning(
            WarningRecord(
                id=0,
                code=WarningCode.NUTRITION_FAILED,
                subject_type=WarningSubject.ITEM,
                subject=str(item_id),
                payload={"attempts": 1, "next_attempt_at": None, "reason": "unavailable"},
                created_at=datetime.now(UTC),
            )
        )
    )

    response = test_client.post("/api/items/nutrition/retry")

    assert response.status_code == 200
    assert response.json() == {"retried_item_ids": [item_id]}
    assert len(seen) == 1
    assert asyncio.run(stores.warnings.list_open()) == []

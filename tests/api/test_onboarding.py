"""First-run setup, localized starter data, and legacy defaults."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
    return TestClient(create_app(require_token=False, stores=stores))


def setup_payload(**changes: object) -> dict[str, object]:
    return {
        "language": "nl",
        "seed_ingredients": True,
        "seed_meals": True,
        "window_days": 21,
        "household_size": 3,
        "repeat_gap_days": 10,
        "balance_targets": {
            "vegetables": 50,
            "protein": 25,
            "carbs": 25,
            "tolerance": 10,
        },
        "template": {"protein": 1, "vegetable": 1, "carb": 1},
        "fish_min_per_7_days": 1,
        "vegetarian_min_per_7_days": 2,
        **changes,
    }


def test_new_database_requires_setup_and_previews_localized_starters(client: TestClient) -> None:
    response = client.get("/api/onboarding")

    assert response.status_code == 200
    body = response.json()
    assert body["required"] is True
    assert body["packs"]["en"]["language_name"] == "English"
    assert "chicken curry" in body["packs"]["en"]["meals"]
    assert body["packs"]["nl"]["language_name"] == "Nederlands"
    assert "kipfilet" in body["packs"]["nl"]["ingredients"]
    assert "groentecurry" in body["packs"]["nl"]["meals"]
    assert body["packs"]["en"]["ingredient_count"] > 150


def test_setup_can_start_empty_and_preserves_user_created_items(client: TestClient) -> None:
    custom = client.post("/api/items", json={"name": "My own food", "type": "vegetable"})
    assert custom.status_code == 201

    completed = client.post(
        "/api/onboarding",
        json=setup_payload(
            seed_ingredients=False,
            seed_meals=False,
            fish_min_per_7_days=0,
            vegetarian_min_per_7_days=0,
        ),
    )

    assert completed.status_code == 200
    assert completed.json()["seeded"] == {"ingredients": 0, "meals": 0}
    assert [item["name"] for item in client.get("/api/items").json()] == ["My own food"]
    assert client.get("/api/onboarding").json()["required"] is False
    settings = client.get("/api/settings").json()
    assert settings["language"] == "nl"
    assert settings["window_days"] == 21
    assert settings["household_size"] == 3
    assert client.get("/api/template").json() == {"protein": 1, "vegetable": 1, "carb": 1}

    repeated = client.post("/api/onboarding", json=setup_payload())
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "setup_complete"


def test_setup_seeds_only_selected_meal_group_in_english(client: TestClient) -> None:
    completed = client.post(
        "/api/onboarding",
        json=setup_payload(
            language="en",
            seed_ingredients=False,
            seed_meals=True,
            fish_min_per_7_days=0,
            vegetarian_min_per_7_days=0,
        ),
    )

    assert completed.status_code == 200
    assert completed.json()["language"] == "en"
    items = client.get("/api/items").json()
    assert items
    assert all(item["is_complete_meal"] for item in items)
    assert any(item["name"] == "chicken curry" for item in items)
    assert client.get("/api/settings").json()["language"] == "en"


def test_setup_applies_dietary_category_minimums_for_dutch_pack(client: TestClient) -> None:
    completed = client.post("/api/onboarding", json=setup_payload())

    assert completed.status_code == 200
    categories = {category["name"]: category for category in client.get("/api/categories").json()}
    assert categories["vis"]["min_per_7_days"] == 1
    assert categories["vegetarisch"]["min_per_7_days"] == 2
    assert any(item["name"] == "rode linzen" for item in client.get("/api/items").json())

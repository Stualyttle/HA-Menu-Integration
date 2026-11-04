"""HTTP tests for the data endpoints. Every test uses a temporary database."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import TOKEN_HEADER
from app.db import Stores
from app.main import create_app
from app.models import WarningCode, WarningRecord, WarningSubject

TOKEN = "test-token-123"


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


def _first_item_id(client: TestClient) -> int:
    return client.get("/api/items").json()[0]["id"]


def _first_category_id(client: TestClient) -> int:
    return client.get("/api/categories").json()[0]["id"]


def _tracked_item_id(client: TestClient) -> int:
    response = client.post(
        "/api/items", json={"name": "Stock Test Item", "type": "carb", "track_stock": True}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _error_code(response) -> str:
    return response.json()["error"]["code"]


# Items


def test_list_items_returns_starter_content(client: TestClient) -> None:
    response = client.get("/api/items")
    assert response.status_code == 200
    assert len(response.json()) == 16


def test_create_get_update_delete_item(client: TestClient) -> None:
    created = client.post(
        "/api/items",
        json={"name": "  Edamame  ", "type": "protein", "portion_grams": 120},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Edamame"
    assert body["type"] == "protein"
    assert body["portion_grams"] == 120
    assert body["nutrition"] is None
    item_id = body["id"]

    assert client.get(f"/api/items/{item_id}").json()["id"] == item_id

    updated = client.put(
        f"/api/items/{item_id}",
        json={"name": "Edamame", "type": "carb", "track_stock": False},
    )
    assert updated.status_code == 200
    assert updated.json()["type"] == "carb"
    assert updated.json()["track_stock"] is False

    assert client.delete(f"/api/items/{item_id}").status_code == 204
    assert client.get(f"/api/items/{item_id}").status_code == 404


def test_item_name_is_unique_case_insensitively(client: TestClient) -> None:
    response = client.post("/api/items", json={"name": "SALMON", "type": "protein"})
    assert response.status_code == 409
    assert _error_code(response) == "duplicate_name"


def test_item_rejects_blank_name_and_bad_type(client: TestClient) -> None:
    blank = client.post("/api/items", json={"name": "   ", "type": "protein"})
    assert blank.status_code == 400
    assert _error_code(blank) == "validation_error"

    bad_type = client.post("/api/items", json={"name": "Soup", "type": "dessert"})
    assert bad_type.status_code == 400
    assert _error_code(bad_type) == "validation_error"


def test_item_missing_returns_404_envelope(client: TestClient) -> None:
    response = client.get("/api/items/999999")
    assert response.status_code == 404
    assert _error_code(response) == "not_found"
    assert "message" in response.json()["error"]


def test_item_put_and_delete_missing_return_404(client: TestClient) -> None:
    body = {"name": "Ghost", "type": "protein"}
    assert client.put("/api/items/999999", json=body).status_code == 404
    assert client.delete("/api/items/999999").status_code == 404


def test_item_category_ids_must_exist(client: TestClient) -> None:
    response = client.post(
        "/api/items",
        json={"name": "Quinoa", "type": "carb", "category_ids": [999999]},
    )
    assert response.status_code == 400
    assert _error_code(response) == "unknown_reference"


def test_item_category_ids_round_trip(client: TestClient) -> None:
    category_id = _first_category_id(client)
    created = client.post(
        "/api/items",
        json={"name": "Farro", "type": "carb", "category_ids": [category_id]},
    )
    assert created.status_code == 201
    assert created.json()["category_ids"] == [category_id]


# Categories


def test_list_categories_returns_starter_content(client: TestClient) -> None:
    response = client.get("/api/categories")
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert len(names) == 8
    fish = next(c for c in response.json() if c["name"].lower() == "fish")
    assert fish["min_per_7_days"] == 1
    assert fish["is_starter"] is True


def test_create_update_delete_category(client: TestClient) -> None:
    item_id = _first_item_id(client)
    created = client.post(
        "/api/categories",
        json={"name": "Weeknight", "min_per_7_days": 3, "item_ids": [item_id]},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["item_ids"] == [item_id]
    assert body["item_count"] == 1
    assert body["is_starter"] is False
    category_id = body["id"]

    updated = client.put(
        f"/api/categories/{category_id}",
        json={"name": "Weeknight", "min_per_7_days": None, "item_ids": []},
    )
    assert updated.status_code == 200
    assert updated.json()["min_per_7_days"] is None
    assert updated.json()["item_count"] == 0

    assert client.delete(f"/api/categories/{category_id}").status_code == 204
    assert client.get(f"/api/categories/{category_id}").status_code == 404


def test_category_name_is_unique(client: TestClient) -> None:
    response = client.post("/api/categories", json={"name": "fish"})
    assert response.status_code == 409
    assert _error_code(response) == "duplicate_name"


def test_category_min_out_of_range_is_rejected(client: TestClient) -> None:
    response = client.post("/api/categories", json={"name": "Too many", "min_per_7_days": 8})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_category_item_ids_must_exist(client: TestClient) -> None:
    response = client.post("/api/categories", json={"name": "Ghosts", "item_ids": [999999]})
    assert response.status_code == 400
    assert _error_code(response) == "unknown_reference"


def test_category_missing_returns_404(client: TestClient) -> None:
    assert client.get("/api/categories/999999").status_code == 404
    assert client.delete("/api/categories/999999").status_code == 404


# Rules


def test_rule_crud_for_combination_rule(client: TestClient) -> None:
    category_id = _first_category_id(client)
    created = client.post(
        "/api/rules",
        json={
            "kind": "blacklist",
            "scope": "combination",
            "category_ids": [category_id],
        },
    )
    assert created.status_code == 201
    rule = created.json()
    assert rule["category_ids"] == [category_id]
    assert rule["item_id"] is None
    assert rule["enabled"] is True
    rule_id = rule["id"]

    listed = client.get("/api/rules").json()
    assert [r["id"] for r in listed] == [rule_id]

    updated = client.put(
        f"/api/rules/{rule_id}",
        json={
            "kind": "whitelist",
            "scope": "combination",
            "category_ids": [category_id],
            "enabled": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["kind"] == "whitelist"
    assert updated.json()["enabled"] is False

    assert client.delete(f"/api/rules/{rule_id}").status_code == 204
    assert client.get("/api/rules").json() == []


def test_item_rule_requires_item_id(client: TestClient) -> None:
    response = client.post("/api/rules", json={"kind": "blacklist", "scope": "item"})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_item_rule_rejects_category_ids(client: TestClient) -> None:
    response = client.post(
        "/api/rules",
        json={
            "kind": "blacklist",
            "scope": "item",
            "item_id": _first_item_id(client),
            "category_ids": [_first_category_id(client)],
        },
    )
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


def test_combination_rule_requires_categories_and_no_item(client: TestClient) -> None:
    empty = client.post(
        "/api/rules", json={"kind": "blacklist", "scope": "combination", "category_ids": []}
    )
    assert empty.status_code == 400

    with_item = client.post(
        "/api/rules",
        json={
            "kind": "blacklist",
            "scope": "combination",
            "category_ids": [_first_category_id(client)],
            "item_id": _first_item_id(client),
        },
    )
    assert with_item.status_code == 400


def test_item_rule_round_trip(client: TestClient) -> None:
    item_id = _first_item_id(client)
    created = client.post(
        "/api/rules", json={"kind": "whitelist", "scope": "item", "item_id": item_id}
    )
    assert created.status_code == 201
    assert created.json()["item_id"] == item_id


def test_rule_references_must_exist(client: TestClient) -> None:
    bad_category = client.post(
        "/api/rules",
        json={"kind": "blacklist", "scope": "combination", "category_ids": [999999]},
    )
    assert bad_category.status_code == 400
    assert _error_code(bad_category) == "unknown_reference"

    bad_item = client.post(
        "/api/rules", json={"kind": "blacklist", "scope": "item", "item_id": 999999}
    )
    assert bad_item.status_code == 400
    assert _error_code(bad_item) == "unknown_reference"


def test_rule_update_and_delete_missing_return_404(client: TestClient) -> None:
    body = {"kind": "blacklist", "scope": "item", "item_id": _first_item_id(client)}
    assert client.put("/api/rules/999999", json=body).status_code == 404
    assert client.delete("/api/rules/999999").status_code == 404


# Stock


def test_stock_list_covers_only_tracked_items(client: TestClient) -> None:
    tracked_id = _tracked_item_id(client)
    response = client.get("/api/stock")
    assert response.status_code == 200
    rows = response.json()
    assert [row["item_id"] for row in rows] == [tracked_id]
    assert rows[0]["in_stock"] is None
    assert isinstance(rows[0]["replaces_count"], int)


def test_stock_answer_is_stored_and_listed(client: TestClient) -> None:
    item_id = _tracked_item_id(client)
    response = client.put(f"/api/stock/{item_id}", json={"in_stock": False})
    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item_id
    assert body["in_stock"] is False

    rows = {row["item_id"]: row for row in client.get("/api/stock").json()}
    assert rows[item_id]["in_stock"] is False


def test_stock_answer_can_be_cleared(client: TestClient) -> None:
    item_id = _tracked_item_id(client)
    client.put(f"/api/stock/{item_id}", json={"in_stock": True})
    cleared = client.put(f"/api/stock/{item_id}", json={"in_stock": None})
    assert cleared.status_code == 200
    rows = {row["item_id"]: row for row in client.get("/api/stock").json()}
    assert rows[item_id]["in_stock"] is None


def test_stock_unknown_item_returns_404(client: TestClient) -> None:
    assert client.put("/api/stock/999999", json={"in_stock": True}).status_code == 404
    preview = client.post("/api/stock/999999/preview", json={"in_stock": True})
    assert preview.status_code == 404


def test_stock_preview_reports_item_and_count(client: TestClient) -> None:
    item_id = _tracked_item_id(client)
    response = client.post(f"/api/stock/{item_id}/preview", json={"in_stock": False})
    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item_id
    assert body["in_stock"] is False
    assert body["replaces_count"] == 0


def test_stock_preview_requires_boolean(client: TestClient) -> None:
    item_id = _first_item_id(client)
    response = client.post(f"/api/stock/{item_id}/preview", json={"in_stock": None})
    assert response.status_code == 400


# Settings and template


def test_settings_defaults(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["window_days"] == 14
    assert body["household_size"] == 2
    assert body["repeat_gap_days"] == 14
    assert body["language"] == "auto"
    assert body["balance_targets"] == {
        "vegetables": 50,
        "protein": 25,
        "carbs": 25,
        "tolerance": 10,
    }
    assert "usda_api_key" not in body


def test_settings_update_is_partial(client: TestClient) -> None:
    response = client.put("/api/settings", json={"household_size": 4, "language": "nl"})
    assert response.status_code == 200
    body = response.json()
    assert body["household_size"] == 4
    assert body["language"] == "nl"
    assert body["window_days"] == 14


def test_settings_bounds_are_enforced(client: TestClient) -> None:
    assert client.put("/api/settings", json={"window_days": 5}).status_code == 400
    assert client.put("/api/settings", json={"household_size": 0}).status_code == 400
    assert client.put("/api/settings", json={"language": "de"}).status_code == 400


def test_settings_never_return_usda_key(client: TestClient) -> None:
    response = client.put("/api/settings", json={"usda_api_key": "secret-key"})
    assert response.status_code == 200
    assert "usda_api_key" not in response.json()
    assert "secret-key" not in client.get("/api/settings").text


def test_template_defaults_and_update(client: TestClient) -> None:
    initial = client.get("/api/template")
    assert initial.status_code == 200
    assert set(initial.json()) == {"protein", "vegetable", "carb"}

    updated = client.put("/api/template", json={"protein": 2, "vegetable": 1, "carb": 0})
    assert updated.status_code == 200
    assert updated.json() == {"protein": 2, "vegetable": 1, "carb": 0}
    assert client.get("/api/template").json() == {"protein": 2, "vegetable": 1, "carb": 0}


def test_all_zero_template_is_rejected_with_400(client: TestClient) -> None:
    response = client.put("/api/template", json={"protein": 0, "vegetable": 0, "carb": 0})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_template_rejects_out_of_range(client: TestClient) -> None:
    response = client.put("/api/template", json={"protein": 3, "vegetable": 1, "carb": 1})
    assert response.status_code == 400
    assert _error_code(response) == "validation_error"


# Warnings


def _seed_warning(stores: Stores) -> int:
    import asyncio

    record = WarningRecord(
        id=0,
        code=WarningCode.EMPTY_DAY,
        subject_type=WarningSubject.DATE,
        subject="2030-01-01",
        payload={"day": "2030-01-01"},
        created_at=None,
        resolved_at=None,
    )
    saved = asyncio.run(stores.warnings.open_warning(record))
    return saved.id


def test_warnings_list_and_resolve(client: TestClient, stores: Stores) -> None:
    warning_id = _seed_warning(stores)

    listed = client.get("/api/warnings")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["id"] == warning_id
    assert rows[0]["code"] == "empty_day"
    assert rows[0]["subject"] == {"type": "date", "id": "2030-01-01"}
    assert rows[0]["payload"] == {"day": "2030-01-01"}

    assert client.post(f"/api/warnings/{warning_id}/resolve").status_code == 204
    assert client.get("/api/warnings").json() == []


def test_resolving_missing_warning_is_idempotent(client: TestClient) -> None:
    assert client.post("/api/warnings/999999/resolve").status_code in (204, 404)


# Token requirement


def test_data_routes_require_token_on_internal_listener(stores: Stores) -> None:
    client = TestClient(create_app(require_token=True, token=TOKEN, stores=stores))
    assert client.get("/api/items").status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/items", headers={TOKEN_HEADER: "wrong"}).status_code == 401
    assert client.get("/api/items", headers={TOKEN_HEADER: TOKEN}).status_code == 200


def test_data_routes_open_on_ingress_listener(stores: Stores) -> None:
    client = TestClient(create_app(require_token=False, stores=stores))
    assert client.get("/api/categories").status_code == 200


# Lifespan


def test_lifespan_opens_database_under_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / "lifespan.db"
    app = create_app(require_token=False, db_path=db_path)
    with TestClient(app) as client:
        assert len(client.get("/api/items").json()) == 16
    assert db_path.exists()

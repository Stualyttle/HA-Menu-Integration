"""Repository behaviour against a real SQLite file in a temporary directory."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from app.db import DuplicateNameError, NotFoundError, Stores
from app.db.connection import Database
from app.db.migrations import DEFAULT_SETTINGS, DEFAULT_TEMPLATE, _v1
from app.models import (
    Category,
    DayStatus,
    Item,
    ItemType,
    MenuDay,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    Rule,
    RuleKind,
    RuleScope,
    WarningCode,
    WarningRecord,
    WarningSubject,
)


@pytest.fixture
def stores(tmp_path: Path):
    opened = Stores.open(tmp_path / "menu_planner.db")
    yield opened
    opened.close()


async def _find_item(stores: Stores, name: str) -> Item:
    return next(i for i in await stores.items.list_items() if i.name == name)


async def _starter_dinner_parts(stores: Stores) -> tuple[int, int, int]:
    salmon = await _find_item(stores, "salmon")
    broccoli = await _find_item(stores, "broccoli")
    rice = await _find_item(stores, "brown rice")
    return salmon.id, broccoli.id, rice.id


def test_schema_version_is_current(stores: Stores) -> None:
    assert stores.database.schema_version == 2


def test_reopen_does_not_reseed_or_change_version(tmp_path: Path) -> None:
    path = tmp_path / "menu_planner.db"
    first = Stores.open(path)
    first.database.execute("DELETE FROM item_categories")
    first.close()

    second = Stores.open(path)
    try:
        assert second.database.schema_version == 2
        count = second.database.query_one("SELECT COUNT(*) AS n FROM item_categories")
        assert count["n"] == 0
    finally:
        second.close()


async def test_v1_database_upgrades_without_losing_existing_items(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _v1(conn)
    conn.execute(
        "INSERT INTO items (name, type, portion_grams, fat_source, track_stock, created_at,"
        " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Existing family meal", "carb", 450, 0, 1, "2024-01-01", "2024-01-01"),
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    stores = Stores.open(path)
    try:
        assert stores.database.schema_version == 2
        item = await _find_item(stores, "Existing family meal")
        assert item.portion_grams == 450
        assert item.track_stock is True
        assert item.is_complete_meal is False
        assert await _find_item(stores, "pizza")
    finally:
        stores.close()


async def test_starter_content_is_seeded(stores: Stores) -> None:
    items = await stores.items.list_items()
    categories = await stores.categories.list_categories()
    assert len(items) > 150
    assert len(categories) >= 18
    names = {item.name for item in items}
    assert {"spaghetti", "lasagne sheets", "macaroni", "pizza", "whole chicken"} <= names
    fish = next(c for c in categories if c.name == "fish")
    assert fish.is_starter is True
    assert fish.min_per_7_days == 1
    assert stores.template.get() == DEFAULT_TEMPLATE


async def test_starter_catalog_category_references_exist(stores: Stores) -> None:
    from app.db.starter_content import STARTER_CATALOG_V2

    categories = {
        category.name.casefold() for category in await stores.categories.list_categories()
    }
    assert {
        category.casefold()
        for _, _, item_categories, _, _ in STARTER_CATALOG_V2
        for category in item_categories
    } <= categories


async def test_starter_item_links(stores: Stores) -> None:
    categories = {c.name: c for c in await stores.categories.list_categories()}
    salmon = await _find_item(stores, "salmon")
    assert salmon.id in categories["fish"].item_ids
    assert salmon.id in categories["Mediterranean"].item_ids


def test_settings_defaults_and_hidden_api_key(stores: Stores) -> None:
    settings = stores.settings.get_all()
    assert settings["window_days"] == DEFAULT_SETTINGS["window_days"]
    assert settings["household_size"] == DEFAULT_SETTINGS["household_size"]
    assert "usda_api_key" not in settings

    stores.settings.update({"usda_api_key": "secret"})
    assert stores.settings.get_value("usda_api_key") == "secret"
    assert "usda_api_key" not in stores.settings.get_all()


def test_settings_update_merges_values(stores: Stores) -> None:
    stores.settings.update({"household_size": 4})
    settings = stores.settings.get_all()
    assert settings["household_size"] == 4
    assert settings["window_days"] == DEFAULT_SETTINGS["window_days"]


def test_template_round_trip(stores: Stores) -> None:
    stores.template.set({"protein": 2, "vegetable": 0, "carb": 1})
    assert stores.template.get() == {"protein": 2, "vegetable": 0, "carb": 1}


def test_template_all_zero_is_rejected(stores: Stores) -> None:
    stores.template.set({"protein": 1, "vegetable": 1, "carb": 1})
    with pytest.raises(ValueError):
        stores.template.set({"protein": 0, "vegetable": 0, "carb": 0})
    assert stores.template.get() == {"protein": 1, "vegetable": 1, "carb": 1}


async def test_item_insert_update_delete(stores: Stores) -> None:
    saved = await stores.items.save_item(
        Item(id=0, name="Feta", type=ItemType.PROTEIN, portion_grams=150)
    )
    assert saved.id > 0
    assert saved.created_at is not None

    fetched = await stores.items.get_item(saved.id)
    assert fetched is not None
    assert fetched.name == "Feta"
    assert fetched.portion_grams == 150

    updated = await stores.items.save_item(
        Item(
            id=saved.id,
            name="Feta cheese",
            type=ItemType.PROTEIN,
            portion_grams=None,
            fat_source=True,
            track_stock=False,
        )
    )
    assert updated.id == saved.id
    fetched = await stores.items.get_item(saved.id)
    assert fetched is not None
    assert fetched.name == "Feta cheese"
    assert fetched.fat_source is True
    assert fetched.track_stock is False

    await stores.items.delete_item(saved.id)
    assert await stores.items.get_item(saved.id) is None


async def test_item_name_is_unique_case_insensitively(stores: Stores) -> None:
    with pytest.raises(DuplicateNameError):
        await stores.items.save_item(Item(id=0, name="SALMON", type=ItemType.PROTEIN))


async def test_item_update_to_taken_name_is_rejected(stores: Stores) -> None:
    saved = await stores.items.save_item(Item(id=0, name="Feta", type=ItemType.PROTEIN))
    with pytest.raises(DuplicateNameError):
        await stores.items.save_item(Item(id=saved.id, name="salmon", type=ItemType.PROTEIN))


async def test_update_or_delete_missing_item_raises(stores: Stores) -> None:
    with pytest.raises(NotFoundError):
        await stores.items.save_item(Item(id=9999, name="ghost", type=ItemType.PROTEIN))
    with pytest.raises(NotFoundError):
        await stores.items.delete_item(9999)


async def test_category_membership_and_minimum(stores: Stores) -> None:
    fish = next(c for c in await stores.categories.list_categories() if c.name == "fish")
    salmon = await _find_item(stores, "salmon")

    assert salmon.id in fish.item_ids

    saved = await stores.categories.save_category(
        Category(id=fish.id, name="fish", is_starter=True, min_per_7_days=2, item_ids=set())
    )
    assert saved.item_ids == set()
    assert saved.min_per_7_days == 2

    cleared = await stores.categories.save_category(
        Category(
            id=fish.id,
            name="fish",
            is_starter=True,
            min_per_7_days=None,
            item_ids={salmon.id},
        )
    )
    assert cleared.min_per_7_days is None
    assert cleared.item_ids == {salmon.id}


async def test_category_name_is_unique(stores: Stores) -> None:
    with pytest.raises(DuplicateNameError):
        await stores.categories.save_category(Category(id=0, name="FISH"))


async def test_category_delete_keeps_items(stores: Stores) -> None:
    created = await stores.categories.save_category(Category(id=0, name="snacks"))
    await stores.categories.delete_category(created.id)
    categories = await stores.categories.list_categories()
    assert all(c.id != created.id for c in categories)
    assert len(await stores.items.list_items()) > 150


async def test_deleting_item_removes_its_category_links(stores: Stores) -> None:
    salmon = await _find_item(stores, "salmon")
    await stores.items.delete_item(salmon.id)
    for category in await stores.categories.list_categories():
        assert salmon.id not in category.item_ids


async def test_rule_crud_with_combination_categories(stores: Stores) -> None:
    categories = await stores.categories.list_categories()
    fish = next(c for c in categories if c.name == "fish")
    vegetarian = next(c for c in categories if c.name == "vegetarian")

    created = await stores.rules.save_rule(
        Rule(
            id=0,
            kind=RuleKind.BLACKLIST,
            scope=RuleScope.COMBINATION,
            category_ids=frozenset({fish.id, vegetarian.id}),
        )
    )
    assert created.id > 0

    stored = next(r for r in await stores.rules.list_rules() if r.id == created.id)
    assert stored.category_ids == frozenset({fish.id, vegetarian.id})
    assert stored.enabled is True

    salmon = await _find_item(stores, "salmon")
    await stores.rules.save_rule(
        Rule(
            id=created.id,
            kind=RuleKind.BLACKLIST,
            scope=RuleScope.ITEM,
            category_ids=frozenset(),
            item_id=salmon.id,
            enabled=False,
        )
    )
    stored = next(r for r in await stores.rules.list_rules() if r.id == created.id)
    assert stored.scope == RuleScope.ITEM
    assert stored.item_id == salmon.id
    assert stored.category_ids == frozenset()
    assert stored.enabled is False

    await stores.rules.delete_rule(created.id)
    assert all(r.id != created.id for r in await stores.rules.list_rules())


async def test_rule_update_missing_raises(stores: Stores) -> None:
    with pytest.raises(NotFoundError):
        await stores.rules.save_rule(
            Rule(
                id=4242,
                kind=RuleKind.BLACKLIST,
                scope=RuleScope.COMBINATION,
                category_ids=frozenset(),
            )
        )


async def test_nutrition_round_trip(stores: Stores) -> None:
    salmon = await _find_item(stores, "salmon")
    assert await stores.nutrition.get_nutrition(salmon.id) is None

    await stores.nutrition.save_nutrition(
        Nutrition(
            item_id=salmon.id,
            source=NutritionSource.USDA,
            status=NutritionStatus.OK,
            kcal=208.0,
            protein_g=20.0,
            carbs_g=0.0,
            fat_g=13.0,
            fiber_g=0.0,
        )
    )
    stored = await stores.nutrition.get_nutrition(salmon.id)
    assert stored is not None
    assert stored.status == NutritionStatus.OK
    assert stored.kcal == 208.0


def test_nutrition_status_check_constraint(stores: Stores) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        stores.database.execute(
            "INSERT INTO nutrition (item_id, source, status) VALUES (1, 'usda', 'bogus')"
        )


async def test_menu_days_range_and_upsert(stores: Stores) -> None:
    salmon_id, broccoli_id, rice_id = await _starter_dinner_parts(stores)
    dinner = await stores.menu.create_dinner([salmon_id, broccoli_id, rice_id])
    assert dinner.id > 0

    await stores.menu.save_days(
        [
            MenuDay(day=date(2026, 3, 1), dinner_id=dinner.id, status=DayStatus.PLANNED),
            MenuDay(day=date(2026, 3, 2), dinner_id=None, status=DayStatus.EMPTY),
            MenuDay(day=date(2026, 3, 9), dinner_id=dinner.id, status=DayStatus.PINNED),
        ]
    )
    days = await stores.menu.get_days(date(2026, 3, 1), date(2026, 3, 2))
    assert [d.day for d in days] == [date(2026, 3, 1), date(2026, 3, 2)]
    assert days[0].dinner_id == dinner.id

    await stores.menu.save_days(
        [MenuDay(day=date(2026, 3, 1), dinner_id=dinner.id, status=DayStatus.EATEN)]
    )
    days = await stores.menu.get_days(date(2026, 3, 1), date(2026, 3, 1))
    assert days[0].status == DayStatus.EATEN

    assert any(d.id == dinner.id for d in await stores.menu.list_dinners())


async def test_create_dinner_is_idempotent(stores: Stores) -> None:
    salmon_id, broccoli_id, rice_id = await _starter_dinner_parts(stores)
    first = await stores.menu.create_dinner([salmon_id, broccoli_id, rice_id])
    second = await stores.menu.create_dinner([rice_id, salmon_id, broccoli_id, rice_id])
    assert first.id == second.id
    assert second.item_ids == tuple(sorted({salmon_id, broccoli_id, rice_id}))
    assert len(await stores.menu.list_dinners()) == 1


async def test_dinner_items_key_is_unique_at_database_level(stores: Stores) -> None:
    salmon_id, broccoli_id, rice_id = await _starter_dinner_parts(stores)
    await stores.menu.create_dinner([salmon_id, broccoli_id, rice_id])
    items_key = ",".join(str(i) for i in sorted((salmon_id, broccoli_id, rice_id)))
    with pytest.raises(sqlite3.IntegrityError):
        stores.database.execute(
            "INSERT INTO dinners (items_key) VALUES (?)",
            (items_key,),
        )


async def test_dinner_with_two_proteins_and_one_vegetable_round_trips(stores: Stores) -> None:
    salmon_id, broccoli_id, rice_id = await _starter_dinner_parts(stores)
    chicken = await _find_item(stores, "chicken breast")
    dinner = await stores.menu.create_dinner([salmon_id, chicken.id, broccoli_id])
    loaded = next(d for d in await stores.menu.list_dinners() if d.id == dinner.id)
    assert loaded.item_ids == tuple(sorted((salmon_id, chicken.id, broccoli_id)))
    assert rice_id not in loaded.item_ids


async def test_deleting_dinner_item_cascades_to_dinner(stores: Stores) -> None:
    salmon_id, broccoli_id, rice_id = await _starter_dinner_parts(stores)
    await stores.menu.create_dinner([salmon_id, broccoli_id, rice_id])
    await stores.items.delete_item(salmon_id)
    assert all(salmon_id not in d.item_ids for d in await stores.menu.list_dinners())


async def test_warnings_open_and_resolve(stores: Stores) -> None:
    opened = await stores.warnings.open_warning(
        WarningRecord(
            id=0,
            code=WarningCode.EMPTY_DAY,
            subject_type=WarningSubject.DATE,
            subject="2026-03-01",
            payload={"reason": "no candidates"},
        )
    )
    assert opened.id > 0
    assert opened.payload == {"reason": "no candidates"}

    assert [w.id for w in await stores.warnings.list_open()] == [opened.id]

    await stores.warnings.resolve_warning(opened.id)
    await stores.warnings.resolve_warning(opened.id)  # idempotent
    assert await stores.warnings.list_open() == []
    stored = await stores.warnings.get_warning(opened.id)
    assert stored is not None
    assert stored.resolved_at is not None


async def test_resolve_missing_warning_raises(stores: Stores) -> None:
    with pytest.raises(NotFoundError):
        await stores.warnings.resolve_warning(777)


async def test_stock_answers(stores: Stores) -> None:
    salmon = await _find_item(stores, "salmon")
    assert stores.stock.get_answer(salmon.id) is None

    stores.stock.set_answer(salmon.id, True)
    assert stores.stock.get_answer(salmon.id) is True
    assert stores.stock.answers()[salmon.id] is True

    stores.stock.set_answer(salmon.id, None)
    assert stores.stock.get_answer(salmon.id) is None


def test_foreign_keys_are_enforced(stores: Stores) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        stores.database.execute(
            "INSERT INTO item_categories (item_id, category_id) VALUES (999999, 999999)"
        )


def test_transaction_rolls_back(tmp_path: Path) -> None:
    db = Database(tmp_path / "tx.db")
    try:
        with pytest.raises(RuntimeError), db.transaction() as conn:
            conn.execute("INSERT INTO settings (key, value_json) VALUES ('tmp', '1')")
            raise RuntimeError("boom")
        assert db.query_one("SELECT 1 FROM settings WHERE key = 'tmp'") is None
    finally:
        db.close()

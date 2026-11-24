"""First-run setup and locale-aware starter content."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import StoresDep
from app.api.errors import ApiError
from app.api.schemas import OnboardingIn
from app.db.starter_content import starter_catalog
from app.domain.config import Template
from app.models import ItemType

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

LANGUAGE_NAMES = {"en": "English", "nl": "Nederlands"}
DIET_CATEGORIES = {
    "en": {"fish": "fish", "vegetarian": "vegetarian"},
    "nl": {"fish": "vis", "vegetarian": "vegetarisch"},
}


def _pack(language: str) -> dict[str, object]:
    catalog = starter_catalog(language)
    ingredient_rows = [row for row in catalog if not row[3]]
    meal_rows = [row for row in catalog if row[3]]
    ingredients = [row[0] for row in ingredient_rows]
    meals = [row[0] for row in meal_rows]
    return {
        "language": language,
        "language_name": LANGUAGE_NAMES[language],
        "ingredient_count": len(ingredients),
        "meal_count": len(meals),
        "ingredients": ingredients,
        "meals": meals,
        "ingredient_categories": sorted(
            {category for row in ingredient_rows for category in row[2]}, key=str.casefold
        ),
        "meal_categories": sorted(
            {category for row in meal_rows for category in row[2]}, key=str.casefold
        ),
    }


@router.get("")
async def get_onboarding(stores: StoresDep) -> dict[str, object]:
    return {
        "required": not bool(stores.settings.get_all()["setup_complete"]),
        "packs": {language: _pack(language) for language in LANGUAGE_NAMES},
    }


def _insert_starter_catalog(conn: sqlite3.Connection, body: OnboardingIn) -> tuple[int, int]:
    catalog = starter_catalog(body.language)
    selected = [
        row
        for row in catalog
        if (row[3] and body.seed_meals) or (not row[3] and body.seed_ingredients)
    ]
    categories = sorted({category for row in selected for category in row[2]}, key=str.casefold)
    category_ids: dict[str, int] = {}
    for name in categories:
        existing = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                "INSERT INTO categories (name, is_starter) VALUES (?, 1)", (name,)
            )
            category_ids[name] = int(cursor.lastrowid or 0)
        else:
            category_ids[name] = int(existing["id"])

    now = datetime.now(UTC).isoformat()
    ingredient_count = 0
    meal_count = 0
    for name, item_type, item_categories, complete_meal, fat_source in selected:
        existing = conn.execute(
            "SELECT id FROM items WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing is not None:
            continue
        cursor = conn.execute(
            "INSERT INTO items (name, type, fat_source, track_stock, created_at, updated_at,"
            " is_complete_meal) VALUES (?, ?, ?, 0, ?, ?, ?)",
            (name, item_type.value, int(fat_source), now, now, int(complete_meal)),
        )
        item_id = int(cursor.lastrowid or 0)
        conn.execute("INSERT INTO starter_items (item_id) VALUES (?)", (item_id,))
        conn.executemany(
            "INSERT INTO item_categories (item_id, category_id) VALUES (?, ?)",
            [(item_id, category_ids[category]) for category in item_categories],
        )
        if complete_meal:
            meal_count += 1
        else:
            ingredient_count += 1

    for preference, minimum in (
        ("fish", body.fish_min_per_7_days),
        ("vegetarian", body.vegetarian_min_per_7_days),
    ):
        category_name = DIET_CATEGORIES[body.language][preference]
        category_id = category_ids.get(category_name)
        if category_id is not None:
            conn.execute(
                "INSERT INTO category_minimums (category_id, min_per_7_days) VALUES (?, ?)"
                " ON CONFLICT(category_id) DO UPDATE SET min_per_7_days = excluded.min_per_7_days",
                (category_id, minimum),
            )

    return ingredient_count, meal_count


@router.post("")
async def complete_onboarding(body: OnboardingIn, stores: StoresDep) -> dict[str, object]:
    if not any((body.seed_ingredients, body.seed_meals)) and (
        body.fish_min_per_7_days or body.vegetarian_min_per_7_days
    ):
        raise ApiError(
            400,
            "validation_error",
            "dietary category minimums require starter items",
        )
    Template({ItemType(slot): count for slot, count in body.template.model_dump().items()})

    with stores.database.transaction() as conn:
        row = conn.execute(
            "SELECT value_json FROM settings WHERE key = 'setup_complete'"
        ).fetchone()
        if row is None or json.loads(row["value_json"]):
            raise ApiError(409, "setup_complete", "first-run setup has already been completed")

        conn.execute("DELETE FROM items WHERE id IN (SELECT item_id FROM starter_items)")
        conn.execute("DELETE FROM categories WHERE is_starter = 1")
        ingredients, meals = _insert_starter_catalog(conn, body)

        values = {
            "window_days": body.window_days,
            "household_size": body.household_size,
            "repeat_gap_days": body.repeat_gap_days,
            "balance_targets": body.balance_targets.model_dump(),
            "language": body.language,
            "setup_complete": True,
        }
        for key, value in values.items():
            conn.execute(
                "INSERT INTO settings (key, value_json) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                (key, json.dumps(value)),
            )
        for slot, count in body.template.model_dump().items():
            conn.execute(
                "INSERT INTO template_slots (slot_type, count) VALUES (?, ?)"
                " ON CONFLICT(slot_type) DO UPDATE SET count = excluded.count",
                (slot, count),
            )

    return {
        "required": False,
        "language": body.language,
        "seeded": {"ingredients": ingredients, "meals": meals},
    }

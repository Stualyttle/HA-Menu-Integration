"""Ordered schema migrations. Index N in MIGRATIONS brings the database to user_version N+1.

Migrations are append-only: never edit a released entry, add a new one instead.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from app.db.starter_content import STARTER_CATALOG_V2, STARTER_CATEGORIES_V2

Migration = Callable[[sqlite3.Connection], None]

SCHEMA_V1 = """
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('protein', 'vegetable', 'carb')),
    portion_grams REAL CHECK (portion_grams IS NULL OR portion_grams > 0),
    fat_source INTEGER NOT NULL DEFAULT 0 CHECK (fat_source IN (0, 1)),
    track_stock INTEGER NOT NULL DEFAULT 0 CHECK (track_stock IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX items_name_nocase ON items (name COLLATE NOCASE);

CREATE TABLE nutrition (
    item_id INTEGER PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('open_food_facts', 'usda', 'manual')),
    external_id TEXT,
    matched_name TEXT,
    kcal REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    user_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (user_confirmed IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('ok', 'not_found', 'error')),
    fetched_at TEXT NOT NULL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_starter INTEGER NOT NULL DEFAULT 0 CHECK (is_starter IN (0, 1))
);
CREATE UNIQUE INDEX categories_name_nocase ON categories (name COLLATE NOCASE);

CREATE TABLE item_categories (
    item_id INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, category_id)
);

CREATE TABLE category_minimums (
    category_id INTEGER PRIMARY KEY REFERENCES categories (id) ON DELETE CASCADE,
    min_per_7_days INTEGER NOT NULL CHECK (min_per_7_days >= 0)
);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('blacklist', 'whitelist')),
    scope TEXT NOT NULL CHECK (scope IN ('combination', 'item')),
    item_id INTEGER REFERENCES items (id) ON DELETE CASCADE,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);

CREATE TABLE rule_categories (
    rule_id INTEGER NOT NULL REFERENCES rules (id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    PRIMARY KEY (rule_id, category_id)
);

CREATE TABLE template_slots (
    slot_type TEXT PRIMARY KEY CHECK (slot_type IN ('protein', 'vegetable', 'carb')),
    count INTEGER NOT NULL CHECK (count BETWEEN 0 AND 2)
);

CREATE TABLE dinners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    items_key TEXT NOT NULL UNIQUE
);

CREATE TABLE dinner_items (
    dinner_id INTEGER NOT NULL REFERENCES dinners (id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    PRIMARY KEY (dinner_id, item_id)
);

CREATE TABLE menu_days (
    day TEXT PRIMARY KEY CHECK (day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    dinner_id INTEGER REFERENCES dinners (id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'pinned', 'eaten', 'empty')),
    replaced_reason TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE stock (
    item_id INTEGER PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
    in_stock INTEGER CHECK (in_stock IS NULL OR in_stock IN (0, 1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    removed_at TEXT
);
CREATE INDEX shopping_items_open ON shopping_items (item_id) WHERE removed_at IS NULL;

CREATE TABLE warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL CHECK (code IN (
        'replaced_dinner', 'missed_minimum', 'repeat_gap_unavoidable', 'empty_day',
        'minimum_infeasible', 'nutrition_failed', 'timezone_mismatch'
    )),
    subject_type TEXT NOT NULL CHECK (subject_type IN ('date', 'item', 'category')),
    subject TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
"""

DEFAULT_SETTINGS: dict[str, object] = {
    "window_days": 14,
    "household_size": 2,
    "repeat_gap_days": 14,
    "balance_targets": {"vegetables": 50, "protein": 25, "carbs": 25, "tolerance": 10},
    "language": "auto",
}

DEFAULT_TEMPLATE: dict[str, int] = {"protein": 1, "vegetable": 1, "carb": 1}

STARTER_CATEGORIES: tuple[str, ...] = (
    "fish",
    "poultry",
    "red meat",
    "vegetarian",
    "legumes",
    "Asian",
    "Mediterranean",
    "Mexican",
)

STARTER_MINIMUMS: dict[str, int] = {"fish": 1, "vegetarian": 2}

STARTER_ITEMS: tuple[tuple[str, str], ...] = (
    ("salmon", "protein"),
    ("chicken breast", "protein"),
    ("lean beef mince", "protein"),
    ("tofu", "protein"),
    ("lentils", "protein"),
    ("chickpeas", "protein"),
    ("broccoli", "vegetable"),
    ("spinach", "vegetable"),
    ("carrot", "vegetable"),
    ("bell pepper", "vegetable"),
    ("zucchini", "vegetable"),
    ("brown rice", "carb"),
    ("potatoes", "carb"),
    ("whole-wheat pasta", "carb"),
    ("quinoa", "carb"),
    ("bulgur", "carb"),
)

STARTER_LINKS: dict[str, tuple[str, ...]] = {
    "salmon": ("fish", "Mediterranean"),
    "tofu": ("vegetarian", "Asian"),
    "lentils": ("legumes", "vegetarian"),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _seed_starter_content(conn: sqlite3.Connection) -> None:
    now = _now()
    category_ids: dict[str, int] = {}
    for name in STARTER_CATEGORIES:
        cur = conn.execute("INSERT INTO categories (name, is_starter) VALUES (?, 1)", (name,))
        category_ids[name] = int(cur.lastrowid or 0)
    for name, minimum in STARTER_MINIMUMS.items():
        conn.execute(
            "INSERT INTO category_minimums (category_id, min_per_7_days) VALUES (?, ?)",
            (category_ids[name], minimum),
        )
    item_ids: dict[str, int] = {}
    for name, item_type in STARTER_ITEMS:
        cur = conn.execute(
            "INSERT INTO items (name, type, fat_source, track_stock, created_at, updated_at)"
            " VALUES (?, ?, 0, 0, ?, ?)",
            (name, item_type, now, now),
        )
        item_ids[name] = int(cur.lastrowid or 0)
    for item_name, categories in STARTER_LINKS.items():
        for category in categories:
            conn.execute(
                "INSERT INTO item_categories (item_id, category_id) VALUES (?, ?)",
                (item_ids[item_name], category_ids[category]),
            )


def _seed_settings(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT INTO settings (key, value_json) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
    for slot_type, count in DEFAULT_TEMPLATE.items():
        conn.execute(
            "INSERT INTO template_slots (slot_type, count) VALUES (?, ?)",
            (slot_type, count),
        )


def _v1(conn: sqlite3.Connection) -> None:
    # executescript() would COMMIT the open transaction, so statements run one by one.
    for statement in SCHEMA_V1.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    _seed_settings(conn)
    _seed_starter_content(conn)


def _v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        "ALTER TABLE items ADD COLUMN is_complete_meal INTEGER NOT NULL DEFAULT 0"
        " CHECK (is_complete_meal IN (0, 1))"
    )

    category_ids: dict[str, int] = {}
    for name in (*STARTER_CATEGORIES, *STARTER_CATEGORIES_V2):
        row = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row is None:
            cur = conn.execute("INSERT INTO categories (name, is_starter) VALUES (?, 1)", (name,))
            category_ids[name] = int(cur.lastrowid or 0)
        else:
            category_ids[name] = int(row["id"])

    for name, item_type, category_names, complete_meal, fat_source in STARTER_CATALOG_V2:
        row = conn.execute("SELECT id FROM items WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if row is None:
            now = _now()
            cur = conn.execute(
                "INSERT INTO items (name, type, fat_source, track_stock, created_at, updated_at,"
                " is_complete_meal) VALUES (?, ?, ?, 0, ?, ?, ?)",
                (name, item_type.value, int(fat_source), now, now, int(complete_meal)),
            )
            item_id = int(cur.lastrowid or 0)
        else:
            item_id = int(row["id"])

        conn.executemany(
            "INSERT OR IGNORE INTO item_categories (item_id, category_id) VALUES (?, ?)",
            [(item_id, category_ids[category]) for category in category_names],
        )


MIGRATIONS: tuple[Migration, ...] = (_v1, _v2)

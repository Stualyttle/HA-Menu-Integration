"""SQLite implementations of the repository Protocols in app/ports.py, plus extra stores.

Save convention: an entity with ``id <= 0`` is inserted, otherwise it is updated. Updating a
missing row raises ``NotFoundError``. Timestamps are stored as UTC ISO-8601 strings.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from app.models import (
    Category,
    DayStatus,
    Dinner,
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

from .connection import Database
from .errors import DuplicateNameError, NotFoundError
from .migrations import DEFAULT_SETTINGS, DEFAULT_TEMPLATE


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str:
    return (value or datetime.now(UTC)).isoformat()


def _check_name_free(conn: sqlite3.Connection, table: str, name: str, own_id: int) -> None:
    row = conn.execute(
        f"SELECT id FROM {table} WHERE name = ? COLLATE NOCASE AND id != ?",
        (name, own_id),
    ).fetchone()
    if row is not None:
        raise DuplicateNameError(f"name already exists: {name}")


class SqliteItemRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_items(self) -> list[Item]:
        rows = self._db.query_all("SELECT * FROM items ORDER BY name COLLATE NOCASE")
        return [_item_from_row(r) for r in rows]

    async def get_item(self, item_id: int) -> Item | None:
        row = self._db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
        return _item_from_row(row) if row else None

    async def save_item(self, item: Item) -> Item:
        with self._db.transaction() as conn:
            if item.id > 0:
                existing = conn.execute(
                    "SELECT created_at FROM items WHERE id = ?", (item.id,)
                ).fetchone()
                if existing is None:
                    raise NotFoundError(f"item {item.id} not found")
                _check_name_free(conn, "items", item.name, item.id)
                now = _now()
                conn.execute(
                    "UPDATE items SET name = ?, type = ?, portion_grams = ?, fat_source = ?,"
                    " track_stock = ?, updated_at = ? WHERE id = ?",
                    (
                        item.name,
                        str(item.type),
                        item.portion_grams,
                        int(item.fat_source),
                        int(item.track_stock),
                        now,
                        item.id,
                    ),
                )
                created_at = existing["created_at"]
                item_id = item.id
            else:
                _check_name_free(conn, "items", item.name, 0)
                now = _now()
                cur = conn.execute(
                    "INSERT INTO items (name, type, portion_grams, fat_source, track_stock,"
                    " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.name,
                        str(item.type),
                        item.portion_grams,
                        int(item.fat_source),
                        int(item.track_stock),
                        now,
                        now,
                    ),
                )
                item_id = int(cur.lastrowid or 0)
                created_at = now
        return Item(
            id=item_id,
            name=item.name,
            type=item.type,
            portion_grams=item.portion_grams,
            fat_source=item.fat_source,
            track_stock=item.track_stock,
            created_at=_ts(created_at),
            updated_at=_ts(now),
        )

    async def delete_item(self, item_id: int) -> None:
        with self._db.transaction() as conn:
            cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"item {item_id} not found")


class SqliteCategoryRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_categories(self) -> list[Category]:
        rows = self._db.query_all(
            "SELECT c.id, c.name, c.is_starter, m.min_per_7_days"
            " FROM categories c LEFT JOIN category_minimums m ON m.category_id = c.id"
            " ORDER BY c.name COLLATE NOCASE"
        )
        links = self._db.query_all("SELECT item_id, category_id FROM item_categories")
        members: dict[int, set[int]] = {}
        for link in links:
            members.setdefault(link["category_id"], set()).add(link["item_id"])
        return [
            Category(
                id=r["id"],
                name=r["name"],
                is_starter=bool(r["is_starter"]),
                min_per_7_days=r["min_per_7_days"],
                item_ids=members.get(r["id"], set()),
            )
            for r in rows
        ]

    async def save_category(self, category: Category) -> Category:
        with self._db.transaction() as conn:
            if category.id > 0:
                exists = conn.execute(
                    "SELECT 1 FROM categories WHERE id = ?", (category.id,)
                ).fetchone()
                if exists is None:
                    raise NotFoundError(f"category {category.id} not found")
                _check_name_free(conn, "categories", category.name, category.id)
                conn.execute(
                    "UPDATE categories SET name = ?, is_starter = ? WHERE id = ?",
                    (category.name, int(category.is_starter), category.id),
                )
                category_id = category.id
            else:
                _check_name_free(conn, "categories", category.name, 0)
                cur = conn.execute(
                    "INSERT INTO categories (name, is_starter) VALUES (?, ?)",
                    (category.name, int(category.is_starter)),
                )
                category_id = int(cur.lastrowid or 0)

            if category.min_per_7_days is None:
                conn.execute("DELETE FROM category_minimums WHERE category_id = ?", (category_id,))
            else:
                conn.execute(
                    "INSERT INTO category_minimums (category_id, min_per_7_days)"
                    " VALUES (?, ?)"
                    " ON CONFLICT(category_id) DO UPDATE"
                    " SET min_per_7_days = excluded.min_per_7_days",
                    (category_id, category.min_per_7_days),
                )
            conn.execute("DELETE FROM item_categories WHERE category_id = ?", (category_id,))
            conn.executemany(
                "INSERT INTO item_categories (item_id, category_id) VALUES (?, ?)",
                [(item_id, category_id) for item_id in sorted(category.item_ids)],
            )
        return Category(
            id=category_id,
            name=category.name,
            is_starter=category.is_starter,
            min_per_7_days=category.min_per_7_days,
            item_ids=set(category.item_ids),
        )

    async def delete_category(self, category_id: int) -> None:
        with self._db.transaction() as conn:
            cur = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"category {category_id} not found")


class SqliteRuleRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_rules(self) -> list[Rule]:
        rows = self._db.query_all("SELECT * FROM rules ORDER BY id")
        links = self._db.query_all("SELECT rule_id, category_id FROM rule_categories")
        members: dict[int, set[int]] = {}
        for link in links:
            members.setdefault(link["rule_id"], set()).add(link["category_id"])
        return [
            Rule(
                id=r["id"],
                kind=RuleKind(r["kind"]),
                scope=RuleScope(r["scope"]),
                category_ids=frozenset(members.get(r["id"], set())),
                item_id=r["item_id"],
                enabled=bool(r["enabled"]),
            )
            for r in rows
        ]

    async def save_rule(self, rule: Rule) -> Rule:
        with self._db.transaction() as conn:
            if rule.id > 0:
                exists = conn.execute("SELECT 1 FROM rules WHERE id = ?", (rule.id,)).fetchone()
                if exists is None:
                    raise NotFoundError(f"rule {rule.id} not found")
                conn.execute(
                    "UPDATE rules SET kind = ?, scope = ?, item_id = ?, enabled = ? WHERE id = ?",
                    (
                        str(rule.kind),
                        str(rule.scope),
                        rule.item_id,
                        int(rule.enabled),
                        rule.id,
                    ),
                )
                rule_id = rule.id
            else:
                cur = conn.execute(
                    "INSERT INTO rules (kind, scope, item_id, enabled) VALUES (?, ?, ?, ?)",
                    (str(rule.kind), str(rule.scope), rule.item_id, int(rule.enabled)),
                )
                rule_id = int(cur.lastrowid or 0)
            conn.execute("DELETE FROM rule_categories WHERE rule_id = ?", (rule_id,))
            conn.executemany(
                "INSERT INTO rule_categories (rule_id, category_id) VALUES (?, ?)",
                [(rule_id, category_id) for category_id in sorted(rule.category_ids)],
            )
        return Rule(
            id=rule_id,
            kind=rule.kind,
            scope=rule.scope,
            category_ids=frozenset(rule.category_ids),
            item_id=rule.item_id,
            enabled=rule.enabled,
        )

    async def delete_rule(self, rule_id: int) -> None:
        with self._db.transaction() as conn:
            cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"rule {rule_id} not found")


class SqliteMenuRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_days(self, start: date, end: date) -> list[MenuDay]:
        rows = self._db.query_all(
            "SELECT * FROM menu_days WHERE day BETWEEN ? AND ? ORDER BY day",
            (start.isoformat(), end.isoformat()),
        )
        return [
            MenuDay(
                day=date.fromisoformat(r["day"]),
                dinner_id=r["dinner_id"],
                status=DayStatus(r["status"]),
                replaced_reason=r["replaced_reason"],
                updated_at=_ts(r["updated_at"]),
            )
            for r in rows
        ]

    async def save_days(self, days: Iterable[MenuDay]) -> None:
        with self._db.transaction() as conn:
            for day in days:
                conn.execute(
                    "INSERT INTO menu_days (day, dinner_id, status, replaced_reason, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(day) DO UPDATE SET dinner_id = excluded.dinner_id,"
                    " status = excluded.status, replaced_reason = excluded.replaced_reason,"
                    " updated_at = excluded.updated_at",
                    (
                        day.day.isoformat(),
                        day.dinner_id,
                        str(day.status),
                        day.replaced_reason,
                        _iso(day.updated_at),
                    ),
                )

    async def list_dinners(self) -> list[Dinner]:
        rows = self._db.query_all("SELECT id FROM dinners ORDER BY id")
        return [self._load_dinner(r["id"]) for r in rows]

    async def create_dinner(self, item_ids: Iterable[int]) -> Dinner:
        """Return the dinner for this item set, inserting it if it does not exist yet."""
        ids = tuple(sorted(set(item_ids)))
        items_key = ",".join(str(i) for i in ids)
        with self._db.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO dinners (items_key) VALUES (?)", (items_key,))
            row = conn.execute(
                "SELECT id FROM dinners WHERE items_key = ?", (items_key,)
            ).fetchone()
            dinner_id = int(row["id"])
            conn.executemany(
                "INSERT OR IGNORE INTO dinner_items (dinner_id, item_id) VALUES (?, ?)",
                [(dinner_id, item_id) for item_id in ids],
            )
        return Dinner(id=dinner_id, item_ids=ids)

    def _load_dinner(self, dinner_id: int) -> Dinner:
        rows = self._db.query_all(
            "SELECT item_id FROM dinner_items WHERE dinner_id = ? ORDER BY item_id",
            (dinner_id,),
        )
        return Dinner(id=dinner_id, item_ids=tuple(int(r["item_id"]) for r in rows))


class SqliteNutritionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_nutrition(self, item_id: int) -> Nutrition | None:
        row = self._db.query_one("SELECT * FROM nutrition WHERE item_id = ?", (item_id,))
        if row is None:
            return None
        return Nutrition(
            item_id=row["item_id"],
            source=NutritionSource(row["source"]),
            status=NutritionStatus(row["status"]),
            external_id=row["external_id"],
            matched_name=row["matched_name"],
            kcal=row["kcal"],
            protein_g=row["protein_g"],
            carbs_g=row["carbs_g"],
            fat_g=row["fat_g"],
            fiber_g=row["fiber_g"],
            user_confirmed=bool(row["user_confirmed"]),
            fetched_at=_ts(row["fetched_at"]),
        )

    async def save_nutrition(self, nutrition: Nutrition) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO nutrition (item_id, source, external_id, matched_name, kcal,"
                " protein_g, carbs_g, fat_g, fiber_g, user_confirmed, status, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(item_id) DO UPDATE SET source = excluded.source,"
                " external_id = excluded.external_id, matched_name = excluded.matched_name,"
                " kcal = excluded.kcal, protein_g = excluded.protein_g,"
                " carbs_g = excluded.carbs_g, fat_g = excluded.fat_g,"
                " fiber_g = excluded.fiber_g, user_confirmed = excluded.user_confirmed,"
                " status = excluded.status, fetched_at = excluded.fetched_at",
                (
                    nutrition.item_id,
                    str(nutrition.source),
                    nutrition.external_id,
                    nutrition.matched_name,
                    nutrition.kcal,
                    nutrition.protein_g,
                    nutrition.carbs_g,
                    nutrition.fat_g,
                    nutrition.fiber_g,
                    int(nutrition.user_confirmed),
                    str(nutrition.status),
                    _iso(nutrition.fetched_at),
                ),
            )


class SqliteWarningRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_open(self) -> list[WarningRecord]:
        rows = self._db.query_all("SELECT * FROM warnings WHERE resolved_at IS NULL ORDER BY id")
        return [_warning_from_row(r) for r in rows]

    async def get_warning(self, warning_id: int) -> WarningRecord | None:
        row = self._db.query_one("SELECT * FROM warnings WHERE id = ?", (warning_id,))
        return _warning_from_row(row) if row else None

    async def open_warning(self, warning: WarningRecord) -> WarningRecord:
        now = _now()
        with self._db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO warnings (code, subject_type, subject, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    str(warning.code),
                    str(warning.subject_type),
                    warning.subject,
                    json.dumps(warning.payload, sort_keys=True),
                    _iso(warning.created_at) if warning.created_at else now,
                ),
            )
            warning_id = int(cur.lastrowid or 0)
        stored = self._db.query_one("SELECT * FROM warnings WHERE id = ?", (warning_id,))
        assert stored is not None
        return _warning_from_row(stored)

    async def resolve_warning(self, warning_id: int) -> None:
        with self._db.transaction() as conn:
            exists = conn.execute(
                "SELECT resolved_at FROM warnings WHERE id = ?", (warning_id,)
            ).fetchone()
            if exists is None:
                raise NotFoundError(f"warning {warning_id} not found")
            if exists["resolved_at"] is None:
                conn.execute(
                    "UPDATE warnings SET resolved_at = ? WHERE id = ?", (_now(), warning_id)
                )


class StockStore:
    """Stock answers per item. ``in_stock`` is None until the user answers."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_answer(self, item_id: int) -> bool | None:
        row = self._db.query_one("SELECT in_stock FROM stock WHERE item_id = ?", (item_id,))
        if row is None or row["in_stock"] is None:
            return None
        return bool(row["in_stock"])

    def answers(self) -> dict[int, bool | None]:
        rows = self._db.query_all("SELECT item_id, in_stock FROM stock")
        return {r["item_id"]: None if r["in_stock"] is None else bool(r["in_stock"]) for r in rows}

    def set_answer(self, item_id: int, in_stock: bool | None) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO stock (item_id, in_stock, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(item_id) DO UPDATE SET in_stock = excluded.in_stock,"
                " updated_at = excluded.updated_at",
                (item_id, None if in_stock is None else int(in_stock), _now()),
            )

    def replaces_count(self, item_id: int, start: date, end: date) -> int:
        """Number of planned days in [start, end] whose dinner uses the item."""
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM menu_days m"
            " WHERE m.status = 'planned' AND m.day BETWEEN ? AND ?"
            " AND EXISTS (SELECT 1 FROM dinner_items di"
            " WHERE di.dinner_id = m.dinner_id AND di.item_id = ?)",
            (start.isoformat(), end.isoformat(), item_id),
        )
        assert row is not None
        return int(row["n"])


class SettingsStore:
    """Key/value settings. Secrets (``usda_api_key``) are stored here but never listed."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self) -> dict[str, Any]:
        """Stored values merged over the defaults. Excludes secrets."""
        values: dict[str, Any] = dict(DEFAULT_SETTINGS)
        for row in self._db.query_all("SELECT key, value_json FROM settings"):
            if row["key"] in DEFAULT_SETTINGS:
                values[row["key"]] = json.loads(row["value_json"])
        return values

    def get_value(self, key: str) -> Any | None:
        row = self._db.query_one("SELECT value_json FROM settings WHERE key = ?", (key,))
        return None if row is None else json.loads(row["value_json"])

    def update(self, values: dict[str, Any]) -> None:
        with self._db.transaction() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO settings (key, value_json) VALUES (?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                    (key, json.dumps(value)),
                )


class TemplateStore:
    """Dinner template: how many protein, vegetable and carb items each dinner has."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self) -> dict[str, int]:
        counts = dict(DEFAULT_TEMPLATE)
        for row in self._db.query_all("SELECT slot_type, count FROM template_slots"):
            counts[row["slot_type"]] = int(row["count"])
        return counts

    def set(self, counts: dict[str, int]) -> None:
        if not any(count > 0 for count in counts.values()):
            raise ValueError("template must have at least one item per dinner")
        with self._db.transaction() as conn:
            for slot_type, count in counts.items():
                conn.execute(
                    "INSERT INTO template_slots (slot_type, count) VALUES (?, ?)"
                    " ON CONFLICT(slot_type) DO UPDATE SET count = excluded.count",
                    (slot_type, count),
                )


def _item_from_row(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        type=ItemType(row["type"]),
        portion_grams=row["portion_grams"],
        fat_source=bool(row["fat_source"]),
        track_stock=bool(row["track_stock"]),
        created_at=_ts(row["created_at"]),
        updated_at=_ts(row["updated_at"]),
    )


def _warning_from_row(row: sqlite3.Row) -> WarningRecord:
    return WarningRecord(
        id=row["id"],
        code=WarningCode(row["code"]),
        subject_type=WarningSubject(row["subject_type"]),
        subject=row["subject"],
        payload=json.loads(row["payload_json"]),
        created_at=_ts(row["created_at"]),
        resolved_at=_ts(row["resolved_at"]),
    )

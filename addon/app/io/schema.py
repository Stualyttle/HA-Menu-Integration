"""JSON document schema for import and export (PLAN §8, schema_version 1).

Validation is hand-written so no dependency is added. Every error carries a path such as
``items[2].nutrition.kcal`` and all errors are collected before raising.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.models import ItemType, NutritionSource, RuleKind, RuleScope

SCHEMA_VERSION = 1

SECRET_SETTING_KEYS = frozenset({"usda_api_key"})
READ_ONLY_SETTING_KEYS = frozenset({"time_zone"})
IMPORTABLE_SETTING_KEYS = frozenset(
    {"window_days", "household_size", "repeat_gap_days", "balance_targets", "language"}
)

TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "items", "categories", "rules", "template", "settings"}
)
ITEM_KEYS = frozenset(
    {
        "name",
        "type",
        "portion_grams",
        "fat_source",
        "track_stock",
        "is_complete_meal",
        "nutrition",
    }
)
NUTRITION_KEYS = frozenset(
    {
        "source",
        "external_id",
        "matched_name",
        "kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "user_confirmed",
    }
)
NUTRITION_VALUE_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")
CATEGORY_KEYS = frozenset({"name", "min_per_7_days", "items"})
RULE_KEYS = frozenset({"kind", "scope", "categories", "item", "enabled"})
TEMPLATE_KEYS = frozenset(t.value for t in ItemType)
MAX_TEMPLATE_SLOTS = 2


class ImportValidationError(ValueError):
    """Raised when a document does not match the schema. ``errors`` lists every problem."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) or "invalid document")


@dataclass(frozen=True, slots=True)
class NutritionDoc:
    source: NutritionSource
    external_id: str | None
    matched_name: str | None
    values: dict[str, float | None]
    user_confirmed: bool


@dataclass(frozen=True, slots=True)
class ItemDoc:
    name: str
    type: ItemType
    portion_grams: float | None
    fat_source: bool
    track_stock: bool
    is_complete_meal: bool
    nutrition: NutritionDoc | None


@dataclass(frozen=True, slots=True)
class CategoryDoc:
    name: str
    min_per_7_days: int | None
    items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuleDoc:
    kind: RuleKind
    scope: RuleScope
    categories: tuple[str, ...]
    item: str | None
    enabled: bool


@dataclass(frozen=True, slots=True)
class Document:
    items: tuple[ItemDoc, ...] = ()
    categories: tuple[CategoryDoc, ...] = ()
    rules: tuple[RuleDoc, ...] = ()
    template: dict[ItemType, int] | None = None
    settings: dict[str, Any] | None = None
    has_settings: bool = field(default=False)


class _Collector:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def add(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_unknown(
    obj: Mapping[str, Any], allowed: frozenset[str], path: str, c: _Collector
) -> None:
    for key in obj:
        if key not in allowed:
            c.add(f"{path}.{key}" if path else key, "unknown field")


def _name(value: object, path: str, c: _Collector) -> str | None:
    if not isinstance(value, str) or not value.strip():
        c.add(path, "must be a non-empty string")
        return None
    return value.strip()


def _bool(obj: Mapping[str, Any], key: str, default: bool, path: str, c: _Collector) -> bool:
    if key not in obj:
        return default
    value = obj[key]
    if not isinstance(value, bool):
        c.add(f"{path}.{key}", "must be a boolean")
        return default
    return value


def _nonneg_number(value: object, path: str, c: _Collector) -> float | None:
    if value is None:
        return None
    if not _is_number(value) or not math.isfinite(float(value)) or float(value) < 0:
        c.add(path, "must be a non-negative number or null")
        return None
    return float(value)


def _parse_nutrition(raw: object, path: str, c: _Collector) -> NutritionDoc | None:
    if not isinstance(raw, Mapping):
        c.add(path, "must be an object")
        return None
    _check_unknown(raw, NUTRITION_KEYS, path, c)
    source_raw = raw.get("source")
    try:
        source = NutritionSource(source_raw)
    except ValueError:
        c.add(f"{path}.source", "must be one of open_food_facts, usda, manual")
        return None
    values: dict[str, float | None] = {}
    for key in NUTRITION_VALUE_KEYS:
        values[key] = _nonneg_number(raw.get(key), f"{path}.{key}", c)
    if source is NutritionSource.MANUAL or raw.get("user_confirmed") is True:
        required = ("kcal", "protein_g", "carbs_g", "fat_g")
        for key in required:
            if values[key] is None:
                c.add(f"{path}.{key}", "is required for manual or confirmed nutrition")
    external_id = raw.get("external_id")
    matched_name = raw.get("matched_name")
    if external_id is not None and not isinstance(external_id, str):
        c.add(f"{path}.external_id", "must be a string or null")
        external_id = None
    if matched_name is not None and not isinstance(matched_name, str):
        c.add(f"{path}.matched_name", "must be a string or null")
        matched_name = None
    user_confirmed = _bool(raw, "user_confirmed", False, path, c)
    return NutritionDoc(source, external_id, matched_name, values, user_confirmed)


def _parse_item(raw: object, path: str, c: _Collector) -> ItemDoc | None:
    if not isinstance(raw, Mapping):
        c.add(path, "must be an object")
        return None
    _check_unknown(raw, ITEM_KEYS, path, c)
    name = _name(raw.get("name"), f"{path}.name", c)
    try:
        item_type = ItemType(raw.get("type"))
    except ValueError:
        c.add(f"{path}.type", "must be one of protein, vegetable, carb")
        return None
    portion = _nonneg_number(raw.get("portion_grams"), f"{path}.portion_grams", c)
    if portion == 0:
        c.add(f"{path}.portion_grams", "must be greater than zero or null")
    fat_source = _bool(raw, "fat_source", False, path, c)
    track_stock = _bool(raw, "track_stock", True, path, c)
    is_complete_meal = _bool(raw, "is_complete_meal", False, path, c)
    if is_complete_meal and item_type is not ItemType.CARB:
        c.add(f"{path}.type", "complete meals must use the carb item type")
    nutrition = None
    if raw.get("nutrition") is not None:
        nutrition = _parse_nutrition(raw["nutrition"], f"{path}.nutrition", c)
    if name is None:
        return None
    return ItemDoc(name, item_type, portion, fat_source, track_stock, is_complete_meal, nutrition)


def _parse_category(raw: object, path: str, c: _Collector) -> CategoryDoc | None:
    if not isinstance(raw, Mapping):
        c.add(path, "must be an object")
        return None
    _check_unknown(raw, CATEGORY_KEYS, path, c)
    name = _name(raw.get("name"), f"{path}.name", c)
    minimum = raw.get("min_per_7_days")
    if minimum is not None and (
        not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0
    ):
        c.add(f"{path}.min_per_7_days", "must be a non-negative integer or null")
        minimum = None
    items_raw = raw.get("items", [])
    names: list[str] = []
    if not isinstance(items_raw, list):
        c.add(f"{path}.items", "must be a list of item names")
    else:
        for i, entry in enumerate(items_raw):
            item_name = _name(entry, f"{path}.items[{i}]", c)
            if item_name is not None:
                names.append(item_name)
    if name is None:
        return None
    return CategoryDoc(name, minimum, tuple(names))


def _parse_rule(raw: object, path: str, c: _Collector) -> RuleDoc | None:
    if not isinstance(raw, Mapping):
        c.add(path, "must be an object")
        return None
    _check_unknown(raw, RULE_KEYS, path, c)
    kind: RuleKind | None
    try:
        kind = RuleKind(raw.get("kind"))
    except ValueError:
        c.add(f"{path}.kind", "must be blacklist or whitelist")
        kind = None
    scope: RuleScope | None
    try:
        scope = RuleScope(raw.get("scope"))
    except ValueError:
        c.add(f"{path}.scope", "must be combination or item")
        scope = None
    if kind is None or scope is None:
        return None
    enabled = _bool(raw, "enabled", True, path, c)
    categories_raw = raw.get("categories", [])
    names: list[str] = []
    if not isinstance(categories_raw, list):
        c.add(f"{path}.categories", "must be a list of category names")
    else:
        for i, entry in enumerate(categories_raw):
            cat_name = _name(entry, f"{path}.categories[{i}]", c)
            if cat_name is not None:
                names.append(cat_name)
    item_raw = raw.get("item")
    item_name = None
    if item_raw is not None:
        item_name = _name(item_raw, f"{path}.item", c)
    if scope is RuleScope.ITEM:
        if item_name is None:
            c.add(f"{path}.item", "is required when scope is item")
        if names:
            c.add(f"{path}.categories", "must be empty when scope is item")
    else:
        if item_raw is not None:
            c.add(f"{path}.item", "must be null when scope is combination")
        if not names:
            c.add(f"{path}.categories", "must list at least one category when scope is combination")
    return RuleDoc(kind, scope, tuple(names), item_name, enabled)


def _parse_template(raw: object, c: _Collector) -> dict[ItemType, int] | None:
    if not isinstance(raw, Mapping):
        c.add("template", "must be an object")
        return None
    _check_unknown(raw, TEMPLATE_KEYS, "template", c)
    slots: dict[ItemType, int] = {}
    for key in TEMPLATE_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_TEMPLATE_SLOTS
        ):
            c.add(f"template.{key}", f"must be an integer from 0 to {MAX_TEMPLATE_SLOTS}")
            continue
        slots[ItemType(key)] = value
    return slots


def _int_in_range(value: object, low: int, high: int | None) -> bool:
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        return False
    return high is None or value <= high


def _check_setting_value(key: str, value: object, path: str, c: _Collector) -> None:
    if key == "window_days":
        if not _int_in_range(value, 7, 60):
            c.add(path, "must be an integer from 7 to 60")
    elif key == "household_size":
        if not _int_in_range(value, 1, None):
            c.add(path, "must be an integer of at least 1")
    elif key == "repeat_gap_days":
        if not _int_in_range(value, 0, None):
            c.add(path, "must be a non-negative integer")
    elif key == "language":
        if value not in ("auto", "en", "nl"):
            c.add(path, "must be one of auto, en, nl")
    elif key == "balance_targets":
        _check_balance_targets(value, path, c)


def _check_balance_targets(value: object, path: str, c: _Collector) -> None:
    allowed = ("vegetables", "protein", "carbs", "tolerance")
    if not isinstance(value, Mapping):
        c.add(path, "must be an object")
        return
    _check_unknown(value, frozenset(allowed), path, c)
    for name in allowed:
        if name not in value:
            continue
        number = value[name]
        if not _is_number(number) or not 0 <= float(number) <= 100:
            c.add(f"{path}.{name}", "must be a number from 0 to 100")


def _parse_settings(raw: object, c: _Collector) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        c.add("settings", "must be an object")
        return None
    settings: dict[str, Any] = {}
    for key, value in raw.items():
        path = f"settings.{key}"
        if key in SECRET_SETTING_KEYS:
            c.add(path, "secrets are never imported; remove this field")
        elif key in READ_ONLY_SETTING_KEYS:
            c.add(path, "is read-only and cannot be imported")
        elif key not in IMPORTABLE_SETTING_KEYS:
            c.add(path, "unknown field")
        else:
            _check_setting_value(key, value, path, c)
            settings[key] = value
    return settings


def parse_document(data: object) -> Document:
    """Validate a decoded JSON document and return typed records.

    Raises ImportValidationError listing every problem found.
    """
    c = _Collector()
    if not isinstance(data, Mapping):
        raise ImportValidationError(["document: must be a JSON object"])
    _check_unknown(data, TOP_LEVEL_KEYS, "", c)
    version = data.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != SCHEMA_VERSION:
        c.add("schema_version", f"must be {SCHEMA_VERSION}")

    items = _parse_list(data, "items", _parse_item, c)
    categories = _parse_list(data, "categories", _parse_category, c)
    rules = _parse_list(data, "rules", _parse_rule, c)
    template = _parse_template(data["template"], c) if "template" in data else None
    has_settings = "settings" in data
    settings = _parse_settings(data["settings"], c) if has_settings else None

    _check_duplicates(items, categories, c)
    if c.errors:
        raise ImportValidationError(c.errors)
    return Document(
        items=tuple(items),
        categories=tuple(categories),
        rules=tuple(rules),
        template=template,
        settings=settings,
        has_settings=has_settings,
    )


def _parse_list(data: Mapping[str, Any], key: str, parser: Any, c: _Collector) -> list[Any]:
    if key not in data:
        return []
    raw_list = data[key]
    if not isinstance(raw_list, list):
        c.add(key, "must be a list")
        return []
    parsed = []
    for i, entry in enumerate(raw_list):
        result = parser(entry, f"{key}[{i}]", c)
        if result is not None:
            parsed.append(result)
    return parsed


def _check_duplicates(items: list[ItemDoc], categories: list[CategoryDoc], c: _Collector) -> None:
    seen: set[str] = set()
    for item in items:
        key = item.name.casefold()
        if key in seen:
            c.add("items", f"duplicate name '{item.name}' (names are case-insensitive)")
        seen.add(key)
    seen = set()
    for category in categories:
        key = category.name.casefold()
        if key in seen:
            c.add("categories", f"duplicate name '{category.name}' (names are case-insensitive)")
        seen.add(key)

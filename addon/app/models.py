"""Shared domain models: enums and dataclasses used across the add-on."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class ItemType(StrEnum):
    PROTEIN = "protein"
    VEGETABLE = "vegetable"
    CARB = "carb"


class DayStatus(StrEnum):
    PLANNED = "planned"
    PINNED = "pinned"
    EATEN = "eaten"
    EMPTY = "empty"


class RuleKind(StrEnum):
    BLACKLIST = "blacklist"
    WHITELIST = "whitelist"


class RuleScope(StrEnum):
    COMBINATION = "combination"
    ITEM = "item"


class NutritionSource(StrEnum):
    OPEN_FOOD_FACTS = "open_food_facts"
    USDA = "usda"
    MANUAL = "manual"


class NutritionStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    ERROR = "error"


class WarningCode(StrEnum):
    REPLACED_DINNER = "replaced_dinner"
    MISSED_MINIMUM = "missed_minimum"
    REPEAT_GAP_UNAVOIDABLE = "repeat_gap_unavoidable"
    EMPTY_DAY = "empty_day"
    MINIMUM_INFEASIBLE = "minimum_infeasible"
    NUTRITION_FAILED = "nutrition_failed"
    TIMEZONE_MISMATCH = "timezone_mismatch"


class WarningSubject(StrEnum):
    DATE = "date"
    ITEM = "item"
    CATEGORY = "category"


@dataclass(slots=True)
class Item:
    id: int
    name: str
    type: ItemType
    portion_grams: float | None = None
    fat_source: bool = False
    track_stock: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Nutrition:
    item_id: int
    source: NutritionSource
    status: NutritionStatus
    external_id: str | None = None
    matched_name: str | None = None
    kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    user_confirmed: bool = False
    fetched_at: datetime | None = None


@dataclass(slots=True)
class Category:
    id: int
    name: str
    is_starter: bool = False
    min_per_7_days: int | None = None
    item_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class Rule:
    id: int
    kind: RuleKind
    scope: RuleScope
    category_ids: frozenset[int] = field(default_factory=frozenset)
    item_id: int | None = None
    enabled: bool = True


@dataclass(slots=True)
class Dinner:
    """A set of items. Each item's type comes from `Item.type`.

    `item_ids` is sorted and duplicate-free. Per-type counts are checked against the
    dinner template by the domain rules, not here.
    """

    id: int
    item_ids: tuple[int, ...]


@dataclass(slots=True)
class MenuDay:
    day: date
    dinner_id: int | None
    status: DayStatus
    replaced_reason: str | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class WarningRecord:
    """A persisted warning shown on the dashboard and in the panel."""

    id: int
    code: WarningCode
    subject_type: WarningSubject
    subject: str
    payload: dict = field(default_factory=dict)
    created_at: datetime | None = None
    resolved_at: datetime | None = None

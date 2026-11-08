"""Pydantic request and response models for the data endpoints (docs/API.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.models import (
    Category,
    DayStatus,
    Item,
    ItemType,
    Nutrition,
    Rule,
    RuleKind,
    RuleScope,
    WarningRecord,
)

Name = Annotated[str, Field(min_length=1, max_length=120)]


def _strip_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


class ItemIn(BaseModel):
    name: Name
    type: ItemType
    portion_grams: Annotated[float | None, Field(ge=0)] = None
    fat_source: bool = False
    track_stock: bool = True
    category_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _strip_name(value)


class NutritionOut(BaseModel):
    source: str
    status: str
    kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    fiber_g: float | None
    user_confirmed: bool

    @classmethod
    def from_model(cls, n: Nutrition) -> NutritionOut:
        return cls(
            source=n.source.value,
            status=n.status.value,
            kcal=n.kcal,
            protein_g=n.protein_g,
            carbs_g=n.carbs_g,
            fat_g=n.fat_g,
            fiber_g=n.fiber_g,
            user_confirmed=n.user_confirmed,
        )


class ItemOut(BaseModel):
    id: int
    name: str
    type: ItemType
    portion_grams: float | None
    fat_source: bool
    track_stock: bool
    category_ids: list[int]
    nutrition: NutritionOut | None

    @classmethod
    def from_model(
        cls, item: Item, category_ids: list[int], nutrition: Nutrition | None
    ) -> ItemOut:
        return cls(
            id=item.id,
            name=item.name,
            type=item.type,
            portion_grams=item.portion_grams,
            fat_source=item.fat_source,
            track_stock=item.track_stock,
            category_ids=sorted(category_ids),
            nutrition=NutritionOut.from_model(nutrition) if nutrition else None,
        )


class CategoryIn(BaseModel):
    name: Name
    min_per_7_days: Annotated[int | None, Field(ge=0, le=7)] = None
    item_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _strip_name(value)


class CategoryOut(BaseModel):
    id: int
    name: str
    is_starter: bool
    min_per_7_days: int | None
    item_count: int
    item_ids: list[int]

    @classmethod
    def from_model(cls, category: Category) -> CategoryOut:
        ids = sorted(category.item_ids)
        return cls(
            id=category.id,
            name=category.name,
            is_starter=category.is_starter,
            min_per_7_days=category.min_per_7_days,
            item_count=len(ids),
            item_ids=ids,
        )


class RuleIn(BaseModel):
    kind: RuleKind
    scope: RuleScope
    category_ids: list[int] = Field(default_factory=list)
    item_id: int | None = None
    enabled: bool = True


class RuleOut(BaseModel):
    id: int
    kind: RuleKind
    scope: RuleScope
    category_ids: list[int]
    item_id: int | None
    enabled: bool

    @classmethod
    def from_model(cls, rule: Rule) -> RuleOut:
        return cls(
            id=rule.id,
            kind=rule.kind,
            scope=rule.scope,
            category_ids=sorted(rule.category_ids),
            item_id=rule.item_id,
            enabled=rule.enabled,
        )


class StockOut(BaseModel):
    item_id: int
    name: str
    type: ItemType
    in_stock: bool | None
    replaces_count: int


class StockAnswerIn(BaseModel):
    in_stock: bool | None


class StockChangeOut(BaseModel):
    item_id: int
    in_stock: bool | None
    replaced_dates: list[str]
    restored_dates: list[str]
    shopping: list[str]


class StockPreviewIn(BaseModel):
    in_stock: bool


class StockPreviewOut(BaseModel):
    item_id: int
    in_stock: bool
    replaces_count: int


class BalanceTargets(BaseModel):
    vegetables: Annotated[int, Field(ge=0, le=100)]
    protein: Annotated[int, Field(ge=0, le=100)]
    carbs: Annotated[int, Field(ge=0, le=100)]
    tolerance: Annotated[int, Field(ge=0, le=100)]


class SettingsIn(BaseModel):
    window_days: Annotated[int | None, Field(ge=7, le=60)] = None
    household_size: Annotated[int | None, Field(ge=1, le=10)] = None
    repeat_gap_days: Annotated[int | None, Field(ge=0, le=60)] = None
    balance_targets: BalanceTargets | None = None
    language: Literal["auto", "en", "nl"] | None = None
    usda_api_key: Annotated[str | None, Field(max_length=200)] = None


class SettingsOut(BaseModel):
    window_days: int
    household_size: int
    repeat_gap_days: int
    balance_targets: BalanceTargets
    language: Literal["auto", "en", "nl"]


class TemplateIn(BaseModel):
    protein: Annotated[int, Field(ge=0, le=2)]
    vegetable: Annotated[int, Field(ge=0, le=2)]
    carb: Annotated[int, Field(ge=0, le=2)]


class DinnerItemOut(BaseModel):
    id: int
    name: str
    type: ItemType


class DinnerOut(BaseModel):
    id: int
    items: list[DinnerItemOut]


class MenuDayOut(BaseModel):
    """One planned day. `date` is an ISO local date (docs/API.md "Menu")."""

    date: str
    status: DayStatus
    dinner: DinnerOut | None
    kcal: float | None
    balance: Literal["ok", "off_target", "unknown"]
    replaced_reason: str | None
    warnings: list[str]


class MenuUpdateIn(BaseModel):
    """Exactly one of: `pinned` (true pins the current dinner, false unpins)
    or `dinner_id` (swap and pin)."""

    pinned: bool | None = None
    dinner_id: int | None = None


class SwapIn(BaseModel):
    dinner_id: int


class SyncIn(BaseModel):
    language: Annotated[str, Field(min_length=1, max_length=35)]
    time_zone: Annotated[str, Field(min_length=1, max_length=64)]


class SyncOut(BaseModel):
    language: str
    time_zone: str
    timezone_mismatch: bool


class RuleCheckIn(BaseModel):
    """A proposed rule. `rule_id` replaces that stored rule; omit it to check an added rule."""

    rule: RuleIn
    rule_id: int | None = None


class RuleCheckOut(BaseModel):
    feasible: bool
    exhausted: bool
    affected_days: list[str]
    locked_conflicts: list[str]


class WarningSubjectOut(BaseModel):
    type: str
    id: str


class WarningOut(BaseModel):
    id: int
    code: str
    subject: WarningSubjectOut
    payload: dict
    created_at: datetime | None

    @classmethod
    def from_model(cls, w: WarningRecord) -> WarningOut:
        return cls(
            id=w.id,
            code=w.code.value,
            subject=WarningSubjectOut(type=w.subject_type.value, id=w.subject),
            payload=w.payload,
            created_at=w.created_at,
        )

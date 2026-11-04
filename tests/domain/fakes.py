"""In-memory repositories implementing the ports.py Protocols, plus a standard household.

The planner is tested against these fakes only; it never touches the SQLite layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from app.domain.config import PlanContext, PlanSettings, Template
from app.domain.engine import PlanResult, replan_all
from app.domain.service import MenuPlanner
from app.domain.snapshot import PlanSnapshot
from app.models import (
    Category,
    DayStatus,
    Dinner,
    Item,
    ItemType,
    MenuDay,
    Nutrition,
    Rule,
    RuleKind,
    RuleScope,
    WarningRecord,
)

TODAY = date(2025, 3, 1)
NOW = datetime(2025, 3, 1, 12, 0)

CHICKEN, BEEF, TOFU = 1, 2, 3
BROCCOLI, CARROT, SPINACH = 10, 11, 12
RICE, PASTA, POTATO = 20, 21, 22

MEAT, VEGETARIAN, VEGETABLES, PASTA_CAT, RICE_CAT, POTATO_CAT = 100, 101, 102, 103, 104, 105


@dataclass
class FakeStore:
    items: dict[int, Item] = field(default_factory=dict)
    categories: dict[int, Category] = field(default_factory=dict)
    rules: dict[int, Rule] = field(default_factory=dict)
    dinners: dict[int, Dinner] = field(default_factory=dict)
    days: dict[date, MenuDay] = field(default_factory=dict)
    nutrition: dict[int, Nutrition] = field(default_factory=dict)
    warnings: dict[int, WarningRecord] = field(default_factory=dict)
    _next_warning_id: int = 1

    def next_dinner_id(self) -> int:
        return max(self.dinners, default=0) + 1


class FakeItems:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def list_items(self) -> list[Item]:
        return [self._store.items[k] for k in sorted(self._store.items)]

    async def get_item(self, item_id: int) -> Item | None:
        return self._store.items.get(item_id)

    async def save_item(self, item: Item) -> Item:
        self._store.items[item.id] = item
        return item

    async def delete_item(self, item_id: int) -> None:
        self._store.items.pop(item_id, None)


class FakeCategories:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def list_categories(self) -> list[Category]:
        return [self._store.categories[k] for k in sorted(self._store.categories)]

    async def save_category(self, category: Category) -> Category:
        self._store.categories[category.id] = category
        return category

    async def delete_category(self, category_id: int) -> None:
        self._store.categories.pop(category_id, None)


class FakeRules:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def list_rules(self) -> list[Rule]:
        return [self._store.rules[k] for k in sorted(self._store.rules)]

    async def save_rule(self, rule: Rule) -> Rule:
        self._store.rules[rule.id] = rule
        return rule

    async def delete_rule(self, rule_id: int) -> None:
        self._store.rules.pop(rule_id, None)


class FakeMenu:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def get_days(self, start: date, end: date) -> list[MenuDay]:
        return [self._store.days[d] for d in sorted(self._store.days) if start <= d <= end]

    async def save_days(self, days: Iterable[MenuDay]) -> None:
        for day in days:
            self._store.days[day.day] = day

    async def list_dinners(self) -> list[Dinner]:
        return [self._store.dinners[k] for k in sorted(self._store.dinners)]


class FakeNutrition:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def get_nutrition(self, item_id: int) -> Nutrition | None:
        return self._store.nutrition.get(item_id)

    async def save_nutrition(self, nutrition: Nutrition) -> None:
        self._store.nutrition[nutrition.item_id] = nutrition


class FakeWarnings:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def list_open(self) -> list[WarningRecord]:
        return [
            record
            for _, record in sorted(self._store.warnings.items())
            if record.resolved_at is None
        ]

    async def open_warning(self, warning: WarningRecord) -> WarningRecord:
        stored = replace(warning, id=self._store._next_warning_id)
        self._store._next_warning_id += 1
        self._store.warnings[stored.id] = stored
        return stored

    async def resolve_warning(self, warning_id: int) -> None:
        record = self._store.warnings[warning_id]
        self._store.warnings[warning_id] = replace(record, resolved_at=NOW)


def make_planner(store: FakeStore) -> MenuPlanner:
    return MenuPlanner(
        items=FakeItems(store),
        categories=FakeCategories(store),
        rules=FakeRules(store),
        menu=FakeMenu(store),
        nutrition=FakeNutrition(store),
        warnings=FakeWarnings(store),
    )


def make_ctx(
    *,
    today: date = TODAY,
    window_days: int = 14,
    repeat_gap_days: int = 14,
    out_of_stock: Iterable[int] = (),
    timezone: str = "Europe/London",
    device_timezone: str | None = None,
    revision: int = 0,
) -> PlanContext:
    return PlanContext(
        today=today,
        timezone=timezone,
        settings=PlanSettings(window_days=window_days, repeat_gap_days=repeat_gap_days),
        template=Template(),
        out_of_stock=frozenset(out_of_stock),
        device_timezone=device_timezone,
        revision=revision,
    )


def snapshot_of(store: FakeStore) -> PlanSnapshot:
    return PlanSnapshot(
        items=dict(store.items),
        categories=dict(store.categories),
        rules=list(store.rules.values()),
        dinners=dict(store.dinners),
        nutrition=dict(store.nutrition),
        days=dict(store.days),
    )


def apply_result(store: FakeStore, result: PlanResult) -> None:
    """Persist a PlanResult into the fake store, as the service does."""
    for record in result.updated.values():
        store.days[record.day] = record


def plan_window(store: FakeStore, ctx: PlanContext, reason: str | None = None) -> PlanResult:
    """Re-plan every fillable day in the window and persist the result."""
    result = replan_all(snapshot_of(store), ctx, reason)
    apply_result(store, result)
    return result


def window_dinners(store: FakeStore, ctx: PlanContext) -> dict[date, Dinner | None]:
    return {day: dinner_of(store, day) for day in window_dates(ctx)}


def window_status(store: FakeStore, ctx: PlanContext) -> dict[date, DayStatus]:
    statuses: dict[date, DayStatus] = {}
    for day in window_dates(ctx):
        record = store.days.get(day)
        statuses[day] = record.status if record is not None else DayStatus.EMPTY
    return statuses


def window_dates(ctx: PlanContext) -> list[date]:
    return [ctx.today + timedelta(days=k) for k in range(ctx.settings.window_days)]


def add_dinner(store: FakeStore, *item_ids: int) -> int:
    dinner_id = store.next_dinner_id()
    store.dinners[dinner_id] = Dinner(id=dinner_id, item_ids=tuple(sorted(set(item_ids))))
    return dinner_id


def find_dinner(store: FakeStore, *item_ids: int) -> int:
    key = tuple(sorted(set(item_ids)))
    for dinner in store.dinners.values():
        if dinner.item_ids == key:
            return dinner.id
    raise KeyError(key)


def dinner_of(store: FakeStore, day: date) -> Dinner | None:
    record = store.days.get(day)
    if record is None or record.dinner_id is None:
        return None
    return store.dinners[record.dinner_id]


def standard_household() -> FakeStore:
    """Three proteins, three vegetables, three carbs, and all 27 dinners as combinations."""
    store = FakeStore()
    names = {
        CHICKEN: ("Chicken", ItemType.PROTEIN),
        BEEF: ("Beef", ItemType.PROTEIN),
        TOFU: ("Tofu", ItemType.PROTEIN),
        BROCCOLI: ("Broccoli", ItemType.VEGETABLE),
        CARROT: ("Carrot", ItemType.VEGETABLE),
        SPINACH: ("Spinach", ItemType.VEGETABLE),
        RICE: ("Rice", ItemType.CARB),
        PASTA: ("Pasta", ItemType.CARB),
        POTATO: ("Potato", ItemType.CARB),
    }
    for item_id, (name, item_type) in names.items():
        store.items[item_id] = Item(id=item_id, name=name, type=item_type)

    categories = [
        Category(MEAT, "Meat", item_ids={CHICKEN, BEEF}),
        Category(VEGETARIAN, "Vegetarian", item_ids={TOFU}),
        Category(VEGETABLES, "Vegetables", item_ids={BROCCOLI, CARROT, SPINACH}),
        Category(PASTA_CAT, "Pasta", item_ids={PASTA}),
        Category(RICE_CAT, "Rice", item_ids={RICE}),
        Category(POTATO_CAT, "Potato", item_ids={POTATO}),
    ]
    for category in categories:
        store.categories[category.id] = category

    for protein in (CHICKEN, BEEF, TOFU):
        for vegetable in (BROCCOLI, CARROT, SPINACH):
            for carb in (RICE, PASTA, POTATO):
                add_dinner(store, protein, vegetable, carb)
    # The standard template is 1 protein + 1 vegetable + 1 carb; the 27 dinners above match it.
    return store


def blacklist_item(rule_id: int, item_id: int) -> Rule:
    return Rule(id=rule_id, kind=RuleKind.BLACKLIST, scope=RuleScope.ITEM, item_id=item_id)


def blacklist_combination(rule_id: int, category_ids: Iterable[int]) -> Rule:
    return Rule(
        id=rule_id,
        kind=RuleKind.BLACKLIST,
        scope=RuleScope.COMBINATION,
        category_ids=frozenset(category_ids),
    )


def whitelist_item(rule_id: int, item_id: int) -> Rule:
    return Rule(id=rule_id, kind=RuleKind.WHITELIST, scope=RuleScope.ITEM, item_id=item_id)

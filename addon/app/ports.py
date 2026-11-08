"""Repository and service Protocols. Implementations live in app/db, app/domain and app/nutrition.

Phases 2 to 5 implement these. Keep the signatures stable; API changes go through docs/API.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Protocol

from app.models import (
    Category,
    Dinner,
    Item,
    MenuDay,
    Nutrition,
    Rule,
    WarningRecord,
)


class ItemRepository(Protocol):
    async def list_items(self) -> list[Item]: ...

    async def get_item(self, item_id: int) -> Item | None: ...

    async def save_item(self, item: Item) -> Item: ...

    async def delete_item(self, item_id: int) -> None: ...


class CategoryRepository(Protocol):
    async def list_categories(self) -> list[Category]: ...

    async def save_category(self, category: Category) -> Category: ...

    async def delete_category(self, category_id: int) -> None: ...


class RuleRepository(Protocol):
    async def list_rules(self) -> list[Rule]: ...

    async def save_rule(self, rule: Rule) -> Rule: ...

    async def delete_rule(self, rule_id: int) -> None: ...


class MenuRepository(Protocol):
    async def get_days(self, start: date, end: date) -> list[MenuDay]: ...

    async def save_days(self, days: Iterable[MenuDay]) -> None: ...

    async def list_dinners(self) -> list[Dinner]: ...

    async def ensure_dinners(self, dinner_item_sets: Sequence[Sequence[int]]) -> list[int]:
        """Create dinners for item-id sets that do not exist yet (idempotent).

        Returns one dinner id per input set, in the same order.
        """
        ...


class NutritionRepository(Protocol):
    async def get_nutrition(self, item_id: int) -> Nutrition | None: ...

    async def save_nutrition(self, nutrition: Nutrition) -> None: ...


class WarningRepository(Protocol):
    async def list_open(self) -> list[WarningRecord]: ...

    async def open_warning(self, warning: WarningRecord) -> WarningRecord: ...

    async def resolve_warning(self, warning_id: int) -> None: ...

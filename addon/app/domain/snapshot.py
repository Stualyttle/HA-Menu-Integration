"""Immutable view of household data that the planning engine works on."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models import Category, Dinner, Item, MenuDay, Nutrition, Rule


@dataclass(slots=True)
class PlanSnapshot:
    items: dict[int, Item]
    categories: dict[int, Category]
    rules: list[Rule]
    dinners: dict[int, Dinner]
    nutrition: dict[int, Nutrition] = field(default_factory=dict)
    days: dict[date, MenuDay] = field(default_factory=dict)
    item_categories: dict[int, frozenset[int]] = field(init=False)

    def __post_init__(self) -> None:
        index: dict[int, set[int]] = {item_id: set() for item_id in self.items}
        for category in self.categories.values():
            for item_id in category.item_ids:
                if item_id in index:
                    index[item_id].add(category.id)
        self.item_categories = {item_id: frozenset(ids) for item_id, ids in index.items()}

    def dinner_items(self, dinner: Dinner) -> tuple[int, ...]:
        return dinner.item_ids

    def dinner_categories(self, dinner: Dinner) -> frozenset[int]:
        found: set[int] = set()
        for item_id in self.dinner_items(dinner):
            found |= self.item_categories.get(item_id, frozenset())
        return frozenset(found)

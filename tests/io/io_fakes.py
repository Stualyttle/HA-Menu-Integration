from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from app.io.export import ExportService
from app.io.importer import ImportService
from app.models import Category, Item, ItemType, Nutrition, Rule


class FakeItems:
    def __init__(self) -> None:
        self.rows: dict[int, Item] = {}
        self._next = 1

    async def list_items(self) -> list[Item]:
        return [replace(item) for item in self.rows.values()]

    async def get_item(self, item_id: int) -> Item | None:
        item = self.rows.get(item_id)
        return replace(item) if item else None

    async def save_item(self, item: Item) -> Item:
        if item.id == 0:
            item = replace(item, id=self._next)
            self._next += 1
        self.rows[item.id] = replace(item)
        return replace(item)

    async def delete_item(self, item_id: int) -> None:
        self.rows.pop(item_id, None)


class FakeCategories:
    def __init__(self) -> None:
        self.rows: dict[int, Category] = {}
        self._next = 1

    async def list_categories(self) -> list[Category]:
        return [replace(c, item_ids=set(c.item_ids)) for c in self.rows.values()]

    async def save_category(self, category: Category) -> Category:
        if category.id == 0:
            category = replace(category, id=self._next)
            self._next += 1
        self.rows[category.id] = replace(category, item_ids=set(category.item_ids))
        return replace(category, item_ids=set(category.item_ids))

    async def delete_category(self, category_id: int) -> None:
        self.rows.pop(category_id, None)


class FakeRules:
    def __init__(self) -> None:
        self.rows: dict[int, Rule] = {}
        self._next = 1

    async def list_rules(self) -> list[Rule]:
        return [replace(r, category_ids=frozenset(r.category_ids)) for r in self.rows.values()]

    async def save_rule(self, rule: Rule) -> Rule:
        if rule.id == 0:
            rule = replace(rule, id=self._next)
            self._next += 1
        self.rows[rule.id] = replace(rule)
        return replace(rule)

    async def delete_rule(self, rule_id: int) -> None:
        self.rows.pop(rule_id, None)


class FakeNutrition:
    def __init__(self) -> None:
        self.rows: dict[int, Nutrition] = {}

    async def get_nutrition(self, item_id: int) -> Nutrition | None:
        row = self.rows.get(item_id)
        return replace(row) if row else None

    async def save_nutrition(self, nutrition: Nutrition) -> None:
        self.rows[nutrition.item_id] = replace(nutrition)


class FakeTemplate:
    def __init__(self, slots: Mapping[ItemType, int] | None = None) -> None:
        self.slots: dict[ItemType, int] = dict(slots or {})

    async def get_template(self) -> dict[ItemType, int]:
        return dict(self.slots)

    async def set_template(self, slots: Mapping[ItemType, int]) -> None:
        self.slots = dict(slots)


class FakeSettings:
    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        self.values: dict[str, Any] = dict(values or {})

    async def get_settings(self) -> dict[str, Any]:
        return dict(self.values)

    async def update_settings(self, values: Mapping[str, Any]) -> None:
        self.values.update(values)


@dataclass
class Store:
    items: FakeItems = field(default_factory=FakeItems)
    categories: FakeCategories = field(default_factory=FakeCategories)
    rules: FakeRules = field(default_factory=FakeRules)
    nutrition: FakeNutrition = field(default_factory=FakeNutrition)
    template: FakeTemplate = field(default_factory=FakeTemplate)
    settings: FakeSettings = field(default_factory=FakeSettings)

    def exporter(self) -> ExportService:
        return ExportService(
            self.items,
            self.categories,
            self.rules,
            self.nutrition,
            self.template,
            self.settings,
        )

    def importer(self) -> ImportService:
        return ImportService(
            self.items,
            self.categories,
            self.rules,
            self.nutrition,
            self.template,
            self.settings,
        )

    async def add_item(self, name: str, item_type: ItemType = ItemType.VEGETABLE) -> Item:
        return await self.items.save_item(Item(id=0, name=name, type=item_type))

    async def add_category(
        self, name: str, item_ids: set[int] | None = None, minimum: int | None = None
    ) -> Category:
        return await self.categories.save_category(
            Category(id=0, name=name, min_per_7_days=minimum, item_ids=set(item_ids or ()))
        )


def minimal_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "items": [],
        "categories": [],
        "rules": [],
        "template": {},
        "settings": {},
    }
    document.update(overrides)
    return document

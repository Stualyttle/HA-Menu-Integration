"""Export the menu planner data to the schema_version 1 JSON document (PLAN §8)."""

from __future__ import annotations

from typing import Any

from app.io.ports import SettingsStore, TemplateStore
from app.io.schema import IMPORTABLE_SETTING_KEYS, NUTRITION_VALUE_KEYS, SCHEMA_VERSION
from app.models import Category, Item, Nutrition, NutritionSource, Rule, RuleScope
from app.ports import CategoryRepository, ItemRepository, NutritionRepository, RuleRepository


class ExportService:
    def __init__(
        self,
        items: ItemRepository,
        categories: CategoryRepository,
        rules: RuleRepository,
        nutrition: NutritionRepository,
        template: TemplateStore,
        settings: SettingsStore,
    ) -> None:
        self._items = items
        self._categories = categories
        self._rules = rules
        self._nutrition = nutrition
        self._template = template
        self._settings = settings

    async def export(self) -> dict[str, Any]:
        items = await self._items.list_items()
        categories = await self._categories.list_categories()
        rules = await self._rules.list_rules()
        item_names = {item.id: item.name for item in items}
        category_names = {category.id: category.name for category in categories}

        return {
            "schema_version": SCHEMA_VERSION,
            "items": [await self._export_item(item) for item in sorted(items, key=_by_name)],
            "categories": [
                _export_category(category, item_names)
                for category in sorted(categories, key=_by_name)
            ],
            "rules": _export_rules(rules, item_names, category_names),
            "template": {
                slot.value: count for slot, count in (await self._template.get_template()).items()
            },
            "settings": await self._export_settings(),
        }

    async def _export_item(self, item: Item) -> dict[str, Any]:
        record: dict[str, Any] = {
            "name": item.name,
            "type": item.type.value,
            "portion_grams": item.portion_grams,
            "fat_source": item.fat_source,
            "track_stock": item.track_stock,
            "nutrition": None,
        }
        nutrition = await self._nutrition.get_nutrition(item.id)
        if nutrition is not None and _is_exportable_nutrition(nutrition):
            record["nutrition"] = _export_nutrition(nutrition)
        return record

    async def _export_settings(self) -> dict[str, Any]:
        stored = await self._settings.get_settings()
        return {key: stored[key] for key in sorted(IMPORTABLE_SETTING_KEYS) if key in stored}


def _by_name(record: Item | Category) -> str:
    return record.name.casefold()


def _is_exportable_nutrition(nutrition: Nutrition) -> bool:
    return nutrition.source is NutritionSource.MANUAL or nutrition.user_confirmed


def _export_nutrition(nutrition: Nutrition) -> dict[str, Any]:
    values = {
        "kcal": nutrition.kcal,
        "protein_g": nutrition.protein_g,
        "carbs_g": nutrition.carbs_g,
        "fat_g": nutrition.fat_g,
        "fiber_g": nutrition.fiber_g,
    }
    record: dict[str, Any] = {
        "source": nutrition.source.value,
        "external_id": nutrition.external_id,
        "matched_name": nutrition.matched_name,
        "user_confirmed": nutrition.user_confirmed,
    }
    for key in NUTRITION_VALUE_KEYS:
        record[key] = values[key]
    return record


def _export_category(category: Category, item_names: dict[int, str]) -> dict[str, Any]:
    names = sorted(
        (item_names[item_id] for item_id in category.item_ids if item_id in item_names),
        key=str.casefold,
    )
    return {
        "name": category.name,
        "min_per_7_days": category.min_per_7_days,
        "items": names,
    }


def _export_rules(
    rules: list[Rule], item_names: dict[int, str], category_names: dict[int, str]
) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for rule in rules:
        if rule.scope is RuleScope.ITEM:
            if rule.item_id not in item_names:
                continue
            categories: list[str] = []
            item = item_names[rule.item_id]
        else:
            categories = sorted(
                (category_names[cid] for cid in rule.category_ids if cid in category_names),
                key=str.casefold,
            )
            item = None
        exported.append(
            {
                "kind": rule.kind.value,
                "scope": rule.scope.value,
                "categories": categories,
                "item": item,
                "enabled": rule.enabled,
            }
        )
    return exported

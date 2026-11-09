"""Import preview and merge for the schema_version 1 JSON document (PLAN §8).

Merge rules:
- Items and categories match by name, case-insensitive. Existing ones are skipped, not overwritten.
- Rules are skipped when an equivalent rule already exists (same kind, scope, categories, item).
- Settings and the dinner template are written only when include_settings is true.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.io.ports import SettingsStore, TemplateStore
from app.io.schema import (
    CategoryDoc,
    Document,
    ImportValidationError,
    ItemDoc,
    NutritionDoc,
    RuleDoc,
    parse_document,
)
from app.models import (
    Category,
    Item,
    ItemType,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    Rule,
    RuleScope,
)
from app.ports import CategoryRepository, ItemRepository, NutritionRepository, RuleRepository

RuleKey = tuple[str, str, frozenset[str], str | None]


@dataclass(frozen=True, slots=True)
class ImportPreview:
    added: dict[str, int]
    skipped: dict[str, int]
    settings_available: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "added": dict(self.added),
            "skipped": dict(self.skipped),
            "settings_available": self.settings_available,
        }


@dataclass(slots=True)
class _Plan:
    document: Document
    new_items: list[ItemDoc] = field(default_factory=list)
    new_categories: list[CategoryDoc] = field(default_factory=list)
    new_rules: list[RuleDoc] = field(default_factory=list)
    skipped_items: int = 0
    skipped_categories: int = 0
    skipped_rules: int = 0
    existing_item_ids: dict[str, int] = field(default_factory=dict)
    existing_category_ids: dict[str, int] = field(default_factory=dict)

    def preview(self) -> ImportPreview:
        return ImportPreview(
            added={
                "items": len(self.new_items),
                "categories": len(self.new_categories),
                "rules": len(self.new_rules),
            },
            skipped={
                "items": self.skipped_items,
                "categories": self.skipped_categories,
                "rules": self.skipped_rules,
            },
            settings_available=_has_settings_group(self.document),
        )


def _has_settings_group(document: Document) -> bool:
    return bool(document.settings) or bool(document.template)


class ImportService:
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

    async def preview(self, data: object) -> ImportPreview:
        plan = await self._plan(data)
        return plan.preview()

    async def apply(self, data: object, include_settings: bool = False) -> ImportPreview:
        plan = await self._plan(data)
        await self._write(plan, include_settings)
        return plan.preview()

    async def _plan(self, data: object) -> _Plan:
        document = parse_document(data)
        existing_items = await self._items.list_items()
        existing_categories = await self._categories.list_categories()
        existing_rules = await self._rules.list_rules()

        plan = _Plan(document=document)
        plan.existing_item_ids = {item.name.casefold(): item.id for item in existing_items}
        plan.existing_category_ids = {
            category.name.casefold(): category.id for category in existing_categories
        }
        _check_references(document, plan)

        for item in document.items:
            if item.name.casefold() in plan.existing_item_ids:
                plan.skipped_items += 1
            else:
                plan.new_items.append(item)

        for category in document.categories:
            if category.name.casefold() in plan.existing_category_ids:
                plan.skipped_categories += 1
            else:
                plan.new_categories.append(category)

        known_rules = _existing_rule_keys(existing_rules, existing_items, existing_categories)
        for rule in document.rules:
            key = _document_rule_key(rule)
            if key in known_rules:
                plan.skipped_rules += 1
            else:
                known_rules.add(key)
                plan.new_rules.append(rule)
        return plan

    async def _write(self, plan: _Plan, include_settings: bool) -> None:
        item_ids = dict(plan.existing_item_ids)
        for item in plan.new_items:
            saved = await self._items.save_item(
                Item(
                    id=0,
                    name=item.name,
                    type=item.type,
                    portion_grams=item.portion_grams,
                    fat_source=item.fat_source,
                    track_stock=item.track_stock,
                    is_complete_meal=item.is_complete_meal,
                )
            )
            item_ids[item.name.casefold()] = saved.id
            if item.nutrition is not None:
                await self._nutrition.save_nutrition(_to_nutrition(saved.id, item.nutrition))

        category_ids = dict(plan.existing_category_ids)
        for category in plan.new_categories:
            saved_category = await self._categories.save_category(
                Category(
                    id=0,
                    name=category.name,
                    is_starter=False,
                    min_per_7_days=category.min_per_7_days,
                    item_ids={item_ids[name.casefold()] for name in category.items},
                )
            )
            category_ids[category.name.casefold()] = saved_category.id

        for rule in plan.new_rules:
            await self._rules.save_rule(
                Rule(
                    id=0,
                    kind=rule.kind,
                    scope=rule.scope,
                    category_ids=frozenset(
                        category_ids[name.casefold()] for name in rule.categories
                    ),
                    item_id=item_ids[rule.item.casefold()] if rule.item is not None else None,
                    enabled=rule.enabled,
                )
            )

        if include_settings:
            await self._write_settings_group(plan.document)

    async def _write_settings_group(self, document: Document) -> None:
        if document.settings:
            await self._settings.update_settings(document.settings)
        if document.template is not None:
            current = await self._template.get_template()
            merged: dict[ItemType, int] = {**current, **document.template}
            await self._template.set_template(merged)


def _check_references(document: Document, plan: _Plan) -> None:
    known_items = set(plan.existing_item_ids) | {item.name.casefold() for item in document.items}
    known_categories = set(plan.existing_category_ids) | {
        category.name.casefold() for category in document.categories
    }
    errors: list[str] = []
    for i, category in enumerate(document.categories):
        for name in category.items:
            if name.casefold() not in known_items:
                errors.append(f"categories[{i}].items: unknown item '{name}'")
    for i, rule in enumerate(document.rules):
        for name in rule.categories:
            if name.casefold() not in known_categories:
                errors.append(f"rules[{i}].categories: unknown category '{name}'")
        if rule.item is not None and rule.item.casefold() not in known_items:
            errors.append(f"rules[{i}].item: unknown item '{rule.item}'")
    if errors:
        raise ImportValidationError(errors)


def _to_nutrition(item_id: int, nutrition: NutritionDoc) -> Nutrition:
    manual = nutrition.source is NutritionSource.MANUAL
    values = nutrition.values
    return Nutrition(
        item_id=item_id,
        source=nutrition.source,
        status=NutritionStatus.OK,
        external_id=nutrition.external_id,
        matched_name=nutrition.matched_name,
        kcal=values["kcal"],
        protein_g=values["protein_g"],
        carbs_g=values["carbs_g"],
        fat_g=values["fat_g"],
        fiber_g=values["fiber_g"],
        user_confirmed=manual or nutrition.user_confirmed,
    )


def _document_rule_key(rule: RuleDoc) -> RuleKey:
    categories = frozenset(name.casefold() for name in rule.categories)
    item = rule.item.casefold() if rule.item is not None else None
    return (rule.kind.value, rule.scope.value, categories, item)


def _existing_rule_keys(
    rules: list[Rule], items: list[Item], categories: list[Category]
) -> set[RuleKey]:
    item_names = {item.id: item.name.casefold() for item in items}
    category_names = {category.id: category.name.casefold() for category in categories}
    keys: set[RuleKey] = set()
    for rule in rules:
        if rule.scope is RuleScope.ITEM:
            if rule.item_id not in item_names:
                continue
            item_key = item_names[rule.item_id]
            categories_key: frozenset[str] = frozenset()
        else:
            item_key = None
            categories_key = frozenset(
                category_names[cid] for cid in rule.category_ids if cid in category_names
            )
        keys.add((rule.kind.value, rule.scope.value, categories_key, item_key))
    return keys

from __future__ import annotations

import pytest
from io_fakes import Store, minimal_document

from app.io.schema import ImportValidationError
from app.models import (
    ItemType,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    Rule,
    RuleKind,
    RuleScope,
)


async def test_preview_counts_new_and_existing_without_writing(store: Store) -> None:
    await store.add_item("Kale", ItemType.VEGETABLE)
    data = minimal_document(
        items=[
            {"name": "Kale", "type": "vegetable"},
            {"name": "Rice", "type": "carb"},
        ],
        categories=[{"name": "Greens", "items": ["Kale"]}],
    )

    preview = await store.importer().preview(data)

    assert preview.added == {"items": 1, "categories": 1, "rules": 0}
    assert preview.skipped == {"items": 1, "categories": 0, "rules": 0}
    assert preview.settings_available is False
    assert [item.name for item in await store.items.list_items()] == ["Kale"]
    assert await store.categories.list_categories() == []


async def test_preview_reports_settings_available(store: Store) -> None:
    data = minimal_document(settings={"language": "en"})

    preview = await store.importer().preview(data)

    assert preview.settings_available is True
    assert preview.as_dict() == {
        "added": {"items": 0, "categories": 0, "rules": 0},
        "skipped": {"items": 0, "categories": 0, "rules": 0},
        "settings_available": True,
    }


async def test_item_names_match_case_insensitively_and_are_skipped(store: Store) -> None:
    await store.add_item("Kale", ItemType.VEGETABLE)
    data = minimal_document(items=[{"name": "KALE", "type": "protein"}])

    preview = await store.importer().apply(data)

    assert preview.skipped["items"] == 1
    assert preview.added["items"] == 0
    items = await store.items.list_items()
    assert [(item.name, item.type) for item in items] == [("Kale", ItemType.VEGETABLE)]


async def test_import_persists_complete_meal_flag(store: Store) -> None:
    await store.importer().apply(
        minimal_document(items=[{"name": "Lasagne", "type": "carb", "is_complete_meal": True}])
    )

    item = (await store.items.list_items())[0]
    assert item.name == "Lasagne"
    assert item.is_complete_meal is True


async def test_existing_category_minimum_is_not_overwritten(store: Store) -> None:
    await store.add_category("Greens", minimum=5)
    data = minimal_document(categories=[{"name": "greens", "min_per_7_days": 3}])

    preview = await store.importer().apply(data)

    assert preview.skipped["categories"] == 1
    categories = await store.categories.list_categories()
    assert [(c.name, c.min_per_7_days) for c in categories] == [("Greens", 5)]


async def test_new_category_links_items_by_name(store: Store) -> None:
    kale = await store.add_item("Kale", ItemType.VEGETABLE)
    data = minimal_document(
        items=[{"name": "Rice", "type": "carb"}],
        categories=[{"name": "Greens", "min_per_7_days": 2, "items": ["kale", "Rice"]}],
    )

    await store.importer().apply(data)

    items = {item.name: item.id for item in await store.items.list_items()}
    categories = await store.categories.list_categories()
    assert len(categories) == 1
    assert categories[0].min_per_7_days == 2
    assert categories[0].item_ids == {kale.id, items["Rice"]}


async def test_equivalent_existing_rule_is_skipped(store: Store) -> None:
    kale = await store.add_item("Kale", ItemType.VEGETABLE)
    await store.rules.save_rule(
        Rule(id=0, kind=RuleKind.BLACKLIST, scope=RuleScope.ITEM, item_id=kale.id)
    )
    data = minimal_document(
        items=[{"name": "Kale", "type": "vegetable"}],
        rules=[{"kind": "blacklist", "scope": "item", "item": "KALE"}],
    )

    preview = await store.importer().apply(data)

    assert preview.skipped["rules"] == 1
    assert preview.added["rules"] == 0
    assert len(await store.rules.list_rules()) == 1


async def test_duplicate_rules_within_document_are_added_once(store: Store) -> None:
    await store.add_item("Rice", ItemType.CARB)
    rule = {"kind": "blacklist", "scope": "item", "item": "Rice"}
    data = minimal_document(
        items=[{"name": "Rice", "type": "carb"}],
        rules=[rule, dict(rule)],
    )

    preview = await store.importer().apply(data)

    assert preview.added["rules"] == 1
    assert preview.skipped["rules"] == 1
    assert len(await store.rules.list_rules()) == 1


async def test_combination_rule_resolves_category_ids(store: Store) -> None:
    data = minimal_document(
        categories=[{"name": "Greens", "items": []}, {"name": "Meat", "items": []}],
        rules=[
            {
                "kind": "whitelist",
                "scope": "combination",
                "categories": ["greens", "Meat"],
            }
        ],
    )

    await store.importer().apply(data)

    categories = {c.name: c.id for c in await store.categories.list_categories()}
    rules = await store.rules.list_rules()
    assert len(rules) == 1
    assert rules[0].kind is RuleKind.WHITELIST
    assert rules[0].scope is RuleScope.COMBINATION
    assert rules[0].category_ids == frozenset({categories["Greens"], categories["Meat"]})


async def test_unknown_category_reference_is_rejected_and_nothing_written(store: Store) -> None:
    data = minimal_document(
        items=[{"name": "Rice", "type": "carb"}],
        categories=[{"name": "Greens", "items": ["Ghost"]}],
    )

    with pytest.raises(ImportValidationError) as exc:
        await store.importer().apply(data)

    assert exc.value.errors == ["categories[0].items: unknown item 'Ghost'"]
    assert await store.items.list_items() == []
    assert await store.categories.list_categories() == []


async def test_unknown_rule_references_are_rejected(store: Store) -> None:
    data = minimal_document(
        rules=[
            {"kind": "blacklist", "scope": "combination", "categories": ["Nope"]},
            {"kind": "blacklist", "scope": "item", "item": "Nope"},
        ],
    )

    with pytest.raises(ImportValidationError) as exc:
        await store.importer().preview(data)

    assert exc.value.errors == [
        "rules[0].categories: unknown category 'Nope'",
        "rules[1].item: unknown item 'Nope'",
    ]


async def test_manual_nutrition_is_saved_as_confirmed(store: Store) -> None:
    data = minimal_document(
        items=[
            {
                "name": "Tofu",
                "type": "protein",
                "nutrition": {
                    "source": "manual",
                    "kcal": 120,
                    "protein_g": 12,
                    "carbs_g": 2,
                    "fat_g": 7,
                    "fiber_g": 1,
                },
            }
        ],
    )

    await store.importer().apply(data)

    tofu = (await store.items.list_items())[0]
    nutrition = await store.nutrition.get_nutrition(tofu.id)
    assert nutrition is not None
    assert nutrition.source is NutritionSource.MANUAL
    assert nutrition.status is NutritionStatus.OK
    assert nutrition.user_confirmed is True
    assert (nutrition.kcal, nutrition.protein_g, nutrition.fiber_g) == (120, 12, 1)


async def test_settings_and_template_are_skipped_unless_requested(store: Store) -> None:
    store.template.slots = {ItemType.CARB: 1}
    store.settings.values = {"language": "auto"}
    data = minimal_document(
        template={"protein": 2},
        settings={"language": "nl", "window_days": 14},
    )

    await store.importer().apply(data, include_settings=False)

    assert store.template.slots == {ItemType.CARB: 1}
    assert store.settings.values == {"language": "auto"}


async def test_settings_and_template_applied_when_requested(store: Store) -> None:
    store.template.slots = {ItemType.CARB: 1, ItemType.PROTEIN: 0}
    store.settings.values = {"language": "auto"}
    data = minimal_document(
        template={"protein": 2, "vegetable": 1},
        settings={"language": "nl", "window_days": 14},
    )

    await store.importer().apply(data, include_settings=True)

    assert store.template.slots == {
        ItemType.CARB: 1,
        ItemType.PROTEIN: 2,
        ItemType.VEGETABLE: 1,
    }
    assert store.settings.values == {"language": "nl", "window_days": 14}


async def test_round_trip_export_then_import_into_empty_store(store: Store) -> None:
    kale = await store.add_item("Kale", ItemType.VEGETABLE)
    rice = await store.add_item("Rice", ItemType.CARB)
    await store.add_category("Greens", item_ids={kale.id}, minimum=3)
    await store.rules.save_rule(
        Rule(id=0, kind=RuleKind.BLACKLIST, scope=RuleScope.ITEM, item_id=rice.id)
    )
    await store.nutrition.save_nutrition(
        Nutrition(
            item_id=kale.id,
            source=NutritionSource.MANUAL,
            status=NutritionStatus.OK,
            kcal=49,
            protein_g=4.3,
            carbs_g=8.8,
            fat_g=0.9,
            fiber_g=3.6,
            user_confirmed=True,
        )
    )
    store.template.slots = {ItemType.PROTEIN: 1, ItemType.VEGETABLE: 2}
    store.settings.values = {"window_days": 14, "language": "en"}
    exported = await store.exporter().export()

    target = Store()
    await target.importer().apply(exported, include_settings=True)

    assert await target.exporter().export() == exported

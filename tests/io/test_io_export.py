from __future__ import annotations

from dataclasses import replace

from io_fakes import Store

from app.models import (
    ItemType,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    Rule,
    RuleKind,
    RuleScope,
)


async def test_export_has_all_sections_and_schema_version(store: Store) -> None:
    exported = await store.exporter().export()
    assert set(exported) == {
        "schema_version",
        "items",
        "categories",
        "rules",
        "template",
        "settings",
    }
    assert exported["schema_version"] == 1


async def test_export_items_are_sorted_by_name_case_insensitively(store: Store) -> None:
    await store.add_item("carrot")
    await store.add_item("Apple")
    await store.add_item("banana")
    exported = await store.exporter().export()
    assert [item["name"] for item in exported["items"]] == ["Apple", "banana", "carrot"]


async def test_export_item_fields(store: Store) -> None:
    item = await store.add_item("Rice", ItemType.CARB)
    item.portion_grams = 80.0
    item.fat_source = True
    await store.items.save_item(item)
    record = (await store.exporter().export())["items"][0]
    assert record == {
        "name": "Rice",
        "type": "carb",
        "portion_grams": 80.0,
        "fat_source": True,
        "track_stock": True,
        "is_complete_meal": False,
        "nutrition": None,
    }


async def test_export_preserves_complete_meal_flag(store: Store) -> None:
    item = await store.add_item("Lasagne", ItemType.CARB)
    await store.items.save_item(replace(item, is_complete_meal=True))
    record = (await store.exporter().export())["items"][0]
    assert record["is_complete_meal"] is True


async def test_export_includes_manual_nutrition(store: Store) -> None:
    item = await store.add_item("Kale", ItemType.VEGETABLE)
    await store.nutrition.save_nutrition(
        Nutrition(
            item_id=item.id,
            source=NutritionSource.MANUAL,
            status=NutritionStatus.OK,
            kcal=49.0,
            protein_g=4.3,
            carbs_g=8.8,
            fat_g=0.9,
            fiber_g=3.6,
            user_confirmed=True,
        )
    )
    nutrition = (await store.exporter().export())["items"][0]["nutrition"]
    assert nutrition == {
        "source": "manual",
        "external_id": None,
        "matched_name": None,
        "user_confirmed": True,
        "kcal": 49.0,
        "protein_g": 4.3,
        "carbs_g": 8.8,
        "fat_g": 0.9,
        "fiber_g": 3.6,
    }


async def test_unconfirmed_lookup_result_is_not_exported(store: Store) -> None:
    item = await store.add_item("Kale", ItemType.VEGETABLE)
    await store.nutrition.save_nutrition(
        Nutrition(
            item_id=item.id,
            source=NutritionSource.OPEN_FOOD_FACTS,
            status=NutritionStatus.OK,
            external_id="123",
            matched_name="Kale raw",
            kcal=49.0,
            protein_g=4.3,
            carbs_g=8.8,
            fat_g=0.9,
            fiber_g=3.6,
            user_confirmed=False,
        )
    )
    exported = await store.exporter().export()
    assert exported["items"][0]["nutrition"] is None


async def test_confirmed_lookup_result_is_exported(store: Store) -> None:
    item = await store.add_item("Kale", ItemType.VEGETABLE)
    await store.nutrition.save_nutrition(
        Nutrition(
            item_id=item.id,
            source=NutritionSource.USDA,
            status=NutritionStatus.OK,
            external_id="171",
            matched_name="Kale, raw",
            kcal=49.0,
            protein_g=4.3,
            carbs_g=8.8,
            fat_g=0.9,
            fiber_g=3.6,
            user_confirmed=True,
        )
    )
    nutrition = (await store.exporter().export())["items"][0]["nutrition"]
    assert nutrition is not None
    assert nutrition["source"] == "usda"
    assert nutrition["external_id"] == "171"
    assert nutrition["user_confirmed"] is True


async def test_export_categories_use_item_names(store: Store) -> None:
    kale = await store.add_item("Kale")
    beans = await store.add_item("Beans")
    await store.add_category("Greens", {kale.id}, minimum=3)
    await store.add_category("Legumes", {beans.id, kale.id})
    exported = (await store.exporter().export())["categories"]
    assert exported == [
        {"name": "Greens", "min_per_7_days": 3, "items": ["Kale"]},
        {"name": "Legumes", "min_per_7_days": None, "items": ["Beans", "Kale"]},
    ]


async def test_export_rules_resolve_names_and_drop_dangling_references(store: Store) -> None:
    kale = await store.add_item("Kale")
    greens = await store.add_category("Greens", {kale.id})
    await store.rules.save_rule(
        Rule(
            id=0,
            kind=RuleKind.BLACKLIST,
            scope=RuleScope.COMBINATION,
            category_ids=frozenset({greens.id}),
        )
    )
    await store.rules.save_rule(
        Rule(id=0, kind=RuleKind.WHITELIST, scope=RuleScope.ITEM, item_id=kale.id)
    )
    await store.rules.save_rule(
        Rule(id=0, kind=RuleKind.WHITELIST, scope=RuleScope.ITEM, item_id=999)
    )
    rules = (await store.exporter().export())["rules"]
    assert rules == [
        {
            "kind": "blacklist",
            "scope": "combination",
            "categories": ["Greens"],
            "item": None,
            "enabled": True,
        },
        {
            "kind": "whitelist",
            "scope": "item",
            "categories": [],
            "item": "Kale",
            "enabled": True,
        },
    ]


async def test_export_template_uses_item_type_values(store: Store) -> None:
    store.template.slots = {ItemType.PROTEIN: 2, ItemType.CARB: 1}
    template = (await store.exporter().export())["template"]
    assert template == {"protein": 2, "carb": 1}


async def test_export_settings_exclude_secrets_and_read_only_values(store: Store) -> None:
    store.settings.values = {
        "usda_api_key": "super-secret",
        "time_zone": "Europe/Amsterdam",
        "window_days": 14,
        "household_size": 4,
        "language": "nl",
    }
    settings = (await store.exporter().export())["settings"]
    assert settings == {"household_size": 4, "language": "nl", "window_days": 14}
    assert "usda_api_key" not in settings
    assert "super-secret" not in repr(settings)


async def test_export_contains_no_secret_anywhere(store: Store) -> None:
    store.settings.values = {"usda_api_key": "super-secret"}
    await store.add_item("Kale")
    exported = await store.exporter().export()
    assert "super-secret" not in repr(exported)

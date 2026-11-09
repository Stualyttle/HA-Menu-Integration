from __future__ import annotations

from typing import Any

import pytest

from app.io.schema import ImportValidationError, parse_document
from app.models import ItemType, NutritionSource


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


def _errors(data: object) -> list[str]:
    with pytest.raises(ImportValidationError) as exc:
        parse_document(data)
    return exc.value.errors


def test_minimal_document_parses() -> None:
    document = parse_document(minimal_document())
    assert document.items == ()
    assert document.has_settings is True


def test_non_object_document_is_rejected() -> None:
    assert _errors([1, 2]) == ["document: must be a JSON object"]


@pytest.mark.parametrize("version", [0, 2, "1", None, True])
def test_wrong_schema_version_is_rejected(version: object) -> None:
    data = minimal_document()
    data["schema_version"] = version
    assert any(error.startswith("schema_version") for error in _errors(data))


def test_unknown_top_level_field_is_rejected() -> None:
    errors = _errors(minimal_document(history=[]))
    assert "history: unknown field" in errors


def test_unknown_item_field_is_rejected_with_path() -> None:
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "colour": "green"}])
    assert "items[0].colour: unknown field" in _errors(data)


def test_unknown_nutrition_field_is_rejected_with_path() -> None:
    nutrition = {"source": "manual", "kcal": 1, "protein_g": 1, "carbs_g": 1, "fat_g": 1, "x": 1}
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "nutrition": nutrition}])
    assert "items[0].nutrition.x: unknown field" in _errors(data)


def test_item_type_must_be_known() -> None:
    data = minimal_document(items=[{"name": "Kale", "type": "dessert"}])
    assert "items[0].type: must be one of protein, vegetable, carb" in _errors(data)


def test_complete_meal_flag_is_backward_compatible_and_validated() -> None:
    old_item = parse_document(minimal_document(items=[{"name": "Old dish", "type": "carb"}])).items[
        0
    ]
    assert old_item.is_complete_meal is False

    meal = parse_document(
        minimal_document(items=[{"name": "Lasagne", "type": "carb", "is_complete_meal": True}])
    ).items[0]
    assert meal.is_complete_meal is True

    data = minimal_document(
        items=[{"name": "Lasagne", "type": "protein", "is_complete_meal": True}]
    )
    assert "items[0].type: complete meals must use the carb item type" in _errors(data)


def test_item_name_must_be_non_empty() -> None:
    data = minimal_document(items=[{"name": "   ", "type": "carb"}])
    assert "items[0].name: must be a non-empty string" in _errors(data)


def test_zero_portion_is_rejected() -> None:
    data = minimal_document(items=[{"name": "Rice", "type": "carb", "portion_grams": 0}])
    assert any("portion_grams" in e for e in _errors(data))


def test_negative_nutrition_value_is_rejected() -> None:
    nutrition = {"source": "manual", "kcal": -1, "protein_g": 1, "carbs_g": 1, "fat_g": 1}
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "nutrition": nutrition}])
    assert any(
        e.endswith("nutrition.kcal: must be a non-negative number or null") for e in _errors(data)
    )


def test_manual_nutrition_requires_core_values() -> None:
    nutrition = {"source": "manual", "kcal": 10}
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "nutrition": nutrition}])
    errors = _errors(data)
    assert "items[0].nutrition.protein_g: is required for manual or confirmed nutrition" in errors
    assert "items[0].nutrition.carbs_g: is required for manual or confirmed nutrition" in errors
    assert "items[0].nutrition.fat_g: is required for manual or confirmed nutrition" in errors


def test_nutrition_source_must_be_known() -> None:
    nutrition = {"source": "guess", "kcal": 10}
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "nutrition": nutrition}])
    assert any(
        e.endswith("nutrition.source: must be one of open_food_facts, usda, manual")
        for e in _errors(data)
    )


def test_open_food_facts_nutrition_without_confirmation_is_accepted() -> None:
    nutrition = {"source": "open_food_facts", "external_id": "123", "kcal": 10}
    data = minimal_document(items=[{"name": "Kale", "type": "vegetable", "nutrition": nutrition}])
    parsed = parse_document(data)
    assert parsed.items[0].nutrition is not None
    assert parsed.items[0].nutrition.source is NutritionSource.OPEN_FOOD_FACTS
    assert parsed.items[0].nutrition.user_confirmed is False


def test_duplicate_item_names_are_rejected_case_insensitively() -> None:
    data = minimal_document(
        items=[
            {"name": "Kale", "type": "vegetable"},
            {"name": "KALE", "type": "vegetable"},
        ]
    )
    assert any("duplicate name 'KALE'" in e for e in _errors(data))


def test_category_items_must_be_names() -> None:
    data = minimal_document(categories=[{"name": "Greens", "items": [1]}])
    assert "categories[0].items[0]: must be a non-empty string" in _errors(data)


def test_category_minimum_must_be_non_negative_integer() -> None:
    data = minimal_document(categories=[{"name": "Greens", "min_per_7_days": -1}])
    assert "categories[0].min_per_7_days: must be a non-negative integer or null" in _errors(data)


def test_combination_rule_needs_categories() -> None:
    data = minimal_document(rules=[{"kind": "blacklist", "scope": "combination"}])
    assert "rules[0].categories: must list at least one category when scope is combination" in (
        _errors(data)
    )


def test_item_rule_needs_item() -> None:
    data = minimal_document(rules=[{"kind": "whitelist", "scope": "item"}])
    assert "rules[0].item: is required when scope is item" in _errors(data)


def test_item_rule_rejects_categories() -> None:
    data = minimal_document(
        rules=[{"kind": "whitelist", "scope": "item", "item": "Kale", "categories": ["Greens"]}]
    )
    assert "rules[0].categories: must be empty when scope is item" in _errors(data)


def test_rule_kind_and_scope_must_be_known() -> None:
    data = minimal_document(
        rules=[{"kind": "greylist", "scope": "galaxy", "categories": ["Greens"]}]
    )
    errors = _errors(data)
    assert "rules[0].kind: must be blacklist or whitelist" in errors
    assert "rules[0].scope: must be combination or item" in errors


def test_template_values_are_bounded() -> None:
    data = minimal_document(template={"protein": 3, "carb": 1})
    assert "template.protein: must be an integer from 0 to 2" in _errors(data)


def test_template_unknown_key_is_rejected() -> None:
    data = minimal_document(template={"dessert": 1})
    assert "template.dessert: unknown field" in _errors(data)


def test_template_parses_to_item_types() -> None:
    parsed = parse_document(minimal_document(template={"protein": 1, "vegetable": 2}))
    assert parsed.template == {ItemType.PROTEIN: 1, ItemType.VEGETABLE: 2}


def test_usda_api_key_in_settings_is_rejected_as_secret() -> None:
    data = minimal_document(settings={"usda_api_key": "abc"})
    assert "settings.usda_api_key: secrets are never imported; remove this field" in _errors(data)


def test_time_zone_in_settings_is_read_only() -> None:
    data = minimal_document(settings={"time_zone": "Europe/Amsterdam"})
    assert "settings.time_zone: is read-only and cannot be imported" in _errors(data)


def test_unknown_setting_is_rejected() -> None:
    data = minimal_document(settings={"theme": "dark"})
    assert "settings.theme: unknown field" in _errors(data)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("window_days", 6),
        ("window_days", 61),
        ("household_size", 0),
        ("repeat_gap_days", -1),
        ("language", "fr"),
        ("balance_targets", {"vegetables": 101}),
        ("balance_targets", {"dessert": 5}),
    ],
)
def test_setting_values_are_validated(key: str, value: object) -> None:
    errors = _errors(minimal_document(settings={key: value}))
    assert any(error.startswith(f"settings.{key}") for error in errors)


def test_valid_settings_are_kept() -> None:
    settings = {
        "window_days": 14,
        "household_size": 4,
        "repeat_gap_days": 2,
        "language": "nl",
        "balance_targets": {"vegetables": 40, "protein": 30, "carbs": 30},
    }
    parsed = parse_document(minimal_document(settings=settings))
    assert parsed.settings == settings


def test_all_errors_are_collected_in_one_pass() -> None:
    data = minimal_document(
        history=[],
        items=[{"name": "", "type": "dessert"}],
        settings={"usda_api_key": "x"},
    )
    errors = _errors(data)
    assert len(errors) >= 4


def test_missing_optional_sections_are_allowed() -> None:
    parsed = parse_document({"schema_version": 1})
    assert parsed.items == ()
    assert parsed.template is None
    assert parsed.settings is None
    assert parsed.has_settings is False

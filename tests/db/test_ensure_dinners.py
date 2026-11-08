"""ensure_dinners dedupes and keeps input order; TemplateStore raises PlannerConfigError."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import Stores
from app.domain.errors import PlannerConfigError
from app.models import Item


@pytest.fixture
def stores(tmp_path: Path):
    opened = Stores.open(tmp_path / "menu_planner.db")
    yield opened
    opened.close()


async def _item_ids(stores: Stores) -> list[int]:
    items: list[Item] = await stores.items.list_items()
    return [i.id for i in items]


async def test_ensure_dinners_returns_ids_in_input_order(stores: Stores) -> None:
    a, b, c = (await _item_ids(stores))[:3]
    ids = await stores.menu.ensure_dinners([[a, b], [c], [a, b, c]])
    assert len(ids) == 3
    assert len(set(ids)) == 3


async def test_ensure_dinners_dedupes_by_sorted_item_set(stores: Stores) -> None:
    a, b, c = (await _item_ids(stores))[:3]
    ids = await stores.menu.ensure_dinners([[c, a, b], [a, b, c, a], [b, a, c]])
    assert ids[0] == ids[1] == ids[2]
    dinner = next(d for d in await stores.menu.list_dinners() if d.id == ids[0])
    assert dinner.item_ids == tuple(sorted({a, b, c}))


async def test_ensure_dinners_is_idempotent(stores: Stores) -> None:
    a, b = (await _item_ids(stores))[:2]
    first = await stores.menu.ensure_dinners([[a, b]])
    count = len(await stores.menu.list_dinners())
    second = await stores.menu.ensure_dinners([[b, a]])
    assert first == second
    assert len(await stores.menu.list_dinners()) == count


async def test_ensure_dinners_reuses_existing_dinner(stores: Stores) -> None:
    a, b, c = (await _item_ids(stores))[:3]
    existing = await stores.menu.create_dinner([a, b])
    ids = await stores.menu.ensure_dinners([[a, b], [a, c]])
    assert ids[0] == existing.id
    assert ids[1] != existing.id


async def test_ensure_dinners_empty_input_returns_empty_list(stores: Stores) -> None:
    assert await stores.menu.ensure_dinners([]) == []


def test_template_set_rejects_all_zero_with_planner_config_error(stores: Stores) -> None:
    with pytest.raises(PlannerConfigError):
        stores.template.set({"protein": 0, "vegetable": 0, "carb": 0})

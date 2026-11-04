"""Reference checks shared by routers: referenced items and categories must exist."""

from __future__ import annotations

from collections.abc import Iterable

from app.api.errors import ApiError
from app.db import Stores
from app.models import Category, Item


async def check_category_ids(stores: Stores, category_ids: Iterable[int]) -> None:
    known = {c.id for c in await stores.categories.list_categories()}
    missing = sorted(set(category_ids) - known)
    if missing:
        raise ApiError(400, "unknown_reference", "unknown category", {"category_ids": missing})


async def check_item_ids(stores: Stores, item_ids: Iterable[int]) -> None:
    known = {i.id for i in await stores.items.list_items()}
    missing = sorted(set(item_ids) - known)
    if missing:
        raise ApiError(400, "unknown_reference", "unknown item", {"item_ids": missing})


async def require_item(stores: Stores, item_id: int) -> Item:
    item = await stores.items.get_item(item_id)
    if item is None:
        raise ApiError(404, "not_found", f"item {item_id} not found")
    return item


async def require_category(stores: Stores, category_id: int) -> Category:
    for category in await stores.categories.list_categories():
        if category.id == category_id:
            return category
    raise ApiError(404, "not_found", f"category {category_id} not found")

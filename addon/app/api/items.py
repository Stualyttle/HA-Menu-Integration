"""Items: list, create, read, update, delete (docs/API.md "Items, categories, rules")."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import StoresDep
from app.api.lookups import check_category_ids, require_item
from app.api.schemas import ItemIn, ItemOut
from app.db import Stores
from app.models import Item, ItemType, NutritionStatus

router = APIRouter(prefix="/api/items", tags=["items"])


async def _category_map(stores: Stores) -> dict[int, set[int]]:
    """Item id to the set of category ids it belongs to."""
    membership: dict[int, set[int]] = {}
    for category in await stores.categories.list_categories():
        for item_id in category.item_ids:
            membership.setdefault(item_id, set()).add(category.id)
    return membership


async def _sync_categories(stores: Stores, item_id: int, category_ids: set[int]) -> None:
    """Make the item's membership match ``category_ids`` by saving only changed categories."""
    for category in await stores.categories.list_categories():
        wanted = category.id in category_ids
        present = item_id in category.item_ids
        if wanted == present:
            continue
        if wanted:
            category.item_ids.add(item_id)
        else:
            category.item_ids.discard(item_id)
        await stores.categories.save_category(category)


async def _to_out(stores: Stores, item: Item, membership: dict[int, set[int]]) -> ItemOut:
    nutrition = await stores.nutrition.get_nutrition(item.id)
    return ItemOut.from_model(item, sorted(membership.get(item.id, set())), nutrition)


def _is_verified(out: ItemOut) -> bool:
    return out.nutrition is not None and out.nutrition.status == NutritionStatus.OK.value


@router.get("", response_model=list[ItemOut])
async def list_items(
    stores: StoresDep,
    type: ItemType | None = None,
    category_id: int | None = None,
    verified: bool | None = None,
    track_stock: bool | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> list[ItemOut]:
    membership = await _category_map(stores)
    needle = q.strip().casefold() if q else None
    result: list[ItemOut] = []
    for item in await stores.items.list_items():
        if type is not None and item.type != type:
            continue
        if category_id is not None and category_id not in membership.get(item.id, set()):
            continue
        if track_stock is not None and item.track_stock != track_stock:
            continue
        if needle and needle not in item.name.casefold():
            continue
        out = await _to_out(stores, item, membership)
        if verified is not None and _is_verified(out) != verified:
            continue
        result.append(out)
    return result


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemIn, stores: StoresDep) -> ItemOut:
    category_ids = set(body.category_ids)
    await check_category_ids(stores, category_ids)
    saved = await stores.items.save_item(
        Item(
            id=0,
            name=body.name,
            type=body.type,
            portion_grams=body.portion_grams,
            fat_source=body.fat_source,
            track_stock=body.track_stock,
            is_complete_meal=body.is_complete_meal,
        )
    )
    await _sync_categories(stores, saved.id, category_ids)
    return await _to_out(stores, saved, await _category_map(stores))


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: int, stores: StoresDep) -> ItemOut:
    item = await require_item(stores, item_id)
    return await _to_out(stores, item, await _category_map(stores))


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(item_id: int, body: ItemIn, stores: StoresDep) -> ItemOut:
    await require_item(stores, item_id)
    category_ids = set(body.category_ids)
    await check_category_ids(stores, category_ids)
    saved = await stores.items.save_item(
        Item(
            id=item_id,
            name=body.name,
            type=body.type,
            portion_grams=body.portion_grams,
            fat_source=body.fat_source,
            track_stock=body.track_stock,
            is_complete_meal=body.is_complete_meal,
        )
    )
    await _sync_categories(stores, item_id, category_ids)
    return await _to_out(stores, saved, await _category_map(stores))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_item(item_id: int, stores: StoresDep) -> Response:
    await require_item(stores, item_id)
    await stores.items.delete_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

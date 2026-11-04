"""Categories: list, create, read, update, delete (docs/API.md "Items, categories, rules")."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import StoresDep
from app.api.lookups import check_item_ids, require_category
from app.api.schemas import CategoryIn, CategoryOut
from app.db import Stores
from app.models import Category

router = APIRouter(prefix="/api/categories", tags=["categories"])


async def _save(stores: Stores, category: Category, body: CategoryIn) -> CategoryOut:
    item_ids = set(body.item_ids)
    await check_item_ids(stores, item_ids)
    saved = await stores.categories.save_category(
        Category(
            id=category.id,
            name=body.name,
            is_starter=category.is_starter,
            min_per_7_days=body.min_per_7_days,
            item_ids=item_ids,
        )
    )
    return CategoryOut.from_model(saved)


@router.get("", response_model=list[CategoryOut])
async def list_categories(stores: StoresDep) -> list[CategoryOut]:
    return [CategoryOut.from_model(c) for c in await stores.categories.list_categories()]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(body: CategoryIn, stores: StoresDep) -> CategoryOut:
    new = Category(id=0, name=body.name, is_starter=False, min_per_7_days=None, item_ids=set())
    return await _save(stores, new, body)


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(category_id: int, stores: StoresDep) -> CategoryOut:
    return CategoryOut.from_model(await require_category(stores, category_id))


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(category_id: int, body: CategoryIn, stores: StoresDep) -> CategoryOut:
    current = await require_category(stores, category_id)
    return await _save(stores, current, body)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_category(category_id: int, stores: StoresDep) -> Response:
    await require_category(stores, category_id)
    await stores.categories.delete_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

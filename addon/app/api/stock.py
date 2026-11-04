"""Stock: per-item in-stock answers and the replacement preview (docs/API.md "Stock")."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StoresDep, planning_window
from app.api.lookups import require_item
from app.api.schemas import (
    StockAnswerIn,
    StockChangeOut,
    StockOut,
    StockPreviewIn,
    StockPreviewOut,
)
from app.db import Stores
from app.models import Item

router = APIRouter(prefix="/api/stock", tags=["stock"])


def _replaces(stores: Stores, item: Item) -> int:
    start, end = planning_window(stores)
    return stores.stock.replaces_count(item.id, start, end)


@router.get("", response_model=list[StockOut])
async def list_stock(stores: StoresDep, unanswered_first: bool = True) -> list[StockOut]:
    answers = stores.stock.answers()
    items = [i for i in await stores.items.list_items() if i.track_stock]
    rows = [
        StockOut(
            item_id=i.id,
            name=i.name,
            type=i.type,
            in_stock=answers.get(i.id),
            replaces_count=_replaces(stores, i),
        )
        for i in items
    ]
    if unanswered_first:
        rows.sort(key=lambda r: r.in_stock is not None)
    return rows


@router.put("/{item_id}", response_model=StockChangeOut)
async def set_stock(item_id: int, body: StockAnswerIn, stores: StoresDep) -> StockChangeOut:
    await require_item(stores, item_id)
    stores.stock.set_answer(item_id, body.in_stock)
    # Replaced/restored days and shopping changes are applied by the stock service (agent B).
    return StockChangeOut(
        item_id=item_id,
        in_stock=body.in_stock,
        replaced_dates=[],
        restored_dates=[],
        shopping=[],
    )


@router.post("/{item_id}/preview", response_model=StockPreviewOut)
async def preview_stock(item_id: int, body: StockPreviewIn, stores: StoresDep) -> StockPreviewOut:
    item = await require_item(stores, item_id)
    return StockPreviewOut(
        item_id=item_id, in_stock=body.in_stock, replaces_count=_replaces(stores, item)
    )

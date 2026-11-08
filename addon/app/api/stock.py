"""Stock: per-item in-stock answers and the replacement preview (docs/API.md "Stock")."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StoresDep, planning_window
from app.api.lookups import require_item
from app.api.planning import build_context, build_planner, now_utc
from app.api.schemas import (
    StockAnswerIn,
    StockChangeOut,
    StockOut,
    StockPreviewIn,
    StockPreviewOut,
)
from app.db import Stores
from app.domain.engine import STOCK_REASON
from app.domain.snapshot import PlanSnapshot
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


def _stock_diff(before: PlanSnapshot, after: PlanSnapshot) -> tuple[list[str], list[str]]:
    """Days newly replaced by stock and days whose stock replacement was undone."""
    replaced: list[str] = []
    restored: list[str] = []
    for day in sorted(set(before.days) | set(after.days)):
        old = before.days.get(day)
        new = after.days.get(day)
        old_reason = old.replaced_reason if old else None
        new_reason = new.replaced_reason if new else None
        if new_reason == STOCK_REASON and new_reason != old_reason:
            replaced.append(day.isoformat())
        elif old_reason == STOCK_REASON and new_reason != STOCK_REASON:
            restored.append(day.isoformat())
    return replaced, restored


@router.put("/{item_id}", response_model=StockChangeOut)
async def set_stock(item_id: int, body: StockAnswerIn, stores: StoresDep) -> StockChangeOut:
    await require_item(stores, item_id)
    planner = build_planner(stores)
    ctx = build_context(stores)
    before = await planner.load(ctx)
    stores.stock.set_answer(item_id, body.in_stock)
    new_ctx = await planner.set_stock(ctx, item_id, body.in_stock is False, now_utc())
    after = await planner.load(new_ctx)
    replaced, restored = _stock_diff(before, after)
    return StockChangeOut(
        item_id=item_id,
        in_stock=body.in_stock,
        replaced_dates=replaced,
        restored_dates=restored,
        shopping=[],
    )


@router.post("/{item_id}/preview", response_model=StockPreviewOut)
async def preview_stock(item_id: int, body: StockPreviewIn, stores: StoresDep) -> StockPreviewOut:
    item = await require_item(stores, item_id)
    return StockPreviewOut(
        item_id=item_id, in_stock=body.in_stock, replaces_count=_replaces(stores, item)
    )

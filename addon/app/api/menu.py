"""Menu: the planned days, pin/unpin, eaten, swaps and replanning (docs/API.md "Menu")."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import StoresDep, local_today
from app.api.errors import ApiError
from app.api.planning import build_context, build_planner, build_settings, now_utc
from app.api.schemas import DinnerItemOut, DinnerOut, MenuDayOut, MenuUpdateIn, SwapIn
from app.db import Stores
from app.domain.errors import DayNotEditableError
from app.domain.service import MenuPlanner
from app.models import (
    DayStatus,
    Dinner,
    Item,
    ItemType,
    MenuDay,
    Nutrition,
    NutritionStatus,
    WarningSubject,
)

router = APIRouter(prefix="/api/menu", tags=["menu"])

MAX_RANGE_DAYS = 400


class _Lookups:
    """Items, dinners, nutrition and open day warnings, loaded once per request."""

    def __init__(
        self,
        items: dict[int, Item],
        dinners: dict[int, Dinner],
        nutrition: dict[int, Nutrition],
        warnings: dict[str, list[str]],
        targets: dict[ItemType, float],
        tolerance: float,
    ) -> None:
        self.items = items
        self.dinners = dinners
        self.nutrition = nutrition
        self.warnings = warnings
        self.targets = targets
        self.tolerance = tolerance


async def _lookups(stores: Stores) -> _Lookups:
    items = {item.id: item for item in await stores.items.list_items()}
    dinners = {dinner.id: dinner for dinner in await stores.menu.list_dinners()}
    nutrition: dict[int, Nutrition] = {}
    for item_id in items:
        record = await stores.nutrition.get_nutrition(item_id)
        if record is not None:
            nutrition[item_id] = record
    warnings: dict[str, list[str]] = defaultdict(list)
    for record in await stores.warnings.list_open():
        if record.subject_type == WarningSubject.DATE:
            warnings[record.subject].append(str(record.code))
    settings = build_settings(stores)
    return _Lookups(
        items=items,
        dinners=dinners,
        nutrition=nutrition,
        warnings=dict(warnings),
        targets=settings.balance_targets,
        tolerance=settings.balance_tolerance,
    )


def _dinner_out(dinner: Dinner, lookups: _Lookups) -> DinnerOut:
    items = [
        DinnerItemOut(id=item.id, name=item.name, type=item.type)
        for item_id in dinner.item_ids
        if (item := lookups.items.get(item_id)) is not None
    ]
    return DinnerOut(id=dinner.id, items=items)


def _kcal(dinner: Dinner, lookups: _Lookups) -> float | None:
    """Energy of one dinner from per-100 g nutrition; None when any item is unverified."""
    total = 0.0
    for item_id in dinner.item_ids:
        item = lookups.items.get(item_id)
        record = lookups.nutrition.get(item_id)
        if (
            item is None
            or item.portion_grams is None
            or record is None
            or record.status != NutritionStatus.OK
            or record.kcal is None
        ):
            return None
        total += record.kcal * item.portion_grams / 100.0
    return round(total, 1)


def _balance(dinner: Dinner, lookups: _Lookups) -> Literal["ok", "off_target", "unknown"]:
    """Compare the dinner's gram shares per type with the balance targets."""
    grams: dict[ItemType, float] = defaultdict(float)
    for item_id in dinner.item_ids:
        item = lookups.items.get(item_id)
        if item is None or item.portion_grams is None:
            return "unknown"
        grams[item.type] += item.portion_grams
    total = sum(grams.values())
    if total <= 0:
        return "unknown"
    excess = 0.0
    for item_type, target in lookups.targets.items():
        share = grams.get(item_type, 0.0) / total * 100.0
        excess += max(0.0, abs(share - target) - lookups.tolerance)
    return "ok" if round(excess, 6) == 0 else "off_target"


def _day_out(day: MenuDay, lookups: _Lookups) -> MenuDayOut:
    key = day.day.isoformat()
    dinner = lookups.dinners.get(day.dinner_id) if day.dinner_id is not None else None
    return MenuDayOut(
        date=key,
        status=day.status,
        dinner=_dinner_out(dinner, lookups) if dinner is not None else None,
        kcal=_kcal(dinner, lookups) if dinner is not None else None,
        balance=_balance(dinner, lookups) if dinner is not None else "unknown",
        replaced_reason=day.replaced_reason,
        warnings=list(lookups.warnings.get(key, [])),
    )


async def _days_out(stores: Stores, start: date, end: date) -> list[MenuDayOut]:
    """One entry per date in [start, end]; dates without a stored day are `empty`."""
    stored = {day.day: day for day in await stores.menu.get_days(start, end)}
    lookups = await _lookups(stores)
    out: list[MenuDayOut] = []
    current = start
    while current <= end:
        day = stored.get(current) or MenuDay(day=current, dinner_id=None, status=DayStatus.EMPTY)
        out.append(_day_out(day, lookups))
        current += timedelta(days=1)
    return out


async def _refresh(stores: Stores, now: datetime) -> MenuPlanner:
    """Roll the window forward (past days drop out, new days fill) before reading."""
    planner = build_planner(stores)
    await planner.roll_forward(build_context(stores), now)
    return planner


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ApiError(400, "validation_error", f"invalid date: {text}") from exc


def _require_future_in_window(stores: Stores, day: date) -> None:
    """Only future days inside the planning window can be edited (docs/API.md "Menu")."""
    today = local_today()
    window_days = build_settings(stores).window_days
    if not today < day <= today + timedelta(days=window_days - 1):
        raise DayNotEditableError(f"{day.isoformat()} cannot be edited")


async def _require_dinner_exists(stores: Stores, dinner_id: int) -> None:
    if not any(dinner.id == dinner_id for dinner in await stores.menu.list_dinners()):
        raise ApiError(400, "unknown_reference", f"unknown dinner: {dinner_id}")


async def _stored_day(stores: Stores, day: date) -> MenuDay:
    found = await stores.menu.get_days(day, day)
    return found[0] if found else MenuDay(day=day, dinner_id=None, status=DayStatus.EMPTY)


async def _swap(stores: Stores, day: date, dinner_id: int, now: datetime) -> None:
    await _require_dinner_exists(stores, dinner_id)
    _require_future_in_window(stores, day)
    planner = build_planner(stores)
    await planner.swap(build_context(stores), day, dinner_id, now)


@router.get("", response_model=list[MenuDayOut])
async def list_menu(
    stores: StoresDep,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> list[MenuDayOut]:
    start, end = _window(stores, from_, to)
    await _refresh(stores, now_utc())
    return await _days_out(stores, start, end)


def _window(stores: Stores, from_: date | None, to: date | None) -> tuple[date, date]:
    start = from_ or local_today()
    end = to or (start + timedelta(days=build_settings(stores).window_days - 1))
    if end < start:
        raise ApiError(400, "validation_error", "'to' must not be before 'from'")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ApiError(400, "validation_error", f"range must be at most {MAX_RANGE_DAYS} days")
    return start, end


@router.get("/today", response_model=MenuDayOut)
async def today_menu(stores: StoresDep) -> MenuDayOut:
    today = local_today()
    await _refresh(stores, now_utc())
    return (await _days_out(stores, today, today))[0]


@router.post("/replan", response_model=list[MenuDayOut])
async def replan(stores: StoresDep) -> list[MenuDayOut]:
    planner = build_planner(stores)
    await planner.replan(build_context(stores), now_utc())
    start, end = _window(stores, None, None)
    return await _days_out(stores, start, end)


@router.get("/{day_text}/swap", response_model=list[DinnerOut])
async def swap_suggestions(day_text: str, stores: StoresDep) -> list[DinnerOut]:
    day = _parse_date(day_text)
    _require_future_in_window(stores, day)
    planner = build_planner(stores)
    suggestions = await planner.suggest_swaps(build_context(stores), day)
    lookups = await _lookups(stores)
    return [_dinner_out(dinner, lookups) for dinner in suggestions]


@router.post("/{day_text}/swap", response_model=MenuDayOut)
async def swap_day(day_text: str, body: SwapIn, stores: StoresDep) -> MenuDayOut:
    day = _parse_date(day_text)
    await _swap(stores, day, body.dinner_id, now_utc())
    return (await _days_out(stores, day, day))[0]


@router.put("/{day_text}", response_model=MenuDayOut)
async def update_day(day_text: str, body: MenuUpdateIn, stores: StoresDep) -> MenuDayOut:
    day = _parse_date(day_text)
    if (body.pinned is None) == (body.dinner_id is None):
        raise ApiError(400, "validation_error", "send exactly one of 'pinned' or 'dinner_id'")
    now = now_utc()
    if body.dinner_id is not None:
        await _swap(stores, day, body.dinner_id, now)
        return (await _days_out(stores, day, day))[0]

    _require_future_in_window(stores, day)
    stored = await _stored_day(stores, day)
    if stored.status == DayStatus.EATEN:
        raise DayNotEditableError(f"{day.isoformat()} is already eaten")
    if body.pinned:
        if stored.dinner_id is None:
            raise ApiError(409, "conflict", f"{day.isoformat()} has no dinner to pin")
        status = DayStatus.PINNED
    else:
        status = DayStatus.PLANNED if stored.status == DayStatus.PINNED else stored.status
    if status != stored.status:
        await stores.menu.save_days(
            [MenuDay(day=day, dinner_id=stored.dinner_id, status=status, updated_at=now)]
        )
    return (await _days_out(stores, day, day))[0]


@router.post("/{day_text}/eaten", response_model=MenuDayOut)
async def mark_eaten(day_text: str, stores: StoresDep) -> MenuDayOut:
    """Marks the dinner as eaten. Stock is never changed here."""
    day = _parse_date(day_text)
    if day > local_today():
        raise DayNotEditableError(f"{day.isoformat()} is in the future")
    stored = await _stored_day(stores, day)
    if stored.dinner_id is None:
        raise ApiError(409, "conflict", f"{day.isoformat()} has no dinner")
    if stored.status != DayStatus.EATEN:
        await stores.menu.save_days(
            [
                MenuDay(
                    day=day,
                    dinner_id=stored.dinner_id,
                    status=DayStatus.EATEN,
                    replaced_reason=stored.replaced_reason,
                    updated_at=now_utc(),
                )
            ]
        )
    return (await _days_out(stores, day, day))[0]

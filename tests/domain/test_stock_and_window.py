from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.config import PlanContext, Template
from app.domain.engine import STOCK_REASON, apply_stock_change, replan_all, roll_forward
from app.domain.errors import PlannerConfigError
from app.models import DayStatus, ItemType, MenuDay, WarningCode
from tests.domain.fakes import (
    CHICKEN,
    TODAY,
    apply_result,
    make_ctx,
    plan_window,
    snapshot_of,
    standard_household,
    window_dates,
    window_status,
)


def _window_ids(store, ctx: PlanContext) -> dict:
    ids = {}
    for day in window_dates(ctx):
        record = store.days.get(day)
        ids[day] = record.dinner_id if record is not None else None
    return ids


def _uses(store, dinner_id: int | None, item_id: int) -> bool:
    if dinner_id is None:
        return False
    dinner = store.dinners[dinner_id]
    return item_id in dinner.item_ids


def test_stock_no_replaces_only_days_using_the_item():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    before = _window_ids(store, ctx)

    new_ctx, result = apply_stock_change(snapshot_of(store), ctx, CHICKEN, out=True)
    apply_result(store, result)
    after = _window_ids(store, ctx)

    assert CHICKEN in new_ctx.out_of_stock
    for day, old_id in before.items():
        if _uses(store, old_id, CHICKEN):
            assert after[day] != old_id
            assert not _uses(store, after[day], CHICKEN)
        else:
            assert after[day] == old_id


def test_stock_no_marks_replaced_days_with_stock_reason_and_warnings():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)

    _, result = apply_stock_change(snapshot_of(store), ctx, CHICKEN, out=True)

    assert result.updated, "stock 'no' should replace at least one dinner"
    for record in result.updated.values():
        assert record.replaced_reason == STOCK_REASON
        assert record.dinner_id is not None
    replaced = [w for w in result.warnings if w.code == WarningCode.REPLACED_DINNER]
    assert len(replaced) == len(result.updated)


def test_stock_yes_replans_only_days_replaced_by_no():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)

    ctx_out, out_result = apply_stock_change(snapshot_of(store), ctx, CHICKEN, out=True)
    apply_result(store, out_result)
    replaced_days = set(out_result.updated)
    before = _window_ids(store, ctx)

    _, back_result = apply_stock_change(snapshot_of(store), ctx_out, CHICKEN, out=False)
    apply_result(store, back_result)
    after = _window_ids(store, ctx)

    assert set(back_result.updated) <= replaced_days
    for day in window_dates(ctx):
        if day not in replaced_days:
            assert after[day] == before[day]


def test_stock_yes_without_prior_no_changes_nothing():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    before = _window_ids(store, ctx)

    _, result = apply_stock_change(snapshot_of(store), ctx, CHICKEN, out=False)
    apply_result(store, result)

    assert result.updated == {}
    assert _window_ids(store, ctx) == before


def test_pinned_day_survives_stock_no():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    pinned_day = TODAY + timedelta(days=3)
    pinned_id = store.days[pinned_day].dinner_id
    store.days[pinned_day] = MenuDay(pinned_day, pinned_id, DayStatus.PINNED)

    _, result = apply_stock_change(snapshot_of(store), ctx, CHICKEN, out=True)
    apply_result(store, result)

    assert pinned_day not in result.updated
    assert store.days[pinned_day].dinner_id == pinned_id
    assert store.days[pinned_day].status == DayStatus.PINNED


def test_eaten_day_is_never_replanned():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    eaten_id = store.days[TODAY].dinner_id
    store.days[TODAY] = MenuDay(TODAY, eaten_id, DayStatus.EATEN)

    result = replan_all(snapshot_of(store), ctx, reason="rule")
    apply_result(store, result)

    assert TODAY not in result.updated
    assert store.days[TODAY].dinner_id == eaten_id
    assert store.days[TODAY].status == DayStatus.EATEN


def test_roll_forward_fills_new_last_day_and_keeps_earlier_dinners():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    before = _window_ids(store, ctx)

    next_ctx = make_ctx(today=TODAY + timedelta(days=1), window_days=14)
    result = roll_forward(snapshot_of(store), next_ctx)
    apply_result(store, result)

    new_last = TODAY + timedelta(days=14)
    assert list(result.updated) == [new_last]
    assert store.days[new_last].status == DayStatus.PLANNED
    after = _window_ids(store, next_ctx)
    for day in window_dates(next_ctx):
        if day != new_last:
            assert after[day] == before[day]


def test_empty_days_are_filled_by_roll_forward_when_a_dinner_becomes_valid():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    empty_day = TODAY + timedelta(days=5)
    store.days[empty_day] = MenuDay(empty_day, None, DayStatus.EMPTY)

    result = roll_forward(snapshot_of(store), ctx)
    apply_result(store, result)

    assert empty_day in result.updated
    assert store.days[empty_day].dinner_id is not None


@pytest.mark.parametrize("window_days", [7, 60])
def test_window_bounds_accept_minimum_and_maximum(window_days):
    store = standard_household()
    ctx = make_ctx(window_days=window_days)
    plan_window(store, ctx)

    assert len(window_dates(ctx)) == window_days
    assert set(window_status(store, ctx).values()) == {DayStatus.PLANNED}


@pytest.mark.parametrize("window_days", [6, 61])
def test_window_bounds_reject_out_of_range(window_days):
    with pytest.raises(PlannerConfigError):
        make_ctx(window_days=window_days)


def test_all_zero_template_is_rejected():
    with pytest.raises(PlannerConfigError):
        Template(slots={ItemType.PROTEIN: 0, ItemType.VEGETABLE: 0, ItemType.CARB: 0})


def test_window_default_is_fourteen_days():
    store = standard_household()
    ctx = make_ctx()
    plan_window(store, ctx)

    assert len(window_dates(ctx)) == 14

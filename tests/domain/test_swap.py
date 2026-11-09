from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.engine import apply_swap, suggest_swaps
from app.domain.errors import DayNotEditableError, SwapRejectedError
from app.domain.rules import RuleIndex, hard_violation
from app.models import DayStatus, MenuDay
from tests.domain.fakes import (
    BEEF,
    CHICKEN,
    TODAY,
    apply_result,
    blacklist_item,
    make_ctx,
    plan_window,
    snapshot_of,
    standard_household,
    window_dates,
)


def test_suggestions_are_at_most_three_and_all_satisfy_hard_rules():
    store = standard_household()
    store.rules[1] = blacklist_item(1, BEEF)
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    day = TODAY + timedelta(days=2)

    snapshot = snapshot_of(store)
    suggestions = suggest_swaps(snapshot, ctx, day)

    assert 1 <= len(suggestions) <= 3
    rules = RuleIndex.build(snapshot.rules)
    for dinner in suggestions:
        assert hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, dinner) is None


def test_suggestions_exclude_the_current_dinner():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    day = TODAY + timedelta(days=2)
    current = store.days[day].dinner_id

    suggestions = suggest_swaps(snapshot_of(store), ctx, day)

    assert current not in [dinner.id for dinner in suggestions]


def test_suggestions_respect_stock_out_items():
    store = standard_household()
    ctx = make_ctx(window_days=14, out_of_stock={CHICKEN})
    plan_window(store, ctx)
    day = TODAY + timedelta(days=2)

    suggestions = suggest_swaps(snapshot_of(store), ctx, day)

    assert suggestions
    assert all(CHICKEN not in d.item_ids for d in suggestions)


def test_apply_swap_pins_the_day_and_keeps_other_days_fillable():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    day = TODAY + timedelta(days=2)
    target = suggest_swaps(snapshot_of(store), ctx, day)[0]

    result = apply_swap(snapshot_of(store), ctx, day, target.id)
    apply_result(store, result)

    assert store.days[day].dinner_id == target.id
    assert store.days[day].status == DayStatus.PINNED
    assert set(result.updated) <= set(window_dates(ctx))
    assert all(store.days[d].status == DayStatus.PLANNED for d in window_dates(ctx) if d != day)


def test_apply_swap_rejects_dinner_that_breaks_a_blacklist():
    store = standard_household()
    store.rules[1] = blacklist_item(1, CHICKEN)
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    day = TODAY + timedelta(days=2)
    chicken_dinner = next(d for d in store.dinners.values() if CHICKEN in d.item_ids)

    with pytest.raises(SwapRejectedError) as excinfo:
        apply_swap(snapshot_of(store), ctx, day, chicken_dinner.id)

    assert excinfo.value.reason == "blacklisted_item"


def test_apply_swap_rejects_unknown_dinner():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)

    with pytest.raises(SwapRejectedError) as excinfo:
        apply_swap(snapshot_of(store), ctx, TODAY, 9999)

    assert excinfo.value.reason == "unknown_dinner"


def test_eaten_day_cannot_be_swapped():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    eaten = store.days[TODAY].dinner_id
    store.days[TODAY] = MenuDay(TODAY, eaten, DayStatus.EATEN)
    other = next(d.id for d in store.dinners.values() if d.id != eaten)

    with pytest.raises(DayNotEditableError):
        apply_swap(snapshot_of(store), ctx, TODAY, other)
    with pytest.raises(DayNotEditableError):
        suggest_swaps(snapshot_of(store), ctx, TODAY)


def test_day_outside_window_cannot_be_swapped():
    store = standard_household()
    ctx = make_ctx(window_days=14)
    plan_window(store, ctx)
    outside = TODAY + timedelta(days=30)
    store.days[outside] = MenuDay(outside, store.days[TODAY].dinner_id, DayStatus.PLANNED)

    with pytest.raises(DayNotEditableError):
        apply_swap(snapshot_of(store), ctx, outside, store.days[TODAY].dinner_id)

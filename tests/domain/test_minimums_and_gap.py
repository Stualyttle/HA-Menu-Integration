"""Soft penalties: category minimums and repeat gap."""

from __future__ import annotations

from datetime import timedelta

from app.models import DayStatus, MenuDay, WarningCode
from tests.domain.fakes import (
    CHICKEN,
    MEAT,
    TODAY,
    TOFU,
    VEGETARIAN,
    dinner_of,
    make_ctx,
    plan_window,
    standard_household,
    window_dinners,
    window_status,
)


def _codes(result, code):
    return [w for w in result.warnings if w.code == code]


def _set_minimum(store, category_id: int, n: int) -> None:
    store.categories[category_id].min_per_7_days = n


def test_achievable_minimum_is_met_without_warning():
    store = standard_household()
    _set_minimum(store, VEGETARIAN, 2)
    ctx = make_ctx(window_days=14, repeat_gap_days=14)

    result = plan_window(store, ctx)

    assert not _codes(result, WarningCode.MISSED_MINIMUM)
    dinners = window_dinners(store, ctx)
    for end in range(6, 14):
        span = [TODAY + timedelta(days=k) for k in range(end - 6, end + 1)]
        count = sum(1 for day in span if dinners[day] is not None and TOFU in dinners[day].item_ids)
        assert count >= 2


def test_minimum_is_counted_over_rolling_seven_days():
    store = standard_household()
    _set_minimum(store, VEGETARIAN, 2)
    ctx = make_ctx(window_days=14, repeat_gap_days=14)

    result = plan_window(store, ctx)

    dinners = window_dinners(store, ctx)
    missed_ends = set()
    for end in range(6, 14):
        span = [TODAY + timedelta(days=k) for k in range(end - 6, end + 1)]
        count = sum(1 for day in span if dinners[day] is not None and TOFU in dinners[day].item_ids)
        if count < 2:
            missed_ends.add((TODAY + timedelta(days=end)).isoformat())
    warned = {
        end for w in _codes(result, WarningCode.MISSED_MINIMUM) for end in w.payload["span_ends"]
    }
    assert warned == missed_ends


def test_unreachable_minimum_emits_missed_minimum_for_category():
    store = standard_household()
    _set_minimum(store, VEGETARIAN, 1)
    ctx = make_ctx(window_days=7, repeat_gap_days=14, out_of_stock={TOFU})

    result = plan_window(store, ctx)

    misses = _codes(result, WarningCode.MISSED_MINIMUM)
    assert misses
    assert all(w.subject == str(VEGETARIAN) for w in misses)
    assert all(w.payload["required"] == 1 for w in misses)


def test_minimum_does_not_override_hard_rules():
    store = standard_household()
    _set_minimum(store, MEAT, 7)
    ctx = make_ctx(window_days=7, repeat_gap_days=14, out_of_stock={CHICKEN})

    plan_window(store, ctx)

    for dinner in window_dinners(store, ctx).values():
        if dinner is not None:
            assert CHICKEN not in dinner.item_ids


def test_repeat_gap_spreads_items_when_possible():
    store = standard_household()
    ctx = make_ctx(window_days=7, repeat_gap_days=3)

    plan_window(store, ctx)

    dinners = window_dinners(store, ctx)
    days = sorted(dinners)
    for i, day in enumerate(days):
        for other in days[i + 1 : i + 3]:
            a, b = dinners[day], dinners[other]
            assert a is not None and b is not None
            shared = set(a.item_ids) & set(b.item_ids)
            assert not shared, f"{day} and {other} share {shared}"


def test_unavoidable_repeat_gap_is_reported_and_days_still_filled():
    store = standard_household()
    ctx = make_ctx(window_days=14, repeat_gap_days=14)

    result = plan_window(store, ctx)

    assert _codes(result, WarningCode.REPEAT_GAP_UNAVOIDABLE)
    assert all(dinner is not None for dinner in window_dinners(store, ctx).values())


def test_pinned_day_is_kept_during_minimum_fill():
    store = standard_household()
    pinned_day = TODAY + timedelta(days=2)
    _set_minimum(store, VEGETARIAN, 3)
    store.days[pinned_day] = MenuDay(
        day=pinned_day,
        dinner_id=next(d.id for d in store.dinners.values() if CHICKEN in d.item_ids),
        status=DayStatus.PINNED,
    )
    before = dinner_of(store, pinned_day)
    ctx = make_ctx(window_days=7, repeat_gap_days=14)

    plan_window(store, ctx)

    assert dinner_of(store, pinned_day) == before
    assert window_status(store, ctx)[pinned_day] == DayStatus.PINNED

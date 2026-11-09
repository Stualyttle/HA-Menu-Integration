from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from tests.domain.fakes import (
    BEEF,
    CHICKEN,
    MEAT,
    NOW,
    TODAY,
    TOFU,
    VEGETARIAN,
    blacklist_item,
    dinner_of,
    make_ctx,
    make_planner,
    plan_window,
    snapshot_of,
    standard_household,
    window_dates,
)

from app.domain.engine import valid_pool
from app.domain.feasibility import search_minimums
from app.domain.rules import RuleIndex
from app.models import DayStatus, WarningCode


def _pool_for(store, ctx):
    snapshot = snapshot_of(store)
    return snapshot, valid_pool(snapshot, ctx, RuleIndex.build(snapshot.rules))


def test_search_feasible_when_every_minimum_fits_the_span():
    store = standard_household()
    snapshot, pool = _pool_for(store, make_ctx())

    result = search_minimums(snapshot, pool, {MEAT: 3, VEGETARIAN: 3})

    assert result.feasible
    assert not result.exhausted
    assert result.unmet_categories == ()


def test_search_infeasible_when_minimums_exceed_the_span():
    store = standard_household()
    snapshot, pool = _pool_for(store, make_ctx())

    result = search_minimums(snapshot, pool, {MEAT: 5, VEGETARIAN: 3})

    assert not result.feasible
    assert MEAT in result.unmet_categories


def test_search_reports_category_removed_by_rules_as_unmet():
    store = standard_household()
    store.rules = {1: blacklist_item(1, CHICKEN), 2: blacklist_item(2, BEEF)}
    ctx = make_ctx()
    snapshot, pool = _pool_for(store, ctx)

    result = search_minimums(snapshot, pool, {MEAT: 1})

    assert not result.feasible
    assert result.unmet_categories == (MEAT,)


def test_search_without_minimums_is_trivially_feasible():
    store = standard_household()
    snapshot, pool = _pool_for(store, make_ctx())

    result = search_minimums(snapshot, pool, {})

    assert result.feasible
    assert not result.exhausted


async def test_replan_persists_only_candidates_selected_for_the_plan():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx()
    planner = make_planner(store)

    result = await planner.replan(ctx, NOW)

    selected_ids = {
        record.dinner_id for record in result.updated.values() if record.dinner_id is not None
    }
    assert selected_ids
    assert all(dinner_id > 0 for dinner_id in selected_ids)
    assert set(store.dinners) == selected_ids
    assert len(store.dinners) < 27


async def test_check_rules_clean_when_nothing_is_planned():
    store = standard_household()
    planner = make_planner(store)

    check = await planner.check_rules(make_ctx(), [blacklist_item(1, CHICKEN)])

    assert check.feasible
    assert check.affected_days == ()
    assert check.locked_conflicts == ()


async def test_check_rules_lists_affected_days_without_saving():
    store = standard_household()
    ctx = make_ctx()
    planner = make_planner(store)
    await planner.replan(ctx, NOW)
    days_before = dict(store.days)

    check = await planner.check_rules(ctx, [blacklist_item(1, CHICKEN)])

    expected = {day for day in window_dates(ctx) if CHICKEN in dinner_of(store, day).item_ids}
    assert expected
    assert set(check.affected_days) == expected
    assert check.locked_conflicts == ()
    assert store.days == days_before
    assert store.rules == {}


async def test_check_rules_reports_pinned_day_as_locked_conflict():
    store = standard_household()
    ctx = make_ctx()
    planner = make_planner(store)
    await planner.replan(ctx, NOW)
    chicken_day = next(
        day for day in window_dates(ctx) if CHICKEN in dinner_of(store, day).item_ids
    )
    store.days[chicken_day] = replace(store.days[chicken_day], status=DayStatus.PINNED)

    check = await planner.check_rules(ctx, [blacklist_item(1, CHICKEN)])

    assert check.locked_conflicts == (chicken_day,)
    assert chicken_day not in check.affected_days


async def test_check_rules_warns_when_a_minimum_becomes_infeasible():
    store = standard_household()
    store.categories[MEAT].min_per_7_days = 1
    planner = make_planner(store)

    check = await planner.check_rules(
        make_ctx(), [blacklist_item(1, CHICKEN), blacklist_item(2, BEEF)]
    )

    assert not check.feasible
    assert [draft.code for draft in check.warnings] == [WarningCode.MINIMUM_INFEASIBLE]
    assert check.warnings[0].payload["required"] == 1


async def test_blacklisting_every_protein_empties_the_window():
    store = standard_household()
    store.rules = {
        1: blacklist_item(1, CHICKEN),
        2: blacklist_item(2, BEEF),
        3: blacklist_item(3, TOFU),
    }
    ctx = make_ctx()
    planner = make_planner(store)

    await planner.replan(ctx, NOW)

    assert all(dinner_of(store, day) is None for day in window_dates(ctx))
    empty_warnings = [
        record
        for record in store.warnings.values()
        if record.code == WarningCode.EMPTY_DAY and record.resolved_at is None
    ]
    assert len(empty_warnings) == ctx.settings.window_days


async def test_removing_rules_fills_window_and_clears_empty_warnings():
    store = standard_household()
    store.rules = {
        1: blacklist_item(1, CHICKEN),
        2: blacklist_item(2, BEEF),
        3: blacklist_item(3, TOFU),
    }
    ctx = make_ctx()
    planner = make_planner(store)
    await planner.replan(ctx, NOW)

    store.rules = {}
    await planner.replan(ctx, NOW)

    assert all(dinner_of(store, day) is not None for day in window_dates(ctx))
    open_empty = [
        record
        for record in store.warnings.values()
        if record.code == WarningCode.EMPTY_DAY and record.resolved_at is None
    ]
    assert open_empty == []


async def test_roll_forward_fills_the_new_day_and_keeps_past_days():
    store = standard_household()
    ctx = make_ctx()
    planner = make_planner(store)
    await planner.replan(ctx, NOW)
    past_day = TODAY
    past_before = dinner_of(store, past_day)

    next_ctx = make_ctx(today=TODAY + timedelta(days=1))
    await planner.roll_forward(next_ctx, NOW)

    assert all(dinner_of(store, day) is not None for day in window_dates(next_ctx))
    assert dinner_of(store, past_day) == past_before


def test_same_inputs_produce_the_same_plan():
    ctx = make_ctx()
    first, second = standard_household(), standard_household()

    plan_window(first, ctx)
    plan_window(second, ctx)

    first_ids = {day: dinner_of(first, day).id for day in window_dates(ctx)}
    second_ids = {day: dinner_of(second, day).id for day in window_dates(ctx)}
    assert first_ids == second_ids

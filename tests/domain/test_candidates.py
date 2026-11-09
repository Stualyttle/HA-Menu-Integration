from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import timedelta

from tests.domain.fakes import (
    BEEF,
    BROCCOLI,
    CARROT,
    CHICKEN,
    NOW,
    PASTA,
    POTATO,
    RICE,
    SPINACH,
    TODAY,
    FakeStore,
    blacklist_item,
    make_ctx,
    make_planner,
    standard_household,
    window_dates,
)

from app.domain.candidates import MAX_CANDIDATES, generate_candidates
from app.domain.config import PlanContext, Template
from app.domain.snapshot import PlanSnapshot
from app.models import Item, ItemType, WarningCode


def snapshot_with(store: FakeStore) -> PlanSnapshot:
    return PlanSnapshot(
        items=dict(store.items),
        categories=dict(store.categories),
        rules=list(store.rules.values()),
        dinners={},
        nutrition={},
        days={},
    )


def template_ctx(slots: dict[ItemType, int], out_of_stock=(), revision: int = 0) -> PlanContext:
    return replace(
        make_ctx(out_of_stock=out_of_stock, revision=revision),
        template=Template(slots=slots),
    )


def wide_household(per_type: int) -> FakeStore:
    """`per_type` items of each type, with ids 1..per_type*3 and no stored dinners."""
    store = FakeStore()
    for offset, item_type in enumerate(ItemType):
        for k in range(per_type):
            item_id = offset * 1000 + k + 1
            store.items[item_id] = Item(id=item_id, name=f"{item_type}-{k}", type=item_type)
    return store


def standard_slots() -> dict[ItemType, int]:
    return {ItemType.PROTEIN: 1, ItemType.VEGETABLE: 1, ItemType.CARB: 1}


def test_generation_is_deterministic_for_the_same_seed():
    store = wide_household(20)
    snapshot = snapshot_with(store)
    ctx = template_ctx(standard_slots())

    first = generate_candidates(snapshot, ctx, seed="candidates-0")
    second = generate_candidates(snapshot, ctx, seed="candidates-0")

    assert first == second
    assert len(first) == MAX_CANDIDATES


def test_sampling_depends_on_the_seed():
    store = wide_household(20)
    snapshot = snapshot_with(store)
    ctx = template_ctx(standard_slots())

    first = generate_candidates(snapshot, ctx, seed="candidates-0")
    other = generate_candidates(snapshot, ctx, seed="candidates-1")

    assert first != other


def test_candidates_match_template_counts_and_are_sorted_tuples():
    store = wide_household(4)
    snapshot = snapshot_with(store)
    slots = {ItemType.PROTEIN: 2, ItemType.VEGETABLE: 1, ItemType.CARB: 0}
    ctx = template_ctx(slots)

    candidates = generate_candidates(snapshot, ctx, seed="s")

    assert candidates
    for item_ids in candidates:
        assert isinstance(item_ids, tuple)
        assert list(item_ids) == sorted(item_ids)
        counts = Counter(store.items[item_id].type for item_id in item_ids)
        assert counts == Counter({ItemType.PROTEIN: 2, ItemType.VEGETABLE: 1})


def test_candidates_are_deduplicated():
    store = wide_household(20)
    candidates = generate_candidates(snapshot_with(store), template_ctx(standard_slots()), "s")

    assert len(candidates) == len(set(candidates))


def test_full_enumeration_produces_every_combination_once():
    store = standard_household()
    store.dinners.clear()
    snapshot = snapshot_with(store)

    candidates = generate_candidates(snapshot, template_ctx(standard_slots()), seed="s")

    assert len(candidates) == 27
    assert len(set(candidates)) == 27


def test_cap_is_respected_for_sampled_and_enumerated_sets():
    store = wide_household(20)
    snapshot = snapshot_with(store)
    ctx = template_ctx(standard_slots())

    assert len(generate_candidates(snapshot, ctx, seed="s")) == MAX_CANDIDATES
    assert len(generate_candidates(snapshot, ctx, seed="s", limit=7)) == 7
    assert generate_candidates(snapshot, ctx, seed="s", limit=0) == []


def test_default_cap_is_500():
    assert MAX_CANDIDATES == 500


def test_all_zero_template_yields_nothing():
    store = standard_household()
    ctx = template_ctx(standard_slots())
    # Template validation rejects all-zero at construction, so zero the slots afterwards.
    ctx.template.slots.update({item_type: 0 for item_type in ItemType})

    assert generate_candidates(snapshot_with(store), ctx, seed="s") == []


def test_blacklisted_items_never_appear_in_candidates():
    store = standard_household()
    store.rules = {1: blacklist_item(1, CHICKEN)}
    snapshot = snapshot_with(store)

    candidates = generate_candidates(snapshot, template_ctx(standard_slots()), seed="s")

    assert candidates
    assert all(CHICKEN not in item_ids for item_ids in candidates)


def test_out_of_stock_tracked_items_never_appear_in_candidates():
    store = standard_household()
    snapshot = snapshot_with(store)

    candidates = generate_candidates(
        snapshot, template_ctx(standard_slots(), out_of_stock={BEEF, RICE}), seed="s"
    )

    assert candidates
    assert all(BEEF not in item_ids and RICE not in item_ids for item_ids in candidates)


def test_untracked_items_stay_eligible_even_when_marked_out():
    store = standard_household()
    store.items[CHICKEN] = replace(store.items[CHICKEN], track_stock=False)
    snapshot = snapshot_with(store)

    candidates = generate_candidates(
        snapshot, template_ctx(standard_slots(), out_of_stock={CHICKEN}), seed="s"
    )

    assert any(CHICKEN in item_ids for item_ids in candidates)


def test_missing_type_yields_no_candidates_without_raising():
    store = standard_household()
    for item_id in (RICE, PASTA, POTATO):
        del store.items[item_id]

    assert generate_candidates(snapshot_with(store), template_ctx(standard_slots()), "s") == []


def test_planner_load_keeps_generated_dinners_transient():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx(window_days=14)
    planner = make_planner(store)

    snapshot = _run(planner.load(ctx))
    count = len(store.dinners)
    second = _run(planner.load(ctx))

    assert count == 0
    assert len(store.dinners) == 0
    assert len(snapshot.dinners) == 27
    assert all(dinner_id < 0 for dinner_id in snapshot.dinners)
    assert second.dinners == snapshot.dinners


def test_planner_fills_window_from_generated_dinners_alone():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx(window_days=14)

    _run(make_planner(store).replan(ctx, NOW))

    planned = [store.days[day].dinner_id for day in window_dates(ctx) if day in store.days]
    assert len(planned) == 14
    assert all(dinner_id in store.dinners for dinner_id in planned)


def test_planner_never_plans_blacklisted_items_from_generated_dinners():
    store = standard_household()
    store.dinners.clear()
    store.rules = {1: blacklist_item(1, CHICKEN)}
    ctx = make_ctx(window_days=14)

    _run(make_planner(store).replan(ctx, NOW))

    for day in window_dates(ctx):
        record = store.days.get(day)
        if record is not None and record.dinner_id is not None:
            assert CHICKEN not in store.dinners[record.dinner_id].item_ids


def test_infeasible_template_surfaces_empty_day_warnings():
    store = standard_household()
    store.dinners.clear()
    for item_id in (RICE, PASTA, POTATO):
        del store.items[item_id]
    ctx = make_ctx(window_days=7)

    _run(make_planner(store).replan(ctx, NOW))

    open_empty = [
        record
        for record in store.warnings.values()
        if record.code == WarningCode.EMPTY_DAY and record.resolved_at is None
    ]
    assert len(open_empty) == 7


def test_suggest_swaps_uses_generated_candidates():
    store = standard_household()
    store.dinners.clear()
    store.rules = {1: blacklist_item(1, BEEF)}
    ctx = make_ctx(window_days=14)
    planner = make_planner(store)
    _run(planner.replan(ctx, NOW))
    day = TODAY + timedelta(days=2)

    suggestions = _run(planner.suggest_swaps(ctx, day))

    assert 1 <= len(suggestions) <= 3
    assert all(BEEF not in dinner.item_ids for dinner in suggestions)


def test_swap_can_select_a_generated_dinner():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx(window_days=14)
    planner = make_planner(store)
    _run(planner.replan(ctx, NOW))
    day = TODAY + timedelta(days=2)
    target = next(
        dinner for dinner in store.dinners.values() if dinner.item_ids == (CHICKEN, BROCCOLI, RICE)
    )

    _run(planner.swap(ctx, day, target.id, NOW))

    assert store.dinners[store.days[day].dinner_id].item_ids == (CHICKEN, BROCCOLI, RICE)


def test_set_stock_yes_makes_items_plannable_again():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx(window_days=14)
    planner = make_planner(store)

    out_ctx = _run(planner.set_stock(ctx, CHICKEN, True, NOW))
    out_snapshot = _run(planner.load(out_ctx))
    assert all(CHICKEN not in d.item_ids for d in out_snapshot.dinners.values())

    back_ctx = _run(planner.set_stock(out_ctx, CHICKEN, False, NOW))
    back_snapshot = _run(planner.load(back_ctx))

    assert CHICKEN not in back_ctx.out_of_stock
    assert any(CHICKEN in d.item_ids for d in back_snapshot.dinners.values())


def test_stock_out_items_are_excluded_from_generation_under_planner():
    store = standard_household()
    store.dinners.clear()
    ctx = make_ctx(window_days=14, out_of_stock={SPINACH, CARROT})

    snapshot = _run(make_planner(store).load(ctx))

    assert all(
        SPINACH not in d.item_ids and CARROT not in d.item_ids for d in snapshot.dinners.values()
    )


def _run(awaitable):
    import asyncio

    return asyncio.run(awaitable)

from __future__ import annotations

from datetime import timedelta

from tests.domain.fakes import (
    BEEF,
    BROCCOLI,
    CHICKEN,
    MEAT,
    POTATO,
    POTATO_CAT,
    RICE,
    TODAY,
    TOFU,
    VEGETABLES,
    add_dinner,
    blacklist_combination,
    blacklist_item,
    make_ctx,
    plan_window,
    snapshot_of,
    standard_household,
    whitelist_item,
    window_dates,
    window_dinners,
    window_status,
)

from app.domain.config import Template
from app.domain.rules import RuleIndex, hard_violation
from app.models import DayStatus, Dinner, ItemType, MenuDay, Rule, RuleKind, RuleScope

STANDARD_TEMPLATE = Template()


def _assert_no_dinner_contains(dinners, item_id: int) -> None:
    for dinner in dinners.values():
        if dinner is None:
            continue
        assert item_id not in dinner.item_ids


def test_blacklisted_item_is_never_planned():
    store = standard_household()
    store.rules[1] = blacklist_item(1, CHICKEN)
    ctx = make_ctx()

    plan_window(store, ctx)

    dinners = window_dinners(store, ctx)
    assert any(dinner is not None for dinner in dinners.values())
    _assert_no_dinner_contains(dinners, CHICKEN)


def test_blacklisted_combination_is_never_planned():
    store = standard_household()
    store.rules[1] = blacklist_combination(1, {MEAT, POTATO_CAT})
    ctx = make_ctx()

    plan_window(store, ctx)

    for dinner in window_dinners(store, ctx).values():
        if dinner is None:
            continue
        meat = CHICKEN in dinner.item_ids or BEEF in dinner.item_ids
        assert not (meat and POTATO in dinner.item_ids)


def test_out_of_stock_item_is_never_planned():
    store = standard_household()
    ctx = make_ctx(out_of_stock={CHICKEN})

    plan_window(store, ctx)

    _assert_no_dinner_contains(window_dinners(store, ctx), CHICKEN)


def test_disabled_rule_is_ignored():
    store = standard_household()
    disabled = Rule(
        id=1, kind=RuleKind.BLACKLIST, scope=RuleScope.ITEM, item_id=CHICKEN, enabled=False
    )
    store.rules[1] = disabled
    ctx = make_ctx(out_of_stock=set())

    plan_window(store, ctx)

    assert any(
        dinner is not None and CHICKEN in dinner.item_ids
        for dinner in window_dinners(store, ctx).values()
    )


def test_hard_violation_reports_each_rule_kind():
    store = standard_household()
    snapshot = snapshot_of(store)
    chicken_broccoli_rice = add_dinner(store, CHICKEN, BROCCOLI, RICE)
    dinner = store.dinners[chicken_broccoli_rice]
    empty_rules = RuleIndex.build([])
    template = STANDARD_TEMPLATE

    assert hard_violation(snapshot, empty_rules, template, frozenset(), dinner) is None
    assert (
        hard_violation(snapshot, empty_rules, template, frozenset({CHICKEN}), dinner)
        == "out_of_stock"
    )

    blacklisted = RuleIndex.build([blacklist_item(1, CHICKEN)])
    assert (
        hard_violation(snapshot, blacklisted, template, frozenset(), dinner) == "blacklisted_item"
    )

    combination = RuleIndex.build([blacklist_combination(2, {MEAT, VEGETABLES})])
    assert (
        hard_violation(snapshot, combination, template, frozenset(), dinner)
        == "blacklist_combination"
    )

    wrong_count = Dinner(id=999, item_ids=(BROCCOLI, CHICKEN, RICE, POTATO))
    assert (
        hard_violation(snapshot, empty_rules, template, frozenset(), wrong_count)
        == "slot_count_mismatch"
    )


def test_hard_violation_reports_missing_item():
    store = standard_household()
    snapshot = snapshot_of(store)
    dinner = Dinner(id=999, item_ids=(BROCCOLI, CHICKEN, 9999))

    reason = hard_violation(snapshot, RuleIndex.build([]), STANDARD_TEMPLATE, frozenset(), dinner)

    assert reason == "missing_item"


def test_two_protein_one_vegetable_no_carb_template_counts():
    store = standard_household()
    snapshot = snapshot_of(store)
    template = Template(slots={ItemType.PROTEIN: 2, ItemType.VEGETABLE: 1, ItemType.CARB: 0})
    empty_rules = RuleIndex.build([])
    valid = Dinner(id=1, item_ids=tuple(sorted((CHICKEN, BEEF, BROCCOLI))))
    one_protein = Dinner(id=2, item_ids=tuple(sorted((CHICKEN, BROCCOLI))))
    with_carb = Dinner(id=3, item_ids=tuple(sorted((CHICKEN, BEEF, BROCCOLI, RICE))))

    assert hard_violation(snapshot, empty_rules, template, frozenset(), valid) is None
    assert (
        hard_violation(snapshot, empty_rules, template, frozenset(), one_protein)
        == "slot_count_mismatch"
    )
    assert (
        hard_violation(snapshot, empty_rules, template, frozenset(), with_carb)
        == "slot_count_mismatch"
    )


def test_whitelist_item_is_preferred_when_it_is_otherwise_free():
    store = standard_household()
    store.rules[1] = whitelist_item(1, TOFU)
    ctx = make_ctx()

    plan_window(store, ctx)

    proteins = [d.item_ids for d in window_dinners(store, ctx).values() if d is not None]
    assert any(TOFU in item_ids for item_ids in proteins)


def test_pinned_day_is_untouched_by_replan():
    store = standard_household()
    ctx = make_ctx()
    pinned_day = TODAY + timedelta(days=3)
    pinned_dinner = add_dinner(store, BEEF, BROCCOLI, POTATO)
    store.days[pinned_day] = MenuDay(
        day=pinned_day, dinner_id=pinned_dinner, status=DayStatus.PINNED
    )

    result = plan_window(store, ctx)

    assert pinned_day not in result.updated
    assert store.days[pinned_day].dinner_id == pinned_dinner
    assert store.days[pinned_day].status is DayStatus.PINNED


def test_eaten_day_is_untouched_by_replan_even_when_it_breaks_a_rule():
    store = standard_household()
    store.rules[1] = blacklist_item(1, CHICKEN)
    ctx = make_ctx()
    eaten_day = TODAY + timedelta(days=5)
    eaten_dinner = add_dinner(store, CHICKEN, BROCCOLI, RICE)
    store.days[eaten_day] = MenuDay(day=eaten_day, dinner_id=eaten_dinner, status=DayStatus.EATEN)

    result = plan_window(store, ctx)

    assert eaten_day not in result.updated
    assert store.days[eaten_day].status is DayStatus.EATEN
    assert store.days[eaten_day].dinner_id == eaten_dinner


def test_past_days_outside_the_window_are_not_planned():
    store = standard_household()
    ctx = make_ctx()
    yesterday = TODAY - timedelta(days=1)

    result = plan_window(store, ctx)

    assert yesterday not in result.updated
    assert yesterday not in store.days


def test_planned_days_cover_exactly_the_window():
    store = standard_household()
    ctx = make_ctx(window_days=10)

    plan_window(store, ctx)

    statuses = window_status(store, ctx)
    assert list(statuses) == window_dates(ctx)
    assert all(status is DayStatus.PLANNED for status in statuses.values())

"""Greedy day-by-day planner with hard rules (PLAN 6) and ordered soft penalties."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from app.domain.config import MINIMUM_SPAN_DAYS, PlanContext
from app.domain.errors import DayNotEditableError, SwapRejectedError
from app.domain.rules import RuleIndex, hard_violation
from app.domain.scoring import Scorer
from app.domain.snapshot import PlanSnapshot
from app.models import (
    DayStatus,
    Dinner,
    MenuDay,
    NutritionStatus,
    WarningCode,
    WarningSubject,
)

STOCK_REASON = "stock"
SWAP_SUGGESTION_COUNT = 3
FILLABLE_STATUSES = frozenset({DayStatus.PLANNED, DayStatus.EMPTY})


@dataclass(slots=True, frozen=True)
class WarningDraft:
    code: WarningCode
    subject_type: WarningSubject
    subject: str
    payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class PlanResult:
    updated: dict[date, MenuDay] = field(default_factory=dict)
    warnings: list[WarningDraft] = field(default_factory=list)


def window_bounds(ctx: PlanContext) -> tuple[date, date]:
    return ctx.today, ctx.today + timedelta(days=ctx.settings.window_days - 1)


def is_fillable(snapshot: PlanSnapshot, ctx: PlanContext, day: date) -> bool:
    start, end = window_bounds(ctx)
    if not start <= day <= end:
        return False
    record = snapshot.days.get(day)
    return record is None or record.status in FILLABLE_STATUSES


def fillable_days(snapshot: PlanSnapshot, ctx: PlanContext) -> list[date]:
    start, end = window_bounds(ctx)
    total = (end - start).days + 1
    return [
        d
        for d in (start + timedelta(days=k) for k in range(total))
        if is_fillable(snapshot, ctx, d)
    ]


def valid_pool(snapshot: PlanSnapshot, ctx: PlanContext, rules: RuleIndex) -> list[Dinner]:
    pool = [
        dinner
        for dinner in snapshot.dinners.values()
        if hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, dinner) is None
    ]
    return sorted(pool, key=lambda dinner: dinner.id)


def _assigned(snapshot: PlanSnapshot, exclude: Iterable[date]) -> dict[date, int]:
    skipped = set(exclude)
    return {
        day: record.dinner_id
        for day, record in snapshot.days.items()
        if record.dinner_id is not None and day not in skipped
    }


def plan(
    snapshot: PlanSnapshot,
    ctx: PlanContext,
    targets: Iterable[date],
    reason: str | None = None,
) -> PlanResult:
    """Fill `targets` in date order. Only fillable window days are changed."""
    rules = RuleIndex.build(snapshot.rules)
    scorer = Scorer.build(snapshot, rules, ctx.settings)
    window = window_bounds(ctx)
    pool = valid_pool(snapshot, ctx, rules)
    chosen_days = sorted(d for d in set(targets) if is_fillable(snapshot, ctx, d))
    assigned = _assigned(snapshot, chosen_days)
    result = PlanResult()

    for day in chosen_days:
        previous = snapshot.days.get(day)
        base = scorer.window_totals(assigned, window, exclude=day)
        candidates = list(pool)
        random.Random(f"{day.isoformat()}-{ctx.revision}").shuffle(candidates)

        best: Dinner | None = None
        best_score = None
        for dinner in candidates:
            score = scorer.score(day, dinner, assigned, base)
            if best_score is None or score < best_score:
                best, best_score = dinner, score

        replaced_reason = None
        if previous is not None and previous.dinner_id is not None:
            old = snapshot.dinners.get(previous.dinner_id)
            if (
                old is None
                or hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, old) is not None
            ):
                replaced_reason = reason
                result.warnings.append(
                    WarningDraft(
                        WarningCode.REPLACED_DINNER,
                        WarningSubject.DATE,
                        day.isoformat(),
                        {"reason": reason, "previous_dinner_id": previous.dinner_id},
                    )
                )

        if best is None:
            result.updated[day] = MenuDay(day, None, DayStatus.EMPTY, replaced_reason)
            continue
        assigned[day] = best.id
        result.updated[day] = MenuDay(day, best.id, DayStatus.PLANNED, replaced_reason)

    _add_state_warnings(snapshot, ctx, result, window)
    return result


def _dinner_map(
    snapshot: PlanSnapshot, result: PlanResult, window: tuple[date, date], margin: int
) -> dict[date, Dinner]:
    """Dinner per day over the window plus `margin` days either side, updates applied."""
    start, end = window
    dinners: dict[date, Dinner] = {}
    first = start - timedelta(days=margin)
    last = end + timedelta(days=margin)
    for day in _date_range(first, last):
        record = result.updated.get(day, snapshot.days.get(day))
        if record is None or record.dinner_id is None:
            continue
        dinner = snapshot.dinners.get(record.dinner_id)
        if dinner is not None:
            dinners[day] = dinner
    return dinners


def _date_range(first: date, last: date) -> list[date]:
    return [first + timedelta(days=k) for k in range((last - first).days + 1)]


def _add_state_warnings(
    snapshot: PlanSnapshot,
    ctx: PlanContext,
    result: PlanResult,
    window: tuple[date, date],
) -> None:
    start, end = window
    margin = max(ctx.settings.repeat_gap_days, MINIMUM_SPAN_DAYS)
    dinners = _dinner_map(snapshot, result, window, margin)
    window_days = _date_range(start, end)

    for day in window_days:
        if day not in dinners:
            result.warnings.append(
                WarningDraft(WarningCode.EMPTY_DAY, WarningSubject.DATE, day.isoformat())
            )

    for day in window_days:
        dinner = dinners.get(day)
        if dinner is None:
            continue
        shared = _shared_items_within_gap(ctx, snapshot, dinners, day, dinner)
        if shared:
            result.warnings.append(
                WarningDraft(
                    WarningCode.REPEAT_GAP_UNAVOIDABLE,
                    WarningSubject.DATE,
                    day.isoformat(),
                    {"items": sorted(shared)},
                )
            )

    result.warnings.extend(_missed_minimum_warnings(snapshot, dinners, window))

    failed_items = {
        item_id
        for day in window_days
        if (dinner := dinners.get(day)) is not None
        for item_id in snapshot.dinner_items(dinner)
        if (nutrition := snapshot.nutrition.get(item_id)) is not None
        and nutrition.status == NutritionStatus.ERROR
    }
    for item_id in sorted(failed_items):
        result.warnings.append(
            WarningDraft(WarningCode.NUTRITION_FAILED, WarningSubject.ITEM, str(item_id))
        )

    if ctx.device_timezone and ctx.device_timezone != ctx.timezone:
        result.warnings.append(
            WarningDraft(
                WarningCode.TIMEZONE_MISMATCH,
                WarningSubject.DATE,
                start.isoformat(),
                {"timezone": ctx.timezone, "device_timezone": ctx.device_timezone},
            )
        )


def _shared_items_within_gap(
    ctx: PlanContext,
    snapshot: PlanSnapshot,
    dinners: dict[date, Dinner],
    day: date,
    dinner: Dinner,
) -> set[int]:
    gap = ctx.settings.repeat_gap_days
    shared: set[int] = set()
    if gap <= 0:
        return shared
    mine = set(snapshot.dinner_items(dinner))
    for offset in range(-gap + 1, gap):
        if offset == 0:
            continue
        other = dinners.get(day + timedelta(days=offset))
        if other is not None:
            shared |= mine & set(snapshot.dinner_items(other))
    return shared


def _missed_minimum_warnings(
    snapshot: PlanSnapshot,
    dinners: dict[date, Dinner],
    window: tuple[date, date],
) -> list[WarningDraft]:
    start, end = window
    drafts: list[WarningDraft] = []
    for category in sorted(snapshot.categories.values(), key=lambda c: c.id):
        if not category.min_per_7_days:
            continue
        misses: list[str] = []
        # Spans that start before the window have no plan data, so only spans fully inside it count.
        first_span_end = start + timedelta(days=MINIMUM_SPAN_DAYS - 1)
        for span_end in _date_range(first_span_end, end):
            span = _date_range(span_end - timedelta(days=MINIMUM_SPAN_DAYS - 1), span_end)
            count = sum(
                1
                for day in span
                if (dinner := dinners.get(day)) is not None
                and category.id in snapshot.dinner_categories(dinner)
            )
            if count < category.min_per_7_days:
                misses.append(span_end.isoformat())
        if misses:
            drafts.append(
                WarningDraft(
                    WarningCode.MISSED_MINIMUM,
                    WarningSubject.CATEGORY,
                    str(category.id),
                    {"required": category.min_per_7_days, "span_ends": misses},
                )
            )
    return drafts


def roll_forward(snapshot: PlanSnapshot, ctx: PlanContext) -> PlanResult:
    """Fill window days that have no dinner yet (new last day, or days that were empty)."""
    targets = [
        d
        for d in fillable_days(snapshot, ctx)
        if snapshot.days.get(d) is None or snapshot.days[d].dinner_id is None
    ]
    return plan(snapshot, ctx, targets)


def replan_all(snapshot: PlanSnapshot, ctx: PlanContext, reason: str | None = None) -> PlanResult:
    """Re-plan every fillable window day (rule, minimum, gap, item, or template edits)."""
    return plan(snapshot, ctx, fillable_days(snapshot, ctx), reason)


def with_stock(ctx: PlanContext, item_id: int, out: bool) -> PlanContext:
    """Return `ctx` with the item's stock flag set (out=True means "no")."""
    stock = set(ctx.out_of_stock)
    if out:
        stock.add(item_id)
    else:
        stock.discard(item_id)
    return replace(ctx, out_of_stock=frozenset(stock))


def apply_stock_change(
    snapshot: PlanSnapshot, ctx: PlanContext, item_id: int, out: bool
) -> tuple[PlanContext, PlanResult]:
    """Update stock and re-plan only the affected days.

    "no" replaces fillable days whose dinner uses the item. "yes" re-plans only the days that
    an earlier "no" replaced, so the rest of the window is left alone.
    """
    new_ctx = with_stock(ctx, item_id, out)
    fillable = fillable_days(snapshot, new_ctx)
    if out:
        targets = [
            d
            for d in fillable
            if snapshot.days.get(d) is not None
            and snapshot.days[d].dinner_id is not None
            and item_id in snapshot.dinner_items(snapshot.dinners[snapshot.days[d].dinner_id])
        ]
        result = plan(snapshot, new_ctx, targets, STOCK_REASON)
    else:
        targets = [
            d
            for d in fillable
            if snapshot.days.get(d) is not None and snapshot.days[d].replaced_reason == STOCK_REASON
        ]
        result = plan(snapshot, new_ctx, targets, None)
    return new_ctx, result


def suggest_swaps(snapshot: PlanSnapshot, ctx: PlanContext, day: date) -> list[Dinner]:
    _require_editable(snapshot, ctx, day)
    rules = RuleIndex.build(snapshot.rules)
    scorer = Scorer.build(snapshot, rules, ctx.settings)
    window = window_bounds(ctx)
    assigned = _assigned(snapshot, [day])
    base = scorer.window_totals(assigned, window, exclude=day)
    current = snapshot.days[day].dinner_id
    ranked = []
    for dinner in valid_pool(snapshot, ctx, rules):
        if dinner.id == current:
            continue
        ranked.append((scorer.score(day, dinner, assigned, base), dinner.id, dinner))
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in ranked[:SWAP_SUGGESTION_COUNT]]


def apply_swap(snapshot: PlanSnapshot, ctx: PlanContext, day: date, dinner_id: int) -> PlanResult:
    """Pin `day` to `dinner_id` and re-plan the other fillable days."""
    _require_editable(snapshot, ctx, day)
    dinner = snapshot.dinners.get(dinner_id)
    if dinner is None:
        raise SwapRejectedError("unknown_dinner")
    rules = RuleIndex.build(snapshot.rules)
    reason = hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, dinner)
    if reason is not None:
        raise SwapRejectedError(reason)

    pinned = MenuDay(day, dinner_id, DayStatus.PINNED)
    new_days = dict(snapshot.days)
    new_days[day] = pinned
    pinned_snapshot = replace(snapshot, days=new_days)
    others = [d for d in fillable_days(pinned_snapshot, ctx) if d != day]
    result = plan(pinned_snapshot, ctx, others, None)
    result.updated[day] = pinned
    return result


def _require_editable(snapshot: PlanSnapshot, ctx: PlanContext, day: date) -> None:
    start, end = window_bounds(ctx)
    if not start <= day <= end:
        raise DayNotEditableError(f"{day} is outside the window")
    record = snapshot.days.get(day)
    if record is None or record.dinner_id is None:
        raise DayNotEditableError(f"{day} has no dinner to swap")
    if record.status == DayStatus.EATEN:
        raise DayNotEditableError(f"{day} is already eaten")

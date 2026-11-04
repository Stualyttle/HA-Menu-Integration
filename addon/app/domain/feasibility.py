"""Bounded search: can the valid dinners meet every category minimum inside one 7-day span?"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.domain.config import MINIMUM_SPAN_DAYS, PlanContext
from app.domain.engine import FILLABLE_STATUSES, WarningDraft, valid_pool, window_bounds
from app.domain.rules import RuleIndex, hard_violation
from app.domain.snapshot import PlanSnapshot
from app.models import Dinner, WarningCode, WarningSubject

DEFAULT_NODE_CAP = 100_000


@dataclass(slots=True, frozen=True)
class MinimumSearch:
    feasible: bool
    exhausted: bool
    unmet_categories: tuple[int, ...] = ()


class _NodeCapReached(Exception):
    pass


def search_minimums(
    snapshot: PlanSnapshot,
    pool: Iterable[Dinner],
    minimums: dict[int, int],
    span: int = MINIMUM_SPAN_DAYS,
    node_cap: int = DEFAULT_NODE_CAP,
) -> MinimumSearch:
    """Decide whether `span` dinners drawn from `pool` can meet every minimum.

    The search is exact until `node_cap` nodes are visited. When the cap is hit the result is
    reported as feasible with `exhausted=True`, so a save is never blocked by a timeout.
    """
    needs = {category_id: n for category_id, n in minimums.items() if n > 0}
    if not needs:
        return MinimumSearch(feasible=True, exhausted=False)

    category_ids = sorted(needs)
    dinners = list(pool)
    coverage = {
        dinner.id: frozenset(snapshot.dinner_categories(dinner)) & frozenset(category_ids)
        for dinner in dinners
    }
    unmet = tuple(
        category_id
        for category_id in category_ids
        if not any(category_id in covered for covered in coverage.values())
    )
    if unmet:
        return MinimumSearch(feasible=False, exhausted=False, unmet_categories=unmet)

    distinct = sorted({covered for covered in coverage.values()}, key=lambda c: sorted(c))
    max_cover = max(len(covered) for covered in distinct)
    remaining_nodes = [node_cap]

    def search(need: dict[int, int], slots: int) -> bool:
        remaining_nodes[0] -= 1
        if remaining_nodes[0] < 0:
            raise _NodeCapReached
        open_categories = [c for c, n in need.items() if n > 0]
        if not open_categories:
            return True
        if slots == 0 or sum(need.values()) > slots * max_cover:
            return False
        pivot = min(
            open_categories,
            key=lambda c: sum(1 for covered in distinct if c in covered),
        )
        for covered in distinct:
            if pivot not in covered:
                continue
            next_need = {c: max(0, n - (1 if c in covered else 0)) for c, n in need.items()}
            if search(next_need, slots - 1):
                return True
        return False

    try:
        found = search(dict(needs), span)
    except _NodeCapReached:
        return MinimumSearch(feasible=True, exhausted=True)
    if found:
        return MinimumSearch(feasible=True, exhausted=False)
    return MinimumSearch(feasible=False, exhausted=False, unmet_categories=tuple(category_ids))


@dataclass(slots=True, frozen=True)
class RuleCheck:
    feasible: bool
    exhausted: bool
    affected_days: tuple[date, ...]
    locked_conflicts: tuple[date, ...]
    warnings: tuple[WarningDraft, ...]


def check_rules(snapshot: PlanSnapshot, ctx: PlanContext) -> RuleCheck:
    """Check a proposed rule set (already present in `snapshot.rules`) before it is saved.

    Reports window days whose dinner becomes invalid. Those that can be re-planned are
    `affected_days`. Pinned or eaten days are `locked_conflicts` and cannot change.
    """
    rules = RuleIndex.build(snapshot.rules)
    pool = valid_pool(snapshot, ctx, rules)
    minimums = {
        category.id: category.min_per_7_days
        for category in snapshot.categories.values()
        if category.min_per_7_days
    }
    search = search_minimums(snapshot, pool, minimums)

    start, end = window_bounds(ctx)
    affected: list[date] = []
    locked: list[date] = []
    for day in sorted(snapshot.days):
        record = snapshot.days[day]
        if record.dinner_id is None or not start <= day <= end:
            continue
        dinner = snapshot.dinners.get(record.dinner_id)
        if (
            dinner is None
            or hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, dinner) is None
        ):
            continue
        if record.status in FILLABLE_STATUSES:
            affected.append(day)
        else:
            locked.append(day)

    warnings = tuple(
        WarningDraft(
            WarningCode.MINIMUM_INFEASIBLE,
            WarningSubject.CATEGORY,
            str(category_id),
            {"required": minimums.get(category_id)},
        )
        for category_id in search.unmet_categories
    )
    return RuleCheck(
        feasible=search.feasible,
        exhausted=search.exhausted,
        affected_days=tuple(affected),
        locked_conflicts=tuple(locked),
        warnings=warnings,
    )

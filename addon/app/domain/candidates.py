"""Pure, bounded generator of dinner item-sets that the planner may choose from.

A candidate has exactly the template count of each item type, uses only items that are not
blacklisted or out of stock, and passes the combination blacklist. Generation is deterministic
for a given (seed, items, rules, template, stock).
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Mapping

from app.domain.config import PlanContext
from app.domain.rules import RuleIndex, hard_violation
from app.domain.snapshot import PlanSnapshot
from app.models import Dinner, ItemType

# Tunable: the most distinct item-sets generated per load. Larger values give more variety at
# the cost of more rows persisted by ensure_dinners. Lower it if the dinner table grows too fast.
MAX_CANDIDATES = 500
SAMPLE_ATTEMPTS_PER_CANDIDATE = 10

CandidateSet = tuple[int, ...]


def eligible_items(
    snapshot: PlanSnapshot, ctx: PlanContext, rules: RuleIndex
) -> dict[ItemType, list[int]]:
    """Sorted item ids per type that may appear in a dinner under the current rules and stock."""
    pools: dict[ItemType, list[int]] = {item_type: [] for item_type in ItemType}
    for item in snapshot.items.values():
        if item.is_complete_meal:
            continue
        if item.id in rules.blocked_items:
            continue
        if item.track_stock and item.id in ctx.out_of_stock:
            continue
        pools[item.type].append(item.id)
    for ids in pools.values():
        ids.sort()
    return pools


def generate_candidates(
    snapshot: PlanSnapshot,
    ctx: PlanContext,
    seed: str,
    limit: int = MAX_CANDIDATES,
) -> list[CandidateSet]:
    """Return up to `limit` valid item-id tuples, sorted and duplicate-free.

    Returns an empty list when the template is all zero, when a type has fewer eligible items
    than the template needs, or when `limit` is not positive. Callers surface that through the
    existing infeasibility warnings.
    """
    if limit <= 0:
        return []
    rules = RuleIndex.build(snapshot.rules)
    complete_meals = []
    for item in sorted(snapshot.items.values(), key=lambda candidate: candidate.id):
        if not item.is_complete_meal:
            continue
        candidate = (item.id,)
        if (
            hard_violation(
                snapshot,
                rules,
                ctx.template,
                ctx.out_of_stock,
                Dinner(id=0, item_ids=candidate),
            )
            is None
        ):
            complete_meals.append(item.id)
        if len(complete_meals) >= limit:
            break
    meal_candidates = {(item_id,) for item_id in complete_meals}
    remaining_limit = limit - len(meal_candidates)

    sizes = {item_type: count for item_type, count in ctx.template.slots.items() if count}
    if remaining_limit <= 0 or not sizes:
        return sorted(meal_candidates)

    pools = eligible_items(snapshot, ctx, rules)
    if any(len(pools[item_type]) < count for item_type, count in sizes.items()):
        return sorted(meal_candidates)

    def is_valid(item_ids: CandidateSet) -> bool:
        dinner = Dinner(id=0, item_ids=item_ids)
        return hard_violation(snapshot, rules, ctx.template, ctx.out_of_stock, dinner) is None

    total = math.prod(math.comb(len(pools[item_type]), count) for item_type, count in sizes.items())
    if total <= remaining_limit:
        found = _enumerate(pools, sizes, is_valid)
    else:
        found = _sample(pools, sizes, is_valid, seed, remaining_limit)
    return sorted(meal_candidates | found)[:limit]


def _enumerate(
    pools: Mapping[ItemType, list[int]],
    sizes: Mapping[ItemType, int],
    is_valid: Callable[[CandidateSet], bool],
) -> set[CandidateSet]:
    per_type = [
        list(itertools.combinations(pools[item_type], count)) for item_type, count in sizes.items()
    ]
    found: set[CandidateSet] = set()
    for choice in itertools.product(*per_type):
        item_ids = tuple(sorted(itertools.chain.from_iterable(choice)))
        if is_valid(item_ids):
            found.add(item_ids)
    return found


def _sample(
    pools: Mapping[ItemType, list[int]],
    sizes: Mapping[ItemType, int],
    is_valid: Callable[[CandidateSet], bool],
    seed: str,
    limit: int,
) -> set[CandidateSet]:
    rng = random.Random(seed)
    found: set[CandidateSet] = set()
    for _ in range(limit * SAMPLE_ATTEMPTS_PER_CANDIDATE):
        if len(found) >= limit:
            break
        item_ids = tuple(
            sorted(
                item_id
                for item_type, count in sizes.items()
                for item_id in rng.sample(pools[item_type], count)
            )
        )
        if item_ids not in found and is_valid(item_ids):
            found.add(item_ids)
    return found

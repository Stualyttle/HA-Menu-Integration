"""Hard rules (PLAN 6): a dinner is valid only if this module accepts it."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.config import Template
from app.domain.snapshot import PlanSnapshot
from app.models import Dinner, ItemType, Rule, RuleKind, RuleScope


@dataclass(slots=True, frozen=True)
class RuleIndex:
    blocked_items: frozenset[int]
    blacklist_combinations: tuple[frozenset[int], ...]
    whitelist_items: frozenset[int]
    whitelist_combinations: tuple[frozenset[int], ...]

    @classmethod
    def build(cls, rules: Iterable[Rule]) -> RuleIndex:
        blocked: set[int] = set()
        blacklist: list[frozenset[int]] = []
        whitelist_items: set[int] = set()
        whitelist: list[frozenset[int]] = []
        for rule in rules:
            if not rule.enabled:
                continue
            if rule.scope == RuleScope.ITEM and rule.item_id is not None:
                if rule.kind == RuleKind.BLACKLIST:
                    blocked.add(rule.item_id)
                else:
                    whitelist_items.add(rule.item_id)
            elif rule.scope == RuleScope.COMBINATION and rule.category_ids:
                if rule.kind == RuleKind.BLACKLIST:
                    blacklist.append(frozenset(rule.category_ids))
                else:
                    whitelist.append(frozenset(rule.category_ids))
        return cls(
            blocked_items=frozenset(blocked),
            blacklist_combinations=tuple(blacklist),
            whitelist_items=frozenset(whitelist_items),
            whitelist_combinations=tuple(whitelist),
        )


def hard_violation(
    snapshot: PlanSnapshot,
    rules: RuleIndex,
    template: Template,
    out_of_stock: frozenset[int],
    dinner: Dinner,
) -> str | None:
    """Return the reason a dinner breaks a hard rule, or None when it is valid.

    A complete meal is a standalone dinner. Other dinners must match every template slot.
    """
    item_ids = snapshot.dinner_items(dinner)
    items = []
    for item_id in item_ids:
        item = snapshot.items.get(item_id)
        if item is None:
            return "missing_item"
        items.append(item)
        if item_id in rules.blocked_items:
            return "blacklisted_item"
        if item.track_stock and item_id in out_of_stock:
            return "out_of_stock"
    complete_meals = [item for item in items if item.is_complete_meal]
    if complete_meals:
        if len(items) != 1:
            return "complete_meal_mixed"
    else:
        counts = dict.fromkeys(ItemType, 0)
        for item in items:
            counts[item.type] += 1
        for item_type, expected in template.slots.items():
            if counts[item_type] != expected:
                return "slot_count_mismatch"
    categories = snapshot.dinner_categories(dinner)
    for combination in rules.blacklist_combinations:
        if combination <= categories:
            return "blacklist_combination"
    return None


def whitelist_hits(snapshot: PlanSnapshot, rules: RuleIndex, dinner: Dinner) -> int:
    hits = sum(1 for item_id in snapshot.dinner_items(dinner) if item_id in rules.whitelist_items)
    categories = snapshot.dinner_categories(dinner)
    hits += sum(1 for combination in rules.whitelist_combinations if combination <= categories)
    return hits

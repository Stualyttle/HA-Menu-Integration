"""Soft penalties (PLAN 6). Lower tuples win; the tuple order is the priority order."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.config import MINIMUM_SPAN_DAYS, PlanSettings
from app.domain.rules import RuleIndex, whitelist_hits
from app.domain.snapshot import PlanSnapshot
from app.models import Dinner, ItemType, NutritionSource, NutritionStatus

Score = tuple[int, int, int, float]


def is_verified(snapshot: PlanSnapshot, item_id: int) -> bool:
    """Balance only counts items with portion grams and trustworthy nutrition (PLAN 15)."""
    item = snapshot.items.get(item_id)
    if item is None or item.portion_grams is None:
        return False
    nutrition = snapshot.nutrition.get(item_id)
    if nutrition is None or nutrition.status != NutritionStatus.OK:
        return False
    return not (nutrition.source == NutritionSource.MANUAL and not nutrition.user_confirmed)


def _excess(totals: dict[ItemType, float], settings: PlanSettings) -> float:
    total = sum(totals.values())
    if total <= 0:
        return 0.0
    excess = 0.0
    for item_type, target in settings.balance_targets.items():
        share = totals.get(item_type, 0.0) / total * 100.0
        excess += max(0.0, abs(share - target) - settings.balance_tolerance)
    return round(excess, 6)


@dataclass(slots=True)
class Scorer:
    snapshot: PlanSnapshot
    rules: RuleIndex
    settings: PlanSettings
    minimums: dict[int, int]

    @classmethod
    def build(cls, snapshot: PlanSnapshot, rules: RuleIndex, settings: PlanSettings) -> Scorer:
        minimums = {
            category.id: category.min_per_7_days
            for category in snapshot.categories.values()
            if category.min_per_7_days
        }
        return cls(snapshot, rules, settings, minimums)

    def window_totals(
        self, assigned: dict[date, int], window: tuple[date, date], exclude: date
    ) -> dict[ItemType, float]:
        totals: dict[ItemType, float] = {item_type: 0.0 for item_type in ItemType}
        start, end = window
        for day, dinner_id in assigned.items():
            if day == exclude or not start <= day <= end:
                continue
            self._add_grams(totals, self._dinner(dinner_id))
        return totals

    def score(
        self,
        day: date,
        dinner: Dinner,
        assigned: dict[date, int],
        base_totals: dict[ItemType, float],
    ) -> Score:
        shortfall = self._shortfall(day, dinner, assigned)
        gap_violations = self._gap_violations(day, dinner, assigned)
        whitelist = whitelist_hits(self.snapshot, self.rules, dinner)
        totals = dict(base_totals)
        self._add_grams(totals, dinner)
        balance = _excess(totals, self.settings)
        return (shortfall, gap_violations, -whitelist, balance)

    def _shortfall(self, day: date, dinner: Dinner, assigned: dict[date, int]) -> int:
        if not self.minimums:
            return 0
        cats = self.snapshot.dinner_categories(dinner)
        previous = [day - timedelta(days=k) for k in range(1, MINIMUM_SPAN_DAYS)]
        counts = {category_id: 0 for category_id in self.minimums}
        for other in previous:
            dinner_id = assigned.get(other)
            if dinner_id is None:
                continue
            other_cats = self.snapshot.dinner_categories(self._dinner(dinner_id))
            for category_id in counts:
                if category_id in other_cats:
                    counts[category_id] += 1
        shortfall = 0
        for category_id, need in self.minimums.items():
            count = counts[category_id] + (1 if category_id in cats else 0)
            shortfall += max(0, need - count)
        return shortfall

    def _gap_violations(self, day: date, dinner: Dinner, assigned: dict[date, int]) -> int:
        gap = self.settings.repeat_gap_days
        if gap <= 0:
            return 0
        violating: set[int] = set()
        candidate_items = set(self.snapshot.dinner_items(dinner))
        for offset in range(-gap + 1, gap):
            if offset == 0:
                continue
            dinner_id = assigned.get(day + timedelta(days=offset))
            if dinner_id is None:
                continue
            other_items = set(self.snapshot.dinner_items(self._dinner(dinner_id)))
            violating |= candidate_items & other_items
        return len(violating)

    def _add_grams(self, totals: dict[ItemType, float], dinner: Dinner) -> None:
        for item_id in self.snapshot.dinner_items(dinner):
            item = self.snapshot.items[item_id]
            if item.portion_grams is None or not is_verified(self.snapshot, item_id):
                continue
            totals[item.type] = totals.get(item.type, 0.0) + float(item.portion_grams)

    def _dinner(self, dinner_id: int) -> Dinner:
        return self.snapshot.dinners[dinner_id]

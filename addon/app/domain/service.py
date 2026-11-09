"""Async facade: loads household data via the repository Protocols and commits engine results."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from app.domain.candidates import generate_candidates
from app.domain.config import MINIMUM_SPAN_DAYS, PlanContext
from app.domain.engine import (
    PlanResult,
    WarningDraft,
    apply_stock_change,
    apply_swap,
    replan_all,
    roll_forward,
    suggest_swaps,
    window_bounds,
    with_stock,
)
from app.domain.errors import SwapRejectedError
from app.domain.feasibility import RuleCheck, check_rules
from app.domain.snapshot import PlanSnapshot
from app.models import Dinner, Rule, WarningCode, WarningRecord, WarningSubject
from app.ports import (
    CategoryRepository,
    ItemRepository,
    MenuRepository,
    NutritionRepository,
    RuleRepository,
    WarningRepository,
)

STATE_WARNING_CODES = frozenset(
    {
        WarningCode.EMPTY_DAY,
        WarningCode.MISSED_MINIMUM,
        WarningCode.REPEAT_GAP_UNAVOIDABLE,
        WarningCode.MINIMUM_INFEASIBLE,
        WarningCode.NUTRITION_FAILED,
        WarningCode.TIMEZONE_MISMATCH,
    }
)

WarningKey = tuple[WarningCode, WarningSubject, str]


@dataclass(slots=True)
class MenuPlanner:
    """Every public method takes `ctx` (today, settings, template, stock) and `now` explicitly."""

    items: ItemRepository
    categories: CategoryRepository
    rules: RuleRepository
    menu: MenuRepository
    nutrition: NutritionRepository
    warnings: WarningRepository

    async def load(
        self, ctx: PlanContext, proposed_rules: list[Rule] | None = None
    ) -> PlanSnapshot:
        """Snapshot of household data plus generated candidate dinners.

        `proposed_rules` replaces the stored rules, so candidates respect a rule set being checked.
        """
        start, end = window_bounds(ctx)
        margin = max(ctx.settings.repeat_gap_days, MINIMUM_SPAN_DAYS)
        items = await self.items.list_items()
        categories = await self.categories.list_categories()
        rules = (
            list(proposed_rules) if proposed_rules is not None else await self.rules.list_rules()
        )
        dinners = await self.menu.list_dinners()
        days = await self.menu.get_days(
            start - timedelta(days=margin), end + timedelta(days=margin)
        )
        nutrition = {}
        for item in items:
            record = await self.nutrition.get_nutrition(item.id)
            if record is not None:
                nutrition[item.id] = record
        snapshot = PlanSnapshot(
            items={item.id: item for item in items},
            categories={category.id: category for category in categories},
            rules=rules,
            dinners={dinner.id: dinner for dinner in dinners},
            nutrition=nutrition,
            days={day.day: day for day in days},
        )
        return await self._with_candidates(snapshot, ctx)

    async def _with_candidates(self, snapshot: PlanSnapshot, ctx: PlanContext) -> PlanSnapshot:
        """Add generated item-sets as transient dinners without writing to the repository."""
        generated = generate_candidates(snapshot, ctx, seed=f"candidates-{ctx.revision}")
        known = {dinner.item_ids for dinner in snapshot.dinners.values()}
        missing = [item_ids for item_ids in generated if item_ids not in known]
        if not missing:
            return snapshot
        added = {
            -(index + 1): Dinner(id=-(index + 1), item_ids=item_ids)
            for index, item_ids in enumerate(missing)
        }
        return replace(snapshot, dinners={**snapshot.dinners, **added})

    async def replan(
        self, ctx: PlanContext, now: datetime, reason: str | None = None
    ) -> PlanResult:
        snapshot = await self.load(ctx)
        return await self._commit(ctx, snapshot, replan_all(snapshot, ctx, reason), now)

    async def roll_forward(self, ctx: PlanContext, now: datetime) -> PlanResult:
        snapshot = await self.load(ctx)
        return await self._commit(ctx, snapshot, roll_forward(snapshot, ctx), now)

    async def set_stock(
        self, ctx: PlanContext, item_id: int, out: bool, now: datetime
    ) -> PlanContext:
        """Apply a stock change and return the updated context the caller must keep."""
        new_ctx = with_stock(ctx, item_id, out)
        snapshot = await self.load(new_ctx)
        new_ctx, result = apply_stock_change(snapshot, new_ctx, item_id, out)
        await self._commit(new_ctx, snapshot, result, now)
        return new_ctx

    async def suggest_swaps(self, ctx: PlanContext, day: date) -> list[Dinner]:
        snapshot = await self.load(ctx)
        return suggest_swaps(snapshot, ctx, day)

    async def swap(self, ctx: PlanContext, day: date, dinner_id: int, now: datetime) -> PlanResult:
        snapshot = await self.load(ctx)
        return await self._commit(ctx, snapshot, apply_swap(snapshot, ctx, day, dinner_id), now)

    async def swap_items(
        self, ctx: PlanContext, day: date, item_ids: list[int], now: datetime
    ) -> PlanResult:
        """Swap to a generated dinner identified by its item set, without requiring a stored ID."""
        snapshot = await self.load(ctx)
        wanted = tuple(sorted(set(item_ids)))
        dinner = next(
            (entry for entry in snapshot.dinners.values() if entry.item_ids == wanted), None
        )
        if dinner is None:
            raise SwapRejectedError("unknown_dinner")
        return await self._commit(ctx, snapshot, apply_swap(snapshot, ctx, day, dinner.id), now)

    async def check_rules(self, ctx: PlanContext, proposed: list[Rule] | None = None) -> RuleCheck:
        """Feasibility of `proposed` rules (or the stored set when None). Run before saving."""
        snapshot = await self.load(ctx, proposed)
        return check_rules(snapshot, ctx)

    async def _commit(
        self,
        ctx: PlanContext,
        snapshot: PlanSnapshot,
        result: PlanResult,
        now: datetime,
    ) -> PlanResult:
        transient_ids = {
            day.dinner_id
            for day in result.updated.values()
            if day.dinner_id is not None and day.dinner_id < 0
        }
        persisted_dinners: dict[int, Dinner] = {}
        if transient_ids:
            transient_item_sets = [
                snapshot.dinners[dinner_id].item_ids for dinner_id in sorted(transient_ids)
            ]
            persisted_ids = await self.menu.ensure_dinners(transient_item_sets)
            id_map = dict(zip(sorted(transient_ids), persisted_ids, strict=True))
            persisted_dinners = {
                id_map[transient_id]: Dinner(
                    id=id_map[transient_id],
                    item_ids=snapshot.dinners[transient_id].item_ids,
                )
                for transient_id in transient_ids
            }
            result = PlanResult(
                updated={
                    day: replace(record, dinner_id=id_map.get(record.dinner_id, record.dinner_id))
                    for day, record in result.updated.items()
                },
                warnings=result.warnings,
            )
        if result.updated:
            days = [replace(day, updated_at=now) for day in result.updated.values()]
            await self.menu.save_days(days)
        merged = replace(
            snapshot,
            dinners={**snapshot.dinners, **persisted_dinners},
            days={**snapshot.days, **result.updated},
        )
        feasibility = check_rules(merged, ctx)
        await self._sync_warnings([*result.warnings, *feasibility.warnings], now)
        return result

    async def _sync_warnings(self, drafts: list[WarningDraft], now: datetime) -> None:
        """Open new warnings, and resolve state warnings that no longer apply.

        Event warnings (replaced_dinner) are never auto-resolved. Each key is opened at most once
        while it is open.
        """
        desired: dict[WarningKey, WarningDraft] = {}
        for draft in drafts:
            desired.setdefault(_key(draft.code, draft.subject_type, draft.subject), draft)

        open_by_key: dict[WarningKey, WarningRecord] = {}
        for record in await self.warnings.list_open():
            open_by_key.setdefault(_key(record.code, record.subject_type, record.subject), record)

        for key, record in open_by_key.items():
            if key[0] in STATE_WARNING_CODES and key not in desired:
                await self.warnings.resolve_warning(record.id)

        for key, draft in desired.items():
            if key in open_by_key:
                continue
            await self.warnings.open_warning(
                WarningRecord(
                    id=0,
                    code=draft.code,
                    subject_type=draft.subject_type,
                    subject=draft.subject,
                    payload=dict(draft.payload),
                    created_at=now,
                )
            )


def _key(code: WarningCode, subject_type: WarningSubject, subject: str) -> WarningKey:
    return (WarningCode(code), WarningSubject(subject_type), subject)

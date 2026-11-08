"""Nutrition lookup service: permanent cache, backoff retries, manual entry, and confirmation."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import (
    Item,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    WarningCode,
    WarningRecord,
    WarningSubject,
)
from app.nutrition.clients import (
    MATCH_THRESHOLD,
    NutritionCandidate,
    NutritionClientError,
    NutritionSearchClient,
    best_match,
    match_score,
)
from app.ports import ItemRepository, NutritionRepository, WarningRepository

BASE_RETRY_DELAY = timedelta(minutes=15)
MAX_RETRY_DELAY = timedelta(hours=6)
MAX_AUTOMATIC_ATTEMPTS = 8


class NutritionError(Exception):
    """Invalid request, such as a manual value that is negative or not finite."""


class ItemNotFoundError(NutritionError):
    pass


def retry_delay(attempts: int) -> timedelta:
    """Backoff after the given number of failed attempts: 15 min, doubling, capped at 6 h."""
    delay = BASE_RETRY_DELAY * (2 ** max(attempts - 1, 0))
    return min(delay, MAX_RETRY_DELAY)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _check_amount(name: str, value: float | None, *, required: bool) -> float | None:
    if value is None:
        if required:
            raise NutritionError(f"{name} is required")
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NutritionError(f"{name} must be a number")
    if not math.isfinite(value) or value < 0:
        raise NutritionError(f"{name} must be a finite number of zero or more")
    return float(value)


class NutritionService:
    """Looks up per-100 g nutrition for items.

    Successful lookups are cached until a refresh is requested. Failures keep any existing
    data, open a ``nutrition_failed`` warning, and schedule a retry with backoff. Manual
    entries are never overwritten by a lookup.
    """

    def __init__(
        self,
        items: ItemRepository,
        nutrition: NutritionRepository,
        warnings: WarningRepository,
        sources: Sequence[NutritionSearchClient],
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not sources:
            raise ValueError("at least one nutrition source is required")
        self._items = items
        self._nutrition = nutrition
        self._warnings = warnings
        self._sources = list(sources)
        self._clock = clock

    async def get(self, item_id: int) -> Nutrition | None:
        return await self._nutrition.get_nutrition(item_id)

    async def lookup(self, item_id: int, *, refresh: bool = False) -> Nutrition:
        item = await self._require_item(item_id)
        current = await self._nutrition.get_nutrition(item_id)
        if current is not None:
            if current.source is NutritionSource.MANUAL:
                return current
            if current.status is NutritionStatus.OK and not refresh:
                return current
        return await self._search(item, current)

    async def set_manual(
        self,
        item_id: int,
        *,
        kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None = None,
    ) -> Nutrition:
        await self._require_item(item_id)
        record = Nutrition(
            item_id=item_id,
            source=NutritionSource.MANUAL,
            status=NutritionStatus.OK,
            kcal=_check_amount("kcal", kcal, required=True),
            protein_g=_check_amount("protein_g", protein_g, required=True),
            carbs_g=_check_amount("carbs_g", carbs_g, required=True),
            fat_g=_check_amount("fat_g", fat_g, required=True),
            fiber_g=_check_amount("fiber_g", fiber_g, required=False),
            user_confirmed=True,
            fetched_at=self._clock(),
        )
        await self._nutrition.save_nutrition(record)
        await self._resolve_open_warning(item_id)
        return record

    async def confirm_candidate(
        self,
        item_id: int,
        *,
        source: NutritionSource,
        external_id: str,
        matched_name: str,
        kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None = None,
    ) -> Nutrition:
        """Stores a candidate the user picked from a lookup, verified by the user.

        Rejects manual sources, names that do not match the item well enough, and incomplete
        macros, since only complete, user-confirmed data is verified.
        """
        item = await self._require_item(item_id)
        if source is NutritionSource.MANUAL:
            raise NutritionError("manual entries use the manual values, not a candidate")
        if not external_id.strip():
            raise NutritionError("external_id is required")
        if match_score(item.name, matched_name) < MATCH_THRESHOLD:
            raise NutritionError("the product name does not match the item closely enough")
        record = Nutrition(
            item_id=item_id,
            source=source,
            status=NutritionStatus.OK,
            external_id=external_id,
            matched_name=matched_name,
            kcal=_check_amount("kcal", kcal, required=True),
            protein_g=_check_amount("protein_g", protein_g, required=True),
            carbs_g=_check_amount("carbs_g", carbs_g, required=True),
            fat_g=_check_amount("fat_g", fat_g, required=True),
            fiber_g=_check_amount("fiber_g", fiber_g, required=False),
            user_confirmed=True,
            fetched_at=self._clock(),
        )
        await self._nutrition.save_nutrition(record)
        await self._resolve_open_warning(item_id)
        return record

    async def confirm_match(self, item_id: int) -> Nutrition:
        """Marks the current automatic match as user-confirmed, which makes it verified."""
        current = await self._nutrition.get_nutrition(item_id)
        if (
            current is None
            or current.source is NutritionSource.MANUAL
            or current.status is not NutritionStatus.OK
        ):
            raise NutritionError("there is no automatic match to confirm")
        confirmed = replace(current, user_confirmed=True)
        await self._nutrition.save_nutrition(confirmed)
        return confirmed

    async def run_due_retries(self) -> list[int]:
        """Re-runs lookups whose backoff has elapsed. Returns the item IDs that were retried."""
        now = self._clock()
        due: list[int] = []
        for warning in await self._warnings.list_open():
            if warning.code is not WarningCode.NUTRITION_FAILED:
                continue
            if warning.subject_type is not WarningSubject.ITEM:
                continue
            next_at = _parse_time(warning.payload.get("next_attempt_at"))
            if next_at is None or next_at > now:
                continue
            try:
                due.append(int(warning.subject))
            except ValueError:
                continue
        for item_id in due:
            await self.lookup(item_id, refresh=True)
        return due

    async def _require_item(self, item_id: int) -> Item:
        item = await self._items.get_item(item_id)
        if item is None:
            raise ItemNotFoundError(f"item {item_id} not found")
        return item

    async def _search(self, item: Item, current: Nutrition | None) -> Nutrition:
        now = self._clock()
        errors: list[NutritionClientError] = []
        attempted: NutritionSource | None = None
        for source in self._sources:
            if not source.enabled():
                continue
            attempted = source.source
            try:
                candidates = await source.search(item.name)
            except NutritionClientError as exc:
                errors.append(exc)
                continue
            match = best_match(item.name, candidates)
            if match is not None:
                return await self._store_match(item, current, match, now)
        if not errors:
            return await self._store_not_found(item, attempted, now)
        return await self._store_failure(item, current, errors, attempted, now)

    async def _store_not_found(
        self,
        item: Item,
        attempted: NutritionSource | None,
        now: datetime,
    ) -> Nutrition:
        """A successful search with no acceptable match: unverified, not a failure."""
        record = Nutrition(
            item_id=item.id,
            source=attempted or self._sources[0].source,
            status=NutritionStatus.NOT_FOUND,
            fetched_at=now,
        )
        await self._nutrition.save_nutrition(record)
        await self._resolve_open_warning(item.id)
        return record

    async def _store_match(
        self,
        item: Item,
        current: Nutrition | None,
        match: NutritionCandidate,
        now: datetime,
    ) -> Nutrition:
        same_product = (
            current is not None
            and current.source is match.source
            and current.external_id == match.external_id
        )
        record = Nutrition(
            item_id=item.id,
            source=match.source,
            status=NutritionStatus.OK,
            external_id=match.external_id,
            matched_name=match.matched_name,
            kcal=match.kcal,
            protein_g=match.protein_g,
            carbs_g=match.carbs_g,
            fat_g=match.fat_g,
            fiber_g=match.fiber_g,
            user_confirmed=bool(same_product and current and current.user_confirmed),
            fetched_at=now,
        )
        await self._nutrition.save_nutrition(record)
        await self._resolve_open_warning(item.id)
        return record

    async def _store_failure(
        self,
        item: Item,
        current: Nutrition | None,
        errors: list[NutritionClientError],
        attempted: NutritionSource | None,
        now: datetime,
    ) -> Nutrition:
        retryable = any(e.retryable for e in errors)
        reason = next((e.reason for e in errors if e.retryable), errors[0].reason)

        previous = await self._open_warning(item.id)
        attempts = _attempts(previous) + 1
        next_at = (
            now + retry_delay(attempts) if retryable and attempts < MAX_AUTOMATIC_ATTEMPTS else None
        )

        if current is not None and current.status is NutritionStatus.OK:
            kept = current
        else:
            source = attempted or self._sources[0].source
            kept = Nutrition(
                item_id=item.id,
                source=source,
                status=NutritionStatus.ERROR,
                fetched_at=None,
            )
            await self._nutrition.save_nutrition(kept)

        await self._resolve_open_warning(item.id)
        await self._warnings.open_warning(
            WarningRecord(
                id=0,
                code=WarningCode.NUTRITION_FAILED,
                subject_type=WarningSubject.ITEM,
                subject=str(item.id),
                payload={
                    "attempts": attempts,
                    "next_attempt_at": next_at.isoformat() if next_at else None,
                    "reason": reason,
                },
                created_at=now,
            )
        )
        return kept

    async def _open_warning(self, item_id: int) -> WarningRecord | None:
        for warning in await self._warnings.list_open():
            if (
                warning.code is WarningCode.NUTRITION_FAILED
                and warning.subject_type is WarningSubject.ITEM
                and warning.subject == str(item_id)
            ):
                return warning
        return None

    async def _resolve_open_warning(self, item_id: int) -> None:
        previous = await self._open_warning(item_id)
        if previous is not None:
            await self._warnings.resolve_warning(previous.id)


def _attempts(warning: WarningRecord | None) -> int:
    if warning is None:
        return 0
    value = warning.payload.get("attempts")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0

"""Tests for NutritionService: cache, refresh, backoff, manual entry, and confirmation."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import (
    Item,
    ItemType,
    Nutrition,
    NutritionSource,
    NutritionStatus,
    WarningCode,
    WarningRecord,
    WarningSubject,
)
from app.nutrition.clients import NutritionCandidate, NutritionClientError
from app.nutrition.service import (
    MAX_AUTOMATIC_ATTEMPTS,
    ItemNotFoundError,
    NutritionError,
    NutritionService,
    retry_delay,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FakeItems:
    def __init__(self, *items: Item) -> None:
        self._items = {i.id: i for i in items}

    async def list_items(self) -> list[Item]:
        return list(self._items.values())

    async def get_item(self, item_id: int) -> Item | None:
        return self._items.get(item_id)

    async def save_item(self, item: Item) -> Item:
        self._items[item.id] = item
        return item

    async def delete_item(self, item_id: int) -> None:
        self._items.pop(item_id, None)


class FakeNutrition:
    def __init__(self) -> None:
        self.rows: dict[int, Nutrition] = {}
        self.saves = 0

    async def get_nutrition(self, item_id: int) -> Nutrition | None:
        return self.rows.get(item_id)

    async def save_nutrition(self, nutrition: Nutrition) -> None:
        self.rows[nutrition.item_id] = nutrition
        self.saves += 1


class FakeWarnings:
    def __init__(self) -> None:
        self.records: list[WarningRecord] = []
        self._next_id = 1

    async def list_open(self) -> list[WarningRecord]:
        return [w for w in self.records if w.resolved_at is None]

    async def open_warning(self, warning: WarningRecord) -> WarningRecord:
        stored = WarningRecord(
            id=self._next_id,
            code=warning.code,
            subject_type=warning.subject_type,
            subject=warning.subject,
            payload=dict(warning.payload),
            created_at=warning.created_at,
        )
        self._next_id += 1
        self.records.append(stored)
        return stored

    async def resolve_warning(self, warning_id: int) -> None:
        for index, warning in enumerate(self.records):
            if warning.id == warning_id and warning.resolved_at is None:
                self.records[index] = WarningRecord(
                    id=warning.id,
                    code=warning.code,
                    subject_type=warning.subject_type,
                    subject=warning.subject,
                    payload=warning.payload,
                    created_at=warning.created_at,
                    resolved_at=T0,
                )

    def open_for(self, item_id: int) -> list[WarningRecord]:
        return [
            w
            for w in self.records
            if w.resolved_at is None
            and w.code is WarningCode.NUTRITION_FAILED
            and w.subject == str(item_id)
        ]


class ScriptedSource:
    """Search client that replays queued outcomes: a candidate list or an error."""

    def __init__(
        self,
        source: NutritionSource,
        *outcomes: list[NutritionCandidate] | NutritionClientError,
        enabled: bool = True,
    ) -> None:
        self.source = source
        self._outcomes = list(outcomes)
        self._enabled = enabled
        self.queries: list[str] = []

    def enabled(self) -> bool:
        return self._enabled

    async def search(self, query: str) -> list[NutritionCandidate]:
        self.queries.append(query)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, NutritionClientError):
            raise outcome
        return outcome


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def _candidate(
    name: str = "Chicken breast fillet",
    external_id: str = "4006381333931",
    source: NutritionSource = NutritionSource.OPEN_FOOD_FACTS,
    kcal: float = 110.0,
) -> NutritionCandidate:
    return NutritionCandidate(
        source=source,
        external_id=external_id,
        matched_name=name,
        kcal=kcal,
        protein_g=23.1,
        carbs_g=0.4,
        fat_g=1.9,
        fiber_g=0.0,
    )


ITEM = Item(id=1, name="Chicken breast", type=ItemType.PROTEIN)


def _service(
    *sources: ScriptedSource,
    items: tuple[Item, ...] = (ITEM,),
) -> tuple[NutritionService, FakeNutrition, FakeWarnings, Clock]:
    clock = Clock()
    nutrition = FakeNutrition()
    warnings = FakeWarnings()
    service = NutritionService(FakeItems(*items), nutrition, warnings, list(sources), clock=clock)
    return service, nutrition, warnings, clock


async def test_lookup_stores_match_unverified_and_keeps_matched_name() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [_candidate()])
    service, nutrition, warnings, _ = _service(off)

    result = await service.lookup(1)

    assert result.status is NutritionStatus.OK
    assert result.source is NutritionSource.OPEN_FOOD_FACTS
    assert result.matched_name == "Chicken breast fillet"
    assert result.kcal == 110.0
    assert result.user_confirmed is False
    assert result.fetched_at == T0
    assert nutrition.rows[1] == result
    assert warnings.records == []


async def test_successful_lookup_is_cached_until_refresh() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        [_candidate()],
        [_candidate(kcal=120.0)],
    )
    service, _, _, _ = _service(off)

    await service.lookup(1)
    cached = await service.lookup(1)
    assert cached.kcal == 110.0
    assert len(off.queries) == 1

    refreshed = await service.lookup(1, refresh=True)
    assert refreshed.kcal == 120.0
    assert len(off.queries) == 2


async def test_unknown_item_raises() -> None:
    service, _, _, _ = _service(ScriptedSource(NutritionSource.OPEN_FOOD_FACTS))
    with pytest.raises(ItemNotFoundError):
        await service.lookup(99)


async def test_no_match_sets_not_found_without_warning() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [_candidate(name="Beef stew")])
    service, nutrition, warnings, _ = _service(off)

    result = await service.lookup(1)

    assert result.status is NutritionStatus.NOT_FOUND
    assert result.kcal is None
    assert nutrition.rows[1].status is NutritionStatus.NOT_FOUND
    assert warnings.open_for(1) == []


async def test_failure_opens_nutrition_failed_warning_with_backoff() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("unavailable", retryable=True),
    )
    service, nutrition, warnings, _clock = _service(off)

    result = await service.lookup(1)

    assert result.status is NutritionStatus.ERROR
    assert nutrition.rows[1].status is NutritionStatus.ERROR
    (warning,) = warnings.open_for(1)
    assert warning.code is WarningCode.NUTRITION_FAILED
    assert warning.subject_type is WarningSubject.ITEM
    assert warning.payload["attempts"] == 1
    assert warning.payload["reason"] == "unavailable"
    assert warning.payload["next_attempt_at"] == (T0 + retry_delay(1)).isoformat()


async def test_failure_keeps_previous_verified_data() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        [_candidate()],
        NutritionClientError("network", retryable=True),
    )
    service, _nutrition, warnings, _ = _service(off)
    await service.lookup(1)
    await service.confirm_match(1)

    result = await service.lookup(1, refresh=True)

    assert result.status is NutritionStatus.OK
    assert result.kcal == 110.0
    assert result.user_confirmed is True
    assert len(warnings.open_for(1)) == 1


async def test_repeated_failures_increase_attempts_and_keep_single_warning() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("network", retryable=True),
        NutritionClientError("network", retryable=True),
    )
    service, _, warnings, _ = _service(off)

    await service.lookup(1)
    await service.lookup(1, refresh=True)

    (warning,) = warnings.open_for(1)
    assert warning.payload["attempts"] == 2


async def test_non_retryable_failure_has_no_next_attempt() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("auth", retryable=False),
    )
    service, _, warnings, _ = _service(off)

    await service.lookup(1)

    (warning,) = warnings.open_for(1)
    assert warning.payload["next_attempt_at"] is None
    assert warning.payload["reason"] == "auth"


async def test_automatic_retries_stop_after_limit() -> None:
    attempts = MAX_AUTOMATIC_ATTEMPTS
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        *[NutritionClientError("network", retryable=True) for _ in range(attempts)],
    )
    service, _, warnings, _ = _service(off)

    for _ in range(attempts):
        await service.lookup(1, refresh=True)

    (warning,) = warnings.open_for(1)
    assert warning.payload["attempts"] == attempts
    assert warning.payload["next_attempt_at"] is None


async def test_success_after_failure_resolves_warning() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("network", retryable=True),
        [_candidate()],
    )
    service, _, warnings, _ = _service(off)

    await service.lookup(1)
    await service.lookup(1, refresh=True)

    assert warnings.open_for(1) == []
    assert [w for w in warnings.records if w.resolved_at is not None]


async def test_usda_failure_falls_back_to_open_food_facts_result() -> None:
    usda = ScriptedSource(
        NutritionSource.USDA,
        NutritionClientError("unavailable", retryable=True),
    )
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [_candidate()])
    warnings = FakeWarnings()
    service = NutritionService(
        FakeItems(ITEM), FakeNutrition(), warnings, [usda, off], clock=Clock()
    )

    result = await service.lookup(1)

    assert result.source is NutritionSource.OPEN_FOOD_FACTS
    assert result.status is NutritionStatus.OK
    assert warnings.open_for(1) == []


async def test_disabled_usda_is_skipped_without_searching() -> None:
    usda = ScriptedSource(NutritionSource.USDA, enabled=False)
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [_candidate()])
    nutrition = FakeNutrition()
    service = NutritionService(
        FakeItems(ITEM), nutrition, FakeWarnings(), [usda, off], clock=Clock()
    )

    await service.lookup(1)

    assert usda.queries == []
    assert nutrition.rows[1].source is NutritionSource.OPEN_FOOD_FACTS


async def test_not_found_after_failure_resolves_warning_without_new_one() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("network", retryable=True),
        [],
    )
    service, _, warnings, _ = _service(off)
    await service.lookup(1)
    assert len(warnings.open_for(1)) == 1

    result = await service.lookup(1, refresh=True)

    assert result.status is NutritionStatus.NOT_FOUND
    assert warnings.open_for(1) == []


async def test_usda_match_used_when_off_has_no_match() -> None:
    usda = ScriptedSource(
        NutritionSource.USDA,
        [_candidate(name="Chicken breast, raw", external_id="747", source=NutritionSource.USDA)],
    )
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [])
    service = NutritionService(
        FakeItems(ITEM), FakeNutrition(), FakeWarnings(), [off, usda], clock=Clock()
    )

    result = await service.lookup(1)

    assert result.source is NutritionSource.USDA
    assert result.external_id == "747"


async def test_refresh_to_different_product_clears_confirmation() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        [_candidate(external_id="A")],
        [_candidate(external_id="B")],
    )
    service, _, _, _ = _service(off)
    await service.lookup(1)
    await service.confirm_match(1)

    result = await service.lookup(1, refresh=True)

    assert result.external_id == "B"
    assert result.user_confirmed is False


async def test_refresh_same_product_keeps_confirmation() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        [_candidate(external_id="A")],
        [_candidate(external_id="A", kcal=112.0)],
    )
    service, _, _, _ = _service(off)
    await service.lookup(1)
    await service.confirm_match(1)

    result = await service.lookup(1, refresh=True)

    assert result.kcal == 112.0
    assert result.user_confirmed is True


async def test_confirm_marks_match_verified() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [_candidate()])
    service, nutrition, _, _ = _service(off)
    await service.lookup(1)

    confirmed = await service.confirm_match(1)

    assert confirmed.user_confirmed is True
    assert nutrition.rows[1].user_confirmed is True


async def test_confirm_without_match_is_rejected() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS, [])
    service, _, _, _ = _service(off)
    with pytest.raises(NutritionError):
        await service.confirm_match(1)


async def test_manual_entry_is_confirmed_and_never_overwritten_by_lookup() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS)
    service, nutrition, _, _ = _service(off)

    manual = await service.set_manual(1, kcal=200, protein_g=30, carbs_g=0, fat_g=5, fiber_g=None)

    assert manual.source is NutritionSource.MANUAL
    assert manual.user_confirmed is True
    assert manual.status is NutritionStatus.OK
    assert manual.fetched_at == T0

    again = await service.lookup(1, refresh=True)
    assert again.source is NutritionSource.MANUAL
    assert off.queries == []
    assert nutrition.rows[1].kcal == 200


async def test_manual_entry_resolves_open_failure_warning() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("network", retryable=True),
    )
    service, _, warnings, _ = _service(off)
    await service.lookup(1)
    assert len(warnings.open_for(1)) == 1

    await service.set_manual(1, kcal=200, protein_g=30, carbs_g=0, fat_g=5)

    assert warnings.open_for(1) == []


@pytest.mark.parametrize(
    "bad",
    [-1.0, float("nan"), float("inf"), True, "100"],
)
async def test_manual_entry_rejects_invalid_amounts(bad) -> None:
    service, nutrition, _, _ = _service(ScriptedSource(NutritionSource.OPEN_FOOD_FACTS))
    with pytest.raises(NutritionError):
        await service.set_manual(1, kcal=bad, protein_g=1, carbs_g=1, fat_g=1)
    assert 1 not in nutrition.rows


async def test_manual_entry_requires_macros_and_unknown_item_raises() -> None:
    service, _, _, _ = _service(ScriptedSource(NutritionSource.OPEN_FOOD_FACTS))
    with pytest.raises(ItemNotFoundError):
        await service.set_manual(99, kcal=1, protein_g=1, carbs_g=1, fat_g=1)
    with pytest.raises(NutritionError):
        await service.set_manual(1, kcal=None, protein_g=1, carbs_g=1, fat_g=1)  # type: ignore[arg-type]


async def test_run_due_retries_only_retries_elapsed_items() -> None:
    off = ScriptedSource(
        NutritionSource.OPEN_FOOD_FACTS,
        NutritionClientError("network", retryable=True),
        [_candidate()],
    )
    service, _, warnings, clock = _service(off)
    await service.lookup(1)

    assert await service.run_due_retries() == []
    assert len(off.queries) == 1

    clock.now = T0 + retry_delay(1)
    assert await service.run_due_retries() == [1]
    assert warnings.open_for(1) == []
    assert len(off.queries) == 2


async def test_run_due_retries_skips_warnings_with_unparseable_subject() -> None:
    off = ScriptedSource(NutritionSource.OPEN_FOOD_FACTS)
    service, _, warnings, clock = _service(off)
    await warnings.open_warning(
        WarningRecord(
            id=0,
            code=WarningCode.NUTRITION_FAILED,
            subject_type=WarningSubject.ITEM,
            subject="not-a-number",
            payload={"next_attempt_at": T0.isoformat()},
        )
    )
    clock.now = T0 + timedelta(days=1)
    assert await service.run_due_retries() == []


def test_retry_delay_doubles_and_caps() -> None:
    assert retry_delay(1) == timedelta(minutes=15)
    assert retry_delay(2) == timedelta(minutes=30)
    assert retry_delay(3) == timedelta(hours=1)
    assert retry_delay(10) == timedelta(hours=6)


def test_service_requires_a_source() -> None:
    with pytest.raises(ValueError):
        NutritionService(FakeItems(ITEM), FakeNutrition(), FakeWarnings(), [])

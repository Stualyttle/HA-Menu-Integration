"""Planner settings, dinner template and the per-run context.

Settings and template are not stored behind a port yet, so the caller passes them in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.errors import PlannerConfigError
from app.models import ItemType

WINDOW_MIN_DAYS = 7
WINDOW_MAX_DAYS = 60
DEFAULT_WINDOW_DAYS = 14
DEFAULT_REPEAT_GAP_DAYS = 14
DEFAULT_HOUSEHOLD_SIZE = 2
DEFAULT_BALANCE_TOLERANCE = 10.0
MAX_SLOT_COUNT = 2
MINIMUM_SPAN_DAYS = 7


def _default_targets() -> dict[ItemType, float]:
    return {ItemType.VEGETABLE: 50.0, ItemType.PROTEIN: 25.0, ItemType.CARB: 25.0}


def _default_template() -> dict[ItemType, int]:
    return {ItemType.PROTEIN: 1, ItemType.VEGETABLE: 1, ItemType.CARB: 1}


@dataclass(slots=True)
class PlanSettings:
    window_days: int = DEFAULT_WINDOW_DAYS
    household_size: int = DEFAULT_HOUSEHOLD_SIZE
    repeat_gap_days: int = DEFAULT_REPEAT_GAP_DAYS
    balance_targets: dict[ItemType, float] = field(default_factory=_default_targets)
    balance_tolerance: float = DEFAULT_BALANCE_TOLERANCE

    def __post_init__(self) -> None:
        if not WINDOW_MIN_DAYS <= self.window_days <= WINDOW_MAX_DAYS:
            raise PlannerConfigError(
                f"window_days must be between {WINDOW_MIN_DAYS} and {WINDOW_MAX_DAYS}"
            )
        if self.household_size < 1:
            raise PlannerConfigError("household_size must be at least 1")
        if self.repeat_gap_days < 0:
            raise PlannerConfigError("repeat_gap_days cannot be negative")
        if self.balance_tolerance < 0:
            raise PlannerConfigError("balance_tolerance cannot be negative")
        if set(self.balance_targets) != set(ItemType):
            raise PlannerConfigError("balance_targets needs protein, vegetable and carb")
        if abs(sum(self.balance_targets.values()) - 100.0) > 1e-9:
            raise PlannerConfigError("balance_targets must add up to 100")


@dataclass(slots=True)
class Template:
    slots: dict[ItemType, int] = field(default_factory=_default_template)

    def __post_init__(self) -> None:
        if set(self.slots) != set(ItemType):
            raise PlannerConfigError("template needs protein, vegetable and carb slots")
        for item_type, count in self.slots.items():
            if not 0 <= count <= MAX_SLOT_COUNT:
                raise PlannerConfigError(f"{item_type} slot count must be 0 to {MAX_SLOT_COUNT}")
        if sum(self.slots.values()) == 0:
            raise PlannerConfigError("template must have at least one item per dinner")


@dataclass(slots=True, frozen=True)
class PlanContext:
    """Everything the engine needs to know about 'now' and the household.

    `today` and the time zones are injected so the engine never reads the system clock.
    """

    today: date
    timezone: str
    settings: PlanSettings = field(default_factory=PlanSettings)
    template: Template = field(default_factory=Template)
    out_of_stock: frozenset[int] = field(default_factory=frozenset)
    device_timezone: str | None = None
    revision: int = 0

"""Builds domain planning objects (PlanContext, MenuPlanner) from the stored add-on state."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.api.deps import local_today, planning_window
from app.db.stores import Stores
from app.domain.config import PlanContext, PlanSettings, Template
from app.domain.service import MenuPlanner
from app.models import ItemType

SETTING_TO_TARGET = {
    "vegetables": ItemType.VEGETABLE,
    "protein": ItemType.PROTEIN,
    "carbs": ItemType.CARB,
}
SYNCED_TIME_ZONE_KEY = "device_time_zone"
SYNCED_LANGUAGE_KEY = "device_language"


def add_on_time_zone() -> str:
    """The add-on's own zone name (TZ env var), falling back to UTC."""
    name = os.environ.get("TZ", "").strip()
    if name:
        try:
            ZoneInfo(name)
            return name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return "UTC"


def now_utc() -> datetime:
    return datetime.now(UTC)


def build_settings(stores: Stores) -> PlanSettings:
    raw = stores.settings.get_all()
    targets = {
        SETTING_TO_TARGET[key]: float(value)
        for key, value in raw["balance_targets"].items()
        if key in SETTING_TO_TARGET
    }
    return PlanSettings(
        window_days=int(raw["window_days"]),
        household_size=int(raw["household_size"]),
        repeat_gap_days=int(raw["repeat_gap_days"]),
        balance_targets=targets,
        balance_tolerance=float(raw["balance_targets"].get("tolerance", 10)),
    )


def build_template(stores: Stores) -> Template:
    counts = stores.template.get()
    return Template({ItemType(slot): int(count) for slot, count in counts.items()})


def build_context(stores: Stores, today: date | None = None) -> PlanContext:
    """Snapshot of settings, template and stock answers used by every planning call."""
    settings = build_settings(stores)
    out_of_stock = frozenset(
        item_id for item_id, answer in stores.stock.answers().items() if answer is False
    )
    device_zone = stores.settings.get_value(SYNCED_TIME_ZONE_KEY)
    return PlanContext(
        today=today or local_today(),
        timezone=add_on_time_zone(),
        settings=settings,
        template=build_template(stores),
        out_of_stock=out_of_stock,
        device_timezone=device_zone if isinstance(device_zone, str) else None,
    )


def build_planner(stores: Stores) -> MenuPlanner:
    return MenuPlanner(
        items=stores.items,
        categories=stores.categories,
        rules=stores.rules,
        menu=stores.menu,
        nutrition=stores.nutrition,
        warnings=stores.warnings,
    )


def window_range(stores: Stores) -> tuple[date, date]:
    return planning_window(stores)

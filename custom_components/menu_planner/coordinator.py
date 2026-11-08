"""DataUpdateCoordinator that polls the add-on and keeps HA language and TZ in sync."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MenuPlannerClient, MenuPlannerError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class MenuPlannerData:
    """Snapshot of add-on state used by sensors."""

    today: dict[str, Any] | None = None
    tomorrow: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    stock: list[dict[str, Any]] = field(default_factory=list)


def async_get_loaded_coordinator(hass: HomeAssistant) -> MenuPlannerCoordinator | None:
    """Return the coordinator of the loaded entry, or None when the integration is not loaded."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _as_days(payload: Any) -> list[dict[str, Any]]:
    """Accept either a bare list of days or a `{days: [...]}` wrapper."""
    if isinstance(payload, dict):
        payload = payload.get("days", [])
    return [day for day in payload if isinstance(day, dict)] if isinstance(payload, list) else []


def _day_for(days: list[dict[str, Any]], day: date) -> dict[str, Any] | None:
    iso = day.isoformat()
    return next((d for d in days if d.get("date") == iso), None)


class MenuPlannerCoordinator(DataUpdateCoordinator[MenuPlannerData]):
    """Polls the add-on every minute and syncs HA language and time zone."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: MenuPlannerClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> MenuPlannerData:
        try:
            await self._async_sync()
            today = dt_util.now().date()
            tomorrow = today + timedelta(days=1)

            today_day = await self._optional(self.client.get_menu_today())
            window = await self._optional(
                self.client.get_menu({"from": today.isoformat(), "to": tomorrow.isoformat()})
            )
            warnings = await self.client.get_warnings()
            stock = await self.client.get_stock(unanswered_first=True)
        except MenuPlannerError as err:
            if err.code == "invalid_auth":
                raise UpdateFailed(f"Add-on rejected the token: {err.message}") from err
            raise UpdateFailed(err.message) from err

        days = _as_days(window) if window is not None else []
        return MenuPlannerData(
            today=today_day if today_day is not None else _day_for(days, today),
            tomorrow=_day_for(days, tomorrow),
            warnings=warnings if isinstance(warnings, list) else [],
            stock=stock if isinstance(stock, list) else [],
        )

    async def _async_sync(self) -> None:
        """Send HA language and time zone so the add-on can match them."""
        result = await self._optional(
            self.client.sync(self.hass.config.language, str(self.hass.config.time_zone))
        )
        if isinstance(result, dict) and result.get("timezone_mismatch"):
            _LOGGER.warning(
                "Menu Planner add-on time zone differs from Home Assistant (%s)",
                self.hass.config.time_zone,
            )

    @staticmethod
    async def _optional(coro: Any) -> Any:
        """Return None when a planned route is not implemented (404)."""
        try:
            return await coro
        except MenuPlannerError as err:
            if err.status == 404:
                return None
            raise

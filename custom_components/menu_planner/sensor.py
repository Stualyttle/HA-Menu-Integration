"""Sensors that mirror the Menu Planner add-on state for dashboards and automations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MenuPlannerCoordinator, MenuPlannerData


def _dinner_text(day: dict[str, Any] | None) -> str | None:
    """Join the item names of a day's dinner, or None when there is no dinner."""
    if not day or not day.get("dinner"):
        return None
    items = day["dinner"].get("items") or []
    names = [item.get("name", "") for item in items if isinstance(item, dict)]
    return ", ".join(name for name in names if name) or None


def _warning_codes(data: MenuPlannerData) -> list[str]:
    return [str(w.get("code", "")) for w in data.warnings if isinstance(w, dict)]


def _out_of_stock(data: MenuPlannerData) -> list[str]:
    return [
        str(item.get("name", ""))
        for item in data.stock
        if isinstance(item, dict) and item.get("in_stock") is False
    ]


@dataclass(frozen=True, kw_only=True)
class MenuPlannerSensorDescription(SensorEntityDescription):
    """Sensor description with value and attribute extractors."""

    value_fn: Callable[[MenuPlannerData], Any]
    attrs_fn: Callable[[MenuPlannerData], dict[str, Any]] | None = None


SENSORS: tuple[MenuPlannerSensorDescription, ...] = (
    MenuPlannerSensorDescription(
        key="today_dinner",
        translation_key="today_dinner",
        value_fn=lambda data: _dinner_text(data.today),
    ),
    MenuPlannerSensorDescription(
        key="tomorrow_dinner",
        translation_key="tomorrow_dinner",
        value_fn=lambda data: _dinner_text(data.tomorrow),
    ),
    MenuPlannerSensorDescription(
        key="warnings",
        translation_key="warnings",
        value_fn=lambda data: len(data.warnings),
        attrs_fn=lambda data: {"codes": _warning_codes(data)},
    ),
    MenuPlannerSensorDescription(
        key="out_of_stock",
        translation_key="out_of_stock",
        value_fn=lambda data: len(_out_of_stock(data)),
        attrs_fn=lambda data: {"items": _out_of_stock(data)},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Menu Planner sensors for a config entry."""
    coordinator: MenuPlannerCoordinator = entry.runtime_data
    async_add_entities(
        MenuPlannerSensor(coordinator, entry, description) for description in SENSORS
    )


class MenuPlannerSensor(CoordinatorEntity[MenuPlannerCoordinator], SensorEntity):
    """A sensor backed by the Menu Planner coordinator."""

    entity_description: MenuPlannerSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MenuPlannerCoordinator,
        entry: ConfigEntry,
        description: MenuPlannerSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Menu Planner",
            manufacturer="Menu Planner",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)

"""Setup, sensors, sync and unload of the Menu Planner config entry."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.menu_planner.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import BASE, ENTRY_DATA, async_setup_entry_for_test, register_addon


def _sync_calls(mocker: AiohttpClientMocker) -> list:
    return [call for call in mocker.mock_calls if str(call[1]) == f"{BASE}/api/sync"]


def _entity_id(hass: HomeAssistant, entry_id: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry_id}_{key}")


async def test_setup_creates_sensors(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    entry = await async_setup_entry_for_test(hass)

    assert entry.state is ConfigEntryState.LOADED

    today = hass.states.get(_entity_id(hass, entry.entry_id, "today_dinner"))
    tomorrow = hass.states.get(_entity_id(hass, entry.entry_id, "tomorrow_dinner"))
    warnings = hass.states.get(_entity_id(hass, entry.entry_id, "warnings"))
    out_of_stock = hass.states.get(_entity_id(hass, entry.entry_id, "out_of_stock"))

    assert today is not None
    assert today.state == "Pasta, Salad"
    assert tomorrow is not None
    assert tomorrow.state == "Soup"
    assert warnings is not None
    assert warnings.state == "1"
    assert warnings.attributes["codes"] == ["low_protein"]
    assert out_of_stock is not None
    assert out_of_stock.state == "2"
    assert out_of_stock.attributes["items"] == ["Milk", "Flour"]


async def test_setup_retries_when_add_on_unreachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    import aiohttp

    register_addon(aioclient_mock, sync={"exc": aiohttp.ClientConnectionError()})
    entry = MockConfigEntry(domain=DOMAIN, data=dict(ENTRY_DATA), unique_id=DOMAIN)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_invalid_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    register_addon(aioclient_mock, sync={"status": 401, "json": {"detail": "bad token"}})
    entry = MockConfigEntry(domain=DOMAIN, data=dict(ENTRY_DATA), unique_id=DOMAIN)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_sync_sends_language_and_time_zone(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    hass.config.language = "nl"

    await async_setup_entry_for_test(hass)

    calls = _sync_calls(addon)
    assert calls, "sync must run on every coordinator poll"
    _, _, body, headers = calls[0]
    assert body == {"language": "nl", "time_zone": "Europe/Amsterdam"}
    assert headers["X-Menu-Planner-Token"] == ENTRY_DATA["token"]


async def test_timezone_mismatch_logs_warning(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, frozen_now: None
) -> None:
    register_addon(aioclient_mock, sync={"json": {"timezone_mismatch": True}})

    with patch("custom_components.menu_planner.coordinator._LOGGER") as logger:
        entry = await async_setup_entry_for_test(hass)

    assert entry.state is ConfigEntryState.LOADED
    logger.warning.assert_called_once()


async def test_missing_sync_route_is_tolerated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, frozen_now: None
) -> None:
    register_addon(aioclient_mock, sync={"status": 404, "json": {"detail": "Not Found"}})

    entry = await async_setup_entry_for_test(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_unload_removes_entities_and_stops_polling(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    entry: MockConfigEntry = await async_setup_entry_for_test(hass)
    today_entity = _entity_id(hass, entry.entry_id, "today_dinner")
    assert hass.states.get(today_entity) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(today_entity)
    assert state is None or state.state == "unavailable"

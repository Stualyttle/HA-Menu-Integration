"""Services proxy the right add-on path and body, and fail cleanly when not loaded."""

from __future__ import annotations

import pytest
import voluptuous as vol
from custom_components.menu_planner.const import (
    DOMAIN,
    SERVICE_LOG_EATEN,
    SERVICE_SET_STOCK,
    SERVICE_SWAP_TODAY,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import BASE, TODAY, async_setup_entry_for_test, envelope, register_addon


def _calls(mocker: AiohttpClientMocker, method: str, path: str) -> list:
    return [
        call
        for call in mocker.mock_calls
        if call[0].upper() == method and str(call[1]) == f"{BASE}{path}"
    ]


async def test_log_eaten_defaults_to_today(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    await hass.services.async_call(DOMAIN, SERVICE_LOG_EATEN, {}, blocking=True)

    assert len(_calls(addon, "POST", f"/api/menu/{TODAY}/eaten")) == 1


async def test_log_eaten_uses_given_date(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    await hass.services.async_call(DOMAIN, SERVICE_LOG_EATEN, {"date": "2026-05-03"}, blocking=True)

    assert len(_calls(addon, "POST", "/api/menu/2026-05-03/eaten")) == 1


async def test_set_stock_sends_in_stock(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_STOCK, {"item": 3, "in_stock": True}, blocking=True
    )

    calls = _calls(addon, "PUT", "/api/stock/3")
    assert len(calls) == 1
    assert calls[0][2] == {"in_stock": True}


async def test_set_stock_rejects_invalid_item(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_STOCK, {"item": -1}, blocking=True)


async def test_swap_today_posts_dinner_id(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    await hass.services.async_call(DOMAIN, SERVICE_SWAP_TODAY, {"dinner_id": 12}, blocking=True)

    calls = _calls(addon, "POST", f"/api/menu/{TODAY}/swap")
    assert len(calls) == 1
    assert calls[0][2] == {"dinner_id": 12}


async def test_swap_today_requires_dinner_id(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    await async_setup_entry_for_test(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, SERVICE_SWAP_TODAY, {}, blocking=True)


async def test_add_on_error_maps_to_home_assistant_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, frozen_now: None
) -> None:
    register_addon(
        aioclient_mock,
        swap_apply={"status": 409, "json": envelope("conflict", "Day is locked")},
    )
    await async_setup_entry_for_test(hass)

    with pytest.raises(HomeAssistantError, match="Day is locked"):
        await hass.services.async_call(DOMAIN, SERVICE_SWAP_TODAY, {"dinner_id": 12}, blocking=True)


async def test_service_fails_when_entry_not_loaded(
    hass: HomeAssistant, addon: AiohttpClientMocker, frozen_now: None
) -> None:
    entry = await async_setup_entry_for_test(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_LOG_EATEN, {}, blocking=True)


async def test_services_registered_without_entry(hass: HomeAssistant) -> None:
    from custom_components.menu_planner import async_setup

    assert await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, SERVICE_LOG_EATEN)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_STOCK)
    assert hass.services.has_service(DOMAIN, SERVICE_SWAP_TODAY)

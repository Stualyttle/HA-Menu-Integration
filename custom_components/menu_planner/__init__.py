"""Menu Planner integration: add-on client, polling, services and websocket API.

Services and websocket commands are registered once in ``async_setup`` and are
never removed, so reloading the config entry keeps them available. Calls made
while no entry is loaded fail with ``not_loaded``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .api import MenuPlannerClient, MenuPlannerError
from .const import (
    ATTR_DATE,
    ATTR_DINNER_ID,
    ATTR_IN_STOCK,
    ATTR_ITEM,
    CARD_BUNDLE_FILENAME,
    CARD_BUNDLE_URL,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    DOMAIN,
    SERVICE_LOG_EATEN,
    SERVICE_SET_STOCK,
    SERVICE_SWAP_TODAY,
)
from .coordinator import MenuPlannerCoordinator, async_get_loaded_coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type MenuPlannerConfigEntry = ConfigEntry[MenuPlannerCoordinator]

WS_WINDOW = "menu_planner/window"
WS_TODAY = "menu_planner/today"
WS_STOCK = "menu_planner/stock"
WS_STOCK_PREVIEW = "menu_planner/stock/preview"
WS_STOCK_SET = "menu_planner/stock/set"
WS_EATEN = "menu_planner/eaten"
WS_SWAP_SUGGESTIONS = "menu_planner/swap/suggestions"
WS_SWAP_APPLY = "menu_planner/swap/apply"

SERVICE_LOG_EATEN_SCHEMA = vol.Schema({vol.Optional(ATTR_DATE): cv.date})
SERVICE_SET_STOCK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ITEM): cv.positive_int,
        vol.Optional(ATTR_IN_STOCK): vol.Any(None, cv.boolean),
    }
)
SERVICE_SWAP_TODAY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DINNER_ID): cv.positive_int,
        vol.Optional(ATTR_DATE): cv.date,
    }
)
CARD_BUNDLE_PATH = Path(__file__).parent / "www" / CARD_BUNDLE_FILENAME


def _day_or_today(value: date | None) -> date:
    return value if value is not None else dt_util.now().date()


async def _async_service(
    call: ServiceCall,
    action: Callable[[MenuPlannerClient], Awaitable[Any]],
) -> None:
    """Run a write action against the add-on, then refresh the coordinator."""
    coordinator = async_get_loaded_coordinator(call.hass)
    if coordinator is None:
        raise HomeAssistantError("Menu Planner is not loaded")
    try:
        await action(coordinator.client)
    except MenuPlannerError as err:
        raise HomeAssistantError(err.message) from err
    await coordinator.async_request_refresh()


async def _async_handle_log_eaten(call: ServiceCall) -> None:
    day = _day_or_today(call.data.get(ATTR_DATE))
    await _async_service(call, lambda client: client.log_eaten(day))


async def _async_handle_set_stock(call: ServiceCall) -> None:
    item = call.data[ATTR_ITEM]
    in_stock = call.data.get(ATTR_IN_STOCK)
    await _async_service(call, lambda client: client.set_stock(item, in_stock))


async def _async_handle_swap_today(call: ServiceCall) -> None:
    day = _day_or_today(call.data.get(ATTR_DATE))
    dinner_id = call.data[ATTR_DINNER_ID]
    await _async_service(call, lambda client: client.apply_swap(day, dinner_id=dinner_id))


async def _async_ws(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    action: Callable[[MenuPlannerClient], Awaitable[Any]],
    *,
    refresh: bool = False,
) -> None:
    """Run an add-on action for a websocket command and send result or error."""
    coordinator = async_get_loaded_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Menu Planner is not loaded")
        return
    try:
        result = await action(coordinator.client)
    except MenuPlannerError as err:
        connection.send_error(msg["id"], err.code, err.message)
        return
    if refresh:
        await coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): WS_TODAY})
@websocket_api.async_response
async def _ws_today(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    await _async_ws(hass, connection, msg, lambda c: c.get_menu_today())


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_WINDOW,
        vol.Optional("from"): cv.date,
        vol.Optional("to"): cv.date,
    }
)
@websocket_api.async_response
async def _ws_window(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    params = {key: msg[key].isoformat() for key in ("from", "to") if msg.get(key) is not None}
    await _async_ws(hass, connection, msg, lambda c: c.get_menu(params or None))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_STOCK,
        vol.Optional("unanswered_first", default=True): cv.boolean,
    }
)
@websocket_api.async_response
async def _ws_stock(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    unanswered_first = msg["unanswered_first"]
    await _async_ws(
        hass,
        connection,
        msg,
        lambda c: c.get_stock(unanswered_first=unanswered_first),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_STOCK_SET,
        vol.Required("item_id"): cv.positive_int,
        vol.Optional("in_stock"): vol.Any(None, cv.boolean),
    }
)
@websocket_api.async_response
async def _ws_stock_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    item_id = msg["item_id"]
    in_stock = msg.get("in_stock")
    await _async_ws(
        hass,
        connection,
        msg,
        lambda c: c.set_stock(item_id, in_stock),
        refresh=True,
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_STOCK_PREVIEW,
        vol.Required("item_id"): cv.positive_int,
        vol.Required("in_stock"): cv.boolean,
    }
)
@websocket_api.async_response
async def _ws_stock_preview(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    await _async_ws(
        hass,
        connection,
        msg,
        lambda client: client.preview_stock(msg["item_id"], msg["in_stock"]),
    )


@websocket_api.websocket_command({vol.Required("type"): WS_EATEN, vol.Required("date"): cv.date})
@websocket_api.async_response
async def _ws_eaten(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    day = msg["date"]
    await _async_ws(hass, connection, msg, lambda c: c.log_eaten(day), refresh=True)


@websocket_api.websocket_command(
    {vol.Required("type"): WS_SWAP_SUGGESTIONS, vol.Required("date"): cv.date}
)
@websocket_api.async_response
async def _ws_swap_suggestions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    day = msg["date"]
    await _async_ws(hass, connection, msg, lambda c: c.get_swap_suggestions(day))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SWAP_APPLY,
        vol.Required("date"): cv.date,
        vol.Optional("dinner_id"): cv.positive_int,
        vol.Optional("item_ids"): vol.All([cv.positive_int], vol.Length(min=1)),
    }
)
@websocket_api.async_response
async def _ws_swap_apply(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    day = msg["date"]
    dinner_id = msg.get("dinner_id")
    item_ids = msg.get("item_ids")
    if (dinner_id is None) == (item_ids is None):
        connection.send_error(
            msg["id"], "invalid_format", "Send exactly one of dinner_id or item_ids"
        )
        return
    await _async_ws(
        hass,
        connection,
        msg,
        lambda c: c.apply_swap(day, dinner_id=dinner_id, item_ids=item_ids),
        refresh=True,
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register services and websocket commands once for the domain."""
    if hass.http is None:
        _LOGGER.warning("HTTP is unavailable; the Lovelace card bundle cannot be served")
    else:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_BUNDLE_URL,
                    str(CARD_BUNDLE_PATH),
                    cache_headers=True,
                )
            ]
        )
        if frontend.DATA_EXTRA_MODULE_URL in hass.data:
            integration = await async_get_integration(hass, DOMAIN)
            frontend.add_extra_js_url(hass, f"{CARD_BUNDLE_URL}?v={integration.version}")
        else:
            _LOGGER.warning(
                "Home Assistant frontend is unavailable; Lovelace cards are not registered"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_EATEN,
        _async_handle_log_eaten,
        schema=SERVICE_LOG_EATEN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STOCK,
        _async_handle_set_stock,
        schema=SERVICE_SET_STOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SWAP_TODAY,
        _async_handle_swap_today,
        schema=SERVICE_SWAP_TODAY_SCHEMA,
    )

    for command in (
        _ws_today,
        _ws_window,
        _ws_stock,
        _ws_stock_set,
        _ws_stock_preview,
        _ws_eaten,
        _ws_swap_suggestions,
        _ws_swap_apply,
    ):
        websocket_api.async_register_command(hass, command)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MenuPlannerConfigEntry) -> bool:
    """Set up Menu Planner from a config entry."""
    client = MenuPlannerClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )
    coordinator = MenuPlannerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: MenuPlannerConfigEntry) -> None:
    """Reload when discovery or the options change the host, port or token."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MenuPlannerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

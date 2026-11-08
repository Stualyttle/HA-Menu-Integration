"""Config flow: hassio discovery, manual fallback, and abort rules."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.menu_planner.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import ENTRY_DATA, HOST, PORT, TOKEN, register_addon


def _discovery(**overrides: object) -> HassioServiceInfo:
    config = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN, **overrides}
    return HassioServiceInfo(
        config=config,
        name="Menu Planner",
        slug="menu_planner",
        uuid="abc123",
    )


async def test_discovery_creates_entry_after_confirm(
    hass: HomeAssistant, addon: AiohttpClientMocker
) -> None:
    """Discovery shows a confirm step and then creates the entry with the add-on config."""
    with patch("custom_components.menu_planner.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=_discovery()
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "hassio_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == DOMAIN


async def test_discovery_aborts_and_updates_existing_entry(
    hass: HomeAssistant, addon: AiohttpClientMocker
) -> None:
    """A repeat discovery aborts and updates the stored host, port, and token in place."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "10.0.0.1", CONF_PORT: 8000, CONF_TOKEN: "old"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=_discovery()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data == ENTRY_DATA


async def test_manual_flow_creates_entry(hass: HomeAssistant, addon: AiohttpClientMocker) -> None:
    """Manual fallback validates the token and creates the entry."""
    with patch("custom_components.menu_planner.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA
    assert addon.call_count >= 1


async def test_manual_flow_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 from the add-on shows invalid_auth on the form."""
    register_addon(
        aioclient_mock, stock={"status": 401, "json": {"detail": "invalid or missing token"}}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_manual_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A connection failure shows cannot_connect on the form."""
    from aiohttp import ClientConnectionError

    register_addon(aioclient_mock, stock={"exc": ClientConnectionError("down")})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_aborts_when_configured(
    hass: HomeAssistant, addon: AiohttpClientMocker
) -> None:
    """The manual flow aborts when an entry already exists."""
    MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

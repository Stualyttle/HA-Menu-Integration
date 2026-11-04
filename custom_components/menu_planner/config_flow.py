"""Config flow. The add-on is found through Supervisor discovery; there is no manual host entry."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_HOST, CONF_PORT, CONF_TOKEN, DISCOVERY_SERVICE, DOMAIN


class MenuPlannerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Menu Planner config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual setup is not offered. Install and start the add-on instead."""
        return self.async_abort(reason="no_discovery")

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Handle discovery from the add-on."""
        if discovery_info.service != DISCOVERY_SERVICE:
            return self.async_abort(reason="unknown_service")

        config = discovery_info.config
        data = {
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_TOKEN: config[CONF_TOKEN],
        }

        # A repeat discovery (new port or token after an add-on restart) updates the entry in place.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=data)

        self._discovered = data
        self.context["title_placeholders"] = {"name": "Menu Planner add-on"}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm the discovered add-on."""
        if self._discovered is None:
            return self.async_abort(reason="no_discovery")

        if user_input is not None:
            return self.async_create_entry(title="Menu Planner", data=self._discovered)

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"name": "Menu Planner add-on"},
            data_schema=vol.Schema({}),
        )

"""Config flow. Discovery from the add-on is preferred; manual host/port/token is the fallback."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import MenuPlannerClient, MenuPlannerError
from .const import CONF_HOST, CONF_PORT, CONF_TOKEN, DEFAULT_PORT, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_TOKEN): str,
    }
)


class MenuPlannerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Menu Planner config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual fallback when discovery is absent (for example, add-on on another host)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST].strip(),
                CONF_PORT: user_input[CONF_PORT],
                CONF_TOKEN: user_input[CONF_TOKEN].strip(),
            }
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            client = MenuPlannerClient(
                async_get_clientsession(self.hass),
                data[CONF_HOST],
                data[CONF_PORT],
                data[CONF_TOKEN],
            )
            try:
                await client.get_stock(unanswered_first=False)
            except MenuPlannerError as err:
                errors["base"] = "invalid_auth" if err.code == "invalid_auth" else "cannot_connect"
            else:
                return self.async_create_entry(title="Menu Planner", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Handle discovery from the add-on."""
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

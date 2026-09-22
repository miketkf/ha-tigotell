"""Config flow for TigoTell."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector

from tigotell_client import TigoTellClient, TigoTellConnectionError, TigoTellError

from .const import CONF_PORT, DEFAULT_PORT, DOMAIN


class TigoTellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle TigoTell configuration."""

    VERSION = 1

    async def _validate(self, host: str, port: int) -> str | None:
        client = TigoTellClient(host, port)
        try:
            await client.async_get_data()
        except TigoTellConnectionError:
            return "cannot_connect"
        except TigoTellError:
            return "invalid_response"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._validate(user_input[CONF_HOST], user_input[CONF_PORT])
            if error:
                errors["base"] = error
            else:
                if any(
                    entry.data.get(CONF_HOST) == user_input[CONF_HOST]
                    and entry.data.get(CONF_PORT) == user_input[CONF_PORT]
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=f"TigoTell ({user_input[CONF_HOST]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): selector.TextSelector(),
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._validate(user_input[CONF_HOST], user_input[CONF_PORT])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=user_input
                )
        entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): selector.TextSelector(),
                    vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

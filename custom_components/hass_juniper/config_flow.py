"""Config flow for hass_juniper."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_INTERFACE, CONF_SSH_KEY_PATH, DOMAIN, DEFAULT_USERNAME
from .migration import entry_unique_id, normalize_legacy_config


class HassJuniperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for hass_juniper."""

    VERSION = 1

    def _build_user_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        user_input = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, "Juniper Port")): str,
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_USERNAME,
                    default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                ): str,
                vol.Required(CONF_INTERFACE, default=user_input.get(CONF_INTERFACE, "")): str,
                vol.Required(
                    CONF_SSH_KEY_PATH,
                    default=user_input.get(CONF_SSH_KEY_PATH, ""),
                ): str,
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_data = normalize_legacy_config(user_input)
            if normalized_data is None:
                errors["base"] = "invalid_config"
            else:
                await self.async_set_unique_id(
                    entry_unique_id(
                        normalized_data[CONF_HOST],
                        normalized_data[CONF_INTERFACE],
                    )
                )
                self._abort_if_unique_id_configured(updates=normalized_data)

                return self.async_create_entry(
                    title=normalized_data[CONF_NAME],
                    data=normalized_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(user_input),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import YAML configuration into config entries."""
        normalized_data = normalize_legacy_config(import_config)
        if normalized_data is None:
            return self.async_abort(reason="invalid_import_config")

        await self.async_set_unique_id(
            entry_unique_id(
                normalized_data[CONF_HOST],
                normalized_data[CONF_INTERFACE],
            )
        )
        self._abort_if_unique_id_configured(updates=normalized_data)

        return self.async_create_entry(
            title=normalized_data[CONF_NAME],
            data=normalized_data,
        )

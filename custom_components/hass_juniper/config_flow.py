"""Config flow for hass_juniper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_SSH_KEY_PATH,
    CONF_UPLOADED_KEY_FILE,
    DEFAULT_USERNAME,
    DOMAIN,
)
from .key_storage import async_store_uploaded_private_key
from .migration import entry_unique_id, normalize_connection_config

SSH_KEY_PATH_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
SSH_KEY_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".key,application/pkcs8,text/plain")
)


class HassJuniperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for hass_juniper."""

    VERSION = 1

    def _build_user_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        user_input = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, "Juniper Switch")): str,
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Required(
                    CONF_USERNAME,
                    default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                ): str,
                vol.Optional(
                    CONF_SSH_KEY_PATH,
                    default=user_input.get(CONF_SSH_KEY_PATH, ""),
                ): SSH_KEY_PATH_SELECTOR,
                vol.Optional(CONF_UPLOADED_KEY_FILE): SSH_KEY_UPLOAD_SELECTOR,
            }
        )

    def _build_credentials_schema(self, user_input: Mapping[str, Any]) -> vol.Schema:
        """Build a schema for updating credentials only (host is fixed)."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                ): str,
                vol.Optional(
                    CONF_SSH_KEY_PATH,
                    default=user_input.get(CONF_SSH_KEY_PATH, ""),
                ): SSH_KEY_PATH_SELECTOR,
                vol.Optional(CONF_UPLOADED_KEY_FILE): SSH_KEY_UPLOAD_SELECTOR,
            }
        )

    async def _async_process_uploaded_key(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> None:
        """Store an uploaded SSH key file and inject its path into user_input."""
        uploaded_file_id = user_input.pop(CONF_UPLOADED_KEY_FILE, None)
        if not uploaded_file_id:
            return

        host = str(user_input.get(CONF_HOST, "")).strip()
        if not host:
            errors["base"] = "invalid_config"
            return

        try:
            user_input[CONF_SSH_KEY_PATH] = await async_store_uploaded_private_key(
                self.hass,
                host,
                uploaded_file_id,
            )
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "key_upload_failed"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = dict(user_input)
            await self._async_process_uploaded_key(user_input, errors)

            if not errors:
                normalized_data = normalize_connection_config(user_input)
                if normalized_data is None:
                    errors["base"] = "invalid_config"
                else:
                    await self.async_set_unique_id(entry_unique_id(normalized_data[CONF_HOST]))
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

    async def async_step_import(self, import_config: dict[str, Any]) -> ConfigFlowResult:
        """Import YAML configuration into config entries."""
        normalized_data = normalize_connection_config(import_config)
        if normalized_data is None:
            return self.async_abort(reason="invalid_import_config")

        await self.async_set_unique_id(entry_unique_id(normalized_data[CONF_HOST]))
        self._abort_if_unique_id_configured(updates=normalized_data)

        return self.async_create_entry(
            title=normalized_data[CONF_NAME],
            data=normalized_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the switch rejects stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect new credentials for an existing config entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            candidate = dict(user_input)
            candidate[CONF_HOST] = reauth_entry.data[CONF_HOST]
            candidate.setdefault(CONF_NAME, reauth_entry.data[CONF_NAME])
            await self._async_process_uploaded_key(candidate, errors)

            if not errors:
                normalized_data = normalize_connection_config(candidate)
                if normalized_data is None:
                    errors["base"] = "invalid_config"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=normalized_data
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._build_credentials_schema(reauth_entry.data),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating connection details for an existing config entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            user_input = dict(user_input)
            await self._async_process_uploaded_key(user_input, errors)

            if not errors:
                normalized_data = normalize_connection_config(user_input)
                if normalized_data is None:
                    errors["base"] = "invalid_config"
                else:
                    await self.async_set_unique_id(entry_unique_id(normalized_data[CONF_HOST]))
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        reconfigure_entry, data=normalized_data
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_user_schema(user_input or dict(reconfigure_entry.data)),
            errors=errors,
        )

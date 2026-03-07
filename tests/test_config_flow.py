"""Unit tests for hass_juniper config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow

from custom_components.hass_juniper.config_flow import HassJuniperConfigFlow
from custom_components.hass_juniper.const import CONF_INTERFACE, CONF_SSH_KEY_PATH


@pytest.mark.asyncio
async def test_user_step_creates_entry() -> None:
    """The user step should normalize values and create an entry."""
    flow = HassJuniperConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    result = await flow.async_step_user(
        {
            CONF_NAME: "Uplink",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_INTERFACE: "ge-0/0/0",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        }
    )

    assert result["type"] == "create_entry"
    flow._abort_if_unique_id_configured.assert_called_once()
    flow.async_create_entry.assert_called_once_with(
        title="Uplink",
        data={
            CONF_NAME: "Uplink",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_INTERFACE: "ge-0/0/0",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        },
    )


@pytest.mark.asyncio
async def test_import_maps_legacy_keys() -> None:
    """Import should map legacy YAML keys to the new schema."""
    flow = HassJuniperConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    result = await flow.async_step_import(
        {
            CONF_NAME: "Legacy",
            CONF_HOST: "10.0.0.3",
            "port": "ge-0/0/1",
            "file_path": "/config/.ssh/legacy_id_rsa",
        }
    )

    assert result["type"] == "create_entry"
    flow.async_create_entry.assert_called_once_with(
        title="Legacy",
        data={
            CONF_NAME: "Legacy",
            CONF_HOST: "10.0.0.3",
            CONF_USERNAME: "root",
            CONF_INTERFACE: "ge-0/0/1",
            CONF_SSH_KEY_PATH: "/config/.ssh/legacy_id_rsa",
        },
    )


@pytest.mark.asyncio
async def test_import_deduplicates_with_update_payload() -> None:
    """Import should invoke dedupe helper with normalized updates."""
    flow = HassJuniperConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock(
        side_effect=AbortFlow("already_configured")
    )

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_import(
            {
                CONF_NAME: "Updated",
                CONF_HOST: "10.0.0.4",
                CONF_INTERFACE: "ge-0/0/2",
                CONF_USERNAME: "admin",
                CONF_SSH_KEY_PATH: "/config/.ssh/new",
            }
        )

    assert err.value.reason == "already_configured"
    flow._abort_if_unique_id_configured.assert_called_once_with(
        updates={
            CONF_NAME: "Updated",
            CONF_HOST: "10.0.0.4",
            CONF_USERNAME: "admin",
            CONF_INTERFACE: "ge-0/0/2",
            CONF_SSH_KEY_PATH: "/config/.ssh/new",
        }
    )

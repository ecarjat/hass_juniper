"""Unit tests for hass_juniper config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow

from custom_components.hass_juniper.config_flow import HassJuniperConfigFlow
from custom_components.hass_juniper.const import CONF_SSH_KEY_PATH, CONF_UPLOADED_KEY_FILE


@pytest.mark.asyncio
async def test_user_step_creates_entry() -> None:
    """The user step should normalize values and create an entry."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    result = await flow.async_step_user(
        {
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        }
    )

    assert result["type"] == "create_entry"
    flow._abort_if_unique_id_configured.assert_called_once()
    flow.async_create_entry.assert_called_once_with(
        title="Switch A",
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        },
    )


@pytest.mark.asyncio
async def test_user_step_uploads_key_and_creates_entry() -> None:
    """Uploaded key file should be stored and referenced in entry data."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    with patch(
        "custom_components.hass_juniper.config_flow.async_store_uploaded_private_key",
        AsyncMock(return_value="/config/.storage/hass_juniper/sw1.key"),
    ) as store_key:
        result = await flow.async_step_user(
            {
                CONF_NAME: "Switch A",
                CONF_HOST: "10.0.0.2",
                CONF_USERNAME: "admin",
                CONF_UPLOADED_KEY_FILE: "11111111-1111-1111-1111-111111111111",
            }
        )

    assert result["type"] == "create_entry"
    store_key.assert_awaited_once()
    flow.async_create_entry.assert_called_once_with(
        title="Switch A",
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.storage/hass_juniper/sw1.key",
        },
    )


@pytest.mark.asyncio
async def test_import_maps_legacy_keys() -> None:
    """Import should map legacy YAML keys to the new schema."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
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
            CONF_SSH_KEY_PATH: "/config/.ssh/legacy_id_rsa",
        },
    )


@pytest.mark.asyncio
async def test_import_deduplicates_by_host() -> None:
    """Import dedupe should use host-level unique id and update payload."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock(
        side_effect=AbortFlow("already_configured")
    )

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_import(
            {
                CONF_NAME: "Updated",
                CONF_HOST: "10.0.0.4",
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
            CONF_SSH_KEY_PATH: "/config/.ssh/new",
        }
    )

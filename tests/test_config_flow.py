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
async def test_reauth_confirm_updates_entry_with_new_credentials() -> None:
    """Reauth confirm should merge new credentials into the existing entry data."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    reauth_entry = SimpleNamespace(
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/old_key",
        }
    )
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    result = await flow.async_step_reauth_confirm(
        {
            CONF_USERNAME: "root",
            CONF_SSH_KEY_PATH: "/config/.ssh/new_key",
        }
    )

    assert result["type"] == "abort"
    flow.async_update_reload_and_abort.assert_called_once_with(
        reauth_entry,
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "root",
            CONF_SSH_KEY_PATH: "/config/.ssh/new_key",
        },
    )


@pytest.mark.asyncio
async def test_reauth_step_shows_confirm_form() -> None:
    """The reauth entry step should delegate straight to reauth_confirm."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    reauth_entry = SimpleNamespace(
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/old_key",
        }
    )
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)

    result = await flow.async_step_reauth({})

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


@pytest.mark.asyncio
async def test_reconfigure_updates_entry_with_new_details() -> None:
    """Reconfigure should validate the new unique id and update the entry."""
    flow = HassJuniperConfigFlow()
    flow.hass = SimpleNamespace()
    reconfigure_entry = SimpleNamespace(
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/old_key",
        }
    )
    flow._get_reconfigure_entry = MagicMock(return_value=reconfigure_entry)
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_mismatch = MagicMock()
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    result = await flow.async_step_reconfigure(
        {
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/new_key",
        }
    )

    assert result["type"] == "abort"
    flow._abort_if_unique_id_mismatch.assert_called_once()
    flow.async_update_reload_and_abort.assert_called_once_with(
        reconfigure_entry,
        data={
            CONF_NAME: "Switch A",
            CONF_HOST: "10.0.0.2",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/new_key",
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

"""Unit tests for hass_juniper integration setup/unload."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.hass_juniper import async_setup, async_setup_entry, async_unload_entry
from custom_components.hass_juniper.const import CONF_SSH_KEY_PATH, DOMAIN
from custom_components.hass_juniper.models import JuniperRuntimeData


class FakeHass:
    """Minimal Home Assistant stub for unit testing."""

    def __init__(self) -> None:
        self.data: dict = {}
        self.created_tasks: list[asyncio.Task] = []
        self.config_entries = SimpleNamespace(
            flow=SimpleNamespace(async_init=AsyncMock()),
            async_update_entry=MagicMock(),
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
        )

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.created_tasks.append(task)
        return task


class FakeEntry:
    """Minimal config entry stub."""

    def __init__(self, data: dict, entry_id: str = "entry_1", unique_id: str | None = None):
        self.data = data
        self.entry_id = entry_id
        self.unique_id = unique_id
        self.runtime_data: JuniperRuntimeData | None = None
        self._on_unload_callbacks: list = []

    def async_on_unload(self, func) -> None:
        """Record a callback to run on unload, mirroring ConfigEntry."""
        self._on_unload_callbacks.append(func)


@pytest.mark.asyncio
async def test_async_setup_starts_single_import_per_host() -> None:
    """YAML migration should deduplicate import requests per host."""
    hass = FakeHass()

    assert await async_setup(
        hass,
        {
            "switch": [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "Uplink",
                    CONF_HOST: "10.0.0.1",
                    "port": "ge-0/0/1",
                    "file_path": "/config/.ssh/id_rsa",
                },
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_NAME: "Downlink",
                    CONF_HOST: "10.0.0.1",
                    "port": "ge-0/0/2",
                    "file_path": "/config/.ssh/id_rsa",
                },
            ]
        },
    )

    await asyncio.gather(*hass.created_tasks)

    hass.config_entries.flow.async_init.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_setup_entry_raises_not_ready_on_connect_error() -> None:
    """Connection errors should raise ConfigEntryNotReady."""
    hass = FakeHass()
    entry = FakeEntry(
        {
            CONF_NAME: "Switch",
            CONF_HOST: "10.0.0.10",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        }
    )

    with patch(
        "custom_components.hass_juniper.JunosPortClient.connect",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_raises_auth_failed_on_bad_credentials() -> None:
    """Authentication errors should raise ConfigEntryAuthFailed to trigger reauth."""
    from custom_components.hass_juniper.junos_client import JunosAuthenticationError

    hass = FakeHass()
    entry = FakeEntry(
        {
            CONF_NAME: "Switch",
            CONF_HOST: "10.0.0.10",
            CONF_USERNAME: "admin",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
        }
    )

    with patch(
        "custom_components.hass_juniper.JunosPortClient.connect",
        AsyncMock(side_effect=JunosAuthenticationError("bad credentials")),
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_unload_entry_disconnects_client() -> None:
    """Unload should unload platforms and disconnect client."""
    hass = FakeHass()
    entry = FakeEntry({}, entry_id="entry_2")

    client = AsyncMock()
    entry.runtime_data = JuniperRuntimeData(client=client, coordinator=MagicMock())

    assert await async_unload_entry(hass, entry)

    hass.config_entries.async_unload_platforms.assert_awaited_once()
    client.disconnect.assert_awaited_once_with(hass)

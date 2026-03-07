"""Unit tests for hass_juniper switch behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_juniper.const import CONF_INTERFACE
from custom_components.hass_juniper.switch import JuniperPortSwitch


class FakeCoordinator:
    """Minimal coordinator for CoordinatorEntity tests."""

    def __init__(self, data: bool, last_update_success: bool = True) -> None:
        self.data = data
        self.last_update_success = last_update_success
        self.async_request_refresh = AsyncMock()


@pytest.mark.asyncio
async def test_turn_on_uses_delete_disable() -> None:
    """Turning on should remove disable config and refresh state."""
    client = MagicMock()
    client.interface = "ge-0/0/3"
    client.set_disabled = AsyncMock()

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20::ge-0/0/3",
            data={
                CONF_NAME: "Uplink",
                CONF_HOST: "10.0.0.20",
                CONF_INTERFACE: "ge-0/0/3",
            },
        ),
        client,
        FakeCoordinator(data=False),
    )

    await entity.async_turn_on()

    client.set_disabled.assert_awaited_once_with(None, False)
    entity.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_off_uses_set_disable() -> None:
    """Turning off should set disable config and refresh state."""
    client = MagicMock()
    client.interface = "ge-0/0/3"
    client.set_disabled = AsyncMock()

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20::ge-0/0/3",
            data={
                CONF_NAME: "Uplink",
                CONF_HOST: "10.0.0.20",
                CONF_INTERFACE: "ge-0/0/3",
            },
        ),
        client,
        FakeCoordinator(data=False),
    )

    await entity.async_turn_off()

    client.set_disabled.assert_awaited_once_with(None, True)
    entity.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_on_failure_propagates_and_refreshes() -> None:
    """Command failures should raise and still request refresh."""
    client = MagicMock()
    client.interface = "ge-0/0/3"
    client.set_disabled = AsyncMock(side_effect=RuntimeError("commit failed"))

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20::ge-0/0/3",
            data={
                CONF_NAME: "Uplink",
                CONF_HOST: "10.0.0.20",
                CONF_INTERFACE: "ge-0/0/3",
            },
        ),
        client,
        FakeCoordinator(data=False),
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()

    entity.coordinator.async_request_refresh.assert_awaited_once()


def test_state_reflects_coordinator_data() -> None:
    """Switch state should map to coordinator disabled state."""
    client = MagicMock()
    client.interface = "ge-0/0/3"

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20::ge-0/0/3",
            data={
                CONF_NAME: "Uplink",
                CONF_HOST: "10.0.0.20",
                CONF_INTERFACE: "ge-0/0/3",
            },
        ),
        client,
        FakeCoordinator(data=True),
    )

    assert entity.is_on is False
    entity.coordinator.data = False
    assert entity.is_on is True

"""Unit tests for hass_juniper switch behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_juniper.switch import JuniperPortSwitch


class FakeCoordinator:
    """Minimal coordinator for CoordinatorEntity tests."""

    def __init__(self, data: dict[str, bool], last_update_success: bool = True) -> None:
        self.data = data
        self.last_update_success = last_update_success
        self.async_request_refresh = AsyncMock()


@pytest.mark.asyncio
async def test_turn_on_uses_delete_disable() -> None:
    """Turning on should remove disable config and refresh state."""
    client = MagicMock()
    client.set_disabled = AsyncMock()

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        FakeCoordinator(data={"ge-0/0/3": False}),
        "ge-0/0/3",
    )

    await entity.async_turn_on()

    client.set_disabled.assert_awaited_once_with(None, "ge-0/0/3", False)
    entity.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_off_uses_set_disable() -> None:
    """Turning off should set disable config and refresh state."""
    client = MagicMock()
    client.set_disabled = AsyncMock()

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        FakeCoordinator(data={"ge-0/0/3": False}),
        "ge-0/0/3",
    )

    await entity.async_turn_off()

    client.set_disabled.assert_awaited_once_with(None, "ge-0/0/3", True)
    entity.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_on_failure_propagates_and_refreshes() -> None:
    """Command failures should raise and still request refresh."""
    client = MagicMock()
    client.set_disabled = AsyncMock(side_effect=RuntimeError("commit failed"))

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        FakeCoordinator(data={"ge-0/0/3": False}),
        "ge-0/0/3",
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()

    entity.coordinator.async_request_refresh.assert_awaited_once()


def test_state_reflects_coordinator_data() -> None:
    """Switch state should map to coordinator disabled state."""
    client = MagicMock()

    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        FakeCoordinator(data={"ge-0/0/3": True}),
        "ge-0/0/3",
    )

    assert entity.is_on is False
    entity.coordinator.data["ge-0/0/3"] = False
    assert entity.is_on is True

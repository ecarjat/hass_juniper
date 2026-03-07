"""Unit tests for hass_juniper switch behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_juniper.junos_client import JunosInterfaceState
from custom_components.hass_juniper.switch import JuniperPortSwitch


class FakeCoordinator:
    """Minimal coordinator for CoordinatorEntity tests."""

    def __init__(
        self, data: dict[str, JunosInterfaceState], last_update_success: bool = True
    ) -> None:
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    admin_status="up",
                    oper_status="up",
                    speed="1Gbps",
                )
            }
        ),
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    admin_status="up",
                    oper_status="down",
                )
            }
        ),
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    admin_status="up",
                    oper_status="up",
                )
            }
        ),
        "ge-0/0/3",
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()

    entity.coordinator.async_request_refresh.assert_awaited_once()


def test_state_reflects_coordinator_data() -> None:
    """Switch state should map to coordinator admin state."""
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=True,
                    admin_status="down",
                    oper_status="down",
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.is_on is False
    entity.coordinator.data["ge-0/0/3"] = JunosInterfaceState(
        disabled=False,
        admin_status="up",
        oper_status="up",
        description="Kids Room",
        speed="1Gbps",
    )
    assert entity.is_on is True


def test_state_falls_back_to_disabled_when_admin_missing() -> None:
    """If admin status is unavailable, disabled flag is used as a fallback."""
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=True,
                    admin_status=None,
                    oper_status="down",
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.is_on is False


def test_name_and_attributes_include_interface_metadata() -> None:
    """Entity should expose description, admin/link status and speed."""
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
        FakeCoordinator(
            data={
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    description="Kids Room",
                    admin_status="up",
                    oper_status="down",
                    speed="1000mbps",
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.name == "ge-0/0/3 - Kids Room"
    assert entity.extra_state_attributes == {
        "interface": "ge-0/0/3",
        "description": "Kids Room",
        "admin_status": "up",
        "oper_status": "down",
        "speed": "1000mbps",
    }

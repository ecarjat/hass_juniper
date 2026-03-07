"""Unit tests for hass_juniper switch behavior."""

from __future__ import annotations

import asyncio
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
        self.async_set_updated_data = MagicMock(side_effect=self._set_updated_data)

    def _set_updated_data(self, data: dict[str, JunosInterfaceState]) -> None:
        self.data = data


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


@pytest.mark.asyncio
async def test_turn_off_is_optimistic_while_command_runs() -> None:
    """Toggle should remain in requested state while command is in-flight."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_disable(*_: object, **__: object) -> None:
        started.set()
        await release.wait()

    client = MagicMock()
    client.set_disabled = AsyncMock(side_effect=_slow_disable)

    coordinator = FakeCoordinator(
        data={
            "ge-0/0/3": JunosInterfaceState(
                disabled=False,
                admin_status="up",
                oper_status="up",
            )
        }
    )
    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        coordinator,
        "ge-0/0/3",
    )

    task = asyncio.create_task(entity.async_turn_off())
    await started.wait()

    assert entity.is_on is False
    assert entity.extra_state_attributes["pending"] is True

    release.set()
    await task
    assert entity.extra_state_attributes["pending"] is False


@pytest.mark.asyncio
async def test_turn_off_failure_rolls_back_optimistic_state() -> None:
    """On command failure, optimistic state should be rolled back then refreshed."""
    client = MagicMock()
    client.set_disabled = AsyncMock(side_effect=RuntimeError("commit failed"))

    coordinator = FakeCoordinator(
        data={
            "ge-0/0/3": JunosInterfaceState(
                disabled=False,
                admin_status="up",
                oper_status="up",
            )
        }
    )
    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        coordinator,
        "ge-0/0/3",
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()

    assert entity.is_on is True
    assert entity.extra_state_attributes["pending"] is False
    assert coordinator.async_set_updated_data.call_count == 2


@pytest.mark.asyncio
async def test_duplicate_toggle_is_ignored_while_command_in_flight() -> None:
    """Repeated toggles should be ignored while operation lock is held."""
    client = MagicMock()
    client.set_disabled = AsyncMock()

    coordinator = FakeCoordinator(
        data={
            "ge-0/0/3": JunosInterfaceState(
                disabled=False,
                admin_status="up",
                oper_status="up",
            )
        }
    )
    entity = JuniperPortSwitch(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        client,
        coordinator,
        "ge-0/0/3",
    )

    await entity._command_lock.acquire()
    try:
        await entity.async_turn_off()
    finally:
        entity._command_lock.release()

    client.set_disabled.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


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
        "pending": False,
        "description": "Kids Room",
        "admin_status": "up",
        "oper_status": "down",
        "speed": "1000mbps",
    }

"""Unit tests for hass_juniper port description text entity."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from custom_components.hass_juniper.junos_client import JunosInterfaceState
from custom_components.hass_juniper.text import JuniperPortDescriptionText


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


def _make_entity(client, coordinator, interface="ge-0/0/3") -> JuniperPortDescriptionText:
    return JuniperPortDescriptionText(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={CONF_NAME: "Switch", CONF_HOST: "10.0.0.20"},
        ),
        client,
        coordinator,
        interface,
    )


def test_name_and_value_reflect_description() -> None:
    """Entity name and value should track the interface description."""
    client = MagicMock()
    coordinator = FakeCoordinator(
        data={
            "ge-0/0/3": JunosInterfaceState(
                disabled=False,
                description="Kids Room",
                admin_status="up",
                oper_status="up",
                speed="1000mbps",
            )
        }
    )
    entity = _make_entity(client, coordinator)

    assert entity.name == "ge-0/0/3 - Kids Room description"
    assert entity.native_value == "Kids Room"
    assert entity.extra_state_attributes == {
        "interface": "ge-0/0/3",
        "admin_status": "up",
        "oper_status": "up",
        "speed": "1000mbps",
    }


def test_name_without_description() -> None:
    """Entity name should fall back when no description is set."""
    client = MagicMock()
    coordinator = FakeCoordinator(
        data={"ge-0/0/3": JunosInterfaceState(disabled=False)}
    )
    entity = _make_entity(client, coordinator)

    assert entity.name == "ge-0/0/3 description"
    assert entity.native_value is None


@pytest.mark.asyncio
async def test_set_value_updates_description_and_refreshes() -> None:
    """Setting a value should push it to the client and refresh afterward."""
    client = MagicMock()
    client.set_description = AsyncMock()
    coordinator = FakeCoordinator(
        data={"ge-0/0/3": JunosInterfaceState(disabled=False, description="Old")}
    )
    entity = _make_entity(client, coordinator)

    await entity.async_set_value("Kids Room")

    client.set_description.assert_awaited_once_with(None, "ge-0/0/3", "Kids Room")
    assert entity.native_value == "Kids Room"
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_value_failure_rolls_back_and_raises() -> None:
    """A failed commit should roll back the optimistic value and surface an error."""
    client = MagicMock()
    client.set_description = AsyncMock(side_effect=RuntimeError("commit failed"))
    coordinator = FakeCoordinator(
        data={"ge-0/0/3": JunosInterfaceState(disabled=False, description="Old")}
    )
    entity = _make_entity(client, coordinator)

    with pytest.raises(HomeAssistantError):
        await entity.async_set_value("New")

    assert entity.native_value == "Old"
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_value_empty_clears_description() -> None:
    """Setting an empty value should clear the description optimistically."""
    client = MagicMock()
    client.set_description = AsyncMock()
    coordinator = FakeCoordinator(
        data={"ge-0/0/3": JunosInterfaceState(disabled=False, description="Old")}
    )
    entity = _make_entity(client, coordinator)

    await entity.async_set_value("")

    assert entity.native_value is None

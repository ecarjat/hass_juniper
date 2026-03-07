"""Unit tests for hass_juniper link binary sensor behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.const import CONF_HOST, CONF_NAME

from custom_components.hass_juniper.binary_sensor import JuniperPortLinkBinarySensor
from custom_components.hass_juniper.junos_client import JunosInterfaceState


class FakeCoordinator:
    """Minimal coordinator for CoordinatorEntity tests."""

    def __init__(self, data: dict[str, JunosInterfaceState], last_update_success: bool = True):
        self.data = data
        self.last_update_success = last_update_success
        self.async_request_refresh = AsyncMock()


def test_link_binary_sensor_state_and_name() -> None:
    """Link sensor should map oper state and include description in name."""
    entity = JuniperPortLinkBinarySensor(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        FakeCoordinator(
            {
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    description="Kids Room",
                    admin_status="up",
                    oper_status="up",
                    speed="1000mbps",
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.name == "ge-0/0/3 - Kids Room link"
    assert entity.is_on is True
    assert entity.extra_state_attributes == {
        "interface": "ge-0/0/3",
        "description": "Kids Room",
        "admin_status": "up",
        "oper_status": "up",
        "speed": "1000mbps",
    }


def test_link_binary_sensor_unknown_oper_state() -> None:
    """Link sensor should be unknown if oper state is missing."""
    entity = JuniperPortLinkBinarySensor(
        SimpleNamespace(
            unique_id="10.0.0.20",
            data={
                CONF_NAME: "Switch",
                CONF_HOST: "10.0.0.20",
            },
        ),
        FakeCoordinator(
            {
                "ge-0/0/3": JunosInterfaceState(
                    disabled=False,
                    admin_status="up",
                    oper_status=None,
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.is_on is None

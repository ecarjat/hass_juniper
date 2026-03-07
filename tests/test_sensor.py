"""Unit tests for hass_juniper speed sensor behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.const import CONF_HOST, CONF_NAME

from custom_components.hass_juniper.junos_client import JunosInterfaceState
from custom_components.hass_juniper.sensor import JuniperPortSpeedSensor


class FakeCoordinator:
    """Minimal coordinator for CoordinatorEntity tests."""

    def __init__(self, data: dict[str, JunosInterfaceState], last_update_success: bool = True):
        self.data = data
        self.last_update_success = last_update_success
        self.async_request_refresh = AsyncMock()


def test_speed_sensor_value_name_and_attributes() -> None:
    """Speed sensor should expose current speed and metadata."""
    entity = JuniperPortSpeedSensor(
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
                    oper_status="down",
                    speed="1000mbps",
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.name == "ge-0/0/3 - Kids Room speed"
    assert entity.native_value == "1000mbps"
    assert entity.extra_state_attributes == {
        "interface": "ge-0/0/3",
        "description": "Kids Room",
        "admin_status": "up",
        "oper_status": "down",
    }


def test_speed_sensor_value_unknown_when_missing() -> None:
    """Speed sensor should be unknown when speed is unavailable."""
    entity = JuniperPortSpeedSensor(
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
                    oper_status="up",
                    speed=None,
                )
            }
        ),
        "ge-0/0/3",
    )

    assert entity.native_value is None

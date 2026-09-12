"""Runtime data models for hass_juniper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import JuniperPortsCoordinator
    from .junos_client import JunosPortClient


@dataclass
class JuniperRuntimeData:
    """Data stored on the config entry while it is loaded."""

    client: JunosPortClient
    coordinator: JuniperPortsCoordinator


type JuniperConfigEntry = ConfigEntry[JuniperRuntimeData]

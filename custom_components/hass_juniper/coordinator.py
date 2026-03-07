"""Shared coordinator for hass_juniper interface state refreshes."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .junos_client import JunosInterfaceState, JunosPortClient

_LOGGER = logging.getLogger(__name__)


class JuniperPortsCoordinator(DataUpdateCoordinator[dict[str, JunosInterfaceState]]):
    """Coordinator that refreshes interface metadata for all interfaces."""

    def __init__(self, hass: HomeAssistant, client: JunosPortClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.host}_ports",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, JunosInterfaceState]:
        """Read current interface metadata from the switch."""
        try:
            return await self._client.read_interface_states(self.hass)
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(f"Failed to refresh Juniper interface state: {err}") from err

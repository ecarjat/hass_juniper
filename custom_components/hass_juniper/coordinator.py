"""Shared coordinator for hass_juniper interface state refreshes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .junos_client import JunosAuthenticationError, JunosInterfaceState, JunosPortClient

if TYPE_CHECKING:
    from .models import JuniperConfigEntry

_LOGGER = logging.getLogger(__name__)


class JuniperPortsCoordinator(DataUpdateCoordinator[dict[str, JunosInterfaceState]]):
    """Coordinator that refreshes interface metadata for all interfaces."""

    def __init__(
        self, hass: HomeAssistant, entry: JuniperConfigEntry, client: JunosPortClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.host}_ports",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, JunosInterfaceState]:
        """Read current interface metadata from the switch."""
        try:
            return await self._client.read_interface_states(self.hass)
        except JunosAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed reading Juniper interface state: {err}"
            ) from err
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(f"Failed to refresh Juniper interface state: {err}") from err

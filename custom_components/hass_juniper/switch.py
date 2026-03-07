"""Switch platform for hass_juniper."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_INTERFACE, DEFAULT_SCAN_INTERVAL, DOMAIN
from .junos_client import JunosPortClient
from .migration import entry_unique_id, normalize_legacy_config

_LOGGER = logging.getLogger(__name__)


class JuniperPortCoordinator(DataUpdateCoordinator[bool]):
    """Coordinator that refreshes interface disabled state."""

    def __init__(self, hass: HomeAssistant, client: JunosPortClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{client.host}_{client.interface}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> bool:
        """Read the current disabled status from the switch."""
        try:
            return await self._client.read_disabled_state(self.hass)
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(f"Failed to refresh Juniper interface state: {err}") from err


class JuniperPortSwitch(CoordinatorEntity[JuniperPortCoordinator], SwitchEntity):
    """Represent a single Juniper interface admin state as a switch."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: JunosPortClient,
        coordinator: JuniperPortCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        host = entry.data[CONF_HOST]
        interface = entry.data[CONF_INTERFACE]
        self._attr_name = entry.data[CONF_NAME]
        self._attr_unique_id = entry.unique_id or entry_unique_id(host, interface)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=f"Juniper {host}",
            manufacturer="Juniper Networks",
        )

    @property
    def is_on(self) -> bool:
        """Return true when the interface is enabled (not disabled)."""
        if self.coordinator.data is None:
            return False
        return not self.coordinator.data

    @property
    def available(self) -> bool:
        """Return if the entity can currently be reached."""
        return super().available and self.coordinator.data is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the interface by removing the disable statement."""
        try:
            await self._client.set_disabled(self.hass, False)
        except Exception as err:  # pylint: disable=broad-except
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to enable interface {self._client.interface}"
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the interface."""
        try:
            await self._client.set_disabled(self.hass, True)
        except Exception as err:  # pylint: disable=broad-except
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to disable interface {self._client.interface}"
            ) from err

        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up hass_juniper switch entities from a config entry."""
    client: JunosPortClient = hass.data[DOMAIN][entry.entry_id]

    coordinator = JuniperPortCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([JuniperPortSwitch(entry, client, coordinator)])


def _schedule_yaml_import(hass: HomeAssistant, raw_config: Mapping[str, Any]) -> None:
    """Convert a legacy YAML switch platform to an import flow."""
    normalized_data = normalize_legacy_config(raw_config)
    if normalized_data is None:
        _LOGGER.warning(
            "Ignoring invalid YAML configuration for %s during migration", DOMAIN
        )
        return

    _LOGGER.warning(
        "YAML switch platform for %s is deprecated; importing into UI config entries",
        DOMAIN,
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=normalized_data,
        )
    )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Legacy sync YAML setup path (migration shim only)."""
    if config.get(CONF_PLATFORM) != DOMAIN:
        return

    _schedule_yaml_import(hass, config)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Legacy async YAML setup path (migration shim only)."""
    if config.get(CONF_PLATFORM) != DOMAIN:
        return

    _schedule_yaml_import(hass, config)

"""Switch platform for hass_juniper."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .junos_client import JunosInterfaceState, JunosPortClient
from .migration import entity_unique_id, entry_unique_id, normalize_connection_config

_LOGGER = logging.getLogger(__name__)


class JuniperPortsCoordinator(DataUpdateCoordinator[dict[str, JunosInterfaceState]]):
    """Coordinator that refreshes disabled state for all interfaces."""

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


class JuniperPortSwitch(CoordinatorEntity[JuniperPortsCoordinator], SwitchEntity):
    """Represent a Juniper interface admin state as a switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        client: JunosPortClient,
        coordinator: JuniperPortsCoordinator,
        interface: str,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._interface = interface
        host = entry.data[CONF_HOST]
        self._attr_name = interface
        self._attr_unique_id = entity_unique_id(host, interface)

        device_key = entry.unique_id or entry_unique_id(host)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=entry.data[CONF_NAME],
            manufacturer="Juniper Networks",
        )

    @property
    def is_on(self) -> bool:
        """Return true when the interface is enabled (not disabled)."""
        state = self.coordinator.data.get(self._interface)
        if state is None:
            return False
        return not state.disabled

    @property
    def name(self) -> str | None:
        """Return entity name including interface description when available."""
        state = self.coordinator.data.get(self._interface)
        if state is None or not state.description:
            return self._interface
        return f"{self._interface} - {state.description}"

    @property
    def available(self) -> bool:
        """Return if the entity can currently be reached."""
        return super().available and self._interface in self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose per-port operational metadata."""
        attributes: dict[str, str] = {"interface": self._interface}
        state = self.coordinator.data.get(self._interface)
        if state is None:
            return attributes

        if state.description:
            attributes["description"] = state.description
        if state.admin_status:
            attributes["admin_status"] = state.admin_status
        if state.oper_status:
            attributes["oper_status"] = state.oper_status
        if state.speed:
            attributes["speed"] = state.speed

        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the interface by removing the disable statement."""
        try:
            await self._client.set_disabled(self.hass, self._interface, False)
        except Exception as err:  # pylint: disable=broad-except
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to enable interface {self._interface}"
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the interface."""
        try:
            await self._client.set_disabled(self.hass, self._interface, True)
        except Exception as err:  # pylint: disable=broad-except
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to disable interface {self._interface}"
            ) from err

        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up hass_juniper switch entities from a config entry."""
    client: JunosPortClient = hass.data[DOMAIN][entry.entry_id]

    coordinator = JuniperPortsCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    known_interfaces: set[str] = set()

    @callback
    def _add_new_interfaces() -> None:
        current_interfaces = set((coordinator.data or {}).keys())
        new_interfaces = sorted(current_interfaces - known_interfaces)
        if not new_interfaces:
            return

        known_interfaces.update(new_interfaces)
        async_add_entities(
            [
                JuniperPortSwitch(entry, client, coordinator, interface)
                for interface in new_interfaces
            ]
        )

    _add_new_interfaces()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_interfaces))


def _schedule_yaml_import(hass: HomeAssistant, raw_config: Mapping[str, Any]) -> None:
    """Convert a legacy YAML switch platform to an import flow."""
    normalized_data = normalize_connection_config(raw_config)
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

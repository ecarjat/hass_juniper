"""Text platform for editing hass_juniper interface descriptions."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JuniperPortsCoordinator
from .junos_client import JunosInterfaceState, JunosPortClient
from .migration import entity_unique_id, entry_unique_id
from .models import JuniperConfigEntry

_LOGGER = logging.getLogger(__name__)


class JuniperPortDescriptionText(CoordinatorEntity[JuniperPortsCoordinator], TextEntity):
    """Represent a Junos interface description as an editable text entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:tag-outline"

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
        self._command_lock = asyncio.Lock()
        host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{entity_unique_id(host, interface)}::description"

        device_key = entry.unique_id or entry_unique_id(host)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=entry.data[CONF_NAME],
            manufacturer="Juniper Networks",
        )

    @property
    def name(self) -> str:
        """Return entity name including interface description when available."""
        state = self.coordinator.data.get(self._interface)
        if state is None or not state.description:
            return f"{self._interface} description"
        return f"{self._interface} - {state.description} description"

    @property
    def native_value(self) -> str | None:
        """Return the current interface description."""
        state = self.coordinator.data.get(self._interface)
        if state is None:
            return None
        return state.description

    @property
    def available(self) -> bool:
        """Return if the entity can currently be reached."""
        return super().available and self._interface in self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose per-port metadata useful for troubleshooting."""
        attributes: dict[str, str] = {"interface": self._interface}
        state = self.coordinator.data.get(self._interface)
        if state is None:
            return attributes

        if state.admin_status:
            attributes["admin_status"] = state.admin_status
        if state.oper_status:
            attributes["oper_status"] = state.oper_status
        if state.speed:
            attributes["speed"] = state.speed

        return attributes

    def _apply_optimistic_description(
        self, description: str
    ) -> dict[str, JunosInterfaceState]:
        """Optimistically update coordinator data so UI reflects the pending value."""
        previous_data = dict(self.coordinator.data or {})
        current_state = previous_data.get(self._interface)
        new_description = description.strip() or None

        if current_state is None:
            current_state = JunosInterfaceState(disabled=False, description=new_description)
        else:
            current_state = replace(current_state, description=new_description)

        optimistic_data = dict(previous_data)
        optimistic_data[self._interface] = current_state
        self.coordinator.async_set_updated_data(optimistic_data)
        return previous_data

    async def async_set_value(self, value: str) -> None:
        """Update the interface description on the switch."""
        async with self._command_lock:
            previous_data = self._apply_optimistic_description(value)
            try:
                await self._client.set_description(self.hass, self._interface, value)
            except Exception as err:  # pylint: disable=broad-except
                self.coordinator.async_set_updated_data(previous_data)
                try:
                    await self.coordinator.async_request_refresh()
                except Exception as refresh_err:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "Failed to refresh interface %s after description update failure: %s",
                        self._interface,
                        refresh_err,
                    )
                raise HomeAssistantError(
                    f"Failed to set description for interface {self._interface}"
                ) from err

            try:
                await self.coordinator.async_request_refresh()
            except Exception as refresh_err:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Failed to refresh interface %s after description update: %s",
                    self._interface,
                    refresh_err,
                )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JuniperConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up hass_juniper description text entities from a config entry."""
    client = entry.runtime_data.client
    coordinator = entry.runtime_data.coordinator

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
                JuniperPortDescriptionText(entry, client, coordinator, interface)
                for interface in new_interfaces
            ]
        )

    _add_new_interfaces()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_interfaces))

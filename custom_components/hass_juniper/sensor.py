"""Sensors for hass_juniper interface telemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import JuniperPortsCoordinator
from .migration import entity_unique_id, entry_unique_id


class JuniperPortSpeedSensor(CoordinatorEntity[JuniperPortsCoordinator], SensorEntity):
    """Represent reported speed of a Junos interface."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: JuniperPortsCoordinator,
        interface: str,
    ) -> None:
        super().__init__(coordinator)
        self._interface = interface
        host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{entity_unique_id(host, interface)}::speed"

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
            return f"{self._interface} speed"
        return f"{self._interface} - {state.description} speed"

    @property
    def native_value(self) -> str | None:
        """Return current speed reported by Junos."""
        state = self.coordinator.data.get(self._interface)
        if state is None:
            return None
        return state.speed

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

        if state.description:
            attributes["description"] = state.description
        if state.admin_status:
            attributes["admin_status"] = state.admin_status
        if state.oper_status:
            attributes["oper_status"] = state.oper_status

        return attributes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up hass_juniper speed sensors from a config entry."""
    runtime_data: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
    coordinator: JuniperPortsCoordinator = runtime_data[DATA_COORDINATOR]

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
                JuniperPortSpeedSensor(entry, coordinator, interface)
                for interface in new_interfaces
            ]
        )

    _add_new_interfaces()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_interfaces))

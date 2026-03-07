"""Junos API wrapper used by the hass_juniper integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from jnpr.junos import Device
else:
    Device = Any


class JunosPortClient:
    """Wrap Junos operations for a single interface."""

    def __init__(self, host: str, username: str, ssh_key_path: str, interface: str) -> None:
        self.host = host
        self.username = username
        self.ssh_key_path = ssh_key_path
        self.interface = interface
        self._device: Device | None = None
        self._operation_lock = asyncio.Lock()

    async def connect(self, hass: HomeAssistant) -> None:
        """Open a network session to the switch."""
        await hass.async_add_executor_job(self._connect_sync)

    async def disconnect(self, hass: HomeAssistant) -> None:
        """Close the network session."""
        await hass.async_add_executor_job(self._disconnect_sync)

    async def set_disabled(self, hass: HomeAssistant, disabled: bool) -> None:
        """Set interface disabled state."""
        async with self._operation_lock:
            await hass.async_add_executor_job(self._set_disabled_sync, disabled)

    async def read_disabled_state(self, hass: HomeAssistant) -> bool:
        """Read interface disabled state from device config."""
        async with self._operation_lock:
            return await hass.async_add_executor_job(self._read_disabled_state_sync)

    def _connect_sync(self) -> None:
        if self._device is not None:
            return

        from jnpr.junos import Device as JunosDevice

        device = JunosDevice(
            host=self.host,
            user=self.username,
            ssh_private_key_file=self.ssh_key_path,
            gather_facts=False,
        )
        device.open()
        self._device = device

    def _disconnect_sync(self) -> None:
        if self._device is None:
            return

        self._device.close()
        self._device = None

    def _set_disabled_sync(self, disabled: bool) -> None:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        from jnpr.junos.utils.config import Config

        command = (
            f"set interfaces {self.interface} disable"
            if disabled
            else f"delete interfaces {self.interface} disable"
        )

        config = Config(self._device)
        config.load(command, format="set")
        config.commit()

    def _read_disabled_state_sync(self) -> bool:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        output = self._device.cli(
            f"show configuration interfaces {self.interface} | display set | match disable",
            warning=False,
        )

        expected_line = f"set interfaces {self.interface} disable"
        return any(line.strip() == expected_line for line in output.splitlines())

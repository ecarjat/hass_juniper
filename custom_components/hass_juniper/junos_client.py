"""Junos API wrapper used by the hass_juniper integration."""

from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from jnpr.junos import Device
else:
    Device = Any


class JunosPortClient:
    """Wrap Junos operations for a switch with multiple interfaces."""

    def __init__(self, host: str, username: str, ssh_key_path: str) -> None:
        self.host = host
        self.username = username
        self.ssh_key_path = ssh_key_path
        self._device: Device | None = None
        self._operation_lock = asyncio.Lock()

    async def connect(self, hass: HomeAssistant) -> None:
        """Open a network session to the switch."""
        await hass.async_add_executor_job(self._connect_sync)

    async def disconnect(self, hass: HomeAssistant) -> None:
        """Close the network session."""
        await hass.async_add_executor_job(self._disconnect_sync)

    async def list_interfaces(self, hass: HomeAssistant) -> list[str]:
        """Return available interfaces on the switch."""
        async with self._operation_lock:
            return await hass.async_add_executor_job(self._list_interfaces_sync)

    async def read_disabled_states(self, hass: HomeAssistant) -> dict[str, bool]:
        """Read disabled state for all discovered interfaces."""
        async with self._operation_lock:
            return await hass.async_add_executor_job(self._read_disabled_states_sync)

    async def set_disabled(self, hass: HomeAssistant, interface: str, disabled: bool) -> None:
        """Set interface disabled state."""
        async with self._operation_lock:
            await hass.async_add_executor_job(self._set_disabled_sync, interface, disabled)

    def _connect_sync(self) -> None:
        if self._device is not None:
            return

        from jnpr.junos import Device as JunosDevice

        # Docker DNS setups may return NXDOMAIN for AAAA and break AF_UNSPEC
        # lookups used by ncclient. Resolve IPv4 first to avoid false negatives.
        transport_host = self._resolve_transport_host()

        device = JunosDevice(
            host=transport_host,
            user=self.username,
            ssh_private_key_file=self.ssh_key_path,
            gather_facts=False,
        )
        device.open()
        self._device = device

    def _resolve_transport_host(self) -> str:
        """Resolve host for transport, preferring IPv4 when available."""
        try:
            ipv4_results = socket.getaddrinfo(
                self.host,
                None,
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
        except socket.gaierror:
            return self.host

        if not ipv4_results:
            return self.host

        return ipv4_results[0][4][0]

    def _disconnect_sync(self) -> None:
        if self._device is None:
            return

        self._device.close()
        self._device = None

    def _normalize_interface_name(self, token: str) -> str | None:
        token = token.strip().rstrip(":")
        if not token or token in {"Interface", "Admin", "Link", "Proto"}:
            return None

        if token.startswith(("{", "->", "(")):
            return None

        base_name = token.split(".", 1)[0]
        if "/" in base_name:
            return base_name

        if base_name.startswith(
            ("ae", "irb", "vlan", "reth", "lo", "em", "fxp", "st0", "gr-", "lt-")
        ):
            return base_name

        return None

    def _list_interfaces_sync(self) -> list[str]:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        output = self._device.cli("show interfaces terse | no-more", warning=False)
        interfaces: set[str] = set()

        for line in output.splitlines():
            if not line.strip():
                continue

            token = line.split(maxsplit=1)[0]
            interface = self._normalize_interface_name(token)
            if interface is not None:
                interfaces.add(interface)

        return sorted(interfaces)

    def _read_disabled_states_sync(self) -> dict[str, bool]:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        interfaces = set(self._list_interfaces_sync())

        disabled_output = self._device.cli(
            'show configuration interfaces | display set | match " disable$"',
            warning=False,
        )

        disabled_interfaces: set[str] = set()
        for line in disabled_output.splitlines():
            tokens = line.split()
            if len(tokens) >= 4 and tokens[0] == "set" and tokens[1] == "interfaces":
                disabled_interfaces.add(tokens[2])

        interfaces.update(disabled_interfaces)
        return {interface: interface in disabled_interfaces for interface in sorted(interfaces)}

    def _set_disabled_sync(self, interface: str, disabled: bool) -> None:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        from jnpr.junos.utils.config import Config

        command = (
            f"set interfaces {interface} disable"
            if disabled
            else f"delete interfaces {interface} disable"
        )

        config = Config(self._device)
        config.load(command, format="set")
        config.commit()

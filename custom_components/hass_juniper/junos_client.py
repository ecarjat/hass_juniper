"""Junos API wrapper used by the hass_juniper integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import shlex
import socket
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from jnpr.junos import Device
else:
    Device = Any


class JunosAuthenticationError(Exception):
    """Raised when the Junos device rejects the configured credentials."""


@dataclass(frozen=True, slots=True)
class JunosInterfaceState:
    """Current admin state metadata for a Junos interface."""

    disabled: bool
    description: str | None = None
    admin_status: str | None = None
    oper_status: str | None = None
    speed: str | None = None


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
        interface_states = await self.read_interface_states(hass)
        return {
            interface: state.disabled
            for interface, state in interface_states.items()
        }

    async def read_interface_states(
        self, hass: HomeAssistant
    ) -> dict[str, JunosInterfaceState]:
        """Read interface disabled state and descriptions for all discovered interfaces."""
        async with self._operation_lock:
            return await hass.async_add_executor_job(self._read_interface_states_sync)

    async def set_disabled(self, hass: HomeAssistant, interface: str, disabled: bool) -> None:
        """Set interface disabled state."""
        async with self._operation_lock:
            await hass.async_add_executor_job(self._set_disabled_sync, interface, disabled)

    def _connect_sync(self) -> None:
        if self._device is not None:
            return

        from jnpr.junos import Device as JunosDevice
        from jnpr.junos.exception import ConnectAuthError

        # Docker DNS setups may return NXDOMAIN for AAAA and break AF_UNSPEC
        # lookups used by ncclient. Resolve IPv4 first to avoid false negatives.
        transport_host = self._resolve_transport_host()

        device = JunosDevice(
            host=transport_host,
            user=self.username,
            ssh_private_key_file=self.ssh_key_path,
            gather_facts=False,
        )
        try:
            device.open()
        except ConnectAuthError as err:
            raise JunosAuthenticationError(str(err)) from err
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
        interfaces = self._parse_interfaces_from_terse_output(output)
        return sorted(interfaces)

    def _read_interface_states_sync(self) -> dict[str, JunosInterfaceState]:
        if self._device is None:
            raise RuntimeError("Junos device connection is not initialized")

        terse_output = self._device.cli("show interfaces terse | no-more", warning=False)
        interfaces = self._parse_interfaces_from_terse_output(terse_output)
        statuses = self._parse_interface_statuses(terse_output)

        disabled_output = self._device.cli(
            'show configuration interfaces | display set | match " disable$"',
            warning=False,
        )

        disabled_interfaces = self._parse_disabled_interfaces(disabled_output)

        descriptions_output = self._device.cli(
            'show configuration interfaces | display set | match " description "',
            warning=False,
        )
        descriptions = self._parse_interface_descriptions(descriptions_output)

        media_output = self._device.cli("show interfaces media | no-more", warning=False)
        speeds = self._parse_interface_speeds(media_output)

        interfaces.update(disabled_interfaces)
        interfaces.update(descriptions)
        interfaces.update(statuses)
        interfaces.update(speeds)

        return {
            interface: JunosInterfaceState(
                disabled=interface in disabled_interfaces,
                description=descriptions.get(interface),
                admin_status=statuses.get(interface, (None, None))[0],
                oper_status=statuses.get(interface, (None, None))[1],
                speed=speeds.get(interface),
            )
            for interface in sorted(interfaces)
        }

    def _read_disabled_states_sync(self) -> dict[str, bool]:
        """Backward-compatible state helper for tests/callers expecting bools."""
        interface_states = self._read_interface_states_sync()
        return {
            interface: state.disabled
            for interface, state in interface_states.items()
        }

    def _parse_disabled_interfaces(self, disabled_output: str) -> set[str]:
        """Extract interfaces with a top-level admin-disable statement."""
        disabled_interfaces: set[str] = set()

        for line in disabled_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("inactive:"):
                continue

            tokens = stripped.split()
            if (
                len(tokens) == 4
                and tokens[0] == "set"
                and tokens[1] == "interfaces"
                and tokens[3] == "disable"
            ):
                disabled_interfaces.add(tokens[2])

        return disabled_interfaces

    def _parse_interfaces_from_terse_output(self, output: str) -> set[str]:
        """Extract interface names from `show interfaces terse` output."""
        interfaces: set[str] = set()
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            token = stripped.split(maxsplit=1)[0]
            interface = self._normalize_interface_name(token)
            if interface is not None:
                interfaces.add(interface)

        return interfaces

    def _parse_interface_descriptions(self, descriptions_output: str) -> dict[str, str]:
        """Extract top-level interface descriptions."""
        descriptions: dict[str, str] = {}

        for line in descriptions_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("inactive:"):
                continue

            try:
                tokens = shlex.split(stripped)
            except ValueError:
                continue

            if (
                len(tokens) >= 5
                and tokens[0] == "set"
                and tokens[1] == "interfaces"
                and tokens[3] == "description"
            ):
                interface = self._normalize_interface_name(tokens[2])
                if interface is None:
                    continue

                description = " ".join(tokens[4:]).strip()
                if description:
                    descriptions[interface] = description

        return descriptions

    def _parse_interface_statuses(self, terse_output: str) -> dict[str, tuple[str, str]]:
        """Extract admin/link state from top-level terse lines."""
        statuses: dict[str, tuple[str, str]] = {}

        for line in terse_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            tokens = stripped.split()
            if len(tokens) < 3:
                continue

            token = tokens[0].rstrip(":")
            if "." in token:
                continue

            interface = self._normalize_interface_name(token)
            if interface is None:
                continue

            statuses[interface] = (tokens[1].lower(), tokens[2].lower())

        return statuses

    def _parse_interface_speeds(self, media_output: str) -> dict[str, str]:
        """Extract per-interface speed from `show interfaces media` output."""
        speeds: dict[str, str] = {}
        current_interface: str | None = None

        for line in media_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.lower().startswith("physical interface:"):
                interface_token = stripped.split(":", 1)[1].split(",", 1)[0].strip()
                current_interface = self._normalize_interface_name(interface_token)
                continue

            if current_interface is not None:
                speed_match = re.search(r"Speed:\s*([^,]+)", stripped, flags=re.IGNORECASE)
                if speed_match:
                    speed = speed_match.group(1).strip()
                    if speed:
                        speeds[current_interface] = speed
                continue

            tokens = stripped.split()
            interface = self._normalize_interface_name(tokens[0].rstrip(":"))
            if interface is None:
                continue

            for token in tokens[1:]:
                candidate = token.rstrip(",")
                if "bps" in candidate.lower():
                    speeds[interface] = candidate
                    break

        return speeds

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

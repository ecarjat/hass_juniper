"""Unit tests for Junos client helpers."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from custom_components.hass_juniper.junos_client import (
    JunosAuthenticationError,
    JunosPortClient,
)


def test_resolve_transport_host_prefers_ipv4() -> None:
    """Client should use IPv4 address when DNS resolution succeeds."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    with patch(
        "custom_components.hass_juniper.junos_client.socket.getaddrinfo",
        return_value=[
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.0.20", 0),
            )
        ],
    ):
        assert client._resolve_transport_host() == "192.168.0.20"


def test_resolve_transport_host_falls_back_to_hostname_on_failure() -> None:
    """Client should keep configured host if IPv4 resolution fails."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    with patch(
        "custom_components.hass_juniper.junos_client.socket.getaddrinfo",
        side_effect=socket.gaierror(-2, "Name does not resolve"),
    ):
        assert client._resolve_transport_host() == "switch.home"


def test_parse_disabled_interfaces_filters_false_positives() -> None:
    """Only top-level interface disable statements should be treated as admin-down."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    parsed = client._parse_disabled_interfaces(
        "\n".join(
            [
                "set interfaces ge-0/0/1 disable",
                "set interfaces ge-0/0/2 unit 0 family ethernet-switching storm-control default disable",
                "inactive: set interfaces ge-0/0/3 disable",
            ]
        )
    )

    assert parsed == {"ge-0/0/1"}


def test_parse_interface_descriptions_top_level_only() -> None:
    """Only top-level interface descriptions should be parsed."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    parsed = client._parse_interface_descriptions(
        "\n".join(
            [
                'set interfaces ge-0/0/1 description "Kids Room"',
                'set interfaces ge-0/0/2 unit 0 description "Ignore unit description"',
                "inactive: set interfaces ge-0/0/3 description Inactive Port",
                "set interfaces ae0 description Uplink",
            ]
        )
    )

    assert parsed == {
        "ge-0/0/1": "Kids Room",
        "ae0": "Uplink",
    }


def test_parse_interface_statuses_from_terse_output() -> None:
    """Admin and operational status should come from top-level terse lines."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    parsed = client._parse_interface_statuses(
        "\n".join(
            [
                "Interface               Admin Link Proto    Local                 Remote",
                "ge-0/0/0                up    up",
                "ge-0/0/0.0              up    up   eth-switch",
                "xe-0/0/1                up    down",
            ]
        )
    )

    assert parsed == {
        "ge-0/0/0": ("up", "up"),
        "xe-0/0/1": ("up", "down"),
    }


def test_connect_sync_translates_auth_error() -> None:
    """Auth failures from the Junos SDK should raise JunosAuthenticationError."""
    from jnpr.junos.exception import ConnectAuthError

    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    with patch("jnpr.junos.Device") as mock_device_cls:
        mock_device_cls.return_value.open.side_effect = ConnectAuthError(MagicMock())

        with pytest.raises(JunosAuthenticationError):
            client._connect_sync()

    assert client._device is None


def test_parse_interface_speeds_from_media_output() -> None:
    """Speed should be parsed from media details output."""
    client = JunosPortClient("switch.home", "admin", "/config/.ssh/id_rsa")

    parsed = client._parse_interface_speeds(
        "\n".join(
            [
                "Physical interface: ge-0/0/1, Enabled, Physical link is Up",
                "  Link-level type: Ethernet, MTU: 1514, Speed: 1000mbps, BPDU Error: None",
                "Physical interface: xe-0/0/0, Enabled, Physical link is Down",
                "  Link-level type: Ethernet, MTU: 9192, Speed: 10Gbps, Loopback: Disabled",
            ]
        )
    )

    assert parsed == {
        "ge-0/0/1": "1000mbps",
        "xe-0/0/0": "10Gbps",
    }

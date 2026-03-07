"""Unit tests for Junos client helpers."""

from __future__ import annotations

import socket
from unittest.mock import patch

from custom_components.hass_juniper.junos_client import JunosPortClient


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

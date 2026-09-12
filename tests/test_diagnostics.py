"""Unit tests for hass_juniper diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.hass_juniper.diagnostics import async_get_config_entry_diagnostics
from custom_components.hass_juniper.junos_client import JunosInterfaceState
from custom_components.hass_juniper.models import JuniperRuntimeData


@pytest.mark.asyncio
async def test_diagnostics_redacts_credentials_and_includes_interfaces() -> None:
    """Diagnostics should redact credentials and expose interface state."""
    entry = SimpleNamespace(
        data={
            "name": "Switch",
            "host": "10.0.0.10",
            "username": "admin",
            "ssh_key_path": "/config/.ssh/id_rsa",
        },
        runtime_data=JuniperRuntimeData(
            client=SimpleNamespace(),
            coordinator=SimpleNamespace(
                data={
                    "ge-0/0/1": JunosInterfaceState(
                        disabled=False,
                        description="Kids Room",
                        admin_status="up",
                        oper_status="up",
                        speed="1000mbps",
                    )
                }
            ),
        ),
    )

    result = await async_get_config_entry_diagnostics(SimpleNamespace(), entry)

    assert result["entry_data"]["username"] == "**REDACTED**"
    assert result["entry_data"]["ssh_key_path"] == "**REDACTED**"
    assert result["entry_data"]["host"] == "10.0.0.10"
    assert result["interfaces"]["ge-0/0/1"]["speed"] == "1000mbps"

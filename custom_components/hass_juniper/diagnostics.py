"""Diagnostics support for hass_juniper."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_SSH_KEY_PATH
from .models import JuniperConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_SSH_KEY_PATH}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JuniperConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "interfaces": {
            interface: asdict(state)
            for interface, state in (coordinator.data or {}).items()
        },
    }

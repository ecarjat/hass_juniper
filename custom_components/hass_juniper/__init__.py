"""The hass_juniper integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_INTERFACE, CONF_SSH_KEY_PATH, DOMAIN, PLATFORMS
from .junos_client import JunosPortClient
from .migration import entry_unique_id, normalize_legacy_config

_LOGGER = logging.getLogger(__name__)


def _iter_legacy_switch_configs(config: ConfigType) -> list[Mapping[str, Any]]:
    """Return legacy switch platform entries from YAML config."""
    switch_config = config.get(SWITCH_DOMAIN, [])

    if isinstance(switch_config, Mapping):
        entries: list[Mapping[str, Any]] = [switch_config]
    elif isinstance(switch_config, list):
        entries = [entry for entry in switch_config if isinstance(entry, Mapping)]
    else:
        entries = []

    return [entry for entry in entries if entry.get(CONF_PLATFORM) == DOMAIN]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the hass_juniper integration from YAML for migration only."""
    hass.data.setdefault(DOMAIN, {})

    for raw_entry in _iter_legacy_switch_configs(config):
        normalized_entry = normalize_legacy_config(raw_entry)
        if normalized_entry is None:
            _LOGGER.warning(
                "Skipping invalid YAML config for %s; expected host/interface/ssh key path",
                DOMAIN,
            )
            continue

        _LOGGER.warning(
            "YAML config for %s is deprecated; importing this device into UI config entries",
            DOMAIN,
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=normalized_entry,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hass_juniper from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    normalized_data = normalize_legacy_config(entry.data)
    if normalized_data is None:
        _LOGGER.error("Invalid config entry data for %s entry %s", DOMAIN, entry.entry_id)
        return False

    client = JunosPortClient(
        host=normalized_data[CONF_HOST],
        username=normalized_data[CONF_USERNAME],
        ssh_key_path=normalized_data[CONF_SSH_KEY_PATH],
        interface=normalized_data[CONF_INTERFACE],
    )

    try:
        await client.connect(hass)
    except Exception as err:  # pylint: disable=broad-except
        raise ConfigEntryNotReady(
            f"Could not connect to {normalized_data[CONF_HOST]}"
        ) from err

    hass.data[DOMAIN][entry.entry_id] = client

    new_unique_id = entry_unique_id(
        normalized_data[CONF_HOST], normalized_data[CONF_INTERFACE]
    )
    if dict(entry.data) != normalized_data or entry.unique_id != new_unique_id:
        hass.config_entries.async_update_entry(
            entry,
            data=normalized_data,
            unique_id=new_unique_id,
        )

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:  # pylint: disable=broad-except
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await client.disconnect(hass)
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    client: JunosPortClient | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if client is not None:
        await client.disconnect(hass)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True

"""Helpers for migrating legacy YAML configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME

from .const import (
    CONF_INTERFACE,
    CONF_SSH_KEY_PATH,
    DEFAULT_USERNAME,
    LEGACY_CONF_FILE_PATH,
    LEGACY_CONF_PORT,
)


def entry_unique_id(host: str, interface: str) -> str:
    """Build a deterministic unique ID for a Juniper interface entry."""
    return f"{host.strip().lower()}::{interface.strip()}"


def normalize_legacy_config(raw_config: Mapping[str, Any]) -> dict[str, str] | None:
    """Normalize old YAML keys to the config-entry schema."""
    host = str(raw_config.get(CONF_HOST, "")).strip()
    name = str(raw_config.get(CONF_NAME, "")).strip()
    username = str(raw_config.get(CONF_USERNAME, DEFAULT_USERNAME)).strip()
    interface = str(
        raw_config.get(CONF_INTERFACE) or raw_config.get(LEGACY_CONF_PORT, "")
    ).strip()
    ssh_key_path = str(
        raw_config.get(CONF_SSH_KEY_PATH) or raw_config.get(LEGACY_CONF_FILE_PATH, "")
    ).strip()

    if not host or not interface or not ssh_key_path:
        return None

    if not name:
        name = f"{host} {interface}"

    if not username:
        username = DEFAULT_USERNAME

    return {
        CONF_NAME: name,
        CONF_HOST: host,
        CONF_USERNAME: username,
        CONF_INTERFACE: interface,
        CONF_SSH_KEY_PATH: ssh_key_path,
    }

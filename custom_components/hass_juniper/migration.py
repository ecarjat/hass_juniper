"""Helpers for migrating legacy YAML configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME

from .const import CONF_SSH_KEY_PATH, DEFAULT_USERNAME, LEGACY_CONF_FILE_PATH


def entry_unique_id(host: str) -> str:
    """Build a deterministic unique ID for a switch device entry."""
    return host.strip().lower()


def entity_unique_id(host: str, interface: str) -> str:
    """Build a deterministic unique ID for each interface entity."""
    return f"{entry_unique_id(host)}::{interface.strip()}"


def normalize_connection_config(raw_config: Mapping[str, Any]) -> dict[str, str] | None:
    """Normalize config values to the connection schema."""
    host = str(raw_config.get(CONF_HOST, "")).strip()
    name = str(raw_config.get(CONF_NAME, "")).strip()
    username = str(raw_config.get(CONF_USERNAME, DEFAULT_USERNAME)).strip()
    ssh_key_path = str(
        raw_config.get(CONF_SSH_KEY_PATH) or raw_config.get(LEGACY_CONF_FILE_PATH, "")
    ).strip()

    if not host or not ssh_key_path:
        return None

    if not name:
        name = f"Juniper {host}"

    if not username:
        username = DEFAULT_USERNAME

    return {
        CONF_NAME: name,
        CONF_HOST: host,
        CONF_USERNAME: username,
        CONF_SSH_KEY_PATH: ssh_key_path,
    }


def normalize_legacy_config(raw_config: Mapping[str, Any]) -> dict[str, str] | None:
    """Backwards-compatible alias for old migration callers/tests."""
    return normalize_connection_config(raw_config)

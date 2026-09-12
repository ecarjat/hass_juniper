"""Constants for the hass_juniper integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME

DOMAIN = "hass_juniper"
PLATFORMS: list[str] = ["switch", "binary_sensor", "sensor"]

CONF_INTERFACE = "interface"
CONF_SSH_KEY_PATH = "ssh_key_path"
CONF_UPLOADED_KEY_FILE = "uploaded_key_file"

LEGACY_CONF_PORT = "port"
LEGACY_CONF_FILE_PATH = "file_path"

DEFAULT_USERNAME = "root"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

KEY_STORAGE_DIR = ".storage/hass_juniper"

REQUIRED_FIELDS: tuple[str, ...] = (
    CONF_NAME,
    CONF_HOST,
    CONF_USERNAME,
    CONF_SSH_KEY_PATH,
)

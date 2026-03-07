"""Tests for YAML normalization helpers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME

from custom_components.hass_juniper.const import CONF_INTERFACE, CONF_SSH_KEY_PATH
from custom_components.hass_juniper.migration import normalize_legacy_config


def test_normalize_legacy_yaml_keys() -> None:
    """Legacy keys should be normalized to the new schema."""
    normalized = normalize_legacy_config(
        {
            CONF_NAME: "Uplink",
            CONF_HOST: "10.0.0.1",
            "port": "ge-0/0/1",
            "file_path": "/config/.ssh/id_rsa",
        }
    )

    assert normalized == {
        CONF_NAME: "Uplink",
        CONF_HOST: "10.0.0.1",
        CONF_USERNAME: "root",
        CONF_INTERFACE: "ge-0/0/1",
        CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
    }


def test_normalize_returns_none_when_required_fields_missing() -> None:
    """Invalid configuration should be rejected."""
    assert normalize_legacy_config({CONF_HOST: "10.0.0.1"}) is None

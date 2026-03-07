"""Tests for configuration normalization helpers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME

from custom_components.hass_juniper.const import CONF_SSH_KEY_PATH
from custom_components.hass_juniper.migration import (
    entity_unique_id,
    entry_unique_id,
    normalize_connection_config,
)


def test_normalize_legacy_yaml_keys() -> None:
    """Legacy keys should normalize to the entry connection schema."""
    normalized = normalize_connection_config(
        {
            CONF_NAME: "Core",
            CONF_HOST: "10.0.0.1",
            "port": "ge-0/0/1",
            "file_path": "/config/.ssh/id_rsa",
        }
    )

    assert normalized == {
        CONF_NAME: "Core",
        CONF_HOST: "10.0.0.1",
        CONF_USERNAME: "root",
        CONF_SSH_KEY_PATH: "/config/.ssh/id_rsa",
    }


def test_normalize_returns_none_when_required_fields_missing() -> None:
    """Invalid configuration should be rejected."""
    assert normalize_connection_config({CONF_HOST: "10.0.0.1"}) is None


def test_unique_id_helpers() -> None:
    """Unique id helpers should be deterministic."""
    assert entry_unique_id("SW1.EXAMPLE") == "sw1.example"
    assert entity_unique_id("SW1.EXAMPLE", "ge-0/0/1") == "sw1.example::ge-0/0/1"

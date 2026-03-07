"""Tests for SSH key storage helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from custom_components.hass_juniper.key_storage import _store_private_key_sync


def test_store_private_key_sync_writes_file_with_restricted_permissions(tmp_path: Path) -> None:
    """Stored key should be written under integration storage with 0600 perms."""
    storage_root = tmp_path / "ha-config"

    hass = SimpleNamespace(
        config=SimpleNamespace(
            path=lambda *parts: str(storage_root.joinpath(*parts)),
        )
    )

    key_path = _store_private_key_sync(
        hass,
        "switch01.example",
        "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
    )

    stored_path = Path(key_path)
    assert stored_path.exists()
    assert stored_path.read_text(encoding="utf-8").startswith("-----BEGIN PRIVATE KEY-----")

    assert (stored_path.stat().st_mode & 0o777) == 0o600
    assert (stored_path.parent.stat().st_mode & 0o777) == 0o700

"""SSH key storage helpers for hass_juniper."""

from __future__ import annotations

import os
from pathlib import Path
import re

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import HomeAssistant

from .const import KEY_STORAGE_DIR


def _sanitize_host(host: str) -> str:
    """Sanitize host for filesystem-safe filenames."""
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", host.strip().lower())
    return safe or "switch"


def _store_private_key_sync(hass: HomeAssistant, host: str, key_content: str) -> str:
    """Persist a private key with restrictive permissions."""
    storage_dir = Path(hass.config.path(KEY_STORAGE_DIR))
    storage_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(storage_dir, 0o700)

    file_path = storage_dir / f"{_sanitize_host(host)}.key"
    temp_path = file_path.with_suffix(".tmp")

    temp_path.write_text(key_content, encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(file_path)
    os.chmod(file_path, 0o600)

    return str(file_path)


def _load_uploaded_key_content_sync(hass: HomeAssistant, uploaded_file_id: str) -> str:
    """Read uploaded key file content from temporary upload storage."""
    with process_uploaded_file(hass, uploaded_file_id) as file_path:
        return file_path.read_text(encoding="utf-8")


async def async_store_uploaded_private_key(
    hass: HomeAssistant,
    host: str,
    uploaded_file_id: str,
) -> str:
    """Store an uploaded private key and return the final file path."""
    key_content = await hass.async_add_executor_job(
        _load_uploaded_key_content_sync,
        hass,
        uploaded_file_id,
    )
    return await hass.async_add_executor_job(_store_private_key_sync, hass, host, key_content)

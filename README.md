# hass_juniper

Home Assistant custom integration to control Juniper interface admin state as switch entities.

## Installation (HACS)

1. Add this repository as a custom integration repository in HACS.
2. Download/install the integration from HACS.
3. Restart Home Assistant.
4. Add **hass_juniper** from **Settings > Devices & Services > Add Integration**.

## YAML Migration

Legacy YAML entries under `switch:` with `platform: hass_juniper` are automatically imported into UI config entries.

Legacy keys are migrated as:

- `port` -> `interface`
- `file_path` -> `ssh_key_path`

## Configuration fields

- `name`
- `host`
- `username`
- `interface`
- `ssh_key_path`

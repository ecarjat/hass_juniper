# hass_juniper

Home Assistant custom integration to control Juniper interface admin state as switch entities.

## Installation (HACS)

1. Add this repository as a custom integration repository in HACS.
2. Download/install the integration from HACS.
3. Restart Home Assistant.
4. Add **hass_juniper** from **Settings > Devices & Services > Add Integration**.

## How It Works

One config entry represents one Juniper switch device and automatically discovers interfaces.
Each discovered interface is exposed as a switch entity (admin state), a link binary sensor,
a speed sensor, and a text entity for the interface description.

Editing the description text entity in Home Assistant pushes the new value to the switch as
`set interfaces <if> description "..."` (or removes the statement if cleared); descriptions
changed directly on the switch are reflected back in Home Assistant on the next poll.

## SSH Key Input

In the UI config flow you can either:

- Provide `ssh_key_path` directly, or
- Upload the SSH private key file.

Uploaded keys are persisted under `.storage/hass_juniper` with restrictive file permissions.

## YAML Migration

Legacy YAML entries under `switch:` with `platform: hass_juniper` are automatically imported into UI config entries.

Legacy keys are migrated as:

- `file_path` -> `ssh_key_path`
- `port` is ignored (interfaces are now auto-discovered)

## Configuration fields

- `name`
- `host`
- `username`
- `ssh_key_path` (or uploaded key)

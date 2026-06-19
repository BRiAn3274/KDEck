"""Trusted-device store migration helpers."""

from typing import Any


def migrate_trusted_devices(data: dict[str, Any], now: int) -> tuple[dict[str, Any], bool]:
    """Normalize trusted-device entries without changing trust decisions.

    Legacy stores can contain non-dict values or old metadata names.  This
    migration makes the shape predictable while preserving unknown fields.
    It intentionally does not turn an incomplete legacy record into a trusted
    ``device_id`` entry unless that trust mode was already present.
    """
    migrated: dict[str, Any] = {}
    changed = False
    for device_id, value in data.items():
        if isinstance(value, dict):
            entry = dict(value)
        else:
            entry = {"legacy_value": value}
            changed = True

        if entry.get("device_id") != device_id:
            entry["device_id"] = device_id
            changed = True

        for old_key, new_key in (("name", "device_name"), ("type", "device_type"), ("host", "last_host")):
            if old_key in entry and new_key not in entry:
                entry[new_key] = entry[old_key]
                changed = True

        if "schema_version" not in entry:
            entry["schema_version"] = 2
            changed = True

        if "migrated_at" not in entry:
            entry["migrated_at"] = now
            changed = True

        migrated[device_id] = entry

    return migrated, changed

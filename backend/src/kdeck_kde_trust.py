"""KDEck KDE Connect trust management.

The receiver owns connection state and event logging; this module owns the
shape of the trusted-device store and the rules for accepting a peer.  Keeping
those rules here makes migrations and trust checks testable without opening
network sockets.
"""

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from kdeck_kde_trust_migration import migrate_trusted_devices


def read_trusted_devices(trusted_path: Path) -> dict[str, Any]:
    """Load the trusted-devices JSON store, returning ``{}`` on any error."""
    if not trusted_path.exists():
        return {}
    try:
        data = json.loads(trusted_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        migrated, changed = migrate_trusted_devices(data, now=int(time.time()))
        if changed:
            write_trusted_devices(trusted_path, migrated)
        return migrated
    except (OSError, json.JSONDecodeError):
        return {}


def write_trusted_devices(
    trusted_path: Path,
    data: dict[str, Any],
    on_error: Optional[Callable[[OSError], None]] = None,
) -> None:
    """Atomically write *data* to the trusted-devices store.

    Uses a temporary file + rename to avoid partial writes.  On failure,
    the optional *on_error* callback is invoked with the exception so the
    caller can log or emit an event.
    """
    try:
        tmp_path = trusted_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(trusted_path)
    except OSError as exc:
        if on_error:
            on_error(exc)


def is_trusted_device(
    trusted: dict[str, Any],
    peer_id: str,
    fingerprint: Optional[str],
) -> bool:
    """Return ``True`` when *peer_id* is present in *trusted* with a matching credential.

    Two trust modes are supported:

    * **fingerprint** – the stored fingerprint must match the peer's TLS
      certificate fingerprint.
    * **device_id** – used as a fallback when the peer could not provide a
      TLS fingerprint (e.g. older Android clients).
    """
    entry = trusted.get(peer_id)
    if not isinstance(entry, dict):
        return False
    trusted_fingerprint = entry.get("fingerprint")
    if trusted_fingerprint:
        return bool(fingerprint and fingerprint == trusted_fingerprint)
    return entry.get("trust_mode") == "device_id"


def remember_trusted_device_metadata(
    trusted: dict[str, Any],
    device_id: Optional[str],
    host: str,
    identity: dict[str, Any],
    connected: bool,
    udp_source_port: Optional[int] = None,
) -> dict[str, Any]:
    """Update metadata for an already-trusted device.

    Returns the (possibly mutated) *trusted* dict.  If *device_id* is
    ``None`` or not present in the store the dict is returned unchanged.
    """
    if not device_id:
        return trusted
    entry = trusted.get(device_id)
    if not isinstance(entry, dict):
        return trusted
    now = int(time.time())
    entry.update(
        {
            "device_name": identity.get("deviceName") or entry.get("device_name"),
            "device_type": identity.get("deviceType") or entry.get("device_type"),
            "protocol_version": identity.get("protocolVersion") or entry.get("protocol_version"),
            "tcp_port": identity.get("tcpPort") or entry.get("tcp_port"),
            "last_host": host,
            "last_seen": now,
        }
    )
    if udp_source_port:
        entry["udp_source_port"] = udp_source_port
    if connected:
        entry["last_connected"] = now
    trusted[device_id] = entry
    return trusted


def accept_pair_record(
    trusted: dict[str, Any],
    peer_id: str,
    peer_host: str,
    fingerprint: Optional[str],
    now: int,
) -> tuple[dict[str, Any], str]:
    """Return updated trust data for an accepted pair request.

    The receiver performs the network reply and event logging.  This helper
    only preserves existing metadata and writes the fields that define trust.
    """
    existing = trusted.get(peer_id) if isinstance(trusted.get(peer_id), dict) else {}
    trust_mode = "fingerprint" if fingerprint else "device_id"
    trusted[peer_id] = {
        **existing,
        "paired_at": now,
        "fingerprint": fingerprint,
        "trust_mode": trust_mode,
        "last_host": peer_host,
        "last_connected": now,
    }
    return trusted, trust_mode

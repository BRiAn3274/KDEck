"""KDE Connect discovery target helpers for KDEck.

This module only calculates direct UDP reannounce targets from receiver state.
It does not open sockets, mutate diagnostics, or decide whether a peer should
connect; the receiver owns those side effects.
"""

from typing import Any, Optional

from kdeck_kde_protocol import RECENT_DISCOVERY_DIRECT_SECONDS, TRUSTED_DEVICE_DIRECT_SECONDS, UDP_PORT


def recent_discovery_targets(
    discovered_devices: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    now: int,
    source_ips_for_host,
) -> list[tuple[Optional[str], str, int]]:
    """Build direct UDP targets from recently discovered peers."""
    targets: list[tuple[Optional[str], str, int]] = []
    seen = set()
    for device in discovered_devices:
        host = device.get("host")
        if not host:
            continue
        if now - int(device.get("last_seen") or 0) > RECENT_DISCOVERY_DIRECT_SECONDS:
            continue
        ports = [int(device.get("udp_source_port") or 0), UDP_PORT]
        source_ips = source_ips_for_host(host, interfaces)
        for port in ports:
            if not (1 <= port <= 65535):
                continue
            for source_ip in source_ips:
                key = (source_ip, host, port)
                if key in seen:
                    continue
                seen.add(key)
                targets.append((source_ip, host, port))
    return targets[:16]


def trusted_direct_targets(
    trusted_devices: dict[str, Any],
    interfaces: list[dict[str, Any]],
    now: int,
    source_ips_for_host,
) -> tuple[list[tuple[Optional[str], str, int]], list[dict[str, Any]]]:
    """Build direct UDP targets from persisted trusted-device metadata.

    Returns both the target list and per-device event details.  The receiver is
    responsible for writing events and diagnostics so this helper stays pure.
    """
    targets: list[tuple[Optional[str], str, int]] = []
    events: list[dict[str, Any]] = []
    seen = set()
    for device_id, data in trusted_devices.items():
        if not isinstance(data, dict):
            continue
        host = data.get("last_host")
        if not host:
            continue
        last_seen = int(data.get("last_seen") or data.get("last_connected") or 0)
        if last_seen and now - last_seen > TRUSTED_DEVICE_DIRECT_SECONDS:
            continue
        ports = [int(data.get("udp_source_port") or 0), UDP_PORT]
        source_ips = source_ips_for_host(str(host), interfaces)
        for port in ports:
            if not (1 <= port <= 65535):
                continue
            for source_ip in source_ips:
                key = (source_ip, str(host), port)
                if key in seen:
                    continue
                seen.add(key)
                targets.append((source_ip, str(host), port))
        events.append({"device_id": device_id, "host": host, "ports": ports, "target_count": len(targets)})
    return targets[:16], events

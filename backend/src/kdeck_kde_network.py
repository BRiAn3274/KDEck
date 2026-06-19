"""KDEck KDE Connect network utilities — interface discovery, broadcast targets,
IP classification, and port binding.

All functions here are stateless. The orchestrator passes in interface lists
and configuration as needed.
"""

import ipaddress
import json
import shutil
import socket
import subprocess
from typing import Any, Optional

from kdeck_kde_protocol import (
    IGNORED_INTERFACE_PREFIXES,
    INTERFACE_PRIORITIES,
    TCP_PORT_MAX,
    TCP_PORT_MIN,
    UDP_PORT,
)


def interface_path_type(name: str) -> str:
    """Classify a network interface name into a path type."""
    clean = (name or "").lower()
    if clean.startswith(("wlan", "wl", "en", "eth")):
        return "lan"
    if clean.startswith("et_"):
        return "easytier"
    if clean.startswith("zt"):
        return "zerotier"
    if clean.startswith(("tailscale", "tailscale0")):
        return "tailscale"
    if clean.startswith(("tun", "tap", "ppp")):
        return "vpn"
    return "other"


def interface_priority(name: str) -> int:
    """Return a priority score for a network interface."""
    return INTERFACE_PRIORITIES.get(interface_path_type(name), 10)


def is_usable_ipv4(address: Optional[str]) -> bool:
    """Return True if the IPv4 address is usable for KDE Connect discovery."""
    if not address:
        return False
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    return ip not in ipaddress.ip_network("198.18.0.0/15")


def is_ignored_interface(name: str) -> bool:
    """Return True if the interface should be excluded from KDE Connect."""
    clean = (name or "").lower()
    return clean.startswith(IGNORED_INTERFACE_PREFIXES)


def network_interfaces() -> list[dict[str, Any]]:
    """Discover usable IPv4 network interfaces via the ``ip`` command.

    Returns a list of dicts sorted by priority (descending), then interface
    name and address.
    """
    interfaces: list[dict[str, Any]] = []
    if shutil.which("ip"):
        try:
            result = subprocess.run(
                ["ip", "-j", "addr"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            for iface in json.loads(result.stdout):
                name = iface.get("ifname", "")
                if is_ignored_interface(name):
                    continue
                for addr in iface.get("addr_info", []):
                    if addr.get("family") == "inet" and addr.get("local"):
                        local = addr.get("local")
                        if not is_usable_ipv4(local):
                            continue
                        interfaces.append(
                            {
                                "interface": name,
                                "address": local,
                                "broadcast": addr.get("broadcast"),
                                "prefixlen": addr.get("prefixlen"),
                                "priority": interface_priority(name),
                                "path_type": interface_path_type(name),
                            }
                        )
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    interfaces.sort(key=lambda item: (-int(item.get("priority") or 0), item.get("interface") or "", item.get("address") or ""))
    return interfaces


def bind_available_tcp_port(
    server: socket.socket,
    port_low: int | None = None,
    port_mid: int | None = None,
) -> int:
    """Bind *server* to the first available TCP port in the given range.

    Raises OSError when no port is available.
    """
    lo = port_low if port_low is not None else TCP_PORT_MIN
    hi = port_mid if port_mid is not None else TCP_PORT_MAX
    last_error: Optional[OSError] = None
    for port in range(lo, hi + 1):
        try:
            server.bind(("0.0.0.0", port))
            return port
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(f"no available TCP port in {lo}-{hi}: {last_error}")


def broadcast_targets(interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str]]:
    """Return (source_ip, broadcast_address) pairs for UDP discovery."""
    targets: list[tuple[Optional[str], str]] = []
    seen: set[tuple[Optional[str], str]] = set()
    for iface in interfaces:
        source = iface.get("address")
        for target in ("255.255.255.255", iface.get("broadcast")):
            if not target:
                continue
            key = (source, target)
            if key not in seen:
                seen.add(key)
                targets.append((source, target))
    if not targets:
        targets.append((None, "255.255.255.255"))
    return targets


def source_ips_for_host(
    host: str,
    interfaces: list[dict[str, Any]],
) -> list[Optional[str]]:
    """Return source IPs sorted by suitability for reaching *host*."""
    matches: list[tuple[int, str]] = []
    fallbacks: list[tuple[int, str]] = []
    try:
        peer = ipaddress.ip_address(host)
    except ValueError:
        peer = None
    for iface in interfaces:
        source = iface.get("address")
        if not source:
            continue
        priority = int(iface.get("priority") or interface_priority(iface.get("interface") or ""))
        fallbacks.append((priority, source))
        if peer is None:
            continue
        try:
            prefixlen = int(iface.get("prefixlen") or 32)
            network = ipaddress.ip_interface(f"{source}/{prefixlen}").network
        except ValueError:
            continue
        if peer in network:
            matches.append((priority, source))
    selected = matches or fallbacks
    selected.sort(key=lambda item: (-item[0], item[1]))
    return [source for _priority, source in selected] or [None]


def local_ipv4_addresses() -> set[str]:
    """Return the set of all local IPv4 addresses (including 127.0.0.1)."""
    addresses = {"127.0.0.1"}
    for iface in network_interfaces():
        address = iface.get("address")
        if address:
            addresses.add(str(address))
    return addresses


def is_local_host(host: str) -> bool:
    """Return True if *host* refers to the local machine."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return str(ip) in local_ipv4_addresses()


def identity_reply_ports(
    source_port: int,
    peer_identity: dict[str, Any],
) -> list[int]:
    """Determine which UDP ports to reply on after receiving a discovery packet.

    Android devices only listen on their source port; other platforms also
    expect a reply on the standard KDE Connect port (1716).
    """
    from kdeck_kde_protocol import ANDROID_DEVICE_TYPES

    device_type = str(peer_identity.get("deviceType") or "").lower()
    if device_type in ANDROID_DEVICE_TYPES:
        return [source_port]
    reply_ports = [source_port]
    if UDP_PORT not in reply_ports:
        reply_ports.append(UDP_PORT)
    return reply_ports


def peer_tls_mode(device_type: str) -> str:
    """Determine the TLS role for an outgoing connection to a peer.

    Currently always returns ``"server"`` — Android 0.3.1 had TLS client-mode
    timeout issues; 0.3.2 reverted to the server-side approach.
    """
    return "server"


def merge_direct_targets(
    first: list[tuple[Optional[str], str, int]],
    second: list[tuple[Optional[str], str, int]],
) -> list[tuple[Optional[str], str, int]]:
    """Merge two direct-target lists, deduplicating and capping at 24."""
    merged: list[tuple[Optional[str], str, int]] = []
    seen: set[tuple[Optional[str], str, int]] = set()
    for item in first + second:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged[:24]

"""KDEck network utilities — interface discovery, IP classification, and sorting."""

import ipaddress
import json
import socket
from typing import Any, Optional

IGNORED_INTERFACE_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "vmnet", "mihomo", "clash")

INTERFACE_PRIORITIES = {
    "lan": 100,
    "easytier": 80,
    "zerotier": 70,
    "tailscale": 60,
    "vpn": 40,
    "other": 10,
}


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


class KDEckNetwork:
    """Network discovery and IP sorting for KDEck."""

    def __init__(self, logger: Any = None, run_fn=None):
        self.logger = logger
        self._run = run_fn  # async _run(command, timeout) -> CommandResult

    async def get_deck_ips(self) -> dict[str, Any]:
        interfaces = await self.network_info()
        items = self._ips_from_interfaces(interfaces)
        items.sort(key=lambda item: (-item["priority"], item["interface"], item["address"]))
        return {"ok": True, "items": items, "primary": items[0] if items else None}

    async def network_info(self) -> dict[str, Any]:
        import shutil

        hostname_ips: list[str] = []
        try:
            hostname_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except OSError:
            hostname_ips = []

        ip_json = None
        if shutil.which("ip") and self._run:
            result = await self._run(["ip", "-j", "addr"], timeout=5)
            if result.ok:
                try:
                    ip_json = json.loads(result.stdout)
                except json.JSONDecodeError:
                    ip_json = None

        from kdeck_config import KDECONNECT_PORT_RANGE

        return {
            "hostname": socket.gethostname(),
            "hostname_ips": hostname_ips,
            "interfaces": ip_json,
            "kdeconnect_ports": KDECONNECT_PORT_RANGE,
        }

    def _ips_from_interfaces(self, interfaces: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for iface in interfaces.get("interfaces") or []:
            name = iface.get("ifname", "")
            if is_ignored_interface(name):
                continue
            for addr in iface.get("addr_info", []):
                if addr.get("family") != "inet":
                    continue
                local = addr.get("local")
                if not is_usable_ipv4(local):
                    continue
                path_type = interface_path_type(name)
                items.append(
                    {
                        "interface": name,
                        "address": local,
                        "prefixlen": addr.get("prefixlen"),
                        "priority": interface_priority(name),
                        "path_type": path_type,
                    }
                )
        return items

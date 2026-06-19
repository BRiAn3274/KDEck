"""KDEck network utilities — interface discovery, IP classification, and sorting."""

import json
import socket
from typing import Any

from kdeck_kde_network import (
    interface_path_type,
    interface_priority,
    is_ignored_interface,
    is_usable_ipv4,
)
from kdeck_kde_protocol import (
    IGNORED_INTERFACE_PREFIXES,
    INTERFACE_PRIORITIES,
)

# Re-export for backward compatibility with code that imports from this module.
__all__ = [
    "IGNORED_INTERFACE_PREFIXES",
    "INTERFACE_PRIORITIES",
    "interface_path_type",
    "interface_priority",
    "is_usable_ipv4",
    "is_ignored_interface",
    "KDEckNetwork",
]


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

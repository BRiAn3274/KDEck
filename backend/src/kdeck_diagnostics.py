"""KDEck diagnostics — system status checks and connection summary."""

import re
import shutil
from pathlib import Path
from typing import Any, Optional

import kdeck_config as config


async def build_status(daemon, run_fn) -> dict[str, Any]:
    """Build the full system status dict (used by daemon.ensure_daemon and diagnostics)."""
    cli_path = shutil.which("kdeconnect-cli")
    daemon_path = shutil.which("kdeconnectd")
    qdbus_path = shutil.which("qdbus6") or shutil.which("qdbus")
    env = config.default_env()
    bus_path = Path(env["XDG_RUNTIME_DIR"]) / "bus"
    daemon_running = await daemon.is_daemon_running()
    dbus_ready = await daemon.is_dbus_service_ready()

    return {
        "ok": bool(cli_path and daemon_running and dbus_ready),
        "kdeconnect_cli": {
            "found": bool(cli_path),
            "path": cli_path,
        },
        "kdeconnectd": {
            "found": bool(daemon_path),
            "path": daemon_path,
            "running": daemon_running,
        },
        "dbus": {
            "bus_path": str(bus_path),
            "bus_exists": bus_path.exists(),
            "address": env["DBUS_SESSION_BUS_ADDRESS"],
            "service_ready": dbus_ready,
            "qdbus_path": qdbus_path,
        },
        "environment": env.copy(),
        "ports": config.KDECONNECT_PORT_RANGE,
        "common_directories": list(config.common_directories()),
    }


class KDEckDiagnostics:
    """Diagnostics, status aggregation, and connection summary."""

    def __init__(self, daemon, network, file_manager, kde_receiver, logger: Any = None, run_fn=None):
        self.daemon = daemon
        self.network = network
        self.file_manager = file_manager
        self.kde_receiver = kde_receiver
        self.logger = logger
        self._run = run_fn

    async def get_status(self) -> dict[str, Any]:
        return await build_status(self.daemon, self._run)

    async def get_connection_summary(self, managed_kde_status_fn) -> dict[str, Any]:
        status = await self.get_status()
        devices = await self._list_devices()
        ips = await self.network.get_deck_ips()
        incoming = self.file_manager.get_incoming_directories()

        paired = devices.get("paired", []) if devices.get("ok") else []
        reachable = [device for device in paired if device.get("reachable") is True]
        selected = reachable[0] if reachable else (paired[0] if paired else None)

        if not status["kdeconnect_cli"]["found"]:
            connection = "组件缺失"
        elif not status["kdeconnectd"]["found"]:
            connection = "组件缺失"
        elif not status["kdeconnectd"]["running"]:
            connection = "未启动"
        elif not status["dbus"]["service_ready"]:
            connection = "启动中"
        elif selected and selected.get("reachable") is False:
            connection = f"{selected['name']} 不可达"
        elif selected:
            connection = f"{selected['name']} 就绪"
        else:
            connection = "未连接"

        return {
            "ok": status["ok"],
            "connection": connection,
            "status": status,
            "devices": devices,
            "selected_device": selected,
            "deck_ips": ips,
            "incoming_directories": incoming,
            "managed_kde": managed_kde_status_fn(),
        }

    async def diagnose(self) -> dict[str, Any]:
        status = await self.get_status()
        devices = await self._list_devices()
        network = await self.network.network_info()
        problems: list[dict[str, str]] = []

        if not status["kdeconnect_cli"]["found"]:
            problems.append({"code": "missing_cli", "message": "找不到 kdeconnect-cli，无法通过命令行控制 KDE Connect。"})
        if not status["kdeconnectd"]["found"]:
            problems.append({"code": "missing_daemon", "message": "找不到 kdeconnectd，系统 KDE Connect 后台组件不完整。"})
        if not status["dbus"]["bus_exists"]:
            problems.append({"code": "missing_dbus", "message": "/run/user/1000/bus 不存在，当前 deck 用户会话 DBus 不可用。"})
        if status["kdeconnectd"]["found"] and not status["kdeconnectd"]["running"]:
            problems.append({"code": "daemon_stopped", "message": "kdeconnectd 未运行，可以由 KDEck 后端尝试拉起。"})
        if status["kdeconnectd"]["running"] and not status["dbus"]["service_ready"]:
            problems.append({"code": "dbus_service_unavailable", "message": "kdeconnectd 进程存在，但 org.kde.kdeconnect DBus 服务未就绪。"})
        if devices["ok"] and not devices["paired"]:
            problems.append({"code": "no_paired_device", "message": "当前没有已配对设备，需要先从可用设备列表发起配对。"})
        explicit_reachability = [d["reachable"] for d in devices["paired"] if d["reachable"] is not None]
        if devices["ok"] and explicit_reachability and not any(explicit_reachability):
            problems.append({
                "code": "paired_not_reachable",
                "message": "已有配对设备，但没有设备可达。常见原因是热点/AP 隔离、VPN 路由或两端不在同一网络。",
            })

        return {
            "ok": not problems,
            "status": status,
            "devices": devices,
            "network": network,
            "problems": problems,
            "hints": [
                "KDE Connect 使用 TCP/UDP 端口 1714-1764。",
                "手机热点、访客 Wi-Fi、AP 隔离会导致设备互相不可见。",
                "EasyTier、ZeroTier、Tailscale 等组网软件可能改变路由，设备可见性需要实测。",
            ],
        }

    async def _list_devices(self) -> dict[str, Any]:
        """List devices via kdeconnect-cli (requires daemon running)."""

        if not shutil.which("kdeconnect-cli"):
            return {"ok": False, "error": {"code": "missing_cli", "message": "kdeconnect-cli not found."}, "paired": [], "available": []}
        if not await self.daemon.is_daemon_running() or not await self.daemon.is_dbus_service_ready():
            return {"ok": False, "state": "daemon_not_ready", "paired": [], "available": [], "commands": {}}

        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        paired_result = await self._run([cli, "--list-devices"], timeout=10)
        available_result = await self._run([cli, "--list-available"], timeout=10)
        paired = parse_device_list(paired_result.stdout)
        available = parse_device_list(available_result.stdout)

        return {
            "ok": paired_result.ok and available_result.ok,
            "paired": paired,
            "available": available,
            "commands": {
                "paired": paired_result.to_dict(),
                "available": available_result.to_dict(),
            },
        }

    @staticmethod
    def receiver_diagnostic_summary(status: dict[str, Any]) -> dict[str, Any]:
        """Build a diagnostic summary for the managed receiver."""
        checks = {
            "desired": bool(status.get("desired")),
            "paused": bool(status.get("paused")),
            "udp": bool(status.get("udp_working")),
            "tcp": bool(status.get("tcp_working")),
            "paired": bool(status.get("paired")),
            "recent_discovery": bool(status.get("last_discovery_received")),
            "recent_connect_attempt": bool(status.get("last_connect_attempt")),
            "recent_tcp_success": bool(status.get("last_tcp_success")),
            "recent_tls_success": bool(status.get("last_tls_success")),
            "recent_pair": bool(status.get("last_pair")),
            "recent_reannounce": bool(status.get("last_reannounce_targets")),
            "recent_payload_error": bool(status.get("last_payload_error")),
            "recent_clipboard": bool(status.get("last_clipboard")),
            "recent_file": bool(status.get("last_file")),
        }
        if checks["paused"]:
            state = "paused_desktop_mode"
            message = "桌面模式运行中，KDEck receiver 已暂停。"
        elif not checks["desired"]:
            state = "disabled"
            message = "KDEck receiver 未被请求启动。"
        elif not checks["udp"] or not checks["tcp"]:
            state = "listener_unready"
            message = "KDEck receiver 正在启动或监听失败。"
        elif not checks["recent_discovery"]:
            state = "waiting_discovery"
            message = "KDEck receiver 正在监听，尚未收到外部设备 discovery。"
        elif checks["paired"]:
            state = "paired"
            message = "KDEck receiver 已有可信设备，可接收剪贴板和文件。"
        else:
            state = "discovered_unpaired"
            message = "KDEck receiver 已发现设备，等待配对或可信连接。"
        return {
            "state": state,
            "message": message,
            "checks": checks,
            "last_error": status.get("last_error"),
            "last_connect_error": status.get("last_connect_error"),
            "last_discovery_received": status.get("last_discovery_received"),
            "last_tcp_success": status.get("last_tcp_success"),
            "last_tls_success": status.get("last_tls_success"),
            "last_tls_error": status.get("last_tls_error"),
            "last_pair": status.get("last_pair"),
            "last_reannounce_targets": status.get("last_reannounce_targets"),
            "last_payload_error": status.get("last_payload_error"),
        }


# ---------------------------------------------------------------------------
# Device list parser (extracted from original kdeck_backend)
# ---------------------------------------------------------------------------


def parse_device_list(output: str) -> list[dict[str, Any]]:
    devices = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("devices:"):
            continue
        parsed = _parse_device_line(line)
        if parsed:
            devices.append(parsed)
    return devices


def _parse_device_line(line: str) -> Optional[dict[str, Any]]:
    clean = line[2:].strip() if line.startswith("- ") else line

    match = re.match(r"(?P<name>.+?):\s+(?P<id>[A-Za-z0-9._:-]+)(?:\s+\((?P<state>[^)]*)\))?", clean)
    if not match:
        id_only = clean.strip()
        if re.fullmatch(r"[A-Za-z0-9._:-]{4,128}", id_only):
            return {"id": id_only, "name": id_only, "paired": None, "reachable": None, "state": ""}
        return None

    state = match.group("state") or ""
    state_lower = state.lower()
    paired = "paired" in state_lower and "unpaired" not in state_lower and "not paired" not in state_lower
    if "not reachable" in state_lower:
        reachable = False
    elif "reachable" in state_lower:
        reachable = True
    else:
        reachable = None
    return {
        "id": match.group("id"),
        "name": match.group("name").strip(),
        "paired": paired,
        "reachable": reachable,
        "state": state,
    }

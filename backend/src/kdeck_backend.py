import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from kdeck_kde_receiver import KDEckKdeReceiver, interface_path_type, interface_priority, is_ignored_interface, is_usable_ipv4

DECK_USER = "deck"
DECK_UID = 1000
DEFAULT_ENV = {
    "DISPLAY": ":0",
    "XDG_RUNTIME_DIR": f"/run/user/{DECK_UID}",
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{DECK_UID}/bus",
    "QT_QPA_PLATFORM": "wayland",
    "WAYLAND_DISPLAY": "gamescope-0",
}
KDECONNECT_PORT_RANGE = "1714-1764"
COMMON_DIRECTORIES = (
    "/home/deck/Downloads",
    "/home/deck/Documents",
    "/home/deck/Pictures",
)
COMMAND_ENV_BASE = {
    "HOME": "/home/deck",
    "USER": DECK_USER,
    "LOGNAME": DECK_USER,
    "SHELL": "/bin/bash",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "en_US.UTF-8",
}


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "ok": self.ok,
        }


class KDEckBackend:
    def __init__(
        self,
        logger: Any = None,
        settings_dir: Optional[str] = None,
        runtime_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
    ):
        self.logger = logger
        self.settings_dir = Path(settings_dir or "/tmp/kdeck-settings")
        self.runtime_dir = Path(runtime_dir or "/tmp/kdeck-runtime")
        self.log_dir = Path(log_dir) if log_dir else None
        self.history_path = self.settings_dir / "transfer-history.json"
        self.notebook_path = self.settings_dir / "clipboard-notebook.json"
        self.daemon_pid_path = self.runtime_dir / "kdeconnectd.pid"
        self.daemon_log_path = self.runtime_dir / "kdeconnectd.log"
        self.managed_kde_dir = self.settings_dir / "managed-kde"
        self.managed_kde_desired = False
        self.managed_kde_pause_reason: Optional[str] = None
        self.mode_monitor_stop = threading.Event()
        self.mode_monitor_thread: Optional[threading.Thread] = None
        self.kde_receiver = KDEckKdeReceiver(
            state_dir=self.managed_kde_dir,
            on_clipboard=self._receive_managed_clipboard,
            incoming_dir=Path("/home/deck/Downloads"),
            logger=logger,
        )
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    async def get_status(self) -> dict[str, Any]:
        cli_path = shutil.which("kdeconnect-cli")
        daemon_path = shutil.which("kdeconnectd")
        qdbus_path = shutil.which("qdbus6") or shutil.which("qdbus")
        bus_path = Path(DEFAULT_ENV["XDG_RUNTIME_DIR"]) / "bus"
        daemon_running = await self._is_daemon_running()
        dbus_ready = await self._is_dbus_service_ready()

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
                "address": DEFAULT_ENV["DBUS_SESSION_BUS_ADDRESS"],
                "service_ready": dbus_ready,
                "qdbus_path": qdbus_path,
            },
            "environment": DEFAULT_ENV.copy(),
            "ports": KDECONNECT_PORT_RANGE,
            "common_directories": list(COMMON_DIRECTORIES),
        }

    async def get_connection_summary(self) -> dict[str, Any]:
        status = await self.get_status()
        devices = await self.list_devices()
        ips = await self.get_deck_ips()
        incoming = self.get_incoming_directories()

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
            "managed_kde": self.get_managed_kde_status(),
        }

    def start_managed_kde(self) -> dict[str, Any]:
        self.managed_kde_desired = True
        self._ensure_mode_monitor()
        if self._is_desktop_mode_active():
            self.managed_kde_pause_reason = "desktop_mode"
            self.kde_receiver.stop()
            return self.get_managed_kde_status()
        self.managed_kde_pause_reason = None
        result = self.kde_receiver.start()
        if result.get("running"):
            self.kde_receiver.reannounce_trusted_devices("start_managed_kde")
        return result

    def stop_managed_kde(self) -> dict[str, Any]:
        self.managed_kde_desired = False
        self._stop_mode_monitor()
        self.managed_kde_pause_reason = None
        return self.kde_receiver.stop()

    def accept_pending_pair(self) -> dict[str, Any]:
        return self.kde_receiver.accept_pending_pair()

    def reject_pending_pair(self) -> dict[str, Any]:
        return self.kde_receiver.reject_pending_pair()

    def get_managed_kde_status(self) -> dict[str, Any]:
        status = self.kde_receiver.status()
        desktop_mode = self._is_desktop_mode_active()
        if desktop_mode and status.get("running"):
            self.managed_kde_pause_reason = "desktop_mode"
        status["desktop_mode_active"] = desktop_mode
        status["desired"] = self.managed_kde_desired
        status["paused"] = self.managed_kde_pause_reason == "desktop_mode"
        status["pause_reason"] = self.managed_kde_pause_reason
        status["diagnostic_summary"] = self._receiver_diagnostic_summary(status)
        return status

    def _receiver_diagnostic_summary(self, status: dict[str, Any]) -> dict[str, Any]:
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

    def run_hidden_command(self, command: str) -> dict[str, Any]:
        normalized = " ".join(str(command or "").strip().lower().split())
        commands = {
            ":kdeck help": "List hidden commands.",
            ":kdeck status": "Show receiver diagnostic summary.",
            ":kdeck devices": "Show discovered and trusted device counts.",
            ":kdeck reannounce": "Send an immediate trusted-device reannounce.",
            ":kdeck logs": "Export redacted logs to Downloads.",
            ":kdeck export logs": "Export redacted logs to Downloads.",
            ":kdeck share logs": "Export logs and explain why direct reverse sending is not used.",
        }
        if normalized == ":kdeck help":
            return {"ok": True, "message": "\n".join(f"{name} - {description}" for name, description in commands.items()), "commands": commands}
        if normalized in (":kdeck logs", ":kdeck export logs", ":kdeck share logs"):
            result = self.export_logs()
            if normalized == ":kdeck share logs":
                result["message"] = "Logs exported to Downloads. Direct reverse sending is not supported by KDEck's isolated receiver."
            else:
                result["message"] = f"Logs exported: {result.get('path')}"
            return result
        if normalized == ":kdeck status":
            status = self.get_managed_kde_status()
            summary = status.get("diagnostic_summary") or {}
            return {"ok": True, "message": summary.get("message") or "Status ready.", "status": status}
        if normalized == ":kdeck devices":
            status = self.get_managed_kde_status()
            discovered = status.get("discovered_devices") or []
            trusted = status.get("trusted_devices") or {}
            message = f"Discovered devices: {len(discovered)}; trusted devices: {len(trusted)}."
            return {"ok": True, "message": message, "discovered_devices": discovered, "trusted_devices": trusted}
        if normalized == ":kdeck reannounce":
            result = self.kde_receiver.reannounce_trusted_devices("hidden_command")
            result["message"] = "Trusted-device reannounce sent." if result.get("ok") else "Receiver TCP listener is not ready."
            return result
        return self._error("unknown_hidden_command", "Unknown hidden command.", command=command)

    def _ensure_mode_monitor(self) -> None:
        if self.mode_monitor_thread and self.mode_monitor_thread.is_alive():
            return
        self.mode_monitor_stop.clear()
        self.mode_monitor_thread = threading.Thread(target=self._mode_monitor_loop, name="KDEckModeMonitor", daemon=True)
        self.mode_monitor_thread.start()

    def _stop_mode_monitor(self) -> None:
        self.mode_monitor_stop.set()
        if self.mode_monitor_thread and self.mode_monitor_thread.is_alive():
            self.mode_monitor_thread.join(timeout=1.5)
        self.mode_monitor_thread = None

    def _mode_monitor_loop(self) -> None:
        while not self.mode_monitor_stop.wait(5):
            if not self.managed_kde_desired:
                continue
            desktop_mode = self._is_desktop_mode_active()
            status = self.kde_receiver.status()
            if desktop_mode:
                if status.get("running"):
                    if self.logger:
                        self.logger.info("KDEck receiver paused because Plasma desktop mode is active")
                    self.kde_receiver.stop()
                self.managed_kde_pause_reason = "desktop_mode"
                continue
            if self.managed_kde_pause_reason == "desktop_mode":
                self.managed_kde_pause_reason = None
            if not status.get("running"):
                if self.logger:
                    self.logger.info("KDEck receiver resumed outside Plasma desktop mode")
                resumed = self.kde_receiver.start()
                if resumed.get("running"):
                    self.kde_receiver.reannounce_trusted_devices("resume_from_desktop_mode")

    def _is_desktop_mode_active(self) -> bool:
        pgrep = shutil.which("pgrep")
        if not pgrep:
            return False
        try:
            result = subprocess.run(
                [pgrep, "-u", DECK_USER, "-x", "plasmashell"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _receive_managed_clipboard(self, text: str, device_id: Optional[str] = None) -> None:
        text = str(text or "")[:10000]
        if not text:
            return
        self.save_notebook(text)
        clipboard_result = self.set_clipboard_sync(text)
        if self.logger:
            self.logger.info(
                "KDEck managed KDE received clipboard, device=%s length=%s clipboard=%s",
                device_id,
                len(text),
                clipboard_result.get("ok"),
            )

    async def diagnose(self) -> dict[str, Any]:
        status = await self.get_status()
        devices = await self.list_devices()
        network = await self._network_info()
        problems: list[dict[str, str]] = []

        if not status["kdeconnect_cli"]["found"]:
            problems.append(
                {
                    "code": "missing_cli",
                    "message": "找不到 kdeconnect-cli，无法通过命令行控制 KDE Connect。",
                }
            )
        if not status["kdeconnectd"]["found"]:
            problems.append(
                {
                    "code": "missing_daemon",
                    "message": "找不到 kdeconnectd，系统 KDE Connect 后台组件不完整。",
                }
            )
        if not status["dbus"]["bus_exists"]:
            problems.append(
                {
                    "code": "missing_dbus",
                    "message": "/run/user/1000/bus 不存在，当前 deck 用户会话 DBus 不可用。",
                }
            )
        if status["kdeconnectd"]["found"] and not status["kdeconnectd"]["running"]:
            problems.append(
                {
                    "code": "daemon_stopped",
                    "message": "kdeconnectd 未运行，可以由 KDEck 后端尝试拉起。",
                }
            )
        if status["kdeconnectd"]["running"] and not status["dbus"]["service_ready"]:
            problems.append(
                {
                    "code": "dbus_service_unavailable",
                    "message": "kdeconnectd 进程存在，但 org.kde.kdeconnect DBus 服务未就绪。",
                }
            )
        if devices["ok"] and not devices["paired"]:
            problems.append(
                {
                    "code": "no_paired_device",
                    "message": "当前没有已配对设备，需要先从可用设备列表发起配对。",
                }
            )
        explicit_reachability = [d["reachable"] for d in devices["paired"] if d["reachable"] is not None]
        if devices["ok"] and explicit_reachability and not any(explicit_reachability):
            problems.append(
                {
                    "code": "paired_not_reachable",
                    "message": "已有配对设备，但没有设备可达。常见原因是热点/AP 隔离、VPN 路由或两端不在同一网络。",
                }
            )

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

    async def ensure_daemon(self) -> dict[str, Any]:
        status = await self.get_status()
        if not status["kdeconnectd"]["found"]:
            return self._error("missing_daemon", "kdeconnectd not found.", status=status)
        if not status["kdeconnect_cli"]["found"]:
            return self._error("missing_cli", "kdeconnect-cli not found.", status=status)
        if not status["dbus"]["bus_exists"]:
            return self._error("missing_dbus", "The deck user DBus session bus is unavailable.", status=status)
        if status["kdeconnectd"]["running"] and status["dbus"]["service_ready"]:
            return {"ok": True, "state": "daemon_ready", "status": status}

        start = await self.start_daemon()
        if not start["ok"]:
            return start
        for _ in range(30):
            await asyncio.sleep(0.5)
            daemon_running = await self._is_daemon_running()
            dbus_ready = await self._is_dbus_service_ready()
            if daemon_running and dbus_ready:
                return {
                    "ok": True,
                    "state": "daemon_ready",
                    "status": await self.get_status(),
                }
        return self._error(
            "daemon_failed",
            "kdeconnectd started but DBus service was not ready within 15 seconds.",
            start=start,
            status=await self.get_status(),
            daemon_log=self._tail_file(self.daemon_log_path, 80),
        )

    async def start_daemon(self) -> dict[str, Any]:
        if await self._is_daemon_running():
            return {"ok": True, "state": "already_running", "status": await self.get_status()}
        daemon_path = shutil.which("kdeconnectd")
        if not daemon_path:
            return self._error("missing_daemon", "kdeconnectd not found.")
        result = self._spawn_daemon(daemon_path)
        if not result["ok"]:
            return self._error("daemon_start_failed", "Failed to start kdeconnectd.", **result)
        await asyncio.sleep(1)
        return {"ok": True, "state": "daemon_starting", **result}

    async def stop_daemon(self) -> dict[str, Any]:
        return await self.stop_managed_daemon()

    async def stop_managed_daemon(self) -> dict[str, Any]:
        pid = self._read_managed_daemon_pid()
        if not pid:
            return {"ok": True, "state": "no_managed_daemon"}
        if not self._is_managed_kdeconnectd_pid(pid):
            self._remove_file(self.daemon_pid_path)
            return {"ok": True, "state": "managed_daemon_not_owned", "pid": pid}
        result = await self._run(["kill", str(pid)], timeout=5)
        if result.returncode not in (0, 1):
            return self._error("managed_daemon_stop_failed", "Failed to stop the managed kdeconnectd.", command=result.to_dict())
        self._remove_file(self.daemon_pid_path)
        return {"ok": True, "state": "managed_daemon_stopped", "pid": pid, "command": result.to_dict()}

    async def restart_daemon(self) -> dict[str, Any]:
        stop = await self.stop_daemon()
        await asyncio.sleep(1)
        start = await self.start_daemon()
        ready = await self.ensure_daemon()
        return {"ok": ready["ok"], "stop": stop, "start": start, "ready": ready}

    async def refresh_devices(self) -> dict[str, Any]:
        ready = await self.ensure_daemon()
        if not ready["ok"]:
            return ready
        result = await self._kdeconnect_cli(["--refresh"], timeout=15)
        if not result.ok:
            return self._error("refresh_failed", "Failed to refresh device list.", command=result.to_dict())
        await asyncio.sleep(1)
        devices = await self.list_devices()
        return {"ok": devices["ok"], "command": result.to_dict(), "devices": devices}

    async def list_devices(self) -> dict[str, Any]:
        if not shutil.which("kdeconnect-cli"):
            return self._error("missing_cli", "kdeconnect-cli not found.")
        if not await self._is_daemon_running() or not await self._is_dbus_service_ready():
            return {
                "ok": False,
                "state": "daemon_not_ready",
                "paired": [],
                "available": [],
                "commands": {},
            }

        paired_result = await self._kdeconnect_cli(["--list-devices"], timeout=10)
        available_result = await self._kdeconnect_cli(["--list-available"], timeout=10)
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

    async def pair_device(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(device_id, "--pair", "pair_failed", "Failed to request pairing.")

    async def unpair_device(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(device_id, "--unpair", "unpair_failed", "Failed to unpair device.")

    async def send_clipboard(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(
            device_id,
            "--send-clipboard",
            "send_clipboard_failed",
            "Failed to send current clipboard.",
        )

    async def share_text(self, device_id: str, text: str) -> dict[str, Any]:
        if not text:
            return self._error("empty_text", "Text to send cannot be empty.")
        normalized = self._validate_device_id(device_id)
        if not normalized["ok"]:
            return normalized
        ready = await self.ensure_daemon()
        if not ready["ok"]:
            return ready
        result = await self._kdeconnect_cli(
            ["--share-text", text, "--device", normalized["device_id"]],
            timeout=30,
        )
        if not result.ok:
            return self._error("share_text_failed", "Failed to send text.", command=result.to_dict())
        return {"ok": True, "command": result.to_dict()}

    async def get_clipboard(self, max_chars: int = 500) -> dict[str, Any]:
        max_chars = max(0, min(int(max_chars), 5000))
        text = await self._read_clipboard(max_chars)
        if text is not None:
            return {
                "ok": True,
                "text": text[:max_chars],
                "length": len(text),
                "truncated": len(text) > max_chars,
            }
        script = (
            "import tkinter as tk\n"
            "root=tk.Tk(); root.withdraw()\n"
            "try:\n"
            "    data=root.clipboard_get()\n"
            "except Exception:\n"
            "    data=''\n"
            "root.destroy()\n"
            "print(data, end='')\n"
        )
        result = await self._run(["python3", "-c", script], timeout=5)
        if not result.ok:
            return self._error("clipboard_read_failed", "Failed to read Deck clipboard.", command=result.to_dict())
        text = result.stdout
        return {
            "ok": True,
            "text": text[:max_chars],
            "length": len(text),
            "truncated": len(text) > max_chars,
        }

    async def _read_clipboard(self, max_chars: int) -> Optional[str]:
        """Try native clipboard tools before falling back to tkinter."""
        if shutil.which("wl-paste"):
            result = await self._run(["wl-paste"], timeout=5)
            if result.ok:
                return result.stdout
        if shutil.which("xclip"):
            result = await self._run(["xclip", "-o", "-selection", "clipboard"], timeout=5)
            if result.ok:
                return result.stdout
        return None

    async def set_clipboard(self, text: str) -> dict[str, Any]:
        return self.set_clipboard_sync(text)

    def set_clipboard_sync(self, text: str) -> dict[str, Any]:
        if self._write_clipboard_native(text):
            return {"ok": True, "length": len(text)}
        script = (
            "import sys, tkinter as tk\n"
            "data=sys.stdin.read()\n"
            "root=tk.Tk(); root.withdraw()\n"
            "root.clipboard_clear(); root.clipboard_append(data); root.update()\n"
            "root.destroy()\n"
        )
        result = self._run_sync(["python3", "-c", script], input_text=text, timeout=5)
        if not result.ok:
            return self._error("clipboard_write_failed", "Failed to write Deck clipboard.", command=result.to_dict())
        return {"ok": True, "length": len(text)}

    def _write_clipboard_native(self, text: str) -> bool:
        """Try native clipboard tools, return True on success."""
        if shutil.which("wl-copy"):
            result = self._run_sync(["wl-copy"], input_text=text, timeout=5)
            if result.ok:
                return True
        if shutil.which("xclip"):
            result = self._run_sync(
                ["xclip", "-selection", "clipboard"],
                input_text=text,
                timeout=5,
            )
            if result.ok:
                return True
        return False

    async def share_file(self, device_id: str, path: str) -> dict[str, Any]:
        normalized = self._validate_device_id(device_id)
        if not normalized["ok"]:
            return normalized
        file_path = Path(path).expanduser()
        if not file_path.is_absolute():
            return self._error("path_not_absolute", "File path must be absolute.")
        if not file_path.exists():
            return self._error("path_not_found", "File not found.", path=str(file_path))
        if not file_path.is_file():
            return self._error("path_not_file", "Only single-file sharing is supported.", path=str(file_path))

        result = await self._kdeconnect_cli(
            ["--share", str(file_path), "--device", normalized["device_id"]],
            timeout=60,
        )
        status = "finished" if result.ok else "failed"
        self._append_transfer_history(
            {
                "direction": "send",
                "status": status,
                "device_id": normalized["device_id"],
                "file_name": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "timestamp": int(time.time()),
                "command_returncode": result.returncode,
            }
        )
        if not result.ok:
            return self._error("share_file_failed", "Failed to send file.", command=result.to_dict())
        return {"ok": True, "status": status, "file": str(file_path), "command": result.to_dict()}

    async def list_files(self, directory: str = "", limit: int = 200) -> dict[str, Any]:
        base = Path(directory or COMMON_DIRECTORIES[0]).expanduser()
        limit = max(1, min(int(limit), 500))
        allowed_roots = [Path(p).expanduser().resolve() for p in COMMON_DIRECTORIES]
        try:
            resolved = base.resolve()
        except FileNotFoundError:
            return self._error("directory_not_found", "Directory not found.", directory=str(base))
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            return self._error(
                "directory_not_allowed",
                "File browser is limited to Downloads, Documents, and Pictures.",
                directory=str(resolved),
            )
        if not resolved.is_dir():
            return self._error("path_not_directory", "Path is not a directory.", directory=str(resolved))

        entries = []
        for item in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:limit]:
            try:
                stat = item.stat()
            except OSError:
                continue
            entries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "is_file": item.is_file(),
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                }
            )
        return {"ok": True, "directory": str(resolved), "entries": entries}

    def get_common_directories(self) -> dict[str, Any]:
        return {
            "ok": True,
            "directories": [
                {"path": path, "exists": Path(path).exists()} for path in COMMON_DIRECTORIES
            ],
        }

    def get_incoming_directories(self) -> dict[str, Any]:
        return {
            "ok": True,
            "items": [
                {
                    "device_id": None,
                    "path": str(self.kde_receiver.incoming_dir),
                    "config": None,
                    "default": True,
                    "managed_by": "KDEck",
                }
            ],
        }

    async def get_deck_ips(self) -> dict[str, Any]:
        interfaces = await self._network_info()
        items = self._receiver_ips_from_interfaces(interfaces)
        items.sort(key=lambda item: (-item["priority"], item["interface"], item["address"]))
        return {"ok": True, "items": items, "primary": items[0] if items else None}

    def get_transfer_history(self, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        history = self._read_history()
        return {"ok": True, "items": history[-limit:][::-1]}

    def get_notebook(self) -> dict[str, Any]:
        if not self.notebook_path.exists():
            return {"ok": True, "text": "", "updated_at": None}
        try:
            data = json.loads(self.notebook_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ok": True, "text": "", "updated_at": None}
        return {
            "ok": True,
            "text": str(data.get("text", "")),
            "updated_at": data.get("updated_at"),
        }

    def save_notebook(self, text: str) -> dict[str, Any]:
        text = str(text or "")
        payload = {"text": text, "updated_at": int(time.time())}
        self.notebook_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, **payload}

    def export_logs(self) -> dict[str, Any]:
        self.kde_receiver._flush_event_buffer()
        target_dir = self._log_export_dir()
        target = target_dir / f"kdeck-logs-{int(time.time())}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "exported_at": int(time.time()),
                "export_path": str(target),
                "settings_dir": str(self.settings_dir),
                "runtime_dir": str(self.runtime_dir),
                "log_dir": str(self.log_dir) if self.log_dir else None,
                "receiver": self.get_managed_kde_status(),
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in (self.daemon_log_path, self.daemon_pid_path):
                if path.exists():
                    archive.write(path, arcname=f"runtime/{path.name}")
            for path in self._receiver_event_logs():
                if path.exists():
                    archive.write(path, arcname=f"managed-kde/{path.name}")
            if self.history_path.exists():
                archive.writestr("transfer-history.redacted.json", self._redacted_json_file(self.history_path, {"device_id", "path"}))
            if self.notebook_path.exists():
                archive.writestr("clipboard-notebook.redacted.json", self._redacted_notebook())
            trusted = self._redacted_trusted_devices()
            if trusted is not None:
                archive.writestr("managed-kde/trusted-devices.redacted.json", json.dumps(trusted, ensure_ascii=False, indent=2))
            for path in self._recent_decky_logs():
                archive.write(path, arcname=f"decky-log/{path.name}")
        return {"ok": True, "path": str(target)}

    def _log_export_dir(self) -> Path:
        downloads = Path(COMMON_DIRECTORIES[0])
        if downloads.exists():
            return downloads
        return self.runtime_dir

    def cleanup_plugin_data(self, log_dir: Optional[str] = None) -> dict[str, Any]:
        removed = []
        for path in (self.settings_dir, self.runtime_dir, Path(log_dir) if log_dir else None):
            if path and self._is_owned_plugin_dir(path):
                shutil.rmtree(path, ignore_errors=True)
                removed.append(str(path))
        return {"ok": True, "removed": removed}

    async def _device_action(
        self,
        device_id: str,
        action: str,
        error_code: str,
        error_message: str,
        extra_args: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        normalized = self._validate_device_id(device_id)
        if not normalized["ok"]:
            return normalized
        ready = await self.ensure_daemon()
        if not ready["ok"]:
            return ready
        args = [action, "--device", normalized["device_id"]]
        if extra_args:
            args.extend(extra_args)
        result = await self._kdeconnect_cli(args, timeout=30)
        if not result.ok:
            return self._error(error_code, error_message, command=result.to_dict())
        return {"ok": True, "command": result.to_dict()}

    async def _is_daemon_running(self) -> bool:
        result = await self._run(["pgrep", "-u", DECK_USER, "-x", "kdeconnectd"], timeout=5)
        return result.ok and bool(result.stdout.strip())

    async def _is_dbus_service_ready(self) -> bool:
        if shutil.which("busctl"):
            result = await self._run(["busctl", "--user", "list"], timeout=5)
            return result.ok and "org.kde.kdeconnect" in result.stdout
        if shutil.which("qdbus6") or shutil.which("qdbus"):
            qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
            result = await self._run([qdbus, "org.kde.kdeconnect"], timeout=5)
            return result.ok
        return False

    async def _kdeconnect_cli(self, args: list[str], timeout: int = 15) -> CommandResult:
        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        return await self._run([cli, *args], timeout=timeout)

    async def _run(
        self,
        command: list[str],
        timeout: int = 15,
        input_text: Optional[str] = None,
        detach: bool = False,
    ) -> CommandResult:
        env = self._command_env()

        actual_command = self._as_deck_user_command(command)
        if detach:
            await asyncio.create_subprocess_exec(
                *actual_command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
            return CommandResult(command=actual_command, returncode=0, stdout="", stderr="")

        proc = await asyncio.create_subprocess_exec(
            *actual_command,
            stdin=asyncio.subprocess.PIPE if input_text is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input_text.encode("utf-8") if input_text is not None else None),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            stdout, stderr = await proc.communicate()
            return CommandResult(
                command=actual_command,
                returncode=124,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=(stderr.decode("utf-8", errors="replace") + "\nCommand timed out.").strip(),
            )
        return CommandResult(
            command=actual_command,
            returncode=proc.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    def _run_sync(
        self,
        command: list[str],
        timeout: int = 15,
        input_text: Optional[str] = None,
    ) -> CommandResult:
        env = self._command_env()
        actual_command = self._as_deck_user_command(command)
        try:
            proc = subprocess.run(
                actual_command,
                input=input_text.encode("utf-8") if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
            return CommandResult(command=actual_command, returncode=124, stdout=stdout, stderr=(stderr + "\nCommand timed out.").strip())
        return CommandResult(
            command=actual_command,
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )

    def _spawn_daemon(self, daemon_path: str) -> dict[str, Any]:
        env = self._command_env()
        env["KDECK_MANAGED_DAEMON"] = "1"
        command = ["setsid", daemon_path]
        actual_command = self._as_deck_user_command(command, {"KDECK_MANAGED_DAEMON": "1"})
        try:
            self.daemon_log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = self.daemon_log_path.open("ab")
            proc = subprocess.Popen(
                actual_command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
            log_file.close()
        except OSError as exc:
            return {
                "ok": False,
                "command": actual_command,
                "error_detail": str(exc),
                "daemon_log": self._tail_file(self.daemon_log_path, 80),
            }
        self.daemon_pid_path.write_text(
            json.dumps({"pid": proc.pid, "command": actual_command, "started_at": int(time.time())}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "pid": proc.pid,
            "command": actual_command,
            "environment": DEFAULT_ENV.copy(),
            "daemon_log_path": str(self.daemon_log_path),
        }

    def _as_deck_user_command(self, command: list[str], extra_env: Optional[dict[str, str]] = None) -> list[str]:
        if hasattr(os, "geteuid") and os.geteuid() == 0 and shutil.which("runuser"):
            command_env = COMMAND_ENV_BASE.copy()
            command_env.update(DEFAULT_ENV)
            if extra_env:
                command_env.update(extra_env)
            return ["runuser", "-u", DECK_USER, "--", "env", *[f"{k}={v}" for k, v in command_env.items()], *command]
        return command

    def _command_env(self) -> dict[str, str]:
        env = COMMAND_ENV_BASE.copy()
        env.update(DEFAULT_ENV)
        return env

    async def _network_info(self) -> dict[str, Any]:
        hostname_ips = []
        try:
            hostname_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except OSError:
            hostname_ips = []

        ip_json = None
        if shutil.which("ip"):
            result = await self._run(["ip", "-j", "addr"], timeout=5)
            if result.ok:
                try:
                    ip_json = json.loads(result.stdout)
                except json.JSONDecodeError:
                    ip_json = None

        return {
            "hostname": socket.gethostname(),
            "hostname_ips": hostname_ips,
            "interfaces": ip_json,
            "kdeconnect_ports": KDECONNECT_PORT_RANGE,
        }

    def _validate_device_id(self, device_id: str) -> dict[str, Any]:
        device_id = (device_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{4,128}", device_id):
            return self._error("invalid_device_id", "Device ID format is invalid.")
        return {"ok": True, "device_id": device_id}

    def _read_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _receiver_ips_from_interfaces(self, interfaces: dict[str, Any]) -> list[dict[str, Any]]:
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

    def _append_transfer_history(self, item: dict[str, Any]) -> None:
        history = self._read_history()
        history.append(item)
        history = history[-500:]
        self.history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _tail_file(self, path: Path, max_lines: int) -> str:
        try:
            with path.open("rb") as f:
                chunk_size = 8192
                f.seek(0, 2)
                file_size = f.tell()
                lines: list[bytes] = []
                remaining = file_size
                while remaining > 0 and len(lines) <= max_lines:
                    read_size = min(chunk_size, remaining)
                    remaining -= read_size
                    f.seek(remaining)
                    chunk = f.read(read_size)
                    if remaining == 0:
                        lines = chunk.splitlines()
                    else:
                        splitted = chunk.split(b"\n")
                        if lines:
                            splitted[-1] += lines[0]
                            lines = splitted + lines[1:]
                        else:
                            lines = splitted
                return "\n".join(
                    line.decode("utf-8", errors="replace") for line in lines[-max_lines:]
                )
        except OSError:
            return ""

    def _read_managed_daemon_pid(self) -> Optional[int]:
        try:
            text = self.daemon_pid_path.read_text(encoding="utf-8").strip()
            if not text:
                return None
            if text.startswith("{"):
                data = json.loads(text)
                return int(data.get("pid"))
            return int(text)
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            return None

    def _is_managed_kdeconnectd_pid(self, pid: int) -> bool:
        proc = Path("/proc") / str(pid)
        try:
            comm = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return False
        if comm != "kdeconnectd":
            return False
        try:
            status = (proc / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if not any(line.startswith("Uid:") and line.split()[1] == str(DECK_UID) for line in status.splitlines()):
            return False
        try:
            environ = (proc / "environ").read_bytes().decode("utf-8", errors="replace")
        except OSError:
            return False
        return "KDECK_MANAGED_DAEMON=1" in environ.split("\0")

    def _remove_file(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            if self.logger:
                self.logger.warning("Failed to remove %s", path)

    def _is_owned_plugin_dir(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        name = resolved.name.lower()
        return name == "kdeck" or name.startswith("kdeck-")

    def _read_ini_value(self, path: Path, key: str) -> Optional[str]:
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                clean = line.strip()
                if not clean or clean.startswith(("#", "[")) or "=" not in clean:
                    continue
                item_key, value = clean.split("=", 1)
                if item_key.strip() == key:
                    return value.strip()
        except OSError:
            return None
        return None

    def _receiver_event_logs(self) -> list[Path]:
        logs = list(self.managed_kde_dir.glob("receiver-events.jsonl*"))
        return sorted(logs, key=lambda path: (path.name != "receiver-events.jsonl", path.name))

    def _recent_decky_logs(self, limit: int = 2) -> list[Path]:
        if not self.log_dir or not self.log_dir.exists():
            return []
        logs = [path for path in self.log_dir.glob("*.log") if path.is_file()]
        return sorted(logs, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]

    def _redacted_json_file(self, path: Path, redacted_keys: set[str]) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "{}"
        return json.dumps(self._redact_json(data, redacted_keys), ensure_ascii=False, indent=2)

    def _redacted_json_value(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        return f"{text[:8]}..." if len(text) > 8 else "***"

    def _redact_json(self, data: Any, redacted_keys: set[str]) -> Any:
        if isinstance(data, dict):
            return {
                key: self._redacted_json_value(value) if key in redacted_keys else self._redact_json(value, redacted_keys)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self._redact_json(item, redacted_keys) for item in data]
        return data

    def _redacted_notebook(self) -> str:
        try:
            data = json.loads(self.notebook_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "{}"
        text = str(data.get("text", ""))
        payload = {"updated_at": data.get("updated_at"), "text_length": len(text)}
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _redacted_trusted_devices(self) -> Optional[dict[str, Any]]:
        if not (self.managed_kde_dir / "trusted-devices.json").exists():
            return None
        trusted = self.kde_receiver._trusted_devices()
        devices = []
        for device_id, value in trusted.items():
            item = value if isinstance(value, dict) else {}
            fingerprint = str(item.get("fingerprint") or "")
            devices.append(
                {
                    "device_id_prefix": str(device_id)[:8],
                    "trust_mode": item.get("trust_mode"),
                    "fingerprint_prefix": fingerprint[:12] if fingerprint else None,
                    "paired_at": item.get("paired_at"),
                }
            )
        return {"device_count": len(devices), "devices": devices}

    def list_sendable_files(self, category: str = "screenshots") -> dict[str, Any]:
        limit = 50
        if category == "screenshots":
            return self._scan_screenshots(limit)
        if category == "recordings":
            return self._scan_recordings(limit)
        if category == "logs":
            return self._scan_logs(limit)
        return {"ok": False, "error": {"code": "unknown_category", "message": f"Unknown category: {category}"}}

    def _scan_screenshots(self, limit: int) -> dict[str, Any]:
        steam_userdata = Path("/home/deck/.local/share/Steam/userdata")
        if not steam_userdata.is_dir():
            return {"ok": True, "files": [], "message": "Steam userdata directory not found."}
        extensions = {".jpg", ".jpeg", ".png"}
        files: list[dict[str, Any]] = []
        for steam_id_dir in sorted(steam_userdata.iterdir()):
            if not steam_id_dir.is_dir() or steam_id_dir.name == "0" or steam_id_dir.name == "anonymous":
                continue
            screenshots_root = steam_id_dir / "760" / "remote"
            if not screenshots_root.is_dir():
                continue
            for app_id_dir in sorted(screenshots_root.iterdir()):
                screenshot_dir = app_id_dir / "screenshots"
                if not screenshot_dir.is_dir():
                    continue
                for entry in sorted(screenshot_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in extensions:
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    files.append(self._file_entry(entry, st, app_id_dir.name))
                    if len(files) >= limit:
                        break
                if len(files) >= limit:
                    break
            if len(files) >= limit:
                break
        return {"ok": True, "files": files}

    def _scan_recordings(self, limit: int) -> dict[str, Any]:
        extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
        files: list[dict[str, Any]] = []
        steam_userdata = Path("/home/deck/.local/share/Steam/userdata")
        if steam_userdata.is_dir():
            for steam_id_dir in sorted(steam_userdata.iterdir()):
                if not steam_id_dir.is_dir() or steam_id_dir.name == "0" or steam_id_dir.name == "anonymous":
                    continue
                recordings_root = steam_id_dir / "gamerecordings"
                if not recordings_root.is_dir():
                    continue
                for entry in sorted(recordings_root.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in extensions:
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    files.append(self._file_entry(entry, st))
                    if len(files) >= limit:
                        break
                if len(files) >= limit:
                    break
        videos_dir = Path("/home/deck/Videos")
        if videos_dir.is_dir():
            for entry in sorted(videos_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in extensions:
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                files.append(self._file_entry(entry, st))
                if len(files) >= limit:
                    break
        return {"ok": True, "files": files}

    def _scan_logs(self, limit: int) -> dict[str, Any]:
        extensions = {".log", ".jsonl", ".txt", ".old"}
        files: list[dict[str, Any]] = []
        search_roots: list[Path] = []
        if self.log_dir:
            search_roots.append(self.log_dir)
        if self.runtime_dir:
            search_roots.append(self.runtime_dir)
        steam_logs = Path("/home/deck/.local/share/Steam/logs")
        if steam_logs.is_dir():
            search_roots.append(steam_logs)
        for root in search_roots:
            if not root.is_dir():
                continue
            for entry in sorted(root.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in extensions and entry.name.lower() != "kdeconnectd.log":
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                files.append(self._file_entry(entry, st))
                if len(files) >= limit:
                    break
            if len(files) >= limit:
                break
        return {"ok": True, "files": files}

    @staticmethod
    def _file_entry(entry: Path, st: Any, app_id: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": str(entry),
            "name": entry.name,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        }
        if app_id:
            result["app_id"] = app_id
        return result

    def send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        return self.kde_receiver.send_share_request_to_peer(file_path, device_id)

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}


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
            return {
                "id": id_only,
                "name": id_only,
                "paired": None,
                "reachable": None,
                "state": "",
            }
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


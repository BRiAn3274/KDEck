"""KDEck diagnostics — system status checks and connection summary."""

import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import kdeck_config as config

DIAGNOSTIC_MESSAGES = {
    "certificate_init_failed": "KDEck receiver could not initialize its certificate.",
    "discovery_udp_bind_failed": "KDEck could not bind the UDP discovery port.",
    "tcp_listener_bind_failed": "KDEck could not bind a KDE Connect TCP listener port.",
    "tcp_connect_failed": "Device was found, but TCP connection failed.",
    "tcp_connect_timeout": "Device was found, but TCP connection timed out.",
    "tls_handshake_failed": "Device connected, but the secure session could not be established.",
    "transfer_timeout": "The device did not request the file payload in time.",
    "transfer_incomplete": "The device did not receive the full file.",
}


def diagnostic_error(code: str, stage: str, message: str, **details: Any) -> dict[str, Any]:
    """Build a structured diagnostic error payload."""
    return {
        "code": code,
        "stage": stage,
        "message": message,
        "time": int(time.time()),
        **details,
    }


def diagnostic_message(code: Optional[str]) -> Optional[str]:
    """Return a user-readable English fallback message for a diagnostic code."""
    if not code:
        return None
    return DIAGNOSTIC_MESSAGES.get(code)


async def build_status(daemon, run_fn) -> dict[str, Any]:
    """Build the full system status dict (used by daemon.ensure_daemon and diagnostics)."""
    cli_path = shutil.which("kdeconnect-cli")
    daemon_path = shutil.which("kdeconnectd")
    qdbus_path = shutil.which("qdbus6") or shutil.which("qdbus")
    env = config.default_env()
    bus_path = Path(env["XDG_RUNTIME_DIR"]) / "bus"
    daemon_running = await daemon.is_daemon_running()
    dbus_ready = await daemon.is_dbus_service_ready()
    daemon_pids = await _kdeconnectd_pids(run_fn)

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
            "pids": daemon_pids,
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
            connection_code = "missing_component"
        elif not status["kdeconnectd"]["found"]:
            connection_code = "missing_component"
        elif not status["kdeconnectd"]["running"]:
            connection_code = "not_started"
        elif not status["dbus"]["service_ready"]:
            connection_code = "starting"
        elif selected and selected.get("reachable") is False:
            connection_code = "unreachable"
        elif selected:
            connection_code = "ready"
        else:
            connection_code = "not_connected"

        connection_device = selected["name"] if selected else None

        return {
            "ok": status["ok"],
            "connection": connection_code,
            "connection_device": connection_device,
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
            problems.append({"code": "missing_cli", "message": "kdeconnect-cli not found, cannot control KDE Connect via CLI."})
        if not status["kdeconnectd"]["found"]:
            problems.append({"code": "missing_daemon", "message": "kdeconnectd not found, KDE Connect daemon is incomplete."})
        if not status["dbus"]["bus_exists"]:
            problems.append({"code": "missing_dbus", "message": "/run/user/1000/bus does not exist, session DBus is unavailable."})
        if status["kdeconnectd"]["found"] and not status["kdeconnectd"]["running"]:
            problems.append({"code": "daemon_stopped", "message": "kdeconnectd is not running, KDEck backend can attempt to start it."})
        if len(status["kdeconnectd"].get("pids") or []) > 0 and self.kde_receiver.status().get("running"):
            problems.append({
                "code": "official_daemon_conflict",
                "message": "kdeconnectd is running while KDEck managed receiver is active; this can steal KDE Connect traffic on port 1716.",
            })
        if status["kdeconnectd"]["running"] and not status["dbus"]["service_ready"]:
            problems.append({"code": "dbus_service_unavailable", "message": "kdeconnectd process exists but org.kde.kdeconnect DBus service is not ready."})
        if devices["ok"] and not devices["paired"]:
            problems.append({"code": "no_paired_device", "message": "No paired device found, pair a device from the available list first."})
        explicit_reachability = [d["reachable"] for d in devices["paired"] if d["reachable"] is not None]
        if devices["ok"] and explicit_reachability and not any(explicit_reachability):
            problems.append({
                "code": "paired_not_reachable",
                "message": "Paired devices exist but none are reachable. Common causes: AP isolation, VPN routing, or different networks.",
            })

        return {
            "ok": not problems,
            "status": status,
            "devices": devices,
            "network": network,
            "problems": problems,
            "hints": [
                "KDE Connect uses TCP/UDP ports 1714-1764.",
                "Mobile hotspots, guest Wi-Fi, and AP isolation can prevent device discovery.",
                "EasyTier, ZeroTier, Tailscale and similar tools may alter routing; device visibility must be tested empirically.",
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
        last_problem = status.get("last_payload_error") or status.get("last_tls_error") or status.get("last_connect_error") or status.get("last_error")
        last_state_transition = status.get("last_state_transition")
        connection_states = status.get("connection_states") if isinstance(status.get("connection_states"), dict) else {}
        if isinstance(last_problem, dict):
            problem_code = last_problem.get("code")
            problem_message = diagnostic_message(problem_code) or last_problem.get("message")
        else:
            problem_code = None
            problem_message = None

        if problem_code == "transfer_timeout":
            state = "transfer_timeout"
            message = problem_message or "The device did not request the file payload in time."
        elif problem_code == "transfer_incomplete":
            state = "transfer_incomplete"
            message = problem_message or "The device did not receive the full file."
        elif problem_code and last_problem and last_problem.get("stage") == "tls":
            state = "tls_error"
            message = problem_message or "Secure session failed."
        elif problem_code and last_problem and last_problem.get("stage") == "tcp":
            state = "tcp_error"
            message = problem_message or "TCP connection failed."
        elif checks["paused"]:
            state = "paused_desktop_mode"
            message = "Desktop mode is active, KDEck receiver is paused."
        elif not checks["desired"]:
            state = "disabled"
            message = "KDEck receiver was not requested to start."
        elif not checks["udp"] or not checks["tcp"]:
            state = "listener_unready"
            message = "KDEck receiver is starting up or listener failed."
        elif not checks["recent_discovery"]:
            state = "waiting_discovery"
            message = "KDEck receiver is listening, no external device discovery received yet."
        elif checks["paired"]:
            state = "paired"
            message = "KDEck receiver has trusted devices, ready for clipboard and file transfer."
        else:
            state = "discovered_unpaired"
            message = "KDEck receiver discovered devices, awaiting pairing or trusted connection."
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
            "last_state_transition": last_state_transition,
            "connection_states": connection_states,
            "last_problem": last_problem,
            "problem_code": problem_code,
            "problem_message": problem_message,
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


async def _kdeconnectd_pids(run_fn) -> list[int]:
    if run_fn is None:
        return []
    try:
        result = await run_fn(["pgrep", "-u", config.deck_user(), "-x", "kdeconnectd"], timeout=5)
    except Exception:
        return []
    if not getattr(result, "ok", False):
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids

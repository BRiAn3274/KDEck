"""KDEck Backend — thin facade orchestrating all sub-modules.

This module is the single entry point used by main.py. It delegates to:
- kdeck_config: environment/path configuration
- kdeck_daemon: kdeconnectd process management
- kdeck_clipboard: clipboard read/write
- kdeck_file_manager: file browsing, transfer, history
- kdeck_network: interface discovery, IP sorting
- kdeck_notebook: clipboard notebook persistence
- kdeck_diagnostics: status checks, connection summary
- kdeck_kde_receiver: managed KDE Connect protocol receiver
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Optional

import kdeck_config as config
from kdeck_clipboard import KDEckClipboard
from kdeck_config import CommandResult
from kdeck_daemon import KDEckDaemon
from kdeck_diagnostics import KDEckDiagnostics
from kdeck_file_manager import KDEckFileManager
from kdeck_kde_receiver import KDEckKdeReceiver
from kdeck_network import KDEckNetwork
from kdeck_notebook import KDEckNotebook


class KDEckBackend:
    """Orchestration facade — all Plugin API methods delegate here."""

    def __init__(
        self,
        logger: Any = None,
        settings_dir: Optional[str] = None,
        runtime_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        event_loop: Any = None,
    ):
        self.logger = logger
        self.loop = event_loop
        self.settings_dir = Path(settings_dir or "/tmp/kdeck-settings")
        self.runtime_dir = Path(runtime_dir or "/tmp/kdeck-runtime")
        self.log_dir = Path(log_dir) if log_dir else None

        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        # Managed KDE receiver state
        self.managed_kde_dir = self.settings_dir / "managed-kde"
        self.managed_kde_desired = False
        self.managed_kde_pause_reason: Optional[str] = None
        self.mode_monitor_stop = threading.Event()
        self.mode_monitor_thread: Optional[threading.Thread] = None

        # Initialize sub-modules
        self.kde_receiver = KDEckKdeReceiver(
            state_dir=self.managed_kde_dir,
            on_clipboard=self._receive_managed_clipboard,
            incoming_dir=config.deck_home() / "Downloads",
            logger=logger,
        )
        self.daemon = KDEckDaemon(
            runtime_dir=self.runtime_dir,
            logger=logger,
            run_fn=self._run,
        )
        self.clipboard = KDEckClipboard(
            logger=logger,
            run_fn=self._run,
            run_sync_fn=self._run_sync,
        )
        self.notebook = KDEckNotebook(
            notebook_path=self.settings_dir / "clipboard-notebook.json",
            logger=logger,
        )
        self.network = KDEckNetwork(
            logger=logger,
            run_fn=self._run,
        )
        self.file_manager = KDEckFileManager(
            settings_dir=self.settings_dir,
            kde_receiver=self.kde_receiver,
            logger=logger,
            run_fn=self._run,
            log_dir=self.log_dir,
            runtime_dir=self.runtime_dir,
        )
        self.kde_receiver.on_file_received = self.file_manager.record_received_file
        self.diagnostics = KDEckDiagnostics(
            daemon=self.daemon,
            network=self.network,
            file_manager=self.file_manager,
            kde_receiver=self.kde_receiver,
            logger=logger,
            run_fn=self._run,
        )

    # ------------------------------------------------------------------
    # Status & diagnostics
    # ------------------------------------------------------------------

    async def get_status(self) -> dict[str, Any]:
        return await self.diagnostics.get_status()

    async def diagnose(self) -> dict[str, Any]:
        return await self.diagnostics.diagnose()

    async def get_connection_summary(self) -> dict[str, Any]:
        return await self.diagnostics.get_connection_summary(self.get_managed_kde_status)

    # ------------------------------------------------------------------
    # Managed KDE receiver
    # ------------------------------------------------------------------

    def start_managed_kde(self) -> dict[str, Any]:
        self.managed_kde_desired = True
        self._ensure_mode_monitor()
        if self._is_desktop_mode_active():
            self.managed_kde_pause_reason = "desktop_mode"
            self.kde_receiver.set_connection_state(self.kde_receiver.device_id, "paused_desktop", "desktop_mode_active")
            self.kde_receiver.stop()
            return self.get_managed_kde_status()
        self.managed_kde_pause_reason = None
        self.daemon.stop_user_daemons_sync("managed_receiver_start")
        self.daemon.stop_managed_daemon_sync()
        result = self.kde_receiver.start()
        if result.get("running"):
            self.kde_receiver.reannounce_trusted_devices("start_managed_kde")
        return result

    def stop_managed_kde(self) -> dict[str, Any]:
        self.managed_kde_desired = False
        self._stop_mode_monitor()
        self.managed_kde_pause_reason = None
        return self.kde_receiver.stop()

    def get_managed_kde_status(self) -> dict[str, Any]:
        status = self.kde_receiver.status()
        desktop_mode = self._is_desktop_mode_active()
        if desktop_mode and status.get("running"):
            self.managed_kde_pause_reason = "desktop_mode"
            self.kde_receiver.set_connection_state(self.kde_receiver.device_id, "paused_desktop", "desktop_mode_active")
        status["desktop_mode_active"] = desktop_mode
        status["desired"] = self.managed_kde_desired
        status["paused"] = self.managed_kde_pause_reason == "desktop_mode"
        status["pause_reason"] = self.managed_kde_pause_reason
        status["diagnostic_summary"] = KDEckDiagnostics.receiver_diagnostic_summary(status)
        return status

    def broadcast_discovery(self) -> dict[str, Any]:
        result = self.kde_receiver.reannounce_trusted_devices("manual_discovery")
        result["message"] = "KDEck discovery broadcast sent." if result.get("ok") else "KDEck receiver TCP listener is not ready."
        return result

    # ------------------------------------------------------------------
    # Daemon lifecycle
    # ------------------------------------------------------------------

    async def ensure_daemon(self) -> dict[str, Any]:
        return await self.daemon.ensure_daemon()

    async def start_daemon(self) -> dict[str, Any]:
        return await self.daemon.start_daemon()

    async def stop_daemon(self) -> dict[str, Any]:
        return await self.daemon.stop_daemon()

    async def stop_managed_daemon(self) -> dict[str, Any]:
        return await self.daemon.stop_managed_daemon()

    async def restart_daemon(self) -> dict[str, Any]:
        return await self.daemon.restart_daemon()

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------

    async def refresh_devices(self) -> dict[str, Any]:
        ready = await self.daemon.ensure_daemon()
        if not ready["ok"]:
            return ready
        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        result = await self._run([cli, "--refresh"], timeout=15)
        if not result.ok:
            return self._error("refresh_failed", "Failed to refresh device list.", command=result.to_dict())
        await asyncio.sleep(1)
        devices = await self.list_devices()
        return {"ok": devices["ok"], "command": result.to_dict(), "devices": devices}

    async def list_devices(self) -> dict[str, Any]:
        return await self.diagnostics._list_devices()

    async def pair_device(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(device_id, "--pair", "pair_failed", "Failed to request pairing.")

    async def unpair_device(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(device_id, "--unpair", "unpair_failed", "Failed to unpair device.")

    async def send_clipboard(self, device_id: str) -> dict[str, Any]:
        return await self._device_action(device_id, "--send-clipboard", "send_clipboard_failed", "Failed to send current clipboard.")

    async def share_text(self, device_id: str, text: str) -> dict[str, Any]:
        if not text:
            return self._error("empty_text", "Text to send cannot be empty.")
        normalized = self._validate_device_id(device_id)
        if not normalized["ok"]:
            return normalized
        ready = await self.daemon.ensure_daemon()
        if not ready["ok"]:
            return ready
        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        result = await self._run([cli, "--share-text", text, "--device", normalized["device_id"]], timeout=30)
        if not result.ok:
            return self._error("share_text_failed", "Failed to send text.", command=result.to_dict())
        return {"ok": True, "command": result.to_dict()}

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    async def get_clipboard(self, max_chars: int = 500) -> dict[str, Any]:
        return await self.clipboard.get_clipboard(max_chars)

    async def set_clipboard(self, text: str) -> dict[str, Any]:
        return await self.clipboard.set_clipboard(text)

    def set_clipboard_sync(self, text: str) -> dict[str, Any]:
        return self.clipboard.set_clipboard_sync(text)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    async def share_file(self, device_id: str, path: str) -> dict[str, Any]:
        ready = await self.daemon.ensure_daemon()
        if not ready["ok"]:
            return ready
        return await self.file_manager.share_file(device_id, path)

    async def list_files(self, directory: str = "", limit: int = 200) -> dict[str, Any]:
        return await self.file_manager.list_files(directory, limit)

    def get_common_directories(self) -> dict[str, Any]:
        return self.file_manager.get_common_directories()

    def get_incoming_directories(self) -> dict[str, Any]:
        return self.file_manager.get_incoming_directories()

    def get_transfer_history(self, limit: int = 50) -> dict[str, Any]:
        return self.file_manager.get_transfer_history(limit)

    def list_sendable_files(self, category: str = "screenshots") -> dict[str, Any]:
        return self.file_manager.list_sendable_files(category)

    def send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        return self.file_manager.send_file_to_phone(file_path, device_id)

    def start_send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        return self.file_manager.start_send_file_to_phone(file_path, device_id)

    def get_send_jobs(self, limit: int = 20) -> dict[str, Any]:
        return self.file_manager.get_send_jobs(limit)

    def start_send_diagnostic_bundle(self, device_id: str) -> dict[str, Any]:
        bundle = self.export_logs()
        if not bundle.get("ok") or not bundle.get("path"):
            return bundle
        return self.file_manager.start_send_file_to_phone(str(bundle["path"]), device_id)

    def get_thumbnail_base64(self, path: str) -> dict[str, Any]:
        return self.file_manager.get_thumbnail_base64(path)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    async def get_deck_ips(self) -> dict[str, Any]:
        return await self.network.get_deck_ips()

    # ------------------------------------------------------------------
    # Notebook
    # ------------------------------------------------------------------

    def get_notebook(self) -> dict[str, Any]:
        return self.notebook.get_notebook()

    def save_notebook(self, text: str) -> dict[str, Any]:
        return self.notebook.save_notebook(text)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def export_logs(self) -> dict[str, Any]:
        self.kde_receiver.flush_events()
        target_dir = self._log_export_dir()
        target = target_dir / f"kdeck-logs-{int(time.time())}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            status_snapshot = self._redact_status_snapshot(self.get_managed_kde_status())
            manifest = {
                "exported_at": int(time.time()),
                "export_name": target.name,
                "settings_dir_name": self.settings_dir.name,
                "runtime_dir_name": self.runtime_dir.name,
                "log_dir_name": self.log_dir.name if self.log_dir else None,
                "receiver": status_snapshot,
                "event_log": self.kde_receiver.events.metadata(),
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("status-snapshot.json", json.dumps(status_snapshot, ensure_ascii=False, indent=2))
            for path in (self.daemon.daemon_log_path, self.daemon.daemon_pid_path):
                if path.exists():
                    archive.write(path, arcname=f"runtime/{path.name}")
            for path in self._receiver_event_logs():
                if path.exists():
                    archive.writestr(
                        f"managed-kde/{path.name}",
                        self._redacted_jsonl_file(
                            path,
                            {
                                "device_id",
                                "target_device_id",
                                "host",
                                "source_ip",
                                "path",
                                "file_path",
                                "fingerprint",
                                "cert",
                                "key",
                                "command",
                                "stdout",
                                "stderr",
                            },
                        ),
                    )
            history_path = self.settings_dir / "transfer-history.jsonl"
            old_history = self.settings_dir / "transfer-history.json"
            if history_path.exists():
                archive.writestr("transfer-history.redacted.jsonl", self._redacted_jsonl_file(history_path, {"device_id", "path"}))
            elif old_history.exists():
                archive.writestr("transfer-history.redacted.json", self._redacted_json_file(old_history, {"device_id", "path"}))
            if self.notebook.notebook_path.exists():
                archive.writestr("clipboard-notebook.redacted.json", self._redacted_notebook())
            trusted = self._redacted_trusted_devices()
            if trusted is not None:
                archive.writestr("managed-kde/trusted-devices.redacted.json", json.dumps(trusted, ensure_ascii=False, indent=2))
            for path in self._recent_decky_logs():
                archive.write(path, arcname=f"decky-log/{path.name}")
        return {"ok": True, "path": str(target)}

    # ------------------------------------------------------------------
    # Hidden commands
    # ------------------------------------------------------------------

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
            ":kdeck reset identity": "Clear KDEck managed KDE Connect identity and trusted-device data.",
        }
        if normalized == ":kdeck help":
            return {"ok": True, "message": "\n".join(f"{name} - {desc}" for name, desc in commands.items()), "commands": commands}
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
        if normalized == ":kdeck reset identity":
            result = self.reset_managed_kde_identity()
            result["message"] = "KDEck identity and trusted-device data cleared. Restart KDEck and pair devices again." if result.get("ok") else "Failed to clear KDEck identity."
            return result
        return self._error("unknown_hidden_command", "Unknown hidden command.", command=command)

    # ------------------------------------------------------------------
    # Multi-device support (Task 5)
    # ------------------------------------------------------------------

    def get_preferred_device(self) -> dict[str, Any]:
        """Return user's preferred device or auto-select from trusted."""
        pref_path = self.settings_dir / "preferred-device.json"
        pref_id = None
        if pref_path.exists():
            try:
                data = json.loads(pref_path.read_text(encoding="utf-8"))
                pref_id = data.get("device_id")
            except (OSError, json.JSONDecodeError):
                pass
        trusted = self.kde_receiver.trusted_devices()
        if pref_id and pref_id in trusted:
            return {"ok": True, "device_id": pref_id, "source": "user_preference"}
        # Auto-select first trusted device
        if trusted:
            auto_id = next(iter(trusted))
            return {"ok": True, "device_id": auto_id, "source": "auto"}
        return {"ok": False, "device_id": None, "source": "none"}

    def get_send_targets(self) -> dict[str, Any]:
        """Return trusted devices formatted for the send page target picker."""
        preferred = self.get_preferred_device()
        status = self.kde_receiver.status()
        trusted = status.get("trusted_devices") or {}
        discovered = status.get("discovered_devices") or []
        connected_ids = set((status.get("peer_connections") or {}).keys())
        devices = []
        for device_id, entry in trusted.items():
            if not isinstance(entry, dict):
                continue
            live = next((item for item in discovered if item.get("device_id") == device_id), None)
            name = (live or {}).get("device_name") or entry.get("device_name") or str(device_id)[:8]
            devices.append({
                "id": device_id,
                "name": name,
                "type": (live or {}).get("device_type") or entry.get("device_type"),
                "connected": bool(device_id in connected_ids or live),
                "last_seen": (live or {}).get("last_seen") or entry.get("last_seen") or entry.get("last_connected"),
            })
        devices.sort(key=lambda item: (not item.get("connected"), str(item.get("name") or "").lower()))
        return {
            "ok": True,
            "preferred_device_id": preferred.get("device_id") if preferred.get("ok") else None,
            "devices": devices,
        }

    def set_preferred_device(self, device_id: str) -> dict[str, Any]:
        """Persist user's device preference."""
        trusted = self.kde_receiver.trusted_devices()
        if device_id not in trusted:
            return self._error("not_trusted", "Device is not trusted.")
        pref_path = self.settings_dir / "preferred-device.json"
        pref_path.write_text(json.dumps({"device_id": device_id, "set_at": int(time.time())}), encoding="utf-8")
        return {"ok": True, "device_id": device_id}

    def reset_managed_kde_identity(self, remove_preferred_device: bool = True) -> dict[str, Any]:
        """Reset managed KDE identity material so the user can re-pair from scratch."""
        removed: list[str] = []
        for path in (
            self.kde_receiver.device_id_path,
            self.kde_receiver.cert_path,
            self.kde_receiver.key_path,
            self.kde_receiver.trusted_path,
        ):
            try:
                if path.exists():
                    path.unlink()
                    removed.append(str(path))
            except OSError as exc:
                return self._error("reset_identity_failed", "Failed to reset managed KDE identity.", path=str(path), error=str(exc))
        if remove_preferred_device:
            pref_path = self.settings_dir / "preferred-device.json"
            try:
                if pref_path.exists():
                    pref_path.unlink()
                    removed.append(str(pref_path))
            except OSError as exc:
                return self._error("reset_identity_failed", "Failed to reset managed KDE identity.", path=str(pref_path), error=str(exc))
        return {"ok": True, "removed": removed}

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def cleanup_plugin_data(self, log_dir: Optional[str] = None) -> dict[str, Any]:
        removed = []
        if self._is_owned_plugin_dir(self.settings_dir):
            removed.extend(self._cleanup_settings_preserving_identity())
        for path in (self.runtime_dir, Path(log_dir) if log_dir else None):
            if path and self._is_owned_plugin_dir(path):
                shutil.rmtree(path, ignore_errors=True)
                removed.append(str(path))
        return {"ok": True, "removed": removed}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _device_action(self, device_id: str, action: str, error_code: str, error_message: str) -> dict[str, Any]:
        normalized = self._validate_device_id(device_id)
        if not normalized["ok"]:
            return normalized
        ready = await self.daemon.ensure_daemon()
        if not ready["ok"]:
            return ready
        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        result = await self._run([cli, action, "--device", normalized["device_id"]], timeout=30)
        if not result.ok:
            return self._error(error_code, error_message, command=result.to_dict())
        return {"ok": True, "command": result.to_dict()}

    def _validate_device_id(self, device_id: str) -> dict[str, Any]:
        device_id = (device_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{4,128}", device_id):
            return self._error("invalid_device_id", "Device ID format is invalid.")
        return {"ok": True, "device_id": device_id}

    async def _run(self, command: list[str], timeout: int = 15, input_text: Optional[str] = None) -> CommandResult:
        env = config.command_env_base()
        env.update(config.default_env())
        actual_command = self._as_deck_user_command(command)

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

    def _run_sync(self, command: list[str], timeout: int = 15, input_text: Optional[str] = None) -> CommandResult:
        env = config.command_env_base()
        env.update(config.default_env())
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

    def _as_deck_user_command(self, command: list[str], extra_env: Optional[dict[str, str]] = None) -> list[str]:
        if hasattr(os, "geteuid") and os.geteuid() == 0 and shutil.which("runuser"):
            command_env = config.command_env_base()
            command_env.update(config.default_env())
            if extra_env:
                command_env.update(extra_env)
            return ["runuser", "-u", config.deck_user(), "--", "env", *[f"{k}={v}" for k, v in command_env.items()], *command]
        return command

    def _receive_managed_clipboard(self, text: str, device_id: Optional[str] = None) -> None:
        text = str(text or "")[:10000]
        if not text:
            return
        self.notebook.save_notebook(text)
        clipboard_result = self.clipboard.set_clipboard_sync(text)
        if self.logger:
            self.logger.info(
                "KDEck managed KDE received clipboard, device=%s length=%s clipboard=%s",
                device_id, len(text), clipboard_result.get("ok"),
            )

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
        daemon_failures = 0
        while not self.mode_monitor_stop.wait(5):
            if not self.managed_kde_desired:
                continue
            desktop_mode = self._is_desktop_mode_active()
            status = self.kde_receiver.status()
            if desktop_mode:
                if status.get("running"):
                    if self.logger:
                        self.logger.info("KDEck receiver paused because Plasma desktop mode is active")
                    self.kde_receiver.set_connection_state(self.kde_receiver.device_id, "paused_desktop", "desktop_mode_active")
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

            # Daemon health watchdog: if the daemon was running and stops,
            # attempt auto-restart with exponential backoff.
            daemon_pid = self.daemon._read_managed_daemon_pid()
            daemon_running = daemon_pid is not None and self.daemon._is_managed_kdeconnectd_pid(daemon_pid)
            daemon_was_expected = daemon_pid is not None
            if daemon_was_expected and not daemon_running and daemon_failures < 3:
                daemon_failures += 1
                if self.logger:
                    self.logger.warning("KDEck daemon watchdog detected daemon down (failure %d/3)", daemon_failures)
                if self.loop is None:
                    continue
                # Fire-and-forget async restart from sync thread.
                try:
                    future = asyncio.run_coroutine_threadsafe(self.daemon.auto_restart_daemon(), self.loop)
                    future.result(timeout=30)
                except Exception:
                    pass
            elif daemon_running:
                daemon_failures = 0

    def _is_desktop_mode_active(self) -> bool:
        pgrep = shutil.which("pgrep")
        if not pgrep:
            return False
        try:
            result = subprocess.run(
                [pgrep, "-u", config.deck_user(), "-x", "plasmashell"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=2, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _log_export_dir(self) -> Path:
        dirs = config.common_directories()
        downloads = Path(dirs[0])
        if downloads.exists():
            return downloads
        return self.runtime_dir

    def _receiver_event_logs(self) -> list[Path]:
        logs = list(self.managed_kde_dir.glob("receiver-events.jsonl*"))
        return sorted(logs, key=lambda p: (p.name != "receiver-events.jsonl", p.name))

    def _recent_decky_logs(self, limit: int = 2) -> list[Path]:
        if not self.log_dir or not self.log_dir.exists():
            return []
        logs = [p for p in self.log_dir.glob("*.log") if p.is_file()]
        return sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    def _redacted_json_file(self, path: Path, redacted_keys: set[str]) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "{}"
        return json.dumps(self._redact_json(data, redacted_keys), ensure_ascii=False, indent=2)

    def _redacted_jsonl_file(self, path: Path, redacted_keys: set[str]) -> str:
        lines = []
        try:
            for raw_line in path.read_text(encoding="utf-8").strip().splitlines():
                if not raw_line.strip():
                    continue
                try:
                    item = json.loads(raw_line)
                    lines.append(json.dumps(self._redact_json(item, redacted_keys), ensure_ascii=False))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
        return "\n".join(lines)

    def _redacted_json_value(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        return f"{text[:8]}..." if len(text) > 8 else "***"

    def _redact_json(self, data: Any, redacted_keys: set[str]) -> Any:
        if isinstance(data, dict):
            return {
                key: self._redacted_json_value_for_key(key, value) if key in redacted_keys else self._redact_json(value, redacted_keys)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self._redact_json(item, redacted_keys) for item in data]
        return data

    def _redacted_json_value_for_key(self, key: str, value: Any) -> str:
        if key in {"host", "source_ip"}:
            return "<redacted host>" if value else ""
        if key == "command":
            return "<redacted command>" if value else ""
        if key in {"stdout", "stderr"}:
            text = str(value or "")
            return f"<redacted:{len(text)} chars>" if text else ""
        return self._redacted_json_value(value)

    def _redacted_notebook(self) -> str:
        try:
            data = json.loads(self.notebook.notebook_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "{}"
        text = str(data.get("text", ""))
        payload = {"updated_at": data.get("updated_at"), "text_length": len(text)}
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _redacted_trusted_devices(self) -> Optional[dict[str, Any]]:
        if not (self.managed_kde_dir / "trusted-devices.json").exists():
            return None
        trusted = self.kde_receiver.trusted_devices()
        devices = []
        for device_id, value in trusted.items():
            item = value if isinstance(value, dict) else {}
            fingerprint = str(item.get("fingerprint") or "")
            devices.append({
                "device_id_prefix": str(device_id)[:8],
                "trust_mode": item.get("trust_mode"),
                "fingerprint_prefix": fingerprint[:12] if fingerprint else None,
                "paired_at": item.get("paired_at"),
            })
        return {"device_count": len(devices), "devices": devices}

    def _redact_status_snapshot(self, status: dict[str, Any]) -> dict[str, Any]:
        return self._redact_json(
            status,
            {
                "device_id",
                "target_device_id",
                "host",
                "source_ip",
                "path",
                "fingerprint",
                "cert",
                "key",
            },
        )

    def _is_owned_plugin_dir(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        name = resolved.name.lower()
        return name == "kdeck" or name.startswith("kdeck-")

    def _cleanup_settings_preserving_identity(self) -> list[str]:
        """清理可丢弃设置，同时保留重装后继承配对所需的身份数据。

        这四个文件定义 KDEck 的 KDE Connect 身份和可信设备。
        卸载时删除它们会导致手机或电脑必须取消配对后重新配对，
        所以清理流程只保留这组身份文件，删除缓存和历史等可再生成数据。
        """
        preserved = {
            self.kde_receiver.device_id_path.resolve(),
            self.kde_receiver.cert_path.resolve(),
            self.kde_receiver.key_path.resolve(),
            self.kde_receiver.trusted_path.resolve(),
        }
        removed: list[str] = []
        if not self.settings_dir.exists():
            return removed
        for path in sorted(self.settings_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in preserved:
                continue
            if path.is_dir():
                try:
                    next(path.iterdir())
                except StopIteration:
                    try:
                        path.rmdir()
                        removed.append(str(path))
                    except OSError:
                        pass
                except OSError:
                    pass
            else:
                try:
                    path.unlink()
                    removed.append(str(path))
                except OSError:
                    pass
        return removed

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

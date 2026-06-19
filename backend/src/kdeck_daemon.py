"""KDEck daemon manager — lifecycle management for kdeconnectd with auto-restart."""

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import kdeck_config as config

MAX_RESTART_ATTEMPTS = 3
RESTART_BACKOFF_BASE = 2  # seconds: 2, 4, 8


class KDEckDaemon:
    """Manages the kdeconnectd process lifecycle."""

    def __init__(
        self,
        runtime_dir: Path,
        logger: Any = None,
        run_fn=None,
    ):
        self.runtime_dir = runtime_dir
        self.logger = logger
        self._run = run_fn  # async _run(command, timeout) -> CommandResult
        self.daemon_pid_path = runtime_dir / "kdeconnectd.pid"
        self.daemon_log_path = runtime_dir / "kdeconnectd.log"

    async def is_daemon_running(self) -> bool:
        result = await self._run(["pgrep", "-u", config.deck_user(), "-x", "kdeconnectd"], timeout=5)
        return result.ok and bool(result.stdout.strip())

    async def is_dbus_service_ready(self) -> bool:
        if shutil.which("busctl"):
            result = await self._run(["busctl", "--user", "list"], timeout=5)
            return result.ok and "org.kde.kdeconnect" in result.stdout
        qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
        if qdbus:
            result = await self._run([qdbus, "org.kde.kdeconnect"], timeout=5)
            return result.ok
        return False

    async def ensure_daemon(self) -> dict[str, Any]:
        from kdeck_diagnostics import build_status

        status = await build_status(self, self._run)
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
            daemon_running = await self.is_daemon_running()
            dbus_ready = await self.is_dbus_service_ready()
            if daemon_running and dbus_ready:
                new_status = await build_status(self, self._run)
                return {"ok": True, "state": "daemon_ready", "status": new_status}
        return self._error(
            "daemon_failed",
            "kdeconnectd started but DBus service was not ready within 15 seconds.",
            start=start,
            status=await build_status(self, self._run),
            daemon_log=self._tail_file(self.daemon_log_path, 80),
        )

    async def start_daemon(self) -> dict[str, Any]:
        if await self.is_daemon_running():
            from kdeck_diagnostics import build_status

            return {"ok": True, "state": "already_running", "status": await build_status(self, self._run)}
        # Clean up orphaned / zombie kdeconnectd processes from previous runs.
        self._cleanup_zombie_daemons()
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

    def stop_user_daemons_sync(self, reason: str = "manual") -> dict[str, Any]:
        """Stop deck-user kdeconnectd processes before KDEck owns the KDE Connect ports."""
        pids = self._user_kdeconnectd_pids()
        if not pids:
            return {"ok": True, "state": "no_user_daemon", "reason": reason, "pids": []}
        stopped: list[int] = []
        failed: list[dict[str, Any]] = []
        for pid in pids:
            try:
                result = subprocess.run(["kill", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                failed.append({"pid": pid, "error": str(exc)})
                continue
            if result.returncode in (0, 1):
                stopped.append(pid)
            else:
                failed.append({"pid": pid, "returncode": result.returncode, "stderr": (result.stderr or "").strip()})
        self._remove_file(self.daemon_pid_path)
        if failed:
            return {"ok": False, "state": "user_daemon_stop_failed", "reason": reason, "stopped": stopped, "failed": failed}
        if self.logger:
            self.logger.info("KDEck stopped kdeconnectd before managed receiver start: %s", stopped)
        return {"ok": True, "state": "user_daemon_stopped", "reason": reason, "stopped": stopped}

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

    def stop_managed_daemon_sync(self) -> dict[str, Any]:
        pid = self._read_managed_daemon_pid()
        if not pid:
            return {"ok": True, "state": "no_managed_daemon"}
        if not self._is_managed_kdeconnectd_pid(pid):
            self._remove_file(self.daemon_pid_path)
            return {"ok": True, "state": "managed_daemon_not_owned", "pid": pid}
        try:
            subprocess.run(["kill", str(pid)], timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return self._error("managed_daemon_stop_failed", "Failed to stop the managed kdeconnectd.")
        self._remove_file(self.daemon_pid_path)
        return {"ok": True, "state": "managed_daemon_stopped", "pid": pid}

    def _managed_kdeconnectd_pids(self) -> list[int]:
        pids: list[int] = []
        pid = self._read_managed_daemon_pid()
        if pid and self._is_managed_kdeconnectd_pid(pid):
            pids.append(pid)
        return pids

    def _user_kdeconnectd_pids(self) -> list[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-u", config.deck_user(), "-x", "kdeconnectd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        pids: list[int] = []
        for line in result.stdout.splitlines():
            try:
                pids.append(int(line.strip()))
            except ValueError:
                continue
        return pids

    async def restart_daemon(self) -> dict[str, Any]:
        stop = await self.stop_daemon()
        await asyncio.sleep(1)
        start = await self.start_daemon()
        ready = await self.ensure_daemon()
        return {"ok": ready["ok"], "stop": stop, "start": start, "ready": ready}

    def _spawn_daemon(self, daemon_path: str) -> dict[str, Any]:
        env = config.command_env_base()
        env.update(config.default_env())
        env["KDECK_MANAGED_DAEMON"] = "1"
        command = ["setsid", daemon_path]
        actual_command = self._as_deck_user_command(command, {"KDECK_MANAGED_DAEMON": "1"})
        try:
            self.daemon_log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = self.daemon_log_path.open("ab")
            try:
                proc = subprocess.Popen(
                    actual_command,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,
                    close_fds=True,
                )
            finally:
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
            "environment": config.default_env(),
            "daemon_log_path": str(self.daemon_log_path),
        }

    async def auto_restart_daemon(self) -> dict[str, Any]:
        """Attempt to restart the daemon with exponential backoff. Returns on first success or after exhausting retries."""
        for attempt in range(1, MAX_RESTART_ATTEMPTS + 1):
            delay = RESTART_BACKOFF_BASE ** attempt
            if self.logger:
                self.logger.info("KDEck daemon auto-restart attempt %d/%d after %ds", attempt, MAX_RESTART_ATTEMPTS, delay)
            await asyncio.sleep(delay)
            start = await self.start_daemon()
            if start.get("ok"):
                ready = await self.ensure_daemon()
                if ready.get("ok"):
                    if self.logger:
                        self.logger.info("KDEck daemon auto-restart succeeded on attempt %d", attempt)
                    return {"ok": True, "attempt": attempt, "ready": ready}
        if self.logger:
            self.logger.warning("KDEck daemon auto-restart failed after %d attempts", MAX_RESTART_ATTEMPTS)
        return {"ok": False, "attempts": MAX_RESTART_ATTEMPTS}

    def _cleanup_zombie_daemons(self) -> None:
        """Kill orphaned kdeconnectd processes from crashed/stale sessions."""
        if not shutil.which("pkill"):
            return
        try:
            result = subprocess.run(
                ["pkill", "-u", config.deck_user(), "-x", "kdeconnectd"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False,
            )
            if result.returncode == 0 and self.logger:
                self.logger.info("KDEck daemon cleaned up stale kdeconnectd processes")
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _as_deck_user_command(self, command: list[str], extra_env: Optional[dict[str, str]] = None) -> list[str]:
        if hasattr(os, "geteuid") and os.geteuid() == 0 and shutil.which("runuser"):
            command_env = config.command_env_base()
            command_env.update(config.default_env())
            if extra_env:
                command_env.update(extra_env)
            return ["runuser", "-u", config.deck_user(), "--", "env", *[f"{k}={v}" for k, v in command_env.items()], *command]
        return command

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
        if not any(line.startswith("Uid:") and line.split()[1] == str(config.deck_uid()) for line in status.splitlines()):
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

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

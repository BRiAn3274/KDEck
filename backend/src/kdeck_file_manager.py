"""KDEck file manager — file browsing, sharing, transfer history, and sendable file scanning."""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import kdeck_config as config


class KDEckFileManager:
    """Handles file operations: browsing, sharing, transfer history, and sendable file scanning."""

    def __init__(
        self,
        settings_dir: Path,
        kde_receiver: Any,
        logger: Any = None,
        run_fn=None,
        log_dir: Optional[Path] = None,
        runtime_dir: Optional[Path] = None,
    ):
        self.settings_dir = settings_dir
        self.kde_receiver = kde_receiver
        self.logger = logger
        self._run = run_fn  # async _run(command, timeout) -> CommandResult
        self.log_dir = log_dir
        self.runtime_dir = runtime_dir
        self.history_path = settings_dir / "transfer-history.jsonl"
        # Support migration from old JSON format
        self._old_history_path = settings_dir / "transfer-history.json"

    async def share_file(self, device_id: str, path: str) -> dict[str, Any]:
        import shutil

        from kdeck_config import CommandResult

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

        cli = shutil.which("kdeconnect-cli") or "kdeconnect-cli"
        result = await self._run(
            [cli, "--share", str(file_path), "--device", normalized["device_id"]],
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
        dirs = config.common_directories()
        base = Path(directory or dirs[0]).expanduser()
        limit = max(1, min(int(limit), 500))
        allowed_roots = [Path(p).expanduser().resolve() for p in dirs]
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
                {"path": path, "exists": Path(path).exists()} for path in config.common_directories()
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

    def get_transfer_history(self, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        history = self._read_history()
        return {"ok": True, "items": history[-limit:][::-1]}

    def list_sendable_files(self, category: str = "screenshots") -> dict[str, Any]:
        limit = 50
        if category == "screenshots":
            return self._scan_screenshots(limit)
        if category == "recordings":
            return self._scan_recordings(limit)
        if category == "logs":
            return self._scan_logs(limit)
        return {"ok": False, "error": {"code": "unknown_category", "message": f"Unknown category: {category}"}}

    def send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        return self.kde_receiver.send_share_request_to_peer(file_path, device_id)

    # ------------------------------------------------------------------
    # Transfer history (JSONL format for efficient append)
    # ------------------------------------------------------------------

    def _append_transfer_history(self, item: dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(item, ensure_ascii=False) + "\n"
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(line)
        self._trim_history_if_needed()

    def _read_history(self) -> list[dict[str, Any]]:
        # Migrate from old JSON format if needed
        if not self.history_path.exists() and self._old_history_path.exists():
            self._migrate_history()
        if not self.history_path.exists():
            return []
        items = []
        for line in self.history_path.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items

    def _trim_history_if_needed(self, max_lines: int = 500) -> None:
        """Keep only the last max_lines entries."""
        if not self.history_path.exists():
            return
        lines = self.history_path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) <= max_lines:
            return
        trimmed = lines[-max_lines:]
        self.history_path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")

    def _migrate_history(self) -> None:
        """Migrate old transfer-history.json to JSONL format."""
        try:
            data = json.loads(self._old_history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                lines = [json.dumps(item, ensure_ascii=False) for item in data]
                self.history_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    # ------------------------------------------------------------------
    # Sendable file scanning
    # ------------------------------------------------------------------

    def _scan_screenshots(self, limit: int) -> dict[str, Any]:
        steam_userdata = Path(str(config.deck_home()) + "/.local/share/Steam/userdata")
        if not steam_userdata.is_dir():
            return {"ok": True, "files": [], "message": "Steam userdata directory not found."}
        extensions = {".jpg", ".jpeg", ".png"}
        entries: list[tuple[int, int, Path, str]] = []
        try:
            for steam_id_dir in sorted(steam_userdata.iterdir()):
                if not steam_id_dir.is_dir() or steam_id_dir.name in ("0", "anonymous"):
                    continue
                remote_root = steam_id_dir / "760" / "remote"
                if not remote_root.is_dir():
                    continue
                for app_id_dir in sorted(remote_root.iterdir()):
                    screenshot_dir = app_id_dir / "screenshots"
                    if not screenshot_dir.is_dir():
                        continue
                    try:
                        for dir_entry in os.scandir(screenshot_dir):
                            if not dir_entry.is_file(follow_symlinks=False):
                                continue
                            if not any(dir_entry.name.lower().endswith(ext) for ext in extensions):
                                continue
                            st = dir_entry.stat()
                            entries.append((int(st.st_mtime), st.st_size, Path(dir_entry.path), app_id_dir.name))
                    except OSError:
                        continue
        except OSError:
            pass
        entries.sort(key=lambda x: x[0], reverse=True)
        return {"ok": True, "files": [self._file_entry(p, self._stat_tuple(m, s), a) for m, s, p, a in entries[:limit]]}

    def _scan_recordings(self, limit: int) -> dict[str, Any]:
        extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
        entries: list[tuple[int, int, Path]] = []
        steam_userdata = Path(str(config.deck_home()) + "/.local/share/Steam/userdata")
        for root_dir in self._recording_roots(steam_userdata):
            try:
                for dir_entry in os.scandir(root_dir):
                    if not dir_entry.is_file(follow_symlinks=False):
                        continue
                    if not any(dir_entry.name.lower().endswith(ext) for ext in extensions):
                        continue
                    st = dir_entry.stat()
                    entries.append((int(st.st_mtime), st.st_size, Path(dir_entry.path)))
            except OSError:
                continue
        entries.sort(key=lambda x: x[0], reverse=True)
        return {"ok": True, "files": [self._file_entry(p, self._stat_tuple(m, s)) for m, s, p in entries[:limit]]}

    def _recording_roots(self, steam_userdata: Path) -> list[Path]:
        roots: list[Path] = []
        videos = config.deck_home() / "Videos"
        if videos.is_dir():
            roots.append(videos)
        if steam_userdata.is_dir():
            try:
                for steam_id_dir in steam_userdata.iterdir():
                    if not steam_id_dir.is_dir() or steam_id_dir.name in ("0", "anonymous"):
                        continue
                    rec = steam_id_dir / "gamerecordings"
                    if rec.is_dir():
                        roots.append(rec)
            except OSError:
                pass
        return roots

    def _scan_logs(self, limit: int) -> dict[str, Any]:
        extensions = {".log", ".jsonl", ".txt", ".old"}
        entries: list[tuple[int, int, Path]] = []
        search_roots: list[Path] = []
        if self.log_dir:
            search_roots.append(self.log_dir)
        if self.runtime_dir:
            search_roots.append(self.runtime_dir)
        steam_logs = Path(str(config.deck_home()) + "/.local/share/Steam/logs")
        if steam_logs.is_dir():
            search_roots.append(steam_logs)
        for root in search_roots:
            if not root.is_dir():
                continue
            try:
                for dir_entry in os.scandir(root):
                    if not dir_entry.is_file(follow_symlinks=False):
                        continue
                    if not (any(dir_entry.name.lower().endswith(ext) for ext in extensions) or dir_entry.name.lower() == "kdeconnectd.log"):
                        continue
                    st = dir_entry.stat()
                    entries.append((int(st.st_mtime), st.st_size, Path(dir_entry.path)))
            except OSError:
                continue
        entries.sort(key=lambda x: x[0], reverse=True)
        return {"ok": True, "files": [self._file_entry(p, self._stat_tuple(m, s)) for m, s, p in entries[:limit]]}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_device_id(self, device_id: str) -> dict[str, Any]:
        device_id = (device_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{4,128}", device_id):
            return self._error("invalid_device_id", "Device ID format is invalid.")
        return {"ok": True, "device_id": device_id}

    @staticmethod
    def _file_entry(entry: Path, st: Any, app_id: str = "") -> dict[str, Any]:
        _size = getattr(st, "st_size", None) or getattr(st, "size", 0)
        _mtime = getattr(st, "st_mtime", None) or getattr(st, "mtime", 0)
        result: dict[str, Any] = {
            "path": str(entry),
            "name": entry.name,
            "size": _size,
            "mtime": int(_mtime) if _mtime else 0,
        }
        if app_id:
            result["app_id"] = app_id
        return result

    @staticmethod
    def _stat_tuple(mtime: int, size: int) -> Any:
        return type("_Stat", (), {"st_mtime": mtime, "st_size": size, "size": size, "mtime": mtime})()

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

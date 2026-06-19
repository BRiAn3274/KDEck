"""KDEck file manager — file browsing, sharing, transfer history, and sendable file scanning."""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
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
        self._jobs_lock = threading.Lock()
        self._send_jobs: dict[str, dict[str, Any]] = {}
        self._thumbnail_cache_cleaned = False

    async def share_file(self, device_id: str, path: str) -> dict[str, Any]:
        import shutil


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
            stderr_snippet = (result.stderr or result.stdout or "").strip()[:200]
            detail = f"kdeconnect-cli exited {result.returncode}"
            if stderr_snippet:
                detail += f": {stderr_snippet}"
            return self._error("share_cli_failed", detail, command=result.to_dict())
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

    def record_received_file(self, event: dict[str, Any]) -> None:
        """Record a managed KDE Connect receive event in transfer history."""
        self._safe_append_transfer_history(
            {
                "direction": "receive",
                "status": "finished",
                "device_id": event.get("device_id"),
                "file_name": event.get("file"),
                "path": event.get("path"),
                "size": event.get("size"),
                "timestamp": int(time.time()),
                "source": "managed_kde",
            }
        )

    def list_sendable_files(self, category: str = "screenshots") -> dict[str, Any]:
        limit = 50
        if category == "screenshots":
            return self._scan_screenshots(limit)
        if category == "recordings":
            return self._scan_recordings(limit)
        if category == "logs":
            return self._scan_logs(limit)
        if category == "saves":
            return self._scan_saves(limit)
        return {"ok": False, "error": {"code": "unknown_category", "message": f"Unknown category: {category}"}}

    def send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        return self.kde_receiver.send_share_request_to_peer(file_path, device_id)

    def start_send_file_to_phone(self, file_path: str, device_id: str) -> dict[str, Any]:
        """Start a background send job and return its current state."""
        source = Path(file_path)
        if not source.is_file():
            return self._error("path_not_found", "File not found.")
        job_id = uuid.uuid4().hex
        now = time.time()
        job = {
            "job_id": job_id,
            "device_id": device_id,
            "file_path": str(source),
            "file_name": source.name,
            "total_bytes": source.stat().st_size,
            "bytes_sent": 0,
            "phase": "queued",
            "status": "running",
            "speed_bps": 0,
            "eta_seconds": None,
            "created_at": int(now),
            "updated_at": int(now),
            "_started_monotonic": time.monotonic(),
        }
        with self._jobs_lock:
            self._send_jobs[job_id] = job
            self._trim_jobs_locked()

        thread = threading.Thread(
            target=self._run_send_job,
            args=(job_id, str(source), device_id),
            name=f"KDEckSendJob-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return {"ok": True, "job": self._public_job(job)}

    def get_send_jobs(self, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        with self._jobs_lock:
            jobs = sorted(self._send_jobs.values(), key=lambda item: int(item.get("created_at") or 0), reverse=True)
            return {"ok": True, "jobs": [self._public_job(item) for item in jobs[:limit]]}

    def _run_send_job(self, job_id: str, file_path: str, device_id: str) -> None:
        def _progress(update: dict[str, Any]) -> None:
            self._update_send_job(job_id, update)

        self._update_send_job(job_id, {"phase": "preparing"})
        result = self.kde_receiver.send_share_request_to_peer(file_path, device_id, progress_callback=_progress)
        source = Path(file_path)
        if result.get("ok"):
            self._safe_append_transfer_history(
                {
                    "direction": "send",
                    "status": "finished",
                    "device_id": device_id,
                    "file_name": source.name,
                    "path": str(source),
                    "size": source.stat().st_size if source.exists() else None,
                    "timestamp": int(time.time()),
                    "source": "managed_kde",
                    "job_id": job_id,
                }
            )
            self._update_send_job(job_id, {"phase": "finished", "status": "finished"})
        else:
            error = result.get("error") if isinstance(result.get("error"), dict) else {}
            failure_update = {
                "phase": "failed",
                "status": "failed",
                "error_code": error.get("code") or "send_failed",
                "error_message": error.get("message") or "Send failed.",
            }
            self._safe_append_transfer_history(
                {
                    "direction": "send",
                    "status": "failed",
                    "device_id": device_id,
                    "file_name": source.name,
                    "path": str(source),
                    "size": source.stat().st_size if source.exists() else None,
                    "timestamp": int(time.time()),
                    "source": "managed_kde",
                    "job_id": job_id,
                    "error_code": error.get("code") or "send_failed",
                    "error_message": error.get("message") or "Send failed.",
                }
            )
            self._update_send_job(job_id, failure_update)

    def _update_send_job(self, job_id: str, update: dict[str, Any]) -> None:
        now = time.time()
        with self._jobs_lock:
            job = self._send_jobs.get(job_id)
            if not job:
                return
            job.update({key: value for key, value in update.items() if value is not None})
            sent = int(job.get("bytes_sent") or 0)
            total = int(job.get("total_bytes") or 0)
            elapsed = max(0.001, time.monotonic() - float(job.get("_started_monotonic") or time.monotonic()))
            speed = int(sent / elapsed) if sent > 0 else 0
            job["speed_bps"] = speed
            job["eta_seconds"] = int((total - sent) / speed) if total > sent and speed > 0 else None
            phase = str(job.get("phase") or "")
            if phase in {"finished", "failed"}:
                job["status"] = phase
                if phase == "finished":
                    job["bytes_sent"] = total
                    job["eta_seconds"] = 0
            else:
                job["status"] = "running"
            job["updated_at"] = int(now)

    def _trim_jobs_locked(self, max_jobs: int = 20) -> None:
        if len(self._send_jobs) <= max_jobs:
            return
        ordered = sorted(self._send_jobs.items(), key=lambda item: int(item[1].get("created_at") or 0), reverse=True)
        keep = {job_id for job_id, _job in ordered[:max_jobs]}
        for job_id in list(self._send_jobs):
            if job_id not in keep:
                self._send_jobs.pop(job_id, None)

    def _public_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if not key.startswith("_")}

    def get_thumbnail_base64(self, path: str) -> dict[str, Any]:
        """Return a small base64 thumbnail for screenshot or recording previews."""
        file_path = Path(path)
        if not file_path.is_file():
            return self._error("path_not_found", "File not found.")

        suffix = file_path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            source = self._existing_thumbnail_for(file_path) or file_path
        elif suffix in {".mp4", ".mkv", ".webm", ".mov", ".avi"}:
            source = self._existing_thumbnail_for(file_path) or self._generate_video_thumbnail(file_path)
            if source is None:
                return self._error("thumbnail_unavailable", "Video thumbnail is unavailable.")
        else:
            app_icon = self._steam_app_thumbnail_for(file_path)
            if app_icon is not None:
                source = app_icon
            else:
                return self._error("thumbnail_unsupported", "This file type has no thumbnail.")

        try:
            data = source.read_bytes()
        except OSError as exc:
            return self._error("read_failed", str(exc))
        if len(data) > 350_000:
            # File too large — generate a cached thumbnail on-the-fly
            generated = self._generate_image_thumbnail(source)
            if generated is None:
                return self._error("file_too_large", "Thumbnail is too large.")
            source = generated
            try:
                data = source.read_bytes()
            except OSError as exc:
                return self._error("read_failed", str(exc))
            if len(data) > 350_000:
                return self._error("file_too_large", "Thumbnail is too large.")
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(source.suffix.lower(), "image/jpeg")
        return {"ok": True, "data": base64.b64encode(data).decode("ascii"), "mime": mime}

    # ------------------------------------------------------------------
    # Transfer history (JSONL format for efficient append)
    # ------------------------------------------------------------------

    def _append_transfer_history(self, item: dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(item, ensure_ascii=False) + "\n"
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(line)
        self._trim_history_if_needed()

    def _safe_append_transfer_history(self, item: dict[str, Any]) -> None:
        try:
            self._append_transfer_history(item)
        except OSError as exc:
            if self.logger:
                self.logger.warning("transfer history write failed: %s", exc)

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
        return {"ok": True, "files": [self._file_entry(p, self._stat_tuple(m, s), a, source="Steam", kind="screenshot") for m, s, p, a in entries[:limit]]}

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
        return {"ok": True, "files": [self._file_entry(p, self._stat_tuple(m, s), source="Steam", kind="recording") for m, s, p in entries[:limit]]}

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
        entries: list[tuple[int, int, Path, str, str, bool]] = []
        search_roots: list[tuple[Path, str, bool]] = []
        managed_kde = self.settings_dir / "managed-kde"
        if managed_kde.is_dir():
            search_roots.append((managed_kde, "KDEck Receiver", True))
        if self.log_dir:
            search_roots.append((self.log_dir, "Decky Plugin", True))
        if self.runtime_dir:
            search_roots.append((self.runtime_dir, "KDE Connect Daemon", True))
        if self.history_path.parent.is_dir():
            search_roots.append((self.history_path.parent, "KDEck Transfer", False))
        steam_logs = Path(str(config.deck_home()) + "/.local/share/Steam/logs")
        if steam_logs.is_dir():
            search_roots.append((steam_logs, "Steam", False))
        for root, source, preferred in search_roots:
            if not root.is_dir():
                continue
            try:
                for dir_entry in os.scandir(root):
                    if not dir_entry.is_file(follow_symlinks=False):
                        continue
                    if not (any(dir_entry.name.lower().endswith(ext) for ext in extensions) or dir_entry.name.lower() == "kdeconnectd.log"):
                        continue
                    st = dir_entry.stat()
                    path = Path(dir_entry.path)
                    summary = self._log_summary(path, source)
                    entries.append((int(st.st_mtime), st.st_size, path, source, summary, preferred))
            except OSError:
                continue
        entries.sort(key=lambda x: (not x[5], -x[0], x[2].name.lower()))
        return {
            "ok": True,
            "files": [
                self._file_entry(p, self._stat_tuple(m, s), source=source, summary=summary, kind="log", recommended=preferred)
                for m, s, p, source, summary, preferred in entries[:limit]
            ],
        }

    def _scan_saves(self, limit: int) -> dict[str, Any]:
        save_extensions = {
            ".sav", ".save", ".dat", ".json", ".ini", ".cfg", ".slot", ".profile",
            ".bin", ".xml", ".lua", ".txt",
        }
        blocked_parts = {
            "cache", "cacheddata", "code cache", "crashes", "crashreports", "debug",
            "gpu_cache", "logs", "shadercache", "temp", "tmp", "webcache",
        }
        steam_root = config.deck_home() / ".local/share/Steam"
        roots: list[tuple[Path, str]] = []
        userdata = steam_root / "userdata"
        compatdata = steam_root / "steamapps" / "compatdata"

        if userdata.is_dir():
            try:
                for steam_id_dir in userdata.iterdir():
                    if not steam_id_dir.is_dir() or steam_id_dir.name in ("0", "anonymous"):
                        continue
                    for app_id_dir in steam_id_dir.iterdir():
                        if not app_id_dir.is_dir():
                            continue
                        remote = app_id_dir / "remote"
                        if remote.is_dir():
                            roots.append((remote, app_id_dir.name))
            except OSError:
                pass

        if compatdata.is_dir():
            try:
                for app_id_dir in compatdata.iterdir():
                    if not app_id_dir.is_dir():
                        continue
                    steamuser = app_id_dir / "pfx" / "drive_c" / "users" / "steamuser"
                    for relative in (
                        "Documents",
                        "Saved Games",
                        "AppData/Local",
                        "AppData/LocalLow",
                        "AppData/Roaming",
                    ):
                        root = steamuser / relative
                        if root.is_dir():
                            roots.append((root, app_id_dir.name))
            except OSError:
                pass

        entries: list[tuple[int, int, int, Path, str]] = []
        deadline = int(time.time()) - 180 * 24 * 60 * 60
        for root, app_id in roots:
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [
                        name for name in dirnames
                        if name.lower() not in blocked_parts and not name.startswith(".")
                    ]
                    base = Path(dirpath)
                    for filename in filenames:
                        source = base / filename
                        suffix = source.suffix.lower()
                        if suffix not in save_extensions:
                            continue
                        parts = {part.lower() for part in source.relative_to(root).parts}
                        if parts & blocked_parts:
                            continue
                        try:
                            st = source.stat()
                        except OSError:
                            continue
                        if st.st_size <= 0 or st.st_size > 200 * 1024 * 1024:
                            continue
                        mtime = int(st.st_mtime)
                        if mtime < deadline:
                            continue
                        score = self._save_candidate_score(source, root)
                        if score <= 0:
                            continue
                        entries.append((score, mtime, st.st_size, source, app_id))
            except OSError:
                continue

        app_names = self._steam_app_names()
        entries.sort(key=lambda item: (-item[0], -item[1], item[3].name.lower()))
        return {
            "ok": True,
            "files": [
                self._file_entry(
                    p,
                    self._stat_tuple(m, s),
                    a,
                    source="Steam",
                    summary=f"score {_score}",
                    kind="save",
                    recommended=_score >= 7,
                    app_name=app_names.get(a, ""),
                )
                for _score, m, s, p, a in entries[:limit]
            ],
        }

    def _log_summary(self, path: Path, source: str) -> str:
        if path.name.startswith("receiver-events"):
            return "KDEck protocol events"
        if path.name == "kdeconnectd.log":
            return "KDE Connect daemon log"
        if path.name.startswith("transfer-history"):
            return "Transfer history"
        return source

    def _save_candidate_score(self, source: Path, root: Path) -> int:
        text = "/".join(part.lower() for part in source.relative_to(root).parts)
        score = 1
        for keyword in ("save", "saved", "savegame", "savegames", "profile", "profiles", "slot", "checkpoint"):
            if keyword in text:
                score += 4
        if source.suffix.lower() in {".sav", ".save", ".slot"}:
            score += 5
        if source.suffix.lower() in {".dat", ".json", ".ini", ".cfg", ".profile"}:
            score += 2
        if any(keyword in text for keyword in ("cache", "temp", "log", "crash", "shader")):
            score -= 8
        return score

    def _steam_app_thumbnail_for(self, file_path: Path) -> Optional[Path]:
        app_id = self._app_id_from_path(file_path)
        if not app_id:
            return None
        librarycache = config.deck_home() / ".local/share/Steam/appcache/librarycache"
        if not librarycache.is_dir():
            return None
        exact_patterns = (
            f"{app_id}_icon.*",
            f"{app_id}_library_600x900.*",
            f"{app_id}_library_hero.*",
            f"{app_id}_logo.*",
            f"{app_id}_header.*",
            f"{app_id}_capsule_616x353.*",
            f"{app_id}_capsule_231x87.*",
        )
        fallback_patterns = (
            f"{app_id}*icon*.*",
            f"{app_id}*logo*.*",
            f"{app_id}*header*.*",
            f"{app_id}*library*.*",
            f"{app_id}*capsule*.*",
        )
        for pattern in exact_patterns + fallback_patterns:
            try:
                for candidate in sorted(librarycache.glob(pattern)):
                    if candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and candidate.is_file():
                        return candidate
            except OSError:
                continue
        return None

    def _steam_app_names(self) -> dict[str, str]:
        steamapps_roots = self._steamapps_roots()
        names: dict[str, str] = {}
        for steamapps in steamapps_roots:
            if not steamapps.is_dir():
                continue
            try:
                for manifest in steamapps.glob("appmanifest_*.acf"):
                    app_id = manifest.stem.removeprefix("appmanifest_")
                    if not app_id.isdigit() or app_id in names:
                        continue
                    try:
                        text = manifest.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    match = re.search(r'"name"\s+"([^"]+)"', text)
                    if match:
                        names[app_id] = match.group(1)
            except OSError:
                continue
        return names

    def _steamapps_roots(self) -> list[Path]:
        steam_root = config.deck_home() / ".local/share/Steam"
        roots = [steam_root / "steamapps"]
        libraryfolders = steam_root / "steamapps" / "libraryfolders.vdf"
        if not libraryfolders.is_file():
            return roots
        try:
            text = libraryfolders.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return roots
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            raw = match.group(1).replace("\\\\", "\\")
            path = Path(raw)
            candidates = [path / "steamapps"]
            if path.name == "steamapps":
                candidates.append(path)
            for candidate in candidates:
                if candidate not in roots:
                    roots.append(candidate)
        return roots

    def _clean_thumbnail_cache(self, max_age_days: int = 14, max_files: int = 200) -> None:
        if self._thumbnail_cache_cleaned:
            return
        self._thumbnail_cache_cleaned = True
        cache_dir = self.settings_dir / "thumbnail-cache"
        if not cache_dir.is_dir():
            return
        deadline = time.time() - max_age_days * 24 * 60 * 60
        files: list[tuple[float, Path]] = []
        try:
            for item in cache_dir.iterdir():
                if not item.is_file():
                    continue
                try:
                    mtime = item.stat().st_mtime
                except OSError:
                    continue
                if mtime < deadline:
                    item.unlink(missing_ok=True)
                    continue
                files.append((mtime, item))
        except OSError:
            return
        if len(files) <= max_files:
            return
        for _mtime, path in sorted(files, key=lambda item: item[0])[: len(files) - max_files]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue

    def _app_id_from_path(self, file_path: Path) -> str:
        parts = file_path.parts
        for marker in ("userdata", "compatdata"):
            if marker not in parts:
                continue
            index = parts.index(marker)
            if marker == "userdata" and len(parts) > index + 2:
                candidate = parts[index + 2]
            elif marker == "compatdata" and len(parts) > index + 1:
                candidate = parts[index + 1]
            else:
                continue
            if candidate.isdigit():
                return candidate
        return ""

    def _existing_thumbnail_for(self, file_path: Path) -> Optional[Path]:
        candidates = []
        for thumb_dir_name in ("thumbnails", ".thumbnails"):
            thumb_dir = file_path.parent / thumb_dir_name
            candidates.extend([
                thumb_dir / file_path.name,
                thumb_dir / f"{file_path.stem}.jpg",
                thumb_dir / f"{file_path.stem}.jpeg",
                thumb_dir / f"{file_path.stem}.png",
                thumb_dir / f"{file_path.stem}.webp",
            ])
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _generate_video_thumbnail(self, file_path: Path) -> Optional[Path]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        cache_dir = self.settings_dir / "thumbnail-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._clean_thumbnail_cache()
        cache_key = hashlib.sha256(str(file_path).encode("utf-8", errors="surrogatepass")).hexdigest()
        target = cache_dir / f"{cache_key}.jpg"
        try:
            source_stat = file_path.stat()
        except OSError:
            return None
        if target.is_file():
            try:
                if target.stat().st_mtime >= source_stat.st_mtime:
                    return target
            except OSError:
                pass
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    "00:00:01",
                    "-i",
                    str(file_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=200:-1",
                    str(target),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return target if target.is_file() else None

    def _generate_image_thumbnail(self, file_path: Path) -> Optional[Path]:
        """Generate a small JPEG thumbnail from a large image file using PIL or ffmpeg."""
        cache_dir = self.settings_dir / "thumbnail-cache"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._clean_thumbnail_cache()
        except OSError as exc:
            if self.logger:
                self.logger.warning("thumbnail cache dir failed: %s", exc)
            return None
        cache_key = hashlib.sha256(str(file_path).encode("utf-8", errors="surrogatepass")).hexdigest()
        target = cache_dir / f"{cache_key}.jpg"
        try:
            source_stat = file_path.stat()
        except OSError:
            return None
        if target.is_file():
            try:
                if target.stat().st_mtime >= source_stat.st_mtime:
                    return target
            except OSError:
                pass
        # Try PIL first
        pil_ok = False
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                if img.mode in ("RGBA", "P", "LA"):
                    bg = Image.new("RGB", img.size, (0, 0, 0))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                    img = bg
                else:
                    img = img.convert("RGB")
                img.thumbnail((200, 200))
                img.save(target, "JPEG", quality=80)
            pil_ok = target.is_file()
            if pil_ok:
                return target
        except Exception as exc:
            if self.logger:
                self.logger.info("PIL thumbnail failed: %s", exc)
        # Fallback to ffmpeg (available on SteamOS)
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                proc = subprocess.run(
                    [
                        ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
                        "-i", str(file_path),
                        "-vf", "scale=200:-1,format=rgb24",
                        "-frames:v", "1",
                        "-update", "1",
                        str(target),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
                if target.is_file() and target.stat().st_size > 0:
                    return target
                if self.logger:
                    self.logger.info(
                        "ffmpeg thumbnail failed (rc=%s): %s",
                        proc.returncode,
                        (proc.stderr or b"").decode("utf-8", errors="replace")[:200],
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                if self.logger:
                    self.logger.info("ffmpeg thumbnail error: %s", exc)
        # Fallback to ImageMagick convert
        convert = shutil.which("convert")
        if convert:
            try:
                subprocess.run(
                    [convert, str(file_path), "-resize", "200x", "-quality", "80", str(target)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                if target.is_file() and target.stat().st_size > 0:
                    return target
            except (OSError, subprocess.TimeoutExpired):
                pass
        if self.logger:
            self.logger.warning(
                "all thumbnail methods failed for %s (pil=%s, ffmpeg=%s, convert=%s)",
                file_path.name, pil_ok, bool(ffmpeg), bool(convert),
            )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_device_id(self, device_id: str) -> dict[str, Any]:
        device_id = (device_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{4,128}", device_id):
            return self._error("invalid_device_id", "Device ID format is invalid.")
        return {"ok": True, "device_id": device_id}

    @staticmethod
    def _file_entry(
        entry: Path,
        st: Any,
        app_id: str = "",
        app_name: str = "",
        source: str = "",
        summary: str = "",
        kind: str = "",
        recommended: bool = False,
    ) -> dict[str, Any]:
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
        if app_name:
            result["app_name"] = app_name
        if source:
            result["source"] = source
        if summary:
            result["summary"] = summary
        if kind:
            result["kind"] = kind
        if recommended:
            result["recommended"] = True
        return result

    @staticmethod
    def _stat_tuple(mtime: int, size: int) -> Any:
        return type("_Stat", (), {"st_mtime": mtime, "st_size": size, "size": size, "mtime": mtime})()

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

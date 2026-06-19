"""KDEck KDE Connect event logging subsystem.

Provides buffered JSONL event logging with log rotation.  The orchestrator
stores a reference to ``EventLogger`` and delegates all ``write_event`` /
``tail_events`` calls to it.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from kdeck_kde_protocol import EVENT_LOG_BACKUPS, EVENT_LOG_MAX_BYTES

EVENT_BUFFER_FLUSH_SIZE = 64
EVENT_RATE_LIMIT_SECONDS = 5.0
RATE_LIMITED_EVENTS = {
    "file_serve_accept_timeout",
    "identity_reply_skipped",
    "packet_decode_failed",
    "packet_rejected",
    "payload_receive_retry",
    "peer_connect_failed",
    "peer_connect_skipped",
    "peer_session_error",
}
SENSITIVE_KEYS = {
    "cert",
    "certificate",
    "command",
    "device_id",
    "host",
    "key",
    "path",
    "private_key",
    "source_ip",
    "stderr",
    "stdout",
    "target_device_id",
}


def infer_event_stage(event: str) -> str:
    """Infer a stable event stage for older call sites that only pass a name."""
    name = str(event or "")
    if "state" in name:
        return "state"
    if name.startswith("receiver_"):
        return "lifecycle"
    if "bluetooth" in name or "_bt_" in name:
        return "bluetooth"
    if "discovery" in name or "identity_reply" in name:
        return "discovery"
    if "certificate" in name or "tls" in name or "secure_identity" in name:
        return "tls"
    if "tcp" in name or "connect" in name or "reconnect" in name:
        return "tcp"
    if "pair" in name or "trusted" in name:
        return "pairing"
    if "file" in name or "payload" in name or "share" in name:
        return "transfer"
    if "clipboard" in name:
        return "clipboard"
    if "packet" in name:
        return "packet"
    return "runtime"


class EventLogger:
    """Thread-safe, buffered JSONL event logger with rotation.

    Parameters
    ----------
    log_path:
        Filesystem path for the ``receiver-events.jsonl`` file.
    log_fn:
        Optional callback for forwarding human-readable log lines to the
        plugin logger (e.g. ``logger.info``).
    """

    def __init__(self, log_path: Path, log_fn: Optional[Callable] = None, default_device_id: Optional[str] = None):
        self._log_path = log_path
        self._log_fn = log_fn
        self._default_device_id = default_device_id or "local"
        self._buffer: list[dict[str, Any]] = []
        self._rate_limits: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ── public API ────────────────────────────────────────────────

    def write_event(self, event: str, details: dict[str, Any]) -> None:
        """Append an event to the buffer, auto-flushing when full."""
        now = time.time()
        payload = self._normalize_event(event, details or {}, now)
        with self._lock:
            if self._rate_limited_locked(payload, now):
                return
            try:
                self._rotate_if_needed()
            except OSError:
                pass
            self._buffer.append(payload)
            if len(self._buffer) >= EVENT_BUFFER_FLUSH_SIZE:
                self._flush_locked()
        self._log("KDE receiver event %s %s", event, details)

    def flush(self) -> None:
        """Force-flush the in-memory buffer to disk."""
        with self._lock:
            self._flush_locked()

    def tail(self, limit: int) -> list[dict[str, Any]]:
        """Return the last *limit* events in chronological order (oldest first)."""
        events: list[dict[str, Any]] = []
        # Read disk log first (older events)
        if self._log_path.exists():
            try:
                lines = self._log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            for line in lines[-limit:]:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        # Append in-memory buffer (newer events)
        with self._lock:
            events.extend(self._buffer[-limit:])
        return events[-limit:]

    def metadata(self) -> dict[str, Any]:
        """Return log policy metadata for diagnostics exports."""
        return {
            "format": "jsonl",
            "required_fields": ["time", "event", "stage", "device_id"],
            "max_bytes": EVENT_LOG_MAX_BYTES,
            "backups": EVENT_LOG_BACKUPS,
            "buffer_flush_size": EVENT_BUFFER_FLUSH_SIZE,
            "rate_limit_seconds": EVENT_RATE_LIMIT_SECONDS,
            "rate_limited_events": sorted(RATE_LIMITED_EVENTS),
            "redacted_keys": sorted(SENSITIVE_KEYS),
        }

    # ── internals ─────────────────────────────────────────────────

    def _flush_locked(self) -> None:
        """Write buffered events to JSONL.  Must hold ``_lock``."""
        if not self._buffer:
            return
        try:
            with self._log_path.open("a", encoding="utf-8") as log:
                for payload in self._buffer:
                    log.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self._buffer.clear()

    def _normalize_event(self, event: str, details: dict[str, Any], now: float) -> dict[str, Any]:
        raw_device_id = details.get("device_id") or details.get("target_device_id") or self._default_device_id
        redacted = self._redact(details)
        payload = dict(redacted) if isinstance(redacted, dict) else {}
        payload["event"] = str(event or "unknown")
        payload["time"] = int(payload.get("time") or now)
        payload["stage"] = str(payload.get("stage") or infer_event_stage(payload["event"]))
        payload["device_id"] = self._redacted_identifier(raw_device_id)
        return payload

    def _rate_limited_locked(self, payload: dict[str, Any], now: float) -> bool:
        event = str(payload.get("event") or "")
        if event not in RATE_LIMITED_EVENTS:
            return False
        discriminator = str(
            payload.get("code")
            or payload.get("reason")
            or payload.get("error")
            or payload.get("error_type")
            or payload.get("message")
            or ""
        )[:160]
        key = (
            event,
            str(payload.get("stage") or ""),
            str(payload.get("device_id") or ""),
            discriminator,
        )
        state = self._rate_limits.get(key)
        if state and now - float(state.get("last_time") or 0) < EVENT_RATE_LIMIT_SECONDS:
            state["suppressed_count"] = int(state.get("suppressed_count") or 0) + 1
            return True
        suppressed_count = int(state.get("suppressed_count") or 0) if state else 0
        self._rate_limits[key] = {"last_time": now, "suppressed_count": 0}
        if suppressed_count:
            payload["suppressed_count"] = suppressed_count
        return False

    def _redact(self, value: Any, key: str = "") -> Any:
        key_lower = key.lower()
        if isinstance(value, dict):
            return {item_key: self._redact(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [self._redact(item, key) for item in value]
        if key_lower in {"device_id", "target_device_id"}:
            return self._redacted_identifier(value)
        if key_lower in SENSITIVE_KEYS or key_lower.endswith("_path"):
            return self._redacted_value(value, key_lower)
        if key_lower == "fingerprint":
            text = str(value or "")
            return f"{text[:12]}..." if text else None
        return value

    @staticmethod
    def _redacted_identifier(value: Any) -> str:
        text = str(value or "")
        if not text:
            return "unknown"
        if len(text) <= 8:
            return f"{text[:4]}..."
        return f"{text[:8]}..."

    @staticmethod
    def _redacted_value(value: Any, key: str) -> Any:
        text = str(value or "")
        if not text:
            return ""
        if key in {"host", "source_ip"}:
            return "<redacted host>"
        if key in {"stdout", "stderr"}:
            return f"<redacted:{len(text)} chars>"
        if key == "command":
            return "<redacted command>"
        name = Path(text).name
        return f"<redacted:{name or 'value'}>"

    def _rotate_if_needed(self) -> None:
        """Rotate the log file when it exceeds the size limit."""
        try:
            if not self._log_path.exists() or self._log_path.stat().st_size < EVENT_LOG_MAX_BYTES:
                return
            for stale in self._log_path.parent.glob(f"{self._log_path.name}.*"):
                try:
                    index = int(stale.name.rsplit(".", 1)[1])
                except (IndexError, ValueError):
                    continue
                if index > EVENT_LOG_BACKUPS:
                    stale.unlink()
            oldest = self._log_path.with_name(f"{self._log_path.name}.{EVENT_LOG_BACKUPS}")
            if oldest.exists():
                oldest.unlink()
            for index in range(EVENT_LOG_BACKUPS - 1, 0, -1):
                source = self._log_path.with_name(f"{self._log_path.name}.{index}")
                target = self._log_path.with_name(f"{self._log_path.name}.{index + 1}")
                if source.exists():
                    source.replace(target)
            self._log_path.replace(self._log_path.with_name(f"{self._log_path.name}.1"))
            self._log_path.write_text("", encoding="utf-8")
        except OSError:
            pass

    def _log(self, message: str, *args: Any) -> None:
        if self._log_fn:
            self._log_fn(message, *args)

"""KDEck KDE Connect file-transfer utilities.

Standalone helpers for filename sanitisation, destination resolution, disk
space checks, file-failure recording, and peer control-socket creation.
The orchestrator (``KDEckKdeReceiver``) keeps thin wrapper methods that
delegate here.
"""

import shutil
import socket
import time
from pathlib import Path
from typing import Any, Callable, Optional


def safe_filename(filename: str) -> str:
    """Sanitise *filename* for safe use as a local file name.

    Strips path components, removes characters that are illegal on Windows,
    and truncates to 180 characters.  Falls back to a timestamped name
    when the result would be empty.
    """
    clean = filename.replace("\\", "/").split("/")[-1].strip()
    clean = "".join(ch for ch in clean if ch not in '<>:"|?*\0')
    return clean[:180] or f"kdeck-{int(time.time())}"


def unique_destination(incoming_dir: Path, filename: str) -> Path:
    """Return a non-conflicting path inside *incoming_dir*.

    If *filename* (or its ``.part`` sibling) already exists, appends an
    incrementing ``(N)`` suffix before the extension, falling back to a
    timestamped name after 999 attempts.
    """
    destination = incoming_dir / filename
    if not destination.exists() and not destination.with_name(f"{destination.name}.part").exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    for index in range(1, 1000):
        candidate = incoming_dir / f"{stem} ({index}){suffix}"
        if not candidate.exists() and not candidate.with_name(f"{candidate.name}.part").exists():
            return candidate
    return incoming_dir / f"{stem}-{int(time.time())}{suffix}"


def has_enough_space(incoming_dir: Path, payload_size: int, min_free: int) -> bool:
    """Return ``True`` when the disk holding *incoming_dir* has enough room.

    *min_free* is the minimum bytes that must remain free **after** the
    transfer completes.
    """
    try:
        usage = shutil.disk_usage(incoming_dir if incoming_dir.exists() else incoming_dir.parent)
    except OSError:
        return False
    return usage.free >= payload_size + min_free


def record_file_failure(
    set_diagnostic: Callable[[str, Any], None],
    write_event: Callable[[str, dict[str, Any]], None],
    peer_id: str,
    filename: str,
    reason: str,
    **details: Any,
) -> None:
    """Record a file-receive failure in diagnostics and the event log."""
    event = {"device_id": peer_id, "file": filename, "error": reason, **details}
    set_diagnostic("last_file", {"status": "failed", "time": int(time.time()), **event})
    set_diagnostic("last_payload_error", {"time": int(time.time()), **event})
    write_event("file_receive_failed", event)


def connect_to_peer_control_socket(
    host: str,
    trusted_info: dict[str, Any],
    source_ips: list[Optional[str]],
) -> Optional[socket.socket]:
    """Open a plain TCP control socket to a trusted peer.

    Tries the peer's recorded ``tcp_port`` first, then falls back to the
    KDE-Connect default port 1716.  Returns ``None`` when no port is
    reachable.
    """
    source_ip = source_ips[0] if source_ips else None
    ports_to_try: list[int] = []
    tcp_port = trusted_info.get("tcp_port")
    if tcp_port and isinstance(tcp_port, int):
        ports_to_try.append(tcp_port)
    if 1716 not in ports_to_try:
        ports_to_try.append(1716)
    for port in ports_to_try:
        try:
            sock = socket.create_connection(
                (host, port), timeout=5,
                source_address=(source_ip, 0) if source_ip else None,
            )
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            return sock
        except OSError:
            continue
    return None

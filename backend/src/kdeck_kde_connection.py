"""KDE Connect connection-state helpers for KDEck.

The receiver owns sockets, TLS, locks, and thread lifecycle.  This module only
contains small deterministic decisions used by that lifecycle.
"""

from typing import Optional


def peer_connect_decision(
    device_id: Optional[str],
    host: str,
    port: int,
    now: float,
    previous_attempts: dict[str, float],
    cooldown: int,
) -> tuple[bool, str, Optional[dict[str, object]]]:
    """Return whether a peer connection attempt should proceed.

    The returned tuple is ``(allowed, key, skipped_event)``.  ``skipped_event``
    is intentionally data-only so the receiver can decide how to log it.
    """
    if not device_id:
        return False, "", None
    key = f"{device_id}@{host}:{port}"
    previous = previous_attempts.get(key)
    if previous is not None and now - previous < cooldown:
        return False, key, {"host": host, "port": port, "device_id": device_id, "reason": "cooldown", "cooldown_seconds": cooldown}
    return True, key, None

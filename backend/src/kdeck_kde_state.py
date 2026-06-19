"""KDEck receiver connection state helpers.

This module records observable state transitions only. It does not decide
whether a peer should connect, pair, retry, or be trusted.
"""

from typing import Any, Optional

VALID_CONNECTION_STATES = {
    "idle",
    "discovered",
    "trusted",
    "connecting",
    "connected",
    "backoff",
    "paused_desktop",
    "failed",
}


def state_transition(
    current_state: Optional[str],
    next_state: str,
    reason: str,
    device_id: str,
    now: int,
    **details: Any,
) -> Optional[dict[str, Any]]:
    """Build a transition event when the state actually changes."""
    if next_state not in VALID_CONNECTION_STATES:
        next_state = "failed"
    previous = current_state or "idle"
    if previous == next_state:
        return None
    return {
        "device_id": device_id or "local",
        "from": previous,
        "to": next_state,
        "reason": reason,
        "time": now,
        **details,
    }

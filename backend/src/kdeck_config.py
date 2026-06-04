"""KDEck configuration — centralizes all environment/path constants.

All values derived from the Deck environment are computed via functions so that
they respond to environment variable overrides (useful for testing or non-standard
setups) and can be initialized once by main.py with the actual Decky directories.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Runtime overrides (set once at startup from main.py / decky env)
# ---------------------------------------------------------------------------

_user_home: Optional[Path] = None


def init(user_home: Optional[str] = None) -> None:
    """Initialize global configuration from Decky environment."""
    global _user_home
    if user_home:
        _user_home = Path(user_home)


# ---------------------------------------------------------------------------
# Deck identity
# ---------------------------------------------------------------------------


def deck_user() -> str:
    return os.environ.get("KDECK_USER", "deck")


def deck_uid() -> int:
    return int(os.environ.get("KDECK_UID", "1000"))


def deck_home() -> Path:
    if _user_home:
        return _user_home
    return Path(os.environ.get("KDECK_HOME", f"/home/{deck_user()}"))


# ---------------------------------------------------------------------------
# Directory constants
# ---------------------------------------------------------------------------


def common_directories() -> tuple[str, ...]:
    home = deck_home()
    return (
        str(home / "Downloads"),
        str(home / "Documents"),
        str(home / "Pictures"),
    )


# ---------------------------------------------------------------------------
# Environment dictionaries for subprocess execution
# ---------------------------------------------------------------------------


def default_env() -> dict[str, str]:
    uid = deck_uid()
    return {
        "DISPLAY": ":0",
        "XDG_RUNTIME_DIR": f"/run/user/{uid}",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus",
        "QT_QPA_PLATFORM": "wayland",
        "WAYLAND_DISPLAY": "gamescope-0",
    }


def command_env_base() -> dict[str, str]:
    return {
        "HOME": str(deck_home()),
        "USER": deck_user(),
        "LOGNAME": deck_user(),
        "SHELL": "/bin/bash",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
    }


# ---------------------------------------------------------------------------
# Port constants
# ---------------------------------------------------------------------------

KDECONNECT_PORT_RANGE = "1714-1764"


# ---------------------------------------------------------------------------
# CommandResult dataclass (shared across modules)
# ---------------------------------------------------------------------------


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

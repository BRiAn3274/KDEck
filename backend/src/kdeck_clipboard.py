"""KDEck clipboard — read/write the system clipboard with multi-tool fallback."""

import shutil
from typing import Any, Optional


class KDEckClipboard:
    """Clipboard operations with wl-copy/xclip/tkinter fallback chain."""

    def __init__(self, logger: Any = None, run_fn=None, run_sync_fn=None):
        self.logger = logger
        self._run = run_fn  # async _run(command, timeout, input_text) -> CommandResult
        self._run_sync = run_sync_fn  # _run_sync(command, timeout, input_text) -> CommandResult

    async def get_clipboard(self, max_chars: int = 500) -> dict[str, Any]:
        max_chars = max(0, min(int(max_chars), 5000))
        text = await self._read_clipboard(max_chars)
        if text is not None:
            return {
                "ok": True,
                "text": text[:max_chars],
                "length": len(text),
                "truncated": len(text) > max_chars,
            }
        # Fallback to tkinter
        script = (
            "import tkinter as tk\n"
            "root=tk.Tk(); root.withdraw()\n"
            "try:\n"
            "    data=root.clipboard_get()\n"
            "except Exception:\n"
            "    data=''\n"
            "root.destroy()\n"
            "print(data, end='')\n"
        )
        result = await self._run(["python3", "-c", script], timeout=5)
        if not result.ok:
            return self._error("clipboard_read_failed", "Failed to read Deck clipboard.", command=result.to_dict())
        text = result.stdout
        return {
            "ok": True,
            "text": text[:max_chars],
            "length": len(text),
            "truncated": len(text) > max_chars,
        }

    async def set_clipboard(self, text: str) -> dict[str, Any]:
        return self.set_clipboard_sync(text)

    def set_clipboard_sync(self, text: str) -> dict[str, Any]:
        if self._write_clipboard_native(text):
            return {"ok": True, "length": len(text)}
        # Fallback to tkinter
        script = (
            "import sys, tkinter as tk\n"
            "data=sys.stdin.read()\n"
            "root=tk.Tk(); root.withdraw()\n"
            "root.clipboard_clear(); root.clipboard_append(data); root.update()\n"
            "root.destroy()\n"
        )
        result = self._run_sync(["python3", "-c", script], input_text=text, timeout=5)
        if not result.ok:
            return self._error("clipboard_write_failed", "Failed to write Deck clipboard.", command=result.to_dict())
        return {"ok": True, "length": len(text)}

    async def _read_clipboard(self, max_chars: int) -> Optional[str]:
        """Try native clipboard tools before falling back to tkinter."""
        if shutil.which("wl-paste"):
            result = await self._run(["wl-paste"], timeout=5)
            if result.ok:
                return result.stdout
        if shutil.which("xclip"):
            result = await self._run(["xclip", "-o", "-selection", "clipboard"], timeout=5)
            if result.ok:
                return result.stdout
        return None

    def _write_clipboard_native(self, text: str) -> bool:
        """Try native clipboard tools, return True on success."""
        if shutil.which("wl-copy"):
            result = self._run_sync(["wl-copy"], input_text=text, timeout=5)
            if result.ok:
                return True
        if shutil.which("xclip"):
            result = self._run_sync(
                ["xclip", "-selection", "clipboard"],
                input_text=text,
                timeout=5,
            )
            if result.ok:
                return True
        return False

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("%s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

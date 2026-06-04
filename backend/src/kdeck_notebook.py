"""KDEck notebook — persistent clipboard text storage."""

import json
import time
from pathlib import Path
from typing import Any


class KDEckNotebook:
    """Manages the clipboard notebook (saved text between sessions)."""

    def __init__(self, notebook_path: Path, logger: Any = None):
        self.notebook_path = notebook_path
        self.logger = logger

    def get_notebook(self) -> dict[str, Any]:
        if not self.notebook_path.exists():
            return {"ok": True, "text": "", "updated_at": None}
        try:
            data = json.loads(self.notebook_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ok": True, "text": "", "updated_at": None}
        return {
            "ok": True,
            "text": str(data.get("text", "")),
            "updated_at": data.get("updated_at"),
        }

    def save_notebook(self, text: str) -> dict[str, Any]:
        text = str(text or "")
        payload = {"text": text, "updated_at": int(time.time())}
        self.notebook_path.parent.mkdir(parents=True, exist_ok=True)
        self.notebook_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, **payload}

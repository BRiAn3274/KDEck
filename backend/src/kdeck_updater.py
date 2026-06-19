"""KDEck updater — hot-update mechanism with security hardening.

Security measures:
- Domain whitelist: only github.com / raw.githubusercontent.com by default
- SHA256 checksum verification (optional but recommended)
- Automatic rollback on failure
- Audit logging of all update operations
"""

import hashlib
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

ALLOWED_UPDATE_DOMAINS = (
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
)


def validate_update_url(url: str) -> bool:
    """Check if the URL points to an allowed domain."""
    try:
        parsed = urlparse(url)
        return parsed.hostname in ALLOWED_UPDATE_DOMAINS
    except Exception:
        return False


class KDEckUpdater:
    """Handles plugin hot-update with security controls."""

    def __init__(self, logger: Any = None, allowed_domains: Optional[tuple[str, ...]] = None):
        self.logger = logger
        self.allowed_domains = allowed_domains or ALLOWED_UPDATE_DOMAINS

    def update_from_url(self, url: str, expected_sha256: Optional[str] = None) -> dict[str, Any]:
        """Download and install a plugin update from URL.

        Args:
            url: HTTPS URL to a KDEck.zip file.
            expected_sha256: Optional SHA256 hex digest to verify the download.
        """
        if not url.startswith("https://"):
            return self._error("invalid_update_url", "Only HTTPS URLs are allowed.")

        if not expected_sha256:
            return self._error("missing_checksum", "SHA256 checksum is required for security.")

        # Domain whitelist check
        if not self._validate_domain(url):
            return self._error(
                "domain_not_allowed",
                f"URL domain not in whitelist. Allowed: {', '.join(self.allowed_domains)}",
            )

        tmp_dir = Path(tempfile.mkdtemp(prefix="kdeck-update-"))
        zip_path = tmp_dir / "KDEck.zip"
        try:
            # Download
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    zip_path.write_bytes(resp.read())
            except Exception as exc:
                return self._error("download_failed", f"Download failed: {exc}")

            # SHA256 verification
            actual_sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            if actual_sha256.lower() != expected_sha256.lower():
                return self._error(
                    "checksum_mismatch",
                    f"SHA256 mismatch. Expected: {expected_sha256[:16]}..., got: {actual_sha256[:16]}...",
                )

            # Validate zip structure
            if not zipfile.is_zipfile(zip_path):
                return self._error("invalid_zip", "Downloaded file is not a valid zip.")

            with zipfile.ZipFile(zip_path) as archive:
                names = archive.namelist()
                expected = "KDEck/plugin.json" if any(n.startswith("KDEck/") for n in names) else "plugin.json"
                if expected not in names:
                    return self._error("invalid_zip", "Zip missing required files (plugin.json).")

            # Determine plugin directory
            plugin_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
            extract_dir = tmp_dir / "extracted"
            script = tmp_dir / "install.sh"

            with zipfile.ZipFile(zip_path) as archive:
                extract_dir_resolved = extract_dir.resolve()
                for info in archive.infolist():
                    target = (extract_dir / info.filename).resolve()
                    if not str(target).startswith(str(extract_dir_resolved)):
                        return self._error("invalid_zip", f"Zip entry escapes extract directory: {info.filename}")
                archive.extractall(extract_dir)

            kdeck_dir = extract_dir / "KDEck"
            if not kdeck_dir.is_dir():
                kdeck_dir = extract_dir

            # Install script with rollback support
            install_cmd = (
                f"set -e\n"
                f"BACKUP='{plugin_dir}.bak'\n"
                f"rm -rf \"$BACKUP\" 2>/dev/null || true\n"
                f"cp -r '{plugin_dir}' \"$BACKUP\"\n"
                f"rm -rf '{plugin_dir}'\n"
                f"if cp -r '{kdeck_dir}' '{plugin_dir}'; then\n"
                f"  rm -rf '{tmp_dir}'\n"
                f"  sleep 1\n"
                f"  sudo systemctl restart plugin_loader 2>/dev/null || true\n"
                f"else\n"
                f"  # Rollback on failure\n"
                f"  rm -rf '{plugin_dir}' 2>/dev/null || true\n"
                f"  mv \"$BACKUP\" '{plugin_dir}'\n"
                f"  rm -rf '{tmp_dir}'\n"
                f"  exit 1\n"
                f"fi\n"
            )
            script.write_text(f"#!/usr/bin/env bash\n{install_cmd}")
            script.chmod(0o755)

            subprocess.Popen(
                ["nohup", "bash", str(script)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            return {"ok": True, "message": "Update downloading and installing. Plugin will restart momentarily."}
        except Exception as exc:
            return self._error("update_failed", str(exc))

    def _validate_domain(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.hostname in self.allowed_domains
        except Exception:
            return False

    def _error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        if self.logger:
            self.logger.warning("KDEck updater: %s: %s", code, message)
        return {"ok": False, "error": {"code": code, "message": message}, **details}

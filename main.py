import asyncio
import os
import sys

import decky

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "backend", "src"))

from kdeck_backend import KDEckBackend  # noqa: E402


class Plugin:
    async def _main(self):
        self.loop = asyncio.get_event_loop()
        self.backend = KDEckBackend(
            logger=decky.logger,
            settings_dir=getattr(decky, "DECKY_PLUGIN_SETTINGS_DIR", None),
            runtime_dir=getattr(decky, "DECKY_PLUGIN_RUNTIME_DIR", None),
            log_dir=getattr(decky, "DECKY_PLUGIN_LOG_DIR", None),
        )
        self.backend.start_managed_kde()
        decky.logger.info("KDEck backend loaded")

    async def _unload(self):
        if hasattr(self, "backend"):
            self.backend.stop_managed_kde()
        decky.logger.info("KDEck backend unloaded")

    async def _uninstall(self):
        if hasattr(self, "backend"):
            self.backend.stop_managed_kde()
            await self.backend.stop_managed_daemon()
            self.backend.cleanup_plugin_data(getattr(decky, "DECKY_PLUGIN_LOG_DIR", None))
        decky.logger.info("KDEck backend uninstalled")

    async def _migration(self):
        decky.migrate_settings(
            os.path.join(getattr(decky, "DECKY_USER_HOME", "/home/deck"), ".config", "kdeck")
        )
        decky.migrate_runtime(
            os.path.join(getattr(decky, "DECKY_USER_HOME", "/home/deck"), ".local", "share", "kdeck")
        )

    async def get_status(self) -> dict:
        return await self.backend.get_status()

    async def diagnose(self) -> dict:
        return await self.backend.diagnose()

    async def get_connection_summary(self) -> dict:
        return await self.backend.get_connection_summary()

    async def start_managed_kde(self) -> dict:
        return self.backend.start_managed_kde()

    async def stop_managed_kde(self) -> dict:
        return self.backend.stop_managed_kde()

    async def accept_pending_pair(self) -> dict:
        return self.backend.accept_pending_pair()

    async def reject_pending_pair(self) -> dict:
        return self.backend.reject_pending_pair()

    async def get_managed_kde_status(self) -> dict:
        return self.backend.get_managed_kde_status()

    async def ensure_daemon(self) -> dict:
        return await self.backend.ensure_daemon()

    async def start_daemon(self) -> dict:
        return await self.backend.start_daemon()

    async def stop_daemon(self) -> dict:
        return await self.backend.stop_daemon()

    async def restart_daemon(self) -> dict:
        return await self.backend.restart_daemon()

    async def refresh_devices(self) -> dict:
        return await self.backend.refresh_devices()

    async def list_devices(self) -> dict:
        return await self.backend.list_devices()

    async def pair_device(self, device_id: str) -> dict:
        return await self.backend.pair_device(device_id)

    async def unpair_device(self, device_id: str) -> dict:
        return await self.backend.unpair_device(device_id)

    async def send_clipboard(self, device_id: str) -> dict:
        return await self.backend.send_clipboard(device_id)

    async def share_text(self, device_id: str, text: str) -> dict:
        return await self.backend.share_text(device_id, text)

    async def get_clipboard(self, max_chars: int = 500) -> dict:
        return await self.backend.get_clipboard(max_chars)

    async def set_clipboard(self, text: str) -> dict:
        return await self.backend.set_clipboard(text)

    async def share_file(self, device_id: str, path: str) -> dict:
        return await self.backend.share_file(device_id, path)

    async def list_files(self, directory: str = "", limit: int = 200) -> dict:
        return await self.backend.list_files(directory, limit)

    async def get_common_directories(self) -> dict:
        return self.backend.get_common_directories()

    async def get_incoming_directories(self) -> dict:
        return self.backend.get_incoming_directories()

    async def get_transfer_history(self, limit: int = 50) -> dict:
        return self.backend.get_transfer_history(limit)

    async def get_deck_ips(self) -> dict:
        return await self.backend.get_deck_ips()

    async def get_notebook(self) -> dict:
        return self.backend.get_notebook()

    async def save_notebook(self, text: str) -> dict:
        return self.backend.save_notebook(text)

    async def export_logs(self) -> dict:
        return self.backend.export_logs()

    async def run_hidden_command(self, command: str) -> dict:
        return self.backend.run_hidden_command(command)

    async def list_sendable_files(self, category: str = "screenshots") -> dict:
        return self.backend.list_sendable_files(category)

    async def send_file_to_phone(self, file_path: str, device_id: str) -> dict:
        return self.backend.send_file_to_phone(file_path, device_id)

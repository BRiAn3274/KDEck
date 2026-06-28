import asyncio
import os
import sys

import decky

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "backend", "src"))

import kdeck_config  # noqa: E402
from kdeck_backend import KDEckBackend  # noqa: E402


class Plugin:
    async def _main(self):
        self.loop = asyncio.get_event_loop()
        self._startup_task = None
        # Initialize config with Decky environment
        kdeck_config.init(
            user_home=getattr(decky, "DECKY_USER_HOME", None),
        )
        self.backend = KDEckBackend(
            logger=decky.logger,
            settings_dir=getattr(decky, "DECKY_PLUGIN_SETTINGS_DIR", None),
            runtime_dir=getattr(decky, "DECKY_PLUGIN_RUNTIME_DIR", None),
            log_dir=getattr(decky, "DECKY_PLUGIN_LOG_DIR", None),
            event_loop=self.loop,
        )
        decky.logger.info("KDEck backend loaded")
        self._startup_task = self.loop.create_task(self._start_managed_kde_after_decky_settles())

    async def _start_managed_kde_after_decky_settles(self):
        try:
            await asyncio.sleep(3)
            result = await self.loop.run_in_executor(None, self.backend.start_managed_kde)
            if not result.get("ok", True):
                decky.logger.warning("KDEck delayed receiver start returned non-ok result: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            decky.logger.exception("KDEck delayed receiver start failed")

    async def _unload(self):
        task = getattr(self, "_startup_task", None)
        if task and not task.done():
            task.cancel()
        if hasattr(self, "backend"):
            self.backend.stop_managed_kde()
            await self.backend.stop_managed_daemon()
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

    def _ensure_backend(self):
        if not hasattr(self, "backend"):
            raise RuntimeError("KDEck backend not initialized")
        return self.backend

    async def get_status(self) -> dict:
        return await self._ensure_backend().get_status()

    async def diagnose(self) -> dict:
        return await self._ensure_backend().diagnose()

    async def get_connection_summary(self) -> dict:
        return await self._ensure_backend().get_connection_summary()

    async def start_managed_kde(self) -> dict:
        return self._ensure_backend().start_managed_kde()

    async def stop_managed_kde(self) -> dict:
        return self._ensure_backend().stop_managed_kde()

    async def get_managed_kde_status(self) -> dict:
        return self._ensure_backend().get_managed_kde_status()

    async def broadcast_discovery(self) -> dict:
        return self._ensure_backend().broadcast_discovery()

    async def ensure_daemon(self) -> dict:
        return await self._ensure_backend().ensure_daemon()

    async def start_daemon(self) -> dict:
        return await self._ensure_backend().start_daemon()

    async def stop_daemon(self) -> dict:
        return await self._ensure_backend().stop_daemon()

    async def restart_daemon(self) -> dict:
        return await self._ensure_backend().restart_daemon()

    async def refresh_devices(self) -> dict:
        return await self._ensure_backend().refresh_devices()

    async def list_devices(self) -> dict:
        return await self._ensure_backend().list_devices()

    async def pair_device(self, device_id: str) -> dict:
        return await self._ensure_backend().pair_device(device_id)

    async def unpair_device(self, device_id: str) -> dict:
        return await self._ensure_backend().unpair_device(device_id)

    async def send_clipboard(self, device_id: str) -> dict:
        return await self._ensure_backend().send_clipboard(device_id)

    async def share_text(self, device_id: str, text: str) -> dict:
        return await self._ensure_backend().share_text(device_id, text)

    async def get_clipboard(self, max_chars: int = 500) -> dict:
        return await self._ensure_backend().get_clipboard(max_chars)

    async def set_clipboard(self, text: str) -> dict:
        return await self._ensure_backend().set_clipboard(text)

    async def share_file(self, device_id: str, path: str) -> dict:
        return await self._ensure_backend().share_file(device_id, path)

    async def list_files(self, directory: str = "", limit: int = 200) -> dict:
        return await self._ensure_backend().list_files(directory, limit)

    async def get_common_directories(self) -> dict:
        return self._ensure_backend().get_common_directories()

    async def get_incoming_directories(self) -> dict:
        return self._ensure_backend().get_incoming_directories()

    async def get_transfer_history(self, limit: int = 50) -> dict:
        return self._ensure_backend().get_transfer_history(limit)

    async def get_deck_ips(self) -> dict:
        return await self._ensure_backend().get_deck_ips()

    async def get_notebook(self) -> dict:
        return self._ensure_backend().get_notebook()

    async def save_notebook(self, text: str) -> dict:
        return self._ensure_backend().save_notebook(text)

    async def export_logs(self) -> dict:
        return self._ensure_backend().export_logs()

    async def run_hidden_command(self, command: str) -> dict:
        return self._ensure_backend().run_hidden_command(command)

    async def list_sendable_files(self, category: str = "screenshots") -> dict:
        return self._ensure_backend().list_sendable_files(category)

    async def send_file_to_phone(self, file_path: str, device_id: str) -> dict:
        return await self.loop.run_in_executor(
            None, self._ensure_backend().send_file_to_phone, file_path, device_id
        )

    async def start_send_file_to_phone(self, file_path: str, device_id: str) -> dict:
        return self._ensure_backend().start_send_file_to_phone(file_path, device_id)

    async def get_send_jobs(self, limit: int = 20) -> dict:
        return self._ensure_backend().get_send_jobs(limit)

    async def start_send_diagnostic_bundle(self, device_id: str) -> dict:
        return self._ensure_backend().start_send_diagnostic_bundle(device_id)

    async def get_thumbnail_base64(self, path: str) -> dict:
        return await self.loop.run_in_executor(
            None, self._ensure_backend().get_thumbnail_base64, path
        )

    async def get_preferred_device(self) -> dict:
        return self._ensure_backend().get_preferred_device()

    async def get_send_targets(self) -> dict:
        return self._ensure_backend().get_send_targets()

    async def set_preferred_device(self, device_id: str) -> dict:
        return self._ensure_backend().set_preferred_device(device_id)

    async def reset_managed_kde_identity(self) -> dict:
        return self._ensure_backend().reset_managed_kde_identity()

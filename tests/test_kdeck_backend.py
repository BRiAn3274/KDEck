import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from kdeck_backend import CommandResult, KDEckBackend
from kdeck_diagnostics import parse_device_list


class DeviceListParserTests(unittest.TestCase):
    def test_parses_paired_reachable_device(self):
        devices = parse_device_list("- Pixel 8: deviceabcdef (paired and reachable)\n")

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "Pixel 8")
        self.assertEqual(devices[0]["id"], "deviceabcdef")
        self.assertTrue(devices[0]["paired"])
        self.assertTrue(devices[0]["reachable"])

    def test_plain_paired_state_has_unknown_reachability(self):
        devices = parse_device_list("- Phone: deviceabcdef (paired)\n")

        self.assertEqual(len(devices), 1)
        self.assertTrue(devices[0]["paired"])
        self.assertIsNone(devices[0]["reachable"])

    def test_unpaired_is_not_misclassified_as_paired(self):
        devices = parse_device_list("- Phone: deviceabcdef (unpaired and reachable)\n")

        self.assertEqual(len(devices), 1)
        self.assertFalse(devices[0]["paired"])
        self.assertTrue(devices[0]["reachable"])

    def test_not_reachable_is_false(self):
        devices = parse_device_list("- Phone: deviceabcdef (paired and not reachable)\n")

        self.assertEqual(len(devices), 1)
        self.assertTrue(devices[0]["paired"])
        self.assertFalse(devices[0]["reachable"])

    def test_accepts_id_only_output(self):
        devices = parse_device_list("deviceabcdef\n")

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["id"], "deviceabcdef")
        self.assertIsNone(devices[0]["paired"])
        self.assertIsNone(devices[0]["reachable"])


class ManagedDaemonStopTests(unittest.IsolatedAsyncioTestCase):
    def make_backend(self) -> KDEckBackend:
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)
        return KDEckBackend(settings_dir=str(root / "settings"), runtime_dir=str(root / "runtime"))

    async def test_stop_managed_daemon_does_not_kill_unowned_pid(self):
        backend = self.make_backend()
        backend.daemon.daemon_pid_path.write_text("12345", encoding="utf-8")

        with mock.patch.object(backend.daemon, "_is_managed_kdeconnectd_pid", return_value=False), mock.patch.object(
            backend, "_run"
        ) as run:
            result = await backend.stop_managed_daemon()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "managed_daemon_not_owned")
        run.assert_not_called()
        self.assertFalse(backend.daemon.daemon_pid_path.exists())

    async def test_stop_daemon_uses_managed_daemon_guard(self):
        backend = self.make_backend()
        backend.daemon.daemon_pid_path.write_text("12345", encoding="utf-8")
        command = CommandResult(command=["kill", "12345"], returncode=0, stdout="", stderr="")

        with mock.patch.object(backend.daemon, "_is_managed_kdeconnectd_pid", return_value=True), mock.patch.object(
            backend.daemon, "_run", return_value=command
        ) as run:
            result = await backend.stop_daemon()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "managed_daemon_stopped")
        run.assert_awaited_once_with(["kill", "12345"], timeout=5)

    async def test_start_managed_kde_pauses_in_desktop_mode(self):
        backend = self.make_backend()

        with mock.patch.object(backend, "_is_desktop_mode_active", return_value=True), mock.patch.object(
            backend.kde_receiver, "start"
        ) as start, mock.patch.object(backend.kde_receiver, "stop", return_value={"ok": True, "running": False}):
            result = backend.start_managed_kde()
            backend.stop_managed_kde()

        start.assert_not_called()
        self.assertTrue(result["paused"])
        self.assertEqual(result["pause_reason"], "desktop_mode")

    async def test_managed_status_includes_diagnostic_summary(self):
        backend = self.make_backend()
        backend.managed_kde_desired = True

        with mock.patch.object(backend, "_is_desktop_mode_active", return_value=False), mock.patch.object(
            backend.kde_receiver,
            "status",
            return_value={
                "ok": True,
                "running": True,
                "udp_working": True,
                "tcp_working": True,
                "paired": False,
                "last_discovery_received": None,
                "last_connect_attempt": None,
                "last_tcp_success": {"host": "192.0.2.153"},
                "last_tls_success": {"host": "192.0.2.153"},
                "last_tls_error": None,
                "last_pair": {"paired": True},
                "last_reannounce_targets": {"direct_targets": []},
                "last_payload_error": None,
                "last_clipboard": None,
                "last_file": None,
                "last_error": None,
                "last_connect_error": None,
            },
        ):
            status = backend.get_managed_kde_status()

        self.assertEqual(status["diagnostic_summary"]["state"], "waiting_discovery")
        self.assertTrue(status["diagnostic_summary"]["checks"]["udp"])
        self.assertTrue(status["diagnostic_summary"]["checks"]["recent_tcp_success"])
        self.assertEqual(status["diagnostic_summary"]["last_pair"], {"paired": True})

    async def test_hidden_status_command_returns_diagnostics(self):
        backend = self.make_backend()

        with mock.patch.object(backend, "get_managed_kde_status", return_value={"diagnostic_summary": {"message": "ready"}}):
            result = backend.run_hidden_command(":kdeck status")

        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "ready")

    async def test_hidden_share_logs_exports_without_reverse_send(self):
        backend = self.make_backend()

        result = backend.run_hidden_command(":kdeck share logs")

        self.assertTrue(result["ok"])
        self.assertTrue(Path(result["path"]).exists())
        self.assertIn("Direct reverse sending is not supported", result["message"])

    async def test_hidden_reannounce_command_calls_receiver(self):
        backend = self.make_backend()

        with mock.patch.object(backend.kde_receiver, "reannounce_trusted_devices", return_value={"ok": True}) as reannounce:
            result = backend.run_hidden_command(":kdeck reannounce")

        self.assertTrue(result["ok"])
        reannounce.assert_called_once_with("hidden_command")

    async def test_incoming_directory_uses_kdeck_receiver_directory(self):
        backend = self.make_backend()

        result = backend.get_incoming_directories()

        self.assertTrue(result["ok"])
        self.assertEqual(result["items"][0]["path"], str(backend.kde_receiver.incoming_dir))
        self.assertEqual(result["items"][0]["managed_by"], "KDEck")

    async def test_received_clipboard_is_saved_and_written_to_deck_clipboard(self):
        backend = self.make_backend()

        with mock.patch.object(backend.clipboard, "set_clipboard_sync", return_value={"ok": True, "length": 5}) as set_clipboard:
            backend._receive_managed_clipboard("hello", "phone")

        self.assertEqual(backend.get_notebook()["text"], "hello")
        set_clipboard.assert_called_once_with("hello")

    async def test_export_logs_redacts_sensitive_receiver_state(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)
        log_dir = root / "logs"
        log_dir.mkdir()
        (log_dir / "latest.log").write_text("decky log", encoding="utf-8")
        backend = KDEckBackend(settings_dir=str(root / "settings"), runtime_dir=str(root / "runtime"), log_dir=str(log_dir))
        backend.save_notebook("secret clipboard")
        backend.file_manager._old_history_path.write_text(
            json.dumps([{"device_id": "phoneabcdef", "path": "/home/deck/Downloads/private.txt", "file_name": "private.txt"}]),
            encoding="utf-8",
        )
        backend.kde_receiver._write_trusted_devices({"phoneabcdef": {"fingerprint": "1234567890abcdef", "trust_mode": "fingerprint", "paired_at": 1}})
        for name in ("receiver-events.jsonl", "receiver-events.jsonl.1"):
            (backend.managed_kde_dir / name).write_text("{}", encoding="utf-8")

        result = backend.export_logs()

        with zipfile.ZipFile(result["path"]) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("managed-kde/receiver-events.jsonl", names)
            self.assertIn("managed-kde/receiver-events.jsonl.1", names)
            self.assertIn("managed-kde/trusted-devices.redacted.json", names)
            self.assertIn("clipboard-notebook.redacted.json", names)
            self.assertIn("transfer-history.redacted.json", names)
            self.assertIn("decky-log/latest.log", names)
            self.assertNotIn("managed-kde/trusted-devices.json", names)
            self.assertNotIn("managed-kde/device-id", names)
            notebook = json.loads(archive.read("clipboard-notebook.redacted.json").decode("utf-8"))
            self.assertEqual(notebook["text_length"], len("secret clipboard"))
            self.assertNotIn("secret clipboard", archive.read("clipboard-notebook.redacted.json").decode("utf-8"))

    async def test_export_logs_prefers_downloads_when_available(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)
        downloads = root / "Downloads"
        downloads.mkdir()
        backend = KDEckBackend(settings_dir=str(root / "settings"), runtime_dir=str(root / "runtime"))

        with mock.patch("kdeck_config.common_directories", return_value=(str(downloads),)):
            result = backend.export_logs()

        self.assertTrue(result["ok"])
        self.assertEqual(Path(result["path"]).parent, downloads)


if __name__ == "__main__":
    unittest.main()


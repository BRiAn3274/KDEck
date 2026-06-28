import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from kdeck_backend import CommandResult, KDEckBackend
from kdeck_diagnostics import KDEckDiagnostics, diagnostic_error, parse_device_list
from kdeck_file_manager import KDEckFileManager

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_release import REQUIRED_ZIP_ENTRIES, validate_release_zip


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


class ReleasePackageTests(unittest.TestCase):
    def test_release_zip_validator_accepts_required_entries(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        zip_path = Path(temp_dir.name) / "KDEck.zip"

        with zipfile.ZipFile(zip_path, "w") as archive:
            for entry in REQUIRED_ZIP_ENTRIES:
                archive.writestr(entry, "x")

        validate_release_zip(zip_path)

    def test_release_zip_validator_rejects_missing_required_entry(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        zip_path = Path(temp_dir.name) / "KDEck.zip"

        with zipfile.ZipFile(zip_path, "w") as archive:
            for entry in REQUIRED_ZIP_ENTRIES[:-1]:
                archive.writestr(entry, "x")

        with self.assertRaises(SystemExit):
            validate_release_zip(zip_path)


class SendableFileScannerTests(unittest.TestCase):
    def make_manager(self, root: Path) -> KDEckFileManager:
        return KDEckFileManager(
            settings_dir=root / "settings",
            kde_receiver=type("_Receiver", (), {"incoming_dir": root / "Downloads"})(),
        )

    def test_saves_category_scans_steam_userdata_and_filters_cache(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        save_dir = root / ".local/share/Steam/userdata/123/456/remote/profile"
        cache_dir = root / ".local/share/Steam/userdata/123/456/remote/cache"
        manifest = root / ".local/share/Steam/steamapps/appmanifest_456.acf"
        save_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)
        manifest.parent.mkdir(parents=True)
        save_file = save_dir / "slot1.sav"
        cache_file = cache_dir / "throwaway.dat"
        save_file.write_bytes(b"save")
        cache_file.write_bytes(b"cache")
        manifest.write_text('"AppState"\n{\n    "appid" "456"\n    "name" "Test Game"\n}\n', encoding="utf-8")
        manager = self.make_manager(root)

        with mock.patch("kdeck_config.deck_home", return_value=root):
            result = manager.list_sendable_files("saves")

        self.assertTrue(result["ok"])
        self.assertEqual([item["name"] for item in result["files"]], ["slot1.sav"])
        self.assertEqual(result["files"][0]["app_id"], "456")
        self.assertEqual(result["files"][0]["app_name"], "Test Game")

    def test_saves_category_reads_external_steam_library_manifest(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        external = root / "external-library"
        save_dir = root / ".local/share/Steam/userdata/123/789/remote/save"
        libraryfolders = root / ".local/share/Steam/steamapps/libraryfolders.vdf"
        manifest = external / "steamapps/appmanifest_789.acf"
        save_dir.mkdir(parents=True)
        libraryfolders.parent.mkdir(parents=True)
        manifest.parent.mkdir(parents=True)
        (save_dir / "slot1.sav").write_bytes(b"save")
        libraryfolders.write_text(f'"libraryfolders"\n{{\n  "1"\n  {{\n    "path" "{str(external).replace(chr(92), chr(92) + chr(92))}"\n  }}\n}}\n', encoding="utf-8")
        manifest.write_text('"AppState"\n{\n    "appid" "789"\n    "name" "External Game"\n}\n', encoding="utf-8")
        manager = self.make_manager(root)

        with mock.patch("kdeck_config.deck_home", return_value=root):
            result = manager.list_sendable_files("saves")

        self.assertTrue(result["ok"])
        self.assertEqual(result["files"][0]["app_name"], "External Game")

    def test_thumbnail_base64_prefers_sibling_thumbnail(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        image = root / "shot.jpg"
        thumb = root / "thumbnails" / "shot.jpg"
        thumb.parent.mkdir()
        image.write_bytes(b"full image")
        thumb.write_bytes(b"thumb image")
        manager = self.make_manager(root)

        result = manager.get_thumbnail_base64(str(image))

        self.assertTrue(result["ok"])
        self.assertEqual(result["mime"], "image/jpeg")
        self.assertEqual(result["data"], "dGh1bWIgaW1hZ2U=")

    def test_video_thumbnail_uses_existing_thumbnail_without_ffmpeg(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        recording = root / "clip.mp4"
        thumb = root / "thumbnails" / "clip.jpg"
        thumb.parent.mkdir()
        recording.write_bytes(b"fake video")
        thumb.write_bytes(b"video thumb")
        manager = self.make_manager(root)

        with mock.patch("shutil.which", return_value=None):
            result = manager.get_thumbnail_base64(str(recording))

        self.assertTrue(result["ok"])
        self.assertEqual(result["mime"], "image/jpeg")
        self.assertEqual(result["data"], "dmlkZW8gdGh1bWI=")

    def test_save_thumbnail_uses_steam_librarycache_icon(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        save_file = root / ".local/share/Steam/userdata/123/456/remote/slot1.sav"
        icon = root / ".local/share/Steam/appcache/librarycache/456_icon.jpg"
        save_file.parent.mkdir(parents=True)
        icon.parent.mkdir(parents=True)
        save_file.write_bytes(b"save")
        icon.write_bytes(b"app icon")
        manager = self.make_manager(root)

        with mock.patch("kdeck_config.deck_home", return_value=root):
            result = manager.get_thumbnail_base64(str(save_file))

        self.assertTrue(result["ok"])
        self.assertEqual(result["mime"], "image/jpeg")
        self.assertEqual(result["data"], "YXBwIGljb24=")

    def test_save_thumbnail_falls_back_to_loose_librarycache_match(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        save_file = root / ".local/share/Steam/userdata/123/456/remote/slot1.sav"
        icon = root / ".local/share/Steam/appcache/librarycache/456_capsule_616x353.jpg"
        save_file.parent.mkdir(parents=True)
        icon.parent.mkdir(parents=True)
        save_file.write_bytes(b"save")
        icon.write_bytes(b"capsule")
        manager = self.make_manager(root)

        with mock.patch("kdeck_config.deck_home", return_value=root):
            result = manager.get_thumbnail_base64(str(save_file))

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], "Y2Fwc3VsZQ==")

    def test_thumbnail_cache_cleanup_removes_old_files(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        manager = self.make_manager(root)
        cache_dir = root / "settings" / "thumbnail-cache"
        cache_dir.mkdir(parents=True)
        old_file = cache_dir / "old.jpg"
        fresh_file = cache_dir / "fresh.jpg"
        old_file.write_bytes(b"old")
        fresh_file.write_bytes(b"fresh")
        old_time = time.time() - 30 * 24 * 60 * 60
        os.utime(old_file, (old_time, old_time))

        manager._clean_thumbnail_cache()

        self.assertFalse(old_file.exists())
        self.assertTrue(fresh_file.exists())

    def test_transfer_history_trims_to_recent_entries(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        manager = self.make_manager(root)

        for index in range(505):
            manager._append_transfer_history({"index": index})

        history = manager._read_history()
        self.assertEqual(len(history), 500)
        self.assertEqual(history[0]["index"], 5)
        self.assertEqual(history[-1]["index"], 504)

    def test_logs_category_includes_source_summary_and_recommended_flag(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        manager = self.make_manager(root)
        receiver_log = root / "settings" / "managed-kde" / "receiver-events.jsonl"
        decky_log = root / "logs" / "latest.log"
        runtime_log = root / "runtime" / "kdeconnectd.log"
        receiver_log.parent.mkdir(parents=True)
        decky_log.parent.mkdir()
        runtime_log.parent.mkdir()
        receiver_log.write_text("{}", encoding="utf-8")
        decky_log.write_text("decky", encoding="utf-8")
        runtime_log.write_text("daemon", encoding="utf-8")
        manager.log_dir = decky_log.parent
        manager.runtime_dir = runtime_log.parent

        result = manager.list_sendable_files("logs")

        self.assertTrue(result["ok"])
        by_name = {item["name"]: item for item in result["files"]}
        self.assertEqual(by_name["receiver-events.jsonl"]["source"], "KDEck Receiver")
        self.assertEqual(by_name["receiver-events.jsonl"]["summary"], "KDEck protocol events")
        self.assertTrue(by_name["receiver-events.jsonl"]["recommended"])
        self.assertEqual(by_name["kdeconnectd.log"]["source"], "KDE Connect Daemon")

    def test_background_send_job_tracks_progress_and_result(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        source = root / "clip.mp4"
        source.write_bytes(b"1234567890")

        class Receiver:
            incoming_dir = root / "Downloads"

            def send_share_request_to_peer(self, file_path, device_id, progress_callback=None):
                if progress_callback:
                    progress_callback({"phase": "transferring", "bytes_sent": 5, "total_bytes": 10})
                    progress_callback({"phase": "transferring", "bytes_sent": 10, "total_bytes": 10})
                return {"ok": True, "file": Path(file_path).name, "size": 10}

        manager = KDEckFileManager(settings_dir=root / "settings", kde_receiver=Receiver())

        result = manager.start_send_file_to_phone(str(source), "phoneabcdef")
        self.assertTrue(result["ok"])
        job_id = result["job"]["job_id"]
        for _ in range(50):
            jobs = manager.get_send_jobs()["jobs"]
            job = next(item for item in jobs if item["job_id"] == job_id)
            if job["status"] == "finished":
                break
            time.sleep(0.02)

        self.assertEqual(job["status"], "finished")
        self.assertEqual(job["bytes_sent"], 10)
        self.assertEqual(job["total_bytes"], 10)
        history = manager.get_transfer_history()["items"]
        self.assertEqual(history[0]["direction"], "send")
        self.assertEqual(history[0]["status"], "finished")
        self.assertEqual(history[0]["file_name"], "clip.mp4")

    def test_background_send_job_records_failed_history(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        source = root / "clip.mp4"
        source.write_bytes(b"1234567890")

        class Receiver:
            incoming_dir = root / "Downloads"

            def send_share_request_to_peer(self, file_path, device_id, progress_callback=None):
                return {"ok": False, "error": {"code": "transfer_incomplete", "message": "File transfer incomplete."}}

        manager = KDEckFileManager(settings_dir=root / "settings", kde_receiver=Receiver())

        result = manager.start_send_file_to_phone(str(source), "phoneabcdef")
        self.assertTrue(result["ok"])
        job_id = result["job"]["job_id"]
        for _ in range(50):
            jobs = manager.get_send_jobs()["jobs"]
            job = next(item for item in jobs if item["job_id"] == job_id)
            if job["status"] == "failed":
                break
            time.sleep(0.02)

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "transfer_incomplete")
        history = manager.get_transfer_history()["items"]
        self.assertEqual(history[0]["direction"], "send")
        self.assertEqual(history[0]["status"], "failed")
        self.assertEqual(history[0]["error_code"], "transfer_incomplete")

    def test_record_received_file_writes_history(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        manager = self.make_manager(root)

        manager.record_received_file(
            {
                "device_id": "phoneabcdef",
                "file": "photo.jpg",
                "path": str(root / "Downloads" / "photo.jpg"),
                "size": 42,
            }
        )

        history = manager.get_transfer_history()["items"]
        self.assertEqual(history[0]["direction"], "receive")
        self.assertEqual(history[0]["status"], "finished")
        self.assertEqual(history[0]["file_name"], "photo.jpg")
        self.assertEqual(history[0]["size"], 42)


class ManagedDaemonStopTests(unittest.IsolatedAsyncioTestCase):
    def make_backend(self) -> KDEckBackend:
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)
        return KDEckBackend(settings_dir=str(root / "settings"), runtime_dir=str(root / "runtime"))

    async def test_stop_managed_daemon_does_not_kill_unowned_pid(self):
        backend = self.make_backend()
        backend.daemon.daemon_pid_path.write_text("12345", encoding="utf-8")

        with mock.patch.object(backend.daemon, "_managed_kdeconnectd_pids", return_value=[]), mock.patch.object(
            backend.daemon, "_is_managed_kdeconnectd_pid", return_value=False
        ), mock.patch.object(
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

        with mock.patch.object(backend.daemon, "_managed_kdeconnectd_pids", return_value=[]), mock.patch.object(
            backend.daemon, "_is_managed_kdeconnectd_pid", return_value=True
        ), mock.patch.object(
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
        ) as start, mock.patch.object(backend.kde_receiver, "stop", return_value={"ok": True, "running": False}), mock.patch.object(
            backend.daemon, "stop_managed_daemon_sync"
        ) as stop_daemon:
            result = backend.start_managed_kde()
            backend.stop_managed_kde()

        start.assert_not_called()
        stop_daemon.assert_not_called()
        self.assertTrue(result["paused"])
        self.assertEqual(result["pause_reason"], "desktop_mode")

    async def test_start_managed_kde_stops_plugin_owned_kdeconnectd(self):
        backend = self.make_backend()

        with mock.patch.object(backend, "_is_desktop_mode_active", return_value=False), mock.patch.object(
            backend.daemon, "stop_user_daemons_sync", return_value={"ok": True}
        ) as stop_user_daemons, mock.patch.object(
            backend.daemon, "stop_managed_daemon_sync", return_value={"ok": True}
        ) as stop_daemon, mock.patch.object(backend.kde_receiver, "start", return_value={"ok": True, "running": True}), mock.patch.object(
            backend.kde_receiver, "reannounce_trusted_devices"
        ):
            backend.start_managed_kde()

        stop_user_daemons.assert_called_once_with("managed_receiver_start")
        stop_daemon.assert_called_once()

    async def test_stop_user_daemons_sync_kills_deck_user_kdeconnectd(self):
        backend = self.make_backend()
        backend.daemon.daemon_pid_path.write_text("12345", encoding="utf-8")

        pgrep = mock.Mock(returncode=0, stdout="123\n456\n", stderr="")
        killed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", side_effect=[pgrep, killed, killed]) as run:
            result = backend.daemon.stop_user_daemons_sync("test")

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "user_daemon_stopped")
        self.assertEqual(result["stopped"], [123, 456])
        self.assertFalse(backend.daemon.daemon_pid_path.exists())
        self.assertEqual(run.call_args_list[1][0][0], ["kill", "123"])
        self.assertEqual(run.call_args_list[2][0][0], ["kill", "456"])

    async def test_backend_keeps_event_loop_for_watchdog_restart(self):
        loop = mock.Mock()
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)

        backend = KDEckBackend(settings_dir=str(root / "settings"), runtime_dir=str(root / "runtime"), event_loop=loop)

        self.assertIs(backend.loop, loop)

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

    async def test_managed_status_diagnostic_summary_promotes_transfer_errors(self):
        payload_error = diagnostic_error(
            "transfer_timeout",
            "transfer",
            "Peer did not connect to download the file.",
            device_id="phone",
        )
        status = {
            "desired": True,
            "paused": False,
            "udp_working": True,
            "tcp_working": True,
            "paired": True,
            "last_discovery_received": {"device_id": "phone"},
            "last_payload_error": payload_error,
            "last_error": payload_error,
        }

        summary = KDEckDiagnostics.receiver_diagnostic_summary(status)

        self.assertEqual(summary["state"], "transfer_timeout")
        self.assertEqual(summary["problem_code"], "transfer_timeout")
        self.assertEqual(summary["problem_message"], "The device did not request the file payload in time.")

    async def test_hidden_status_command_returns_diagnostics(self):
        backend = self.make_backend()

        with mock.patch.object(backend, "get_managed_kde_status", return_value={"diagnostic_summary": {"message": "ready"}}):
            result = backend.run_hidden_command(":kdeck status")

        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "ready")

    async def test_hidden_help_lists_current_commands(self):
        backend = self.make_backend()

        result = backend.run_hidden_command(":kdeck help")

        self.assertTrue(result["ok"])
        self.assertEqual(
            set(result["commands"]),
            {
                ":kdeck help",
                ":kdeck status",
                ":kdeck devices",
                ":kdeck reannounce",
                ":kdeck logs",
                ":kdeck export logs",
                ":kdeck share logs",
                ":kdeck reset identity",
            },
        )

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

    async def test_get_send_targets_returns_trusted_devices_with_preference(self):
        backend = self.make_backend()
        trusted = {
            "desktop1234": {"device_name": "Desktop", "device_type": "desktop", "trust_mode": "device_id"},
            "phone1234": {"device_name": "Phone", "device_type": "phone", "trust_mode": "device_id"},
        }
        status = {
            "trusted_devices": trusted,
            "discovered_devices": [{"device_id": "phone1234", "device_name": "Phone Live", "device_type": "phone", "last_seen": 100}],
            "peer_connections": {"phone1234": {"host": "192.0.2.10"}},
        }

        with mock.patch.object(backend.kde_receiver, "trusted_devices", return_value=trusted), mock.patch.object(
            backend.kde_receiver, "status", return_value=status
        ):
            backend.set_preferred_device("desktop1234")
            result = backend.get_send_targets()

        self.assertTrue(result["ok"])
        self.assertEqual(result["preferred_device_id"], "desktop1234")
        self.assertEqual([item["id"] for item in result["devices"]], ["phone1234", "desktop1234"])
        self.assertTrue(result["devices"][0]["connected"])

    async def test_set_preferred_device_rejects_untrusted_device(self):
        backend = self.make_backend()

        with mock.patch.object(backend.kde_receiver, "trusted_devices", return_value={}):
            result = backend.set_preferred_device("missing1234")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "not_trusted")

    async def test_cleanup_plugin_data_preserves_managed_identity(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: temp_dir.cleanup())
        root = Path(temp_dir.name)
        settings = root / "settings" / "kdeck"
        runtime = root / "runtime" / "kdeck"
        logs = root / "logs" / "kdeck"
        backend = KDEckBackend(settings_dir=str(settings), runtime_dir=str(runtime), log_dir=str(logs))
        identity_files = (
            backend.kde_receiver.device_id_path,
            backend.kde_receiver.cert_path,
            backend.kde_receiver.key_path,
            backend.kde_receiver.trusted_path,
        )
        for path in identity_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("identity", encoding="utf-8")
        transient = settings / "thumbnail-cache" / "old.jpg"
        transient.parent.mkdir(parents=True, exist_ok=True)
        transient.write_bytes(b"cache")
        runtime.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)

        result = backend.cleanup_plugin_data(str(logs))

        self.assertTrue(result["ok"])
        self.assertTrue(settings.exists())
        for path in identity_files:
            self.assertTrue(path.exists(), path.name)
        self.assertFalse(transient.exists())
        self.assertFalse(runtime.exists())
        self.assertFalse(logs.exists())

    async def test_reset_managed_kde_identity_removes_identity_and_preference(self):
        backend = self.make_backend()
        identity_files = (
            backend.kde_receiver.device_id_path,
            backend.kde_receiver.cert_path,
            backend.kde_receiver.key_path,
            backend.kde_receiver.trusted_path,
        )
        for path in identity_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("identity", encoding="utf-8")
        preferred = backend.settings_dir / "preferred-device.json"
        preferred.write_text(json.dumps({"device_id": "phone1234"}), encoding="utf-8")

        result = backend.reset_managed_kde_identity()

        self.assertTrue(result["ok"])
        for path in identity_files:
            self.assertFalse(path.exists(), path.name)
        self.assertFalse(preferred.exists())

    async def test_hidden_reset_identity_command_clears_identity(self):
        backend = self.make_backend()
        backend.kde_receiver.trusted_path.parent.mkdir(parents=True, exist_ok=True)
        backend.kde_receiver.trusted_path.write_text("{}", encoding="utf-8")

        result = backend.run_hidden_command(":kdeck reset identity")

        self.assertTrue(result["ok"])
        self.assertIn("cleared", result["message"])
        self.assertFalse(backend.kde_receiver.trusted_path.exists())

    async def test_hidden_update_command_is_not_available_in_store_build(self):
        backend = self.make_backend()

        result = backend.run_hidden_command(":kdeck update https://github.com/BRiAn3274/KDEck/releases/download/v0.6.1/KDEck.zip " + "a" * 64)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "unknown_hidden_command")

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
        backend.kde_receiver.write_trusted_devices({"phoneabcdef": {"fingerprint": "1234567890abcdef", "trust_mode": "fingerprint", "paired_at": 1}})
        for name in ("receiver-events.jsonl", "receiver-events.jsonl.1"):
            (backend.managed_kde_dir / name).write_text("{}", encoding="utf-8")

        result = backend.export_logs()

        with zipfile.ZipFile(result["path"]) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("status-snapshot.json", names)
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
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["event_log"]["required_fields"], ["time", "event", "stage", "device_id"])
            self.assertIn("peer_connect_failed", manifest["event_log"]["rate_limited_events"])
            self.assertNotIn(str(root), archive.read("manifest.json").decode("utf-8"))
            snapshot = json.loads(archive.read("status-snapshot.json").decode("utf-8"))
            self.assertNotEqual(snapshot["device_id"], backend.kde_receiver.device_id)

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


import unittest
import tempfile
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from kdeck_backend import CommandResult, KDEckBackend, parse_device_list


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
        backend.daemon_pid_path.write_text("12345", encoding="utf-8")

        with mock.patch.object(backend, "_is_managed_kdeconnectd_pid", return_value=False), mock.patch.object(
            backend, "_run"
        ) as run:
            result = await backend.stop_managed_daemon()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "managed_daemon_not_owned")
        run.assert_not_called()
        self.assertFalse(backend.daemon_pid_path.exists())

    async def test_stop_daemon_uses_managed_daemon_guard(self):
        backend = self.make_backend()
        backend.daemon_pid_path.write_text("12345", encoding="utf-8")
        command = CommandResult(command=["kill", "12345"], returncode=0, stdout="", stderr="")

        with mock.patch.object(backend, "_is_managed_kdeconnectd_pid", return_value=True), mock.patch.object(
            backend, "_run", return_value=command
        ) as run:
            result = await backend.stop_daemon()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "managed_daemon_stopped")
        run.assert_awaited_once_with(["kill", "12345"], timeout=5)


if __name__ == "__main__":
    unittest.main()


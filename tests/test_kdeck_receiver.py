import tempfile
import unittest
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from kdeck_kde_receiver import KDEckKdeReceiver


class ReceiverSecurityTests(unittest.TestCase):
    def make_receiver(self) -> KDEckKdeReceiver:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return KDEckKdeReceiver(
            state_dir=Path(temp_dir.name),
            on_clipboard=lambda _text, _device_id=None: None,
            incoming_dir=Path(temp_dir.name) / "incoming",
        )

    def test_trust_requires_matching_fingerprint(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"fingerprint": "abc123"}})

        self.assertTrue(receiver._is_trusted_device("phone", "abc123"))
        self.assertFalse(receiver._is_trusted_device("phone", "wrong"))
        self.assertFalse(receiver._is_trusted_device("other", "abc123"))

    def test_legacy_trust_without_fingerprint_is_not_enough(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"paired_at": 123}})

        self.assertFalse(receiver._is_trusted_device("phone", "abc123"))
        status = receiver.status()
        self.assertFalse(status["paired"])
        self.assertEqual(status["trusted_devices"], {})
        self.assertEqual(status["legacy_trusted_devices"], ["phone"])

    def test_pair_fallback_trust_mode_allows_device_id_when_certificate_is_unavailable(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"paired_at": 123, "fingerprint": None, "trust_mode": "device_id"}})

        self.assertTrue(receiver._is_trusted_device("phone", None))
        self.assertTrue(receiver.status()["paired"])

    def test_bind_available_tcp_port_skips_busy_port(self):
        receiver = self.make_receiver()

        server = mock.Mock()
        server.bind.side_effect = [OSError("busy"), None]
        with mock.patch("kdeck_kde_receiver.TCP_PORT_MIN", 18100), mock.patch(
            "kdeck_kde_receiver.TCP_PORT_MAX", 18101
        ):
            port = receiver._bind_available_tcp_port(server)

        self.assertEqual(port, 18101)
        self.assertEqual(server.bind.call_args_list, [mock.call(("0.0.0.0", 18100)), mock.call(("0.0.0.0", 18101))])

    def test_identity_packet_advertises_actual_tcp_port(self):
        receiver = self.make_receiver()
        receiver.tcp_port = 1739

        packet = receiver._identity_packet(target_device_id="phone", target_protocol_version=8)

        self.assertEqual(packet["body"]["tcpPort"], 1739)
        self.assertEqual(packet["body"]["targetDeviceId"], "phone")
        self.assertEqual(packet["body"]["targetProtocolVersion"], 8)

    def test_peer_connect_attempts_are_rate_limited(self):
        receiver = self.make_receiver()

        identity = {"deviceId": "desktop", "deviceType": "desktop"}

        self.assertTrue(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))
        self.assertFalse(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))

    def test_android_devices_are_not_skipped(self):
        receiver = self.make_receiver()

        self.assertTrue(receiver._should_connect_to_peer("192.0.2.2", 1716, {"deviceId": "phone", "deviceType": "phone"}))

    def test_android_identity_reply_uses_source_port_only(self):
        receiver = self.make_receiver()

        self.assertEqual(receiver._identity_reply_ports(43566, {"deviceType": "phone"}), [43566])

    def test_desktop_identity_reply_keeps_1716_fallback(self):
        receiver = self.make_receiver()

        self.assertEqual(receiver._identity_reply_ports(43566, {"deviceType": "desktop"}), [43566, 1716])

    def test_android_peer_tls_mode_matches_legacy_server_path(self):
        receiver = self.make_receiver()

        self.assertEqual(receiver._peer_tls_mode("phone"), "server")

    def test_source_ips_for_host_prefers_same_subnet(self):
        receiver = self.make_receiver()
        interfaces = [
            {"interface": "zt0", "address": "203.0.113.96", "prefixlen": 24},
            {"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24},
            {"interface": "et_7_b3xs", "address": "198.51.100.2", "prefixlen": 24},
        ]

        self.assertEqual(receiver._source_ips_for_host("192.0.2.153", interfaces), ["192.0.2.144"])

    def test_source_ips_for_host_falls_back_to_all_interfaces(self):
        receiver = self.make_receiver()
        interfaces = [
            {"interface": "zt0", "address": "203.0.113.96", "prefixlen": 24},
            {"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24},
        ]

        self.assertEqual(receiver._source_ips_for_host("198.51.100.10", interfaces), ["192.0.2.144", "203.0.113.96"])

    def test_usable_ipv4_excludes_proxy_benchmark_range(self):
        receiver = self.make_receiver()

        self.assertFalse(receiver._is_usable_ipv4("198.18.0.1"))
        self.assertFalse(receiver._is_usable_ipv4("169.254.1.1"))
        self.assertTrue(receiver._is_usable_ipv4("192.0.2.37"))

    def test_safe_filename_removes_paths_and_reserved_characters(self):
        receiver = self.make_receiver()

        self.assertEqual(receiver._safe_filename(r"..\bad/name?.txt"), "name.txt")

    def test_recent_discovery_targets_include_source_port_and_udp_fallback(self):
        receiver = self.make_receiver()
        receiver._record_discovery_received(
            ("192.0.2.153", 50484),
            {
                "deviceId": "phone",
                "deviceName": "Phone",
                "deviceType": "phone",
                "tcpPort": 1716,
                "protocolVersion": 8,
            },
        )
        interfaces = [{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24, "priority": 100}]

        self.assertEqual(
            receiver._recent_discovery_targets(interfaces),
            [("192.0.2.144", "192.0.2.153", 50484), ("192.0.2.144", "192.0.2.153", 1716)],
        )


if __name__ == "__main__":
    unittest.main()


import json
import shutil
import socket
import ssl
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from kdeck_kde_connection import peer_connect_decision
from kdeck_kde_discovery import recent_discovery_targets, trusted_direct_targets
from kdeck_kde_protocol import decode_packet, encode_packet, packet_payload_size, payload_port
from kdeck_kde_receiver import EVENT_LOG_MAX_BYTES, FILE_CHUNK_BYTES, MAX_FILE_BYTES, MAX_PACKET_BYTES, KDEckKdeReceiver
from kdeck_kde_trust import accept_pair_record
from kdeck_kde_trust_migration import migrate_trusted_devices


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

    def test_trusted_device_migration_preserves_legacy_untrusted_state(self):
        migrated, changed = migrate_trusted_devices(
            {
                "phone": {
                    "name": "Pixel",
                    "type": "phone",
                    "host": "192.0.2.153",
                    "paired_at": 123,
                },
                "desktop": True,
            },
            now=500,
        )

        self.assertTrue(changed)
        self.assertEqual(migrated["phone"]["device_id"], "phone")
        self.assertEqual(migrated["phone"]["device_name"], "Pixel")
        self.assertEqual(migrated["phone"]["device_type"], "phone")
        self.assertEqual(migrated["phone"]["last_host"], "192.0.2.153")
        self.assertEqual(migrated["phone"]["schema_version"], 2)
        self.assertNotIn("trust_mode", migrated["phone"])
        self.assertEqual(migrated["desktop"]["device_id"], "desktop")
        self.assertEqual(migrated["desktop"]["legacy_value"], True)

    def test_pair_fallback_trust_mode_allows_device_id_when_certificate_is_unavailable(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"paired_at": 123, "fingerprint": None, "trust_mode": "device_id"}})

        self.assertTrue(receiver._is_trusted_device("phone", None))
        self.assertTrue(receiver.status()["paired"])

    def test_accept_pair_record_preserves_metadata_and_sets_trust_fields(self):
        trusted, trust_mode = accept_pair_record(
            {"phone": {"device_name": "Phone"}},
            "phone",
            "192.0.2.153",
            "abc123",
            now=500,
        )

        self.assertEqual(trust_mode, "fingerprint")
        self.assertEqual(trusted["phone"]["device_name"], "Phone")
        self.assertEqual(trusted["phone"]["fingerprint"], "abc123")
        self.assertEqual(trusted["phone"]["last_host"], "192.0.2.153")
        self.assertEqual(trusted["phone"]["paired_at"], 500)

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

    def test_bind_available_tcp_port_prefers_kdeconnect_default_port(self):
        receiver = self.make_receiver()

        server = mock.Mock()
        server.bind.return_value = None
        port = receiver._bind_available_tcp_port(server)

        self.assertEqual(port, 1716)
        server.bind.assert_called_once_with(("0.0.0.0", 1716))

    def test_identity_packet_advertises_actual_tcp_port(self):
        receiver = self.make_receiver()
        receiver.tcp_port = 1739

        packet = receiver._identity_packet(target_device_id="phone", target_protocol_version=8)

        self.assertEqual(packet["body"]["tcpPort"], 1739)
        self.assertEqual(packet["body"]["targetDeviceId"], "phone")
        self.assertEqual(packet["body"]["targetProtocolVersion"], 8)
        self.assertIn("kdeconnect.pair", packet["body"]["incomingCapabilities"])
        self.assertIn("kdeconnect.pair", packet["body"]["outgoingCapabilities"])

    def test_peer_connect_attempts_are_rate_limited(self):
        receiver = self.make_receiver()

        identity = {"deviceId": "desktop", "deviceType": "desktop"}

        self.assertTrue(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))
        self.assertFalse(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))

    def test_peer_connect_decision_reports_cooldown_event(self):
        allowed, key, event = peer_connect_decision(
            "phone",
            "192.0.2.2",
            1716,
            now=12.0,
            previous_attempts={"phone@192.0.2.2:1716": 10.0},
            cooldown=5,
        )

        self.assertFalse(allowed)
        self.assertEqual(key, "phone@192.0.2.2:1716")
        self.assertEqual(event["reason"], "cooldown")
        self.assertEqual(event["cooldown_seconds"], 5)

    def test_trusted_peer_connect_cooldown_is_shorter(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"fingerprint": "abc123"}})

        identity = {"deviceId": "phone", "deviceType": "phone"}

        self.assertTrue(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))
        with mock.patch("time.monotonic", return_value=time.monotonic() + 6):
            self.assertTrue(receiver._should_connect_to_peer("192.0.2.2", 1716, identity))

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

    def test_trusted_direct_targets_survive_receiver_restart_state(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices(
            {
                "phone": {
                    "fingerprint": "abc123",
                    "last_host": "192.0.2.153",
                    "udp_source_port": 50484,
                    "last_seen": 200,
                }
            }
        )
        interfaces = [{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24, "priority": 100}]

        with mock.patch("time.time", return_value=300):
            targets = receiver._trusted_direct_targets(interfaces)

        self.assertEqual(targets, [("192.0.2.144", "192.0.2.153", 50484), ("192.0.2.144", "192.0.2.153", 1716)])

    def test_direct_target_merge_preserves_order_and_deduplicates(self):
        receiver = self.make_receiver()

        merged = receiver._merge_direct_targets(
            [("192.0.2.144", "192.0.2.153", 50484), ("192.0.2.144", "192.0.2.153", 1716)],
            [("192.0.2.144", "192.0.2.153", 1716), ("203.0.113.2", "203.0.113.3", 1716)],
        )

        self.assertEqual(
            merged,
            [
                ("192.0.2.144", "192.0.2.153", 50484),
                ("192.0.2.144", "192.0.2.153", 1716),
                ("203.0.113.2", "203.0.113.3", 1716),
            ],
        )

    def test_discovery_helper_ignores_stale_recent_devices(self):
        interfaces = [{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24, "priority": 100}]

        targets = recent_discovery_targets(
            [{"device_id": "phone", "host": "192.0.2.153", "udp_source_port": 50484, "last_seen": 1}],
            interfaces,
            now=1000,
            source_ips_for_host=lambda _host, _interfaces: ["192.0.2.144"],
        )

        self.assertEqual(targets, [])

    def test_trusted_target_helper_returns_event_details_without_side_effects(self):
        interfaces = [{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24, "priority": 100}]

        targets, events = trusted_direct_targets(
            {"phone": {"last_host": "192.0.2.153", "udp_source_port": 50484, "last_seen": 900}},
            interfaces,
            now=1000,
            source_ips_for_host=lambda _host, _interfaces: ["192.0.2.144"],
        )

        self.assertEqual(targets, [("192.0.2.144", "192.0.2.153", 50484), ("192.0.2.144", "192.0.2.153", 1716)])
        self.assertEqual(events, [{"device_id": "phone", "host": "192.0.2.153", "ports": [50484, 1716], "target_count": 2}])

    def test_trusted_device_metadata_updates_from_discovery(self):
        receiver = self.make_receiver()
        receiver._write_trusted_devices({"phone": {"fingerprint": "abc123"}})

        with mock.patch("time.time", return_value=300):
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

        trusted = receiver._trusted_devices()["phone"]
        self.assertEqual(trusted["last_host"], "192.0.2.153")
        self.assertEqual(trusted["udp_source_port"], 50484)
        self.assertEqual(trusted["device_name"], "Phone")

    def test_trusted_devices_public_api_wraps_internal_state(self):
        receiver = self.make_receiver()

        receiver.write_trusted_devices({"phone": {"fingerprint": "abc123"}})

        self.assertEqual(receiver.trusted_devices()["phone"]["fingerprint"], "abc123")

    def test_local_host_detection_uses_receiver_interfaces(self):
        receiver = self.make_receiver()

        with mock.patch.object(receiver, "_network_interfaces", return_value=[{"address": "192.0.2.144"}]):
            self.assertTrue(receiver._is_local_host("192.0.2.144"))
            self.assertFalse(receiver._is_local_host("192.0.2.153"))

    def test_decode_packet_rejects_oversized_packet(self):
        receiver = self.make_receiver()

        packet = receiver._decode_packet(b"x" * (MAX_PACKET_BYTES + 1), context={"stage": "test"})

        self.assertEqual(packet, {})
        self.assertEqual(receiver._tail_events(1)[0]["reason"], "packet_too_large")

    def test_decode_packet_rejects_invalid_body_shape(self):
        receiver = self.make_receiver()
        payload = json.dumps({"type": "kdeconnect.clipboard", "body": "bad"}).encode("utf-8")

        packet = receiver._decode_packet(payload, context={"stage": "test"})

        self.assertEqual(packet, {})
        self.assertEqual(receiver._tail_events(1)[0]["reason"], "body_not_object")

    def test_protocol_codec_round_trips_packet_body(self):
        encoded = encode_packet({"type": "kdeconnect.ping", "body": {"hello": "world"}})

        decoded = decode_packet(encoded)

        self.assertEqual(decoded["type"], "kdeconnect.ping")
        self.assertEqual(decoded["body"], {"hello": "world"})
        self.assertIsInstance(decoded["id"], int)

    def test_protocol_payload_helpers_validate_size_and_port(self):
        self.assertEqual(packet_payload_size({"payloadSize": "42"}), 42)
        self.assertIsNone(packet_payload_size({"payloadSize": "-1"}))
        self.assertEqual(payload_port({"port": "1716"}), 1716)
        self.assertIsNone(payload_port({"port": "70000"}))

    def test_share_request_rejects_invalid_payload_size(self):
        receiver = self.make_receiver()

        receiver._receive_share_request(
            "phone",
            "192.0.2.153",
            {"body": {"filename": "bad.bin"}, "payloadTransferInfo": {"port": 1716}, "payloadSize": -1},
        )

        event = receiver._tail_events(1)[0]
        self.assertEqual(event["event"], "share_ignored")
        self.assertEqual(event["reason"], "invalid_payload_size")

    def test_share_request_rejects_invalid_payload_port(self):
        receiver = self.make_receiver()

        receiver._receive_share_request(
            "phone",
            "192.0.2.153",
            {"body": {"filename": "bad.bin"}, "payloadTransferInfo": {"port": 70000}, "payloadSize": 1},
        )

        event = receiver._tail_events(1)[0]
        self.assertEqual(event["event"], "share_ignored")
        self.assertEqual(event["reason"], "invalid_payload_port")

    def test_share_request_rejects_oversized_file_without_connecting(self):
        receiver = self.make_receiver()

        with mock.patch("socket.create_connection") as connect:
            receiver._receive_share_request(
                "phone",
                "192.0.2.153",
                {"body": {"filename": "huge.bin"}, "payloadTransferInfo": {"port": 1716}, "payloadSize": MAX_FILE_BYTES + 1},
            )

        connect.assert_not_called()
        event = receiver._tail_events(1)[0]
        self.assertEqual(event["event"], "file_receive_failed")
        self.assertEqual(event["error"], "file_too_large")

    def test_unique_destination_avoids_existing_partial_file(self):
        receiver = self.make_receiver()
        receiver.incoming_dir.mkdir(parents=True)
        (receiver.incoming_dir / "file.txt.part").write_text("partial", encoding="utf-8")

        destination = receiver._unique_destination("file.txt")

        self.assertEqual(destination.name, "file (1).txt")

    def test_event_log_rotates_and_keeps_configured_backups(self):
        receiver = self.make_receiver()
        receiver.event_log_path.write_text("x" * EVENT_LOG_MAX_BYTES, encoding="utf-8")
        for index in range(1, 5):
            receiver.event_log_path.with_name(f"{receiver.event_log_path.name}.{index}").write_text(str(index), encoding="utf-8")

        receiver._write_event("rotation_test", {})

        self.assertTrue(receiver.event_log_path.exists())
        self.assertTrue(receiver.event_log_path.with_name("receiver-events.jsonl.1").exists())
        self.assertTrue(receiver.event_log_path.with_name("receiver-events.jsonl.2").exists())
        self.assertTrue(receiver.event_log_path.with_name("receiver-events.jsonl.3").exists())
        self.assertFalse(receiver.event_log_path.with_name("receiver-events.jsonl.4").exists())

    def test_event_log_normalizes_redacts_and_rate_limits(self):
        receiver = self.make_receiver()

        receiver._write_event("file_serve_error", {"path": "/home/deck/Downloads/private.txt", "error": "boom"})
        receiver._write_event("peer_connect_failed", {"device_id": "phone", "host": "192.0.2.153", "error": "down"})
        receiver._write_event("peer_connect_failed", {"device_id": "phone", "host": "192.0.2.153", "error": "down"})

        events = receiver._tail_events(10)
        first = events[0]
        self.assertEqual(first["event"], "file_serve_error")
        self.assertEqual(first["stage"], "transfer")
        self.assertTrue(first["device_id"].endswith("..."))
        self.assertEqual(first["path"], "<redacted:private.txt>")
        self.assertEqual(len([event for event in events if event["event"] == "peer_connect_failed"]), 1)

    def test_connection_state_transition_is_recorded(self):
        receiver = self.make_receiver()

        receiver.set_connection_state("phone", "connecting", "test_connect")
        receiver.set_connection_state("phone", "connected", "test_ready")

        status = receiver.status()
        self.assertEqual(status["connection_states"]["phone"]["state"], "connected")
        self.assertEqual(status["last_state_transition"]["from"], "connecting")
        self.assertEqual(status["last_state_transition"]["to"], "connected")
        event = receiver._tail_events(1)[0]
        self.assertEqual(event["event"], "connection_state_changed")
        self.assertEqual(event["stage"], "state")
        self.assertEqual(event["device_id"], "phon...")

    @unittest.skipUnless(shutil.which("openssl"), "openssl is required to generate KDE Connect test certificates")
    def test_file_tls_server_streams_file_without_reading_all_bytes(self):
        receiver = self.make_receiver()
        receiver._ensure_certificate()
        source = receiver.state_dir / "large.bin"
        expected = b"a" * (FILE_CHUNK_BYTES + 17)
        source.write_bytes(expected)
        stop_event = mock.Mock()
        stop_event.is_set.return_value = False

        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes must not be used")) as read_bytes:
            port, thread, state = receiver._serve_file_tls(source, stop_event)
            self.assertIsNotNone(port)

            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname="KDEck") as tls:
                    received = bytearray()
                    while True:
                        chunk = tls.recv(65536)
                        if not chunk:
                            break
                        received.extend(chunk)

            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(bytes(received), expected)
        self.assertTrue(state["accepted"])
        self.assertTrue(state["completed"])
        self.assertEqual(state["bytes_sent"], len(expected))
        read_bytes.assert_not_called()

    def test_peer_control_socket_uses_recorded_tcp_port_before_1716(self):
        receiver = self.make_receiver()
        created = []

        def fake_create_connection(address, timeout=0, source_address=None):
            created.append((address, source_address))
            if address[1] == 1739:
                return mock.Mock()
            raise OSError("wrong port")

        with mock.patch("socket.create_connection", side_effect=fake_create_connection):
            sock = receiver._connect_to_peer_control_socket("192.0.2.153", {"tcp_port": 1739}, ["192.0.2.144"])

        self.assertIsNotNone(sock)
        self.assertEqual(created[0], (("192.0.2.153", 1739), ("192.0.2.144", 0)))

    def test_send_share_request_fails_when_phone_never_requests_payload(self):
        receiver = self.make_receiver()
        source = receiver.state_dir / "KDEck.zip"
        source.write_bytes(b"plugin")
        receiver.write_trusted_devices({"phone": {"last_host": "192.0.2.153", "fingerprint": "abc123", "tcp_port": 1739}})
        thread = mock.Mock()
        thread.is_alive.return_value = False
        raw = mock.Mock()
        tls = mock.Mock()
        context = mock.Mock()
        context.wrap_socket.return_value = tls
        identity_bytes = (
            json.dumps({"id": 0, "type": "kdeconnect.identity", "body": {"deviceId": "phone", "deviceName": "Phone", "deviceType": "phone", "protocolVersion": 8}})
            + "\n"
        ).encode()
        tls.recv.return_value = identity_bytes

        with mock.patch.object(receiver, "_serve_file_tls", return_value=(1742, thread, {"accepted": False, "completed": False, "bytes_sent": 0})), \
            mock.patch.object(receiver, "_ensure_certificate", return_value=None), \
            mock.patch.object(receiver, "_network_interfaces", return_value=[{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24}]), \
            mock.patch.object(receiver, "_connect_to_peer_control_socket", return_value=raw), \
            mock.patch("ssl.SSLContext", return_value=context):
            result = receiver.send_share_request_to_peer(str(source), "phone")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "transfer_timeout")

    def test_send_share_request_fails_when_payload_stream_is_incomplete(self):
        receiver = self.make_receiver()
        source = receiver.state_dir / "clip.mp4"
        source.write_bytes(b"1234567890")
        receiver.write_trusted_devices({"phone": {"last_host": "192.0.2.153", "fingerprint": "abc123", "tcp_port": 1739}})
        thread = mock.Mock()
        thread.is_alive.return_value = False
        raw = mock.Mock()
        tls = mock.Mock()
        context = mock.Mock()
        context.wrap_socket.return_value = tls
        identity_bytes = (
            json.dumps({"id": 0, "type": "kdeconnect.identity", "body": {"deviceId": "phone", "deviceName": "Phone", "deviceType": "phone", "protocolVersion": 8}})
            + "\n"
        ).encode()
        tls.recv.return_value = identity_bytes

        with mock.patch.object(receiver, "_serve_file_tls", return_value=(1742, thread, {"accepted": True, "completed": False, "bytes_sent": 5})), \
            mock.patch.object(receiver, "_network_interfaces", return_value=[{"interface": "wlan0", "address": "192.0.2.144", "prefixlen": 24}]), \
            mock.patch.object(receiver, "_connect_to_peer_control_socket", return_value=raw), \
            mock.patch("ssl.SSLContext", return_value=context):
            result = receiver.send_share_request_to_peer(str(source), "phone")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "transfer_incomplete")
        self.assertEqual(result["bytes_sent"], 5)


if __name__ == "__main__":
    unittest.main()

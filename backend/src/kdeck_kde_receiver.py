import hashlib
import ipaddress
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

UDP_PORT = 1716
TCP_PORT_MIN = 1714
TCP_PORT_MAX = 1764
PROTOCOL_VERSION = 8
DEVICE_NAME = "KDEck"
DEVICE_TYPE = "desktop"
PACKET_IDENTITY = "kdeconnect.identity"
PACKET_PAIR = "kdeconnect.pair"
PACKET_CLIPBOARD = "kdeconnect.clipboard"
PACKET_CLIPBOARD_CONNECT = "kdeconnect.clipboard.connect"
PACKET_SHARE_REQUEST = "kdeconnect.share.request"
CAPABILITIES = [
    PACKET_CLIPBOARD,
    PACKET_CLIPBOARD_CONNECT,
    PACKET_SHARE_REQUEST,
]
STARTUP_BROADCAST_DELAYS = (0, 1, 2, 5, 10, 15, 20, 25, 30)
BROADCAST_INTERVAL_SECONDS = 20
RECENT_DISCOVERY_DIRECT_SECONDS = 180
TRUSTED_DEVICE_DIRECT_SECONDS = 7 * 24 * 60 * 60
PEER_CONNECT_COOLDOWN_SECONDS = 30
TRUSTED_PEER_CONNECT_COOLDOWN_SECONDS = 5
MAX_PACKET_BYTES = 64 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MIN_FREE_SPACE_BYTES = 64 * 1024 * 1024
EVENT_LOG_MAX_BYTES = 2 * 1024 * 1024
EVENT_LOG_BACKUPS = 3
IGNORED_INTERFACE_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "vmnet", "mihomo", "clash")

# Bluetooth constants: use numeric fallbacks since PyBluez (which monkey-patches
# socket.AF_BLUETOOTH / BTPROTO_RFCOMM via import bluetooth) may not be
# available in Deckys embedded Python.
BT_AF = getattr(socket, "AF_BLUETOOTH", None) or 31
BT_BTPROTO = getattr(socket, "BTPROTO_RFCOMM", None) or 3
ANDROID_DEVICE_TYPES = {"phone", "tablet"}


def interface_path_type(name: str) -> str:
    """Classify a network interface name into a path type."""
    clean = (name or "").lower()
    if clean.startswith(("wlan", "wl", "en", "eth")):
        return "lan"
    if clean.startswith("et_"):
        return "easytier"
    if clean.startswith("zt"):
        return "zerotier"
    if clean.startswith(("tailscale", "tailscale0")):
        return "tailscale"
    if clean.startswith(("tun", "tap", "ppp")):
        return "vpn"
    return "other"


INTERFACE_PRIORITIES = {
    "lan": 100,
    "easytier": 80,
    "zerotier": 70,
    "tailscale": 60,
    "vpn": 40,
    "other": 10,
}


def interface_priority(name: str) -> int:
    """Return a priority score for a network interface."""
    return INTERFACE_PRIORITIES.get(interface_path_type(name), 10)


def is_usable_ipv4(address: Optional[str]) -> bool:
    """Return True if the IPv4 address is usable for KDE Connect discovery."""
    if not address:
        return False
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    return ip not in ipaddress.ip_network("198.18.0.0/15")


def is_ignored_interface(name: str) -> bool:
    """Return True if the interface should be excluded from KDE Connect."""
    clean = (name or "").lower()
    return clean.startswith(IGNORED_INTERFACE_PREFIXES)


class KDEckKdeReceiver:
    def __init__(
        self,
        state_dir: Path,
        on_clipboard: Callable[[str, Optional[str]], None],
        incoming_dir: Path,
        logger: Any = None,
    ):
        self.state_dir = state_dir
        self.on_clipboard = on_clipboard
        self.incoming_dir = incoming_dir
        self.logger = logger
        self.device_id_path = state_dir / "device-id"
        self.cert_path = state_dir / "kdeck.crt"
        self.key_path = state_dir / "kdeck.key"
        self.trusted_path = state_dir / "trusted-devices.json"
        self.event_log_path = state_dir / "receiver-events.jsonl"
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.connection_threads: list[threading.Thread] = []
        self.tcp_socket: Optional[socket.socket] = None
        self.udp_socket: Optional[socket.socket] = None
        self.bt_socket: Optional[socket.socket] = None
        self._bt_helper_proc: Optional[subprocess.Popen] = None
        self.tcp_port: Optional[int] = None
        self.peer_connect_attempts: dict[str, float] = {}
        self.state_lock = threading.Lock()
        self.data_lock = threading.Lock()
        self.event_buffer: list[dict[str, Any]] = []
        self.event_buffer_lock = threading.Lock()
        self.diagnostics: dict[str, Any] = {
            "udp_working": False,
            "tcp_working": False,
            "bt_working": False,
            "bt_error": None,
            "udp_error": None,
            "tcp_error": None,
            "last_error": None,
            "last_discovery_sent": None,
            "last_discovery_received": None,
            "last_connect_attempt": None,
            "last_connect_error": None,
            "last_tcp_success": None,
            "last_tls_success": None,
            "last_tls_error": None,
            "last_pair": None,
            "pending_pair": None,
            "last_reannounce_targets": None,
            "last_payload_error": None,
            "last_clipboard": None,
            "last_file": None,
            "interfaces": [],
            "discovered_devices": {},
        }
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.device_id = self._device_id()

    def start(self) -> dict[str, Any]:
        if self.threads:
            return self.status()
        try:
            self._ensure_certificate()
        except Exception as exc:
            self._log("KDE receiver certificate init failed: %s", exc)
            self._set_diagnostic("last_error", {"stage": "certificate", "message": str(exc), "time": int(time.time())})
            self._write_event("certificate_init_failed", {"error": str(exc)})
            return {"ok": False, "running": False, "error": {"code": "certificate_init_failed", "message": str(exc)}}
        self.stop_event.clear()
        with self.data_lock:
            self.tcp_port = None
        self._write_event("receiver_starting", {"udp_port": UDP_PORT, "tcp_port_range": f"{TCP_PORT_MIN}-{TCP_PORT_MAX}"})
        for name, target in (
            ("KDEckKdeTcpServer", self._tcp_server),
            ("KDEckKdeUdpServer", self._udp_server),
        ):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)
        bt_thread = threading.Thread(target=self._bluetooth_server, name="KDEckKdeBtServer", daemon=True)
        bt_thread.start()
        self.threads.append(bt_thread)
        self._wait_for_listener_state(timeout=1.0)
        thread = threading.Thread(target=self._broadcast_loop, name="KDEckKdeBroadcaster", daemon=True)
        thread.start()
        self.threads.append(thread)
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        for sock in (self.tcp_socket, self.udp_socket, self.bt_socket):
            try:
                if sock:
                    sock.close()
            except OSError:
                pass
        self.tcp_socket = None
        self.udp_socket = None
        if self._bt_helper_proc is not None:
            try:
                self._bt_helper_proc.terminate()
                self._bt_helper_proc.wait(timeout=3)
            except Exception:
                pass
            try:
                self._bt_helper_proc.kill()
            except Exception:
                pass
            self._bt_helper_proc = None
        self.bt_socket = None
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1.5)
        self.threads = [thread for thread in self.threads if thread.is_alive()]
        with self.data_lock:
            self.connection_threads[:] = [t for t in self.connection_threads if t.is_alive()]
            for thread in self.connection_threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            self.connection_threads.clear()
            self.tcp_port = None
        self._set_diagnostic("udp_working", False)
        self._set_diagnostic("tcp_working", False)
        self._set_diagnostic("pending_pair", None)
        self._flush_event_buffer()
        self._write_event("receiver_stopped", {})
        return {"ok": True, "running": False}

    def _tcp_port_value(self) -> Optional[int]:
        with self.data_lock:
            return self.tcp_port

    def _start_connection_thread(self, target: Callable, name: str) -> threading.Thread:
        """Track a daemon thread that will be joined on stop()."""
        thread = threading.Thread(target=target, name=name, daemon=True)
        with self.data_lock:
            self.connection_threads[:] = [t for t in self.connection_threads if t.is_alive()]
            self.connection_threads.append(thread)
        thread.start()
        return thread

    def reannounce_trusted_devices(self, reason: str = "manual_trusted_reannounce") -> dict[str, Any]:
        with self.data_lock:
            port = self.tcp_port
        if not port:
            self._write_event("trusted_reannounce_skipped", {"reason": reason, "skip_reason": "tcp_not_ready"})
            return {"ok": False, "reason": "tcp_not_ready"}
        self._broadcast_identity(reason=reason)
        return {"ok": True, "reason": reason}

    def status(self) -> dict[str, Any]:
        trusted = self._trusted_devices()
        valid_trusted = {
            device_id: data
            for device_id, data in trusted.items()
            if isinstance(data, dict) and (data.get("fingerprint") or data.get("trust_mode") == "device_id")
        }
        with self.state_lock:
            diagnostics = json.loads(json.dumps(self.diagnostics, ensure_ascii=False))
        discovered = list(diagnostics.get("discovered_devices", {}).values())
        discovered.sort(key=lambda item: item.get("last_seen", 0), reverse=True)
        running = bool(self.threads) and bool(diagnostics.get("udp_working")) and bool(diagnostics.get("tcp_working"))
        return {
            "ok": True,
            "running": running,
            "device_name": DEVICE_NAME,
            "device_id": self.device_id,
            "tcp_port": self._tcp_port_value(),
            "tcp_port_range": f"{TCP_PORT_MIN}-{TCP_PORT_MAX}",
            "udp_port": UDP_PORT,
            "udp_working": diagnostics.get("udp_working"),
            "tcp_working": diagnostics.get("tcp_working"),
            "bt_working": diagnostics.get("bt_working"),
            "bt_error": diagnostics.get("bt_error"),
            "udp_error": diagnostics.get("udp_error"),
            "tcp_error": diagnostics.get("tcp_error"),
            "current_ips": [item["address"] for item in diagnostics.get("interfaces", []) if item.get("address")],
            "interfaces": diagnostics.get("interfaces", []),
            "discovered_devices": discovered,
            "last_error": diagnostics.get("last_error"),
            "last_discovery_sent": diagnostics.get("last_discovery_sent"),
            "last_discovery_received": diagnostics.get("last_discovery_received"),
            "last_connect_attempt": diagnostics.get("last_connect_attempt"),
            "last_connect_error": diagnostics.get("last_connect_error"),
            "last_tcp_success": diagnostics.get("last_tcp_success"),
            "last_tls_success": diagnostics.get("last_tls_success"),
            "last_tls_error": diagnostics.get("last_tls_error"),
            "last_pair": diagnostics.get("last_pair"),
            "pending_pair": diagnostics.get("pending_pair"),
            "last_reannounce_targets": diagnostics.get("last_reannounce_targets"),
            "last_payload_error": diagnostics.get("last_payload_error"),
            "last_clipboard": diagnostics.get("last_clipboard"),
            "last_file": diagnostics.get("last_file"),
            "paired": bool(valid_trusted),
            "trusted_device": next((item for item in discovered if item.get("device_id") in valid_trusted), None),
            "trusted_devices": valid_trusted,
            "legacy_trusted_devices": [device_id for device_id in trusted if device_id not in valid_trusted],
            "last_events": self._tail_events(20),
        }

    def _bluetooth_server(self) -> None:
        bt_channel = 22
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdeck_bt_helper.py")

        if not os.path.exists(helper) or shutil.which("sdptool") is None:
            self._write_event("bluetooth_init_failed", {"error": "helper missing or sdptool not installed"})
            self._set_diagnostic("bt_working", False)
            return

        # The helper runs under system Python (which has PyBluez) and forwards
        # Bluetooth RFCOMM connections to a local TCP port inside the Deck.
        bt_tcp_port = self._bind_available_tcp_port(socket.socket(socket.AF_INET, socket.SOCK_STREAM), port_low=1730, port_mid=1740)

        helper_proc = subprocess.Popen(
            [sys.executable or "/usr/bin/python", helper, str(bt_tcp_port)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self._bt_helper_proc = helper_proc

        # Read one line to confirm startup.
        line = helper_proc.stdout.readline() if helper_proc.stdout else ""
        if "BT listening" not in line:
            self._write_event("bluetooth_init_failed", {"error": f"helper startup failed: {line.strip()}"})
            self._set_diagnostic("bt_working", False)
            return

        self._set_diagnostic("bt_working", True)
        self._set_diagnostic("bt_error", None)
        self._write_event("bluetooth_listening", {"channel": bt_channel})

        # Accept connections on the local TCP bridge port.
        tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server.bind(("127.0.0.1", bt_tcp_port))
        tcp_server.listen(1)
        tcp_server.settimeout(3)

        while not self.stop_event.is_set():
            try:
                conn, addr = tcp_server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._start_connection_thread(
                lambda c=conn, a=addr: self._handle_incoming_bt(c, str(addr)),
                f"KDEckBtHandler-{addr}",
            )

    def _handle_incoming_bt(self, conn: socket.socket, addr: str) -> None:
        bt_id = str(addr).replace(":", "")[:16]
        try:
            self._write_event("incoming_bt_connected", {"addr": str(addr)})
            identity = self._read_plain_packet(conn)
            body = identity.get("body") or {}
            peer_id = body.get("deviceId")
            if identity.get("type") != PACKET_IDENTITY or not peer_id:
                self._write_event("incoming_bt_identity_invalid", {"addr": str(addr), "packet_type": identity.get("type")})
                conn.close()
                return
            self._write_event("incoming_bt_identity_received", {"addr": str(addr), "device_id": peer_id, "device_name": body.get("deviceName")})
            # TLS: Bluetooth uses client-side TLS (same as incoming TCP)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            self._write_event("incoming_bt_tls_start", {"addr": str(addr), "device_id": peer_id})
            tls = context.wrap_socket(conn, server_hostname=peer_id, do_handshake_on_connect=True)
            self._write_event("incoming_bt_tls_done", {"addr": str(addr), "device_id": peer_id})
            self._after_tls(tls, peer_id, peer_host=bt_id, send_identity_first=True)
        except Exception as exc:
            self._log("KDE receiver BT connection failed from %s: %s", addr, exc)
            error = {"stage": "incoming_bt", "addr": str(addr), "error_type": type(exc).__name__, "message": str(exc), "time": int(time.time())}
            self._set_diagnostic("last_error", error)
            self._write_event("incoming_bt_failed", error)
            try:
                conn.close()
            except OSError:
                pass

    def _tcp_server(self) -> None:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_port = self._bind_available_tcp_port(server)
            server.listen(5)
            server.settimeout(1)
            self.tcp_socket = server
            with self.data_lock:
                self.tcp_port = tcp_port
        except OSError as exc:
            self._log("KDE receiver TCP start failed: %s", exc)
            error = {"message": str(exc), "time": int(time.time()), "port_range": f"{TCP_PORT_MIN}-{TCP_PORT_MAX}"}
            self._set_diagnostic("tcp_working", False)
            self._set_diagnostic("tcp_error", error)
            self._set_diagnostic("last_error", {"stage": "tcp_bind", **error})
            self._write_event("tcp_bind_failed", error)
            return
        self._set_diagnostic("tcp_working", True)
        self._set_diagnostic("tcp_error", None)
        self._write_event("tcp_listening", {"host": "0.0.0.0", "port": tcp_port})

        while not self.stop_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._start_connection_thread(lambda c=conn, a=addr: self._handle_incoming_tcp(c, a), f"KDEckTcpHandler-{addr[0]}:{addr[1]}")

    def _udp_server(self) -> None:
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind(("0.0.0.0", UDP_PORT))
            udp.settimeout(1)
            self.udp_socket = udp
        except OSError as exc:
            self._log("KDE receiver UDP start failed: %s", exc)
            error = {"message": str(exc), "time": int(time.time()), "port": UDP_PORT}
            self._set_diagnostic("udp_working", False)
            self._set_diagnostic("udp_error", error)
            self._set_diagnostic("last_error", {"stage": "udp_bind", **error})
            self._write_event("udp_bind_failed", error)
            return
        self._set_diagnostic("udp_working", True)
        self._set_diagnostic("udp_error", None)
        self._write_event("udp_listening", {"host": "0.0.0.0", "port": UDP_PORT})

        while not self.stop_event.is_set():
            try:
                data, addr = udp.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            packet = self._decode_packet(data, context={"stage": "udp_discovery", "host": addr[0], "port": addr[1]})
            if packet.get("type") != PACKET_IDENTITY:
                continue
            body = packet.get("body") or {}
            device_id = body.get("deviceId")
            tcp_port = int(body.get("tcpPort") or 0)
            if not device_id or device_id == self.device_id or not (1714 <= tcp_port <= 1764):
                continue
            if self._is_local_host(addr[0]):
                self._write_event(
                    "discovery_ignored",
                    {"host": addr[0], "device_id": device_id, "device_name": body.get("deviceName"), "reason": "local_host"},
                )
                continue
            self._record_discovery_received(addr, body)
            reply_ports = self._identity_reply_ports(addr[1], body)
            reply_strategy = "source_port_only" if len(reply_ports) == 1 else "source_port_and_1716"
            for reply_port in reply_ports:
                self._send_udp_identity(
                    addr[0],
                    reply_port,
                    target_device_id=device_id,
                    target_protocol_version=body.get("protocolVersion"),
                    reason="discovery_reply",
                    peer_identity=body,
                    reply_strategy=reply_strategy,
                )
            if self._should_connect_to_peer(addr[0], tcp_port, body):
                self._start_connection_thread(
                    lambda h=addr[0], p=tcp_port, b=body: self._connect_to_peer(h, p, b),
                    f"KDEckPeerConnect-{addr[0]}:{tcp_port}",
                )

    def _broadcast_loop(self) -> None:
        started_at = time.monotonic()
        for delay in STARTUP_BROADCAST_DELAYS:
            if self.stop_event.wait(max(0, started_at + delay - time.monotonic())):
                return
            if not self._tcp_port_value():
                continue
            self._broadcast_identity(reason=f"startup_{delay}s")
        while not self.stop_event.wait(BROADCAST_INTERVAL_SECONDS):
            if not self._tcp_port_value():
                continue
            self._broadcast_identity(reason="interval")

    def _broadcast_identity(self, reason: str = "manual") -> None:
        tcp_port = self._tcp_port_value()
        packet = self._identity_packet()
        packet["body"]["tcpPort"] = tcp_port
        payload = self._encode_packet(packet)
        interfaces = self._network_interfaces()
        targets = self._broadcast_targets(interfaces)
        direct_targets = self._recent_discovery_targets(interfaces)
        direct_targets = self._merge_direct_targets(direct_targets, self._trusted_direct_targets(interfaces))
        sent = 0
        failures = []
        for source_ip, address in targets:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    udp.settimeout(2)
                    if source_ip:
                        udp.bind((source_ip, 0))
                    udp.sendto(payload, (address, UDP_PORT))
                    sent += 1
            except OSError as exc:
                failures.append({"source": source_ip, "target": address, "error": str(exc)})
        for source_ip, address, port in direct_targets:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    udp.settimeout(2)
                    if source_ip:
                        udp.bind((source_ip, 0))
                    udp.sendto(payload, (address, port))
                    sent += 1
            except OSError as exc:
                failures.append({"source": source_ip, "target": address, "port": port, "error": str(exc)})
        details = {
            "reason": reason,
            "sent": sent,
            "failures": failures[:5],
            "targets": [{"source": source, "target": target} for source, target in targets],
            "direct_targets": [
                {"source": source, "target": target, "port": port} for source, target, port in direct_targets
            ],
            "paths": [
                {"interface": item.get("interface"), "address": item.get("address"), "path_type": item.get("path_type")}
                for item in interfaces
            ],
        }
        self._set_diagnostic("interfaces", interfaces)
        self._set_diagnostic("last_discovery_sent", {"time": int(time.time()), **details})
        self._set_diagnostic("last_reannounce_targets", {"time": int(time.time()), "reason": reason, "direct_targets": details["direct_targets"]})
        self._write_event("discovery_sent", details)

    def _send_udp_identity(
        self,
        host: str,
        port: int,
        target_device_id: Optional[str] = None,
        target_protocol_version: Any = None,
        reason: str = "manual",
        peer_identity: Optional[dict[str, Any]] = None,
        reply_strategy: Optional[str] = None,
    ) -> None:
        tcp_port = self._tcp_port_value()
        if not tcp_port:
            self._write_event("identity_reply_skipped", {"host": host, "reason": "tcp_not_ready"})
            return
        packet = self._identity_packet(target_device_id=target_device_id, target_protocol_version=target_protocol_version)
        packet["body"]["tcpPort"] = tcp_port
        payload = self._encode_packet(packet)
        interfaces = self._network_interfaces()
        source_ips = self._source_ips_for_host(host, interfaces)
        sent = 0
        failures = []
        sent_sources = []
        for source_ip in source_ips:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    udp.settimeout(2)
                    if source_ip:
                        udp.bind((source_ip, 0))
                    udp.sendto(payload, (host, port))
                    sent += 1
                    sent_sources.append(source_ip)
            except OSError as exc:
                failures.append({"source": source_ip, "target": host, "error": str(exc)})
        self._write_event(
            "identity_reply_sent",
            {
                "host": host,
                "port": port,
                "reason": reason,
                "reply_strategy": reply_strategy,
                "target_device_id": target_device_id,
                "peer_device_type": (peer_identity or {}).get("deviceType"),
                "peer_protocol_version": (peer_identity or {}).get("protocolVersion"),
                "sent": sent,
                "sources": sent_sources,
                "failures": failures[:5],
            },
        )

    def _handle_incoming_tcp(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        try:
            self._write_event("incoming_tcp_connected", {"host": addr[0], "port": addr[1]})
            self._set_diagnostic("last_tcp_success", {"host": addr[0], "port": addr[1], "stage": "incoming", "time": int(time.time())})
            if self._is_local_host(addr[0]):
                self._write_event("incoming_tcp_rejected", {"host": addr[0], "port": addr[1], "reason": "local_host"})
                conn.close()
                return
            identity = self._read_plain_packet(conn)
            body = identity.get("body") or {}
            peer_id = body.get("deviceId")
            if identity.get("type") != PACKET_IDENTITY or not peer_id:
                self._write_event("incoming_plain_identity_invalid", {"host": addr[0], "port": addr[1], "packet_type": identity.get("type")})
                conn.close()
                return
            self._write_event(
                "incoming_plain_identity_received",
                {
                    "host": addr[0],
                    "port": addr[1],
                    "device_id": peer_id,
                    "device_name": body.get("deviceName"),
                    "device_type": body.get("deviceType"),
                    "protocol_version": body.get("protocolVersion"),
                    "tcp_port": body.get("tcpPort"),
                },
            )
            target = body.get("targetDeviceId")
            if target and target != self.device_id:
                self._write_event("incoming_tcp_rejected", {"host": addr[0], "port": addr[1], "device_id": peer_id, "target_device_id": target})
                conn.close()
                return
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            tls_started = time.monotonic()
            self._write_event("incoming_tls_handshake_start", {"host": addr[0], "port": addr[1], "device_id": peer_id, "tls_mode": "client"})
            tls = context.wrap_socket(conn, server_hostname=peer_id, do_handshake_on_connect=True)
            self._set_diagnostic("last_tls_success", {"host": addr[0], "port": addr[1], "device_id": peer_id, "stage": "incoming", "time": int(time.time())})
            self._write_event(
                "incoming_tls_handshake_done",
                {"host": addr[0], "port": addr[1], "device_id": peer_id, "tls_mode": "client", "duration_ms": int((time.monotonic() - tls_started) * 1000)},
            )
            self._after_tls(tls, peer_id, peer_host=addr[0], send_identity_first=True)
        except Exception as exc:
            self._log("KDE receiver incoming connection failed from %s: %s", addr, exc)
            error = {"stage": "incoming_tcp", "host": addr[0], "port": addr[1], "error_type": type(exc).__name__, "message": str(exc), "time": int(time.time())}
            self._set_diagnostic("last_error", error)
            self._set_diagnostic("last_tls_error", error)
            self._write_event("incoming_tcp_failed", error)
            try:
                conn.close()
            except OSError:
                pass

    def _connect_to_peer(self, host: str, port: int, peer_identity: dict[str, Any]) -> None:
        peer_id = peer_identity.get("deviceId")
        if not peer_id:
            return
        self._set_diagnostic(
            "last_connect_attempt",
            {
                "host": host,
                "port": port,
                "device_id": peer_id,
                "device_type": peer_identity.get("deviceType"),
                "protocol_version": peer_identity.get("protocolVersion"),
                "time": int(time.time()),
            },
        )
        self._write_event(
            "peer_connect_attempt",
            {
                "host": host,
                "port": port,
                "device_id": peer_id,
                "device_name": peer_identity.get("deviceName"),
                "device_type": peer_identity.get("deviceType"),
                "protocol_version": peer_identity.get("protocolVersion"),
            },
        )
        interfaces = self._network_interfaces()
        source_ips = self._source_ips_for_host(host, interfaces)
        source_ip = source_ips[0] if source_ips else None
        device_type = str(peer_identity.get("deviceType") or "").lower()
        tls_mode = self._peer_tls_mode(device_type)
        use_tls_client = tls_mode == "client"
        try:
            tcp_started = time.monotonic()
            raw = socket.create_connection((host, port), timeout=5, source_address=(source_ip, 0) if source_ip else None)
            self._set_diagnostic("last_tcp_success", {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "time": int(time.time())})
            self._write_event(
                "peer_tcp_connected",
                {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "duration_ms": int((time.monotonic() - tcp_started) * 1000)},
            )
            hello = self._identity_packet(target_device_id=peer_id, target_protocol_version=peer_identity.get("protocolVersion"))
            raw.sendall(self._encode_packet(hello))
            self._write_event(
                "peer_plain_identity_sent",
                {
                    "host": host,
                    "port": port,
                    "device_id": peer_id,
                    "source_ip": source_ip,
                    "target_protocol_version": peer_identity.get("protocolVersion"),
                    "tls_mode": tls_mode,
                },
            )
            if use_tls_client:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            else:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            tls_started = time.monotonic()
            self._write_event(
                "peer_tls_handshake_start",
                {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "tls_mode": tls_mode, "device_type": device_type},
            )
            tls = context.wrap_socket(
                raw,
                server_hostname=peer_id if use_tls_client else None,
                server_side=not use_tls_client,
                do_handshake_on_connect=True,
            )
            self._set_diagnostic("last_tls_success", {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "tls_mode": tls_mode, "stage": "peer_connect", "time": int(time.time())})
            self._write_event(
                "peer_tls_handshake_done",
                {
                    "host": host,
                    "port": port,
                    "device_id": peer_id,
                    "source_ip": source_ip,
                    "tls_mode": tls_mode,
                    "duration_ms": int((time.monotonic() - tls_started) * 1000),
                },
            )
            self._after_tls(tls, peer_id, peer_host=host, send_identity_first=True)
        except Exception as exc:
            self._log("KDE receiver peer connection failed %s:%s: %s", host, port, exc)
            error = {
                "host": host,
                "port": port,
                "device_id": peer_id,
                "device_type": peer_identity.get("deviceType"),
                "source_ip": source_ip,
                "tls_mode": tls_mode,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "time": int(time.time()),
            }
            self._set_diagnostic("last_connect_error", error)
            self._set_diagnostic("last_error", {"stage": "peer_connect", **error})
            self._set_diagnostic("last_tls_error", error)
            self._write_event("peer_connect_failed", error)
            if device_type in ANDROID_DEVICE_TYPES:
                self._write_event(
                    "identity_reply_skipped",
                    {"host": host, "port": UDP_PORT, "target_device_id": peer_id, "reason": "android_failure_fallback_suppressed"},
                )
                return
            self._send_udp_identity(
                host,
                UDP_PORT,
                target_device_id=peer_id,
                target_protocol_version=peer_identity.get("protocolVersion"),
                reason="peer_connect_failed_fallback",
                peer_identity=peer_identity,
            )

    def _after_tls(self, tls: ssl.SSLSocket, peer_id: str, peer_host: str, send_identity_first: bool) -> None:
        tls.settimeout(60)
        fingerprint = self._peer_fingerprint(tls)
        if send_identity_first:
            tls.sendall(self._encode_packet(self._identity_packet()))
            self._write_event("secure_identity_sent", {"host": peer_host, "device_id": peer_id})
        secure_identity = self._read_tls_packet(tls)
        if secure_identity.get("type") == PACKET_IDENTITY:
            secure_body = secure_identity.get("body") or {}
            peer_id = secure_body.get("deviceId") or peer_id
            self._remember_trusted_device_metadata(peer_id, peer_host, secure_body, connected=True)
            self._write_event(
                "secure_identity_received",
                {
                    "host": peer_host,
                    "device_id": peer_id,
                    "device_name": secure_body.get("deviceName"),
                    "device_type": secure_body.get("deviceType"),
                    "protocol_version": secure_body.get("protocolVersion"),
                    "tcp_port": secure_body.get("tcpPort"),
                },
            )
        else:
            self._write_event("secure_identity_missing", {"host": peer_host, "device_id": peer_id, "packet_type": secure_identity.get("type")})
        self._packet_loop(tls, peer_id, peer_host, fingerprint)

    def _packet_loop(self, tls: ssl.SSLSocket, peer_id: str, peer_host: str, fingerprint: Optional[str]) -> None:
        buffer = b""
        while not self.stop_event.is_set():
            try:
                chunk = tls.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > MAX_PACKET_BYTES and b"\n" not in buffer:
                self._write_event(
                    "packet_rejected",
                    {
                        "device_id": peer_id,
                        "host": peer_host,
                        "reason": "packet_too_large",
                        "size": len(buffer),
                        "max_size": MAX_PACKET_BYTES,
                    },
                )
                buffer = b""
                continue
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if len(line) + 1 > MAX_PACKET_BYTES:
                    self._write_event(
                        "packet_rejected",
                        {
                            "device_id": peer_id,
                            "host": peer_host,
                            "reason": "packet_too_large",
                            "size": len(line) + 1,
                            "max_size": MAX_PACKET_BYTES,
                        },
                    )
                    continue
                packet = self._decode_packet(line + b"\n", context={"stage": "tls_packet", "device_id": peer_id, "host": peer_host})
                self._handle_packet(tls, peer_id, peer_host, packet, fingerprint)

    def _handle_packet(
        self,
        tls: ssl.SSLSocket,
        peer_id: str,
        peer_host: str,
        packet: dict[str, Any],
        fingerprint: Optional[str],
    ) -> None:
        packet_type = packet.get("type")
        body = packet.get("body") or {}
        if packet_type == PACKET_PAIR:
            if body.get("pair") is False:
                trusted = self._trusted_devices()
                trusted.pop(peer_id, None)
                self._write_trusted_devices(trusted)
                self._set_diagnostic("last_pair", {"device_id": peer_id, "paired": False, "time": int(time.time())})
                self._write_event("unpaired", {"device_id": peer_id})
                self._set_diagnostic("pending_pair", None)
                return
            if self._is_trusted_device(peer_id, fingerprint):
                self._accept_pair_inner(tls, peer_id, peer_host, fingerprint)
                return
            self._accept_pair_inner(tls, peer_id, peer_host, fingerprint)
            return
        if not self._is_trusted_device(peer_id, fingerprint):
            self._write_event("untrusted_packet_rejected", {"device_id": peer_id, "packet_type": packet_type})
            return
        if packet_type in (PACKET_CLIPBOARD, PACKET_CLIPBOARD_CONNECT):
            content = str(body.get("content") or "")
            if content:
                self.on_clipboard(content, peer_id)
                self._set_diagnostic("last_clipboard", {"device_id": peer_id, "length": len(content), "time": int(time.time())})
                self._write_event("clipboard_received", {"device_id": peer_id, "length": len(content)})
            return
        if packet_type == PACKET_SHARE_REQUEST:
            self._receive_share_request(peer_id, peer_host, packet)

    def _accept_pair_inner(
        self,
        tls: ssl.SSLSocket,
        peer_id: str,
        peer_host: str,
        fingerprint: Optional[str],
    ) -> None:
        trusted = self._trusted_devices()
        existing = trusted.get(peer_id) if isinstance(trusted.get(peer_id), dict) else {}
        trust_mode = "fingerprint" if fingerprint else "device_id"
        trusted[peer_id] = {
            **existing,
            "paired_at": int(time.time()),
            "fingerprint": fingerprint,
            "trust_mode": trust_mode,
            "last_host": peer_host,
            "last_connected": int(time.time()),
        }
        self._write_trusted_devices(trusted)
        tls.sendall(self._encode_packet({"type": PACKET_PAIR, "body": {"pair": True}}))
        self._log("KDE receiver paired with %s", peer_id)
        self._set_diagnostic("last_pair", {"device_id": peer_id, "paired": True, "time": int(time.time()), "trust_mode": trust_mode})
        self._write_event(
            "paired",
            {
                "device_id": peer_id,
                "fingerprint": fingerprint,
                "trust_mode": trust_mode,
                "weak_trust_fallback": fingerprint is None,
            },
        )

    def _identity_packet(self, target_device_id: Optional[str] = None, target_protocol_version: Any = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "deviceId": self.device_id,
            "deviceName": DEVICE_NAME,
            "deviceType": DEVICE_TYPE,
            "protocolVersion": PROTOCOL_VERSION,
            "incomingCapabilities": CAPABILITIES,
            "outgoingCapabilities": [],
        }
        tcp_port = self._tcp_port_value()
        if tcp_port:
            body["tcpPort"] = tcp_port
        if target_device_id:
            body["targetDeviceId"] = target_device_id
        if target_protocol_version:
            body["targetProtocolVersion"] = target_protocol_version
        return {"type": PACKET_IDENTITY, "body": body}

    def _should_connect_to_peer(self, host: str, port: int, peer_identity: dict[str, Any]) -> bool:
        device_id = peer_identity.get("deviceId")
        if not device_id:
            return False
        key = f"{device_id}@{host}:{port}"
        now = time.monotonic()
        cooldown = TRUSTED_PEER_CONNECT_COOLDOWN_SECONDS if self._trusted_devices().get(device_id) else PEER_CONNECT_COOLDOWN_SECONDS
        with self.data_lock:
            previous = self.peer_connect_attempts.get(key)
            if previous is not None and now - previous < cooldown:
                skip = True
            else:
                self.peer_connect_attempts[key] = now
                skip = False
        if skip:
            self._write_event("peer_connect_skipped", {"host": host, "port": port, "device_id": device_id, "reason": "cooldown", "cooldown_seconds": cooldown})
            return False
        return True

    def _identity_reply_ports(self, source_port: int, peer_identity: dict[str, Any]) -> list[int]:
        device_type = str(peer_identity.get("deviceType") or "").lower()
        if device_type in ANDROID_DEVICE_TYPES:
            return [source_port]
        reply_ports = [source_port]
        if UDP_PORT not in reply_ports:
            reply_ports.append(UDP_PORT)
        return reply_ports

    def _peer_tls_mode(self, device_type: str) -> str:
        # Android 0.3.1 实测 TLS client 模式超时；0.3.2 回到 0.2.0 的主动连接 server 模式。
        return "server"

    def _device_id(self) -> str:
        if self.device_id_path.exists():
            value = self.device_id_path.read_text(encoding="utf-8").strip()
            if 32 <= len(value) <= 38:
                return value
        value = secrets.token_hex(16)
        self.device_id_path.write_text(value, encoding="utf-8")
        return value

    def _ensure_certificate(self) -> None:
        if self.cert_path.exists() and self.key_path.exists():
            self._write_event("certificate_ready", {"cert": str(self.cert_path), "existing": True})
            return
        openssl = shutil.which("openssl")
        if not openssl:
            raise RuntimeError("找不到 openssl，无法生成 KDEck KDE Connect 证书。")
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/deck",
            "USER": "deck",
            "LOGNAME": "deck",
            "LANG": "en_US.UTF-8",
        }
        result = subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(self.key_path),
                "-out",
                str(self.cert_path),
                "-days",
                "3650",
                "-subj",
                f"/CN={self.device_id}",
            ],
            env=env,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "openssl req failed").strip())
        os.chmod(self.key_path, 0o600)
        self._write_event("certificate_ready", {"cert": str(self.cert_path), "existing": False})

    def _read_plain_packet(self, conn: socket.socket) -> dict[str, Any]:
        conn.settimeout(5)
        data = b""
        oversized = False
        while b"\n" not in data and len(data) <= MAX_PACKET_BYTES:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            oversized = len(data) > MAX_PACKET_BYTES
        if oversized:
            self._write_event("packet_rejected", {"stage": "plain_identity", "reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES})
            return {}
        return self._decode_packet(data, context={"stage": "plain_identity"})

    def _read_tls_packet(self, tls: ssl.SSLSocket) -> dict[str, Any]:
        data = b""
        oversized = False
        while b"\n" not in data and len(data) <= MAX_PACKET_BYTES:
            chunk = tls.recv(4096)
            if not chunk:
                break
            data += chunk
            oversized = len(data) > MAX_PACKET_BYTES
        if oversized:
            self._write_event("packet_rejected", {"stage": "secure_identity", "reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES})
            return {}
        return self._decode_packet(data, context={"stage": "secure_identity"})

    def _encode_packet(self, packet: dict[str, Any]) -> bytes:
        payload = {
            "id": int(time.time() * 1000),
            "type": packet["type"],
            "body": packet.get("body") or {},
        }
        return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

    def _decode_packet(self, data: bytes, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if len(data) > MAX_PACKET_BYTES:
            self._write_event("packet_rejected", {"reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES, **(context or {})})
            return {}
        try:
            packet = json.loads(data.decode("utf-8", errors="replace").strip())
        except json.JSONDecodeError:
            self._write_event("packet_decode_failed", {"reason": "invalid_json", "size": len(data), **(context or {})})
            return {}
        if not isinstance(packet, dict):
            self._write_event("packet_decode_failed", {"reason": "not_object", "size": len(data), **(context or {})})
            return {}
        if "type" in packet and "body" in packet and not isinstance(packet.get("body"), dict):
            self._write_event("packet_decode_failed", {"reason": "body_not_object", "packet_type": packet.get("type"), **(context or {})})
            return {}
        return packet

    def _receive_share_request(self, peer_id: str, peer_host: str, packet: dict[str, Any]) -> None:
        body = packet.get("body") or {}
        transfer_info = packet.get("payloadTransferInfo") or {}
        payload_size = self._packet_payload_size(packet)
        if payload_size is None:
            self._write_event("share_ignored", {"device_id": peer_id, "reason": "invalid_payload_size", "payload_size": packet.get("payloadSize")})
            return
        if body.get("text"):
            text = str(body.get("text") or "")
            self.on_clipboard(text, peer_id)
            self._write_event("shared_text_received", {"device_id": peer_id, "length": len(text)})
            return
        if not transfer_info or "port" not in transfer_info:
            self._write_event("share_ignored", {"device_id": peer_id, "reason": "missing_payload"})
            return

        filename = self._safe_filename(str(body.get("filename") or f"kdeck-{int(time.time())}"))
        destination = self._unique_destination(filename)
        partial_destination = destination.with_name(f"{destination.name}.part")
        port = self._payload_port(transfer_info)
        if port is None:
            self._write_event("share_ignored", {"device_id": peer_id, "file": filename, "reason": "invalid_payload_port", "port": transfer_info.get("port")})
            return
        if payload_size > MAX_FILE_BYTES:
            self._record_file_failure(peer_id, filename, "file_too_large", expected=payload_size, max_size=MAX_FILE_BYTES)
            return
        if not self._has_enough_space(payload_size):
            self._record_file_failure(peer_id, filename, "not_enough_space", expected=payload_size, min_free_space=MIN_FREE_SPACE_BYTES)
            return

        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            raw = socket.create_connection((peer_host, port), timeout=15)
            with context.wrap_socket(raw, server_hostname=peer_id) as tls:
                payload_fingerprint = self._peer_fingerprint(tls)
                if not self._is_trusted_device(peer_id, payload_fingerprint):
                    payload_error = {"device_id": peer_id, "file": filename, "error": "untrusted_payload_certificate", "time": int(time.time())}
                    self._set_diagnostic("last_payload_error", payload_error)
                    self._write_event(
                        "file_receive_failed",
                        payload_error,
                    )
                    return
                tls.settimeout(30)
                written = 0
                self.incoming_dir.mkdir(parents=True, exist_ok=True)
                try:
                    partial_destination.unlink()
                except FileNotFoundError:
                    pass
                with partial_destination.open("wb") as output:
                    while written < payload_size:
                        chunk = tls.recv(min(65536, payload_size - written))
                        if not chunk:
                            break
                        output.write(chunk)
                        written += len(chunk)
            if written != payload_size:
                try:
                    partial_destination.unlink()
                except OSError:
                    pass
                self._record_file_failure(peer_id, filename, "payload_incomplete", expected=payload_size, written=written)
                return
            partial_destination.replace(destination)
            file_event = {"device_id": peer_id, "file": destination.name, "path": str(destination), "size": written}
            self._set_diagnostic("last_file", {"status": "received", "time": int(time.time()), **file_event})
            self._write_event("file_received", file_event)
        except Exception as exc:
            try:
                partial_destination.unlink()
            except OSError:
                pass
            self._set_diagnostic(
                "last_file",
                {"device_id": peer_id, "file": filename, "status": "failed", "error": str(exc), "time": int(time.time())},
            )
            self._set_diagnostic("last_payload_error", {"device_id": peer_id, "file": filename, "error": str(exc), "time": int(time.time())})
            self._write_event("file_receive_failed", {"device_id": peer_id, "file": filename, "error": str(exc)})
            self._log("KDE receiver file transfer failed: %s", exc)

    def _safe_filename(self, filename: str) -> str:
        clean = filename.replace("\\", "/").split("/")[-1].strip()
        clean = "".join(ch for ch in clean if ch not in '<>:"|?*\0')
        return clean[:180] or f"kdeck-{int(time.time())}"

    def _unique_destination(self, filename: str) -> Path:
        destination = self.incoming_dir / filename
        if not destination.exists() and not destination.with_name(f"{destination.name}.part").exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        for index in range(1, 1000):
            candidate = self.incoming_dir / f"{stem} ({index}){suffix}"
            if not candidate.exists() and not candidate.with_name(f"{candidate.name}.part").exists():
                return candidate
        return self.incoming_dir / f"{stem}-{int(time.time())}{suffix}"

    def _packet_payload_size(self, packet: dict[str, Any]) -> Optional[int]:
        try:
            payload_size = int(packet.get("payloadSize") or 0)
        except (TypeError, ValueError):
            return None
        return payload_size if payload_size >= 0 else None

    def _payload_port(self, transfer_info: dict[str, Any]) -> Optional[int]:
        try:
            port = int(transfer_info.get("port"))
        except (TypeError, ValueError):
            return None
        return port if 1 <= port <= 65535 else None

    def _has_enough_space(self, payload_size: int) -> bool:
        try:
            usage = shutil.disk_usage(self.incoming_dir if self.incoming_dir.exists() else self.incoming_dir.parent)
        except OSError:
            return False
        return usage.free >= payload_size + MIN_FREE_SPACE_BYTES

    def _record_file_failure(self, peer_id: str, filename: str, reason: str, **details: Any) -> None:
        event = {"device_id": peer_id, "file": filename, "error": reason, **details}
        self._set_diagnostic("last_file", {"status": "failed", "time": int(time.time()), **event})
        self._set_diagnostic("last_payload_error", {"time": int(time.time()), **event})
        self._write_event("file_receive_failed", event)

    def _network_interfaces(self) -> list[dict[str, Any]]:
        interfaces: list[dict[str, Any]] = []
        if shutil.which("ip"):
            try:
                result = subprocess.run(
                    ["ip", "-j", "addr"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                for iface in json.loads(result.stdout):
                    name = iface.get("ifname", "")
                    if self._is_ignored_interface(name):
                        continue
                    for addr in iface.get("addr_info", []):
                        if addr.get("family") == "inet" and addr.get("local"):
                            local = addr.get("local")
                            if not self._is_usable_ipv4(local):
                                continue
                            interfaces.append(
                                {
                                    "interface": name,
                                    "address": local,
                                    "broadcast": addr.get("broadcast"),
                                    "prefixlen": addr.get("prefixlen"),
                                    "priority": self._interface_priority(name),
                                    "path_type": self._interface_path_type(name),
                                }
                            )
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                pass
        interfaces.sort(key=lambda item: (-int(item.get("priority") or 0), item.get("interface") or "", item.get("address") or ""))
        return interfaces

    def _bind_available_tcp_port(self, server: socket.socket, port_low: int = None, port_mid: int = None) -> int:
        lo = port_low if port_low is not None else TCP_PORT_MIN
        hi = port_mid if port_mid is not None else TCP_PORT_MAX
        last_error: Optional[OSError] = None
        for port in range(lo, hi + 1):
            try:
                server.bind(("0.0.0.0", port))
                return port
            except OSError as exc:
                last_error = exc
                continue
        raise OSError(f"no available TCP port in {lo}-{hi}: {last_error}")

    def _wait_for_listener_state(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.state_lock:
                udp_done = bool(self.diagnostics.get("udp_working") or self.diagnostics.get("udp_error"))
                tcp_done = bool(self.diagnostics.get("tcp_working") or self.diagnostics.get("tcp_error"))
            if udp_done and tcp_done:
                return
            time.sleep(0.05)

    def _peer_fingerprint(self, tls: ssl.SSLSocket) -> Optional[str]:
        try:
            cert = tls.getpeercert(binary_form=True)
        except (ssl.SSLError, ValueError):
            cert = None
        if not cert:
            return None
        return hashlib.sha256(cert).hexdigest()

    def _is_trusted_device(self, peer_id: str, fingerprint: Optional[str]) -> bool:
        trusted = self._trusted_devices().get(peer_id)
        if not isinstance(trusted, dict):
            return False
        trusted_fingerprint = trusted.get("fingerprint")
        if trusted_fingerprint:
            return bool(fingerprint and fingerprint == trusted_fingerprint)
        return trusted.get("trust_mode") == "device_id"

    def _broadcast_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str]]:
        targets: list[tuple[Optional[str], str]] = []
        seen = set()
        for iface in interfaces:
            source = iface.get("address")
            for target in ("255.255.255.255", iface.get("broadcast")):
                if not target:
                    continue
                key = (source, target)
                if key not in seen:
                    seen.add(key)
                    targets.append((source, target))
        if not targets:
            targets.append((None, "255.255.255.255"))
        return targets

    def _recent_discovery_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str, int]]:
        now = int(time.time())
        targets: list[tuple[Optional[str], str, int]] = []
        seen = set()
        with self.state_lock:
            devices = list((self.diagnostics.get("discovered_devices") or {}).values())
        for device in devices:
            host = device.get("host")
            if not host:
                continue
            if now - int(device.get("last_seen") or 0) > RECENT_DISCOVERY_DIRECT_SECONDS:
                continue
            ports = [int(device.get("udp_source_port") or 0), UDP_PORT]
            source_ips = self._source_ips_for_host(host, interfaces)
            for port in ports:
                if not (1 <= port <= 65535):
                    continue
                for source_ip in source_ips:
                    key = (source_ip, host, port)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append((source_ip, host, port))
        return targets[:16]

    def _trusted_direct_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str, int]]:
        now = int(time.time())
        targets: list[tuple[Optional[str], str, int]] = []
        seen = set()
        trusted = self._trusted_devices()
        for device_id, data in trusted.items():
            if not isinstance(data, dict):
                continue
            host = data.get("last_host")
            if not host:
                continue
            last_seen = int(data.get("last_seen") or data.get("last_connected") or 0)
            if last_seen and now - last_seen > TRUSTED_DEVICE_DIRECT_SECONDS:
                continue
            ports = [int(data.get("udp_source_port") or 0), UDP_PORT]
            source_ips = self._source_ips_for_host(str(host), interfaces)
            for port in ports:
                if not (1 <= port <= 65535):
                    continue
                for source_ip in source_ips:
                    key = (source_ip, str(host), port)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append((source_ip, str(host), port))
            self._write_event(
                "trusted_device_reannounce_target",
                {"device_id": device_id, "host": host, "ports": ports, "target_count": len(targets)},
            )
        self._set_diagnostic(
            "last_reannounce_targets",
            {
                "time": int(time.time()),
                "reason": "trusted_direct_targets",
                "targets": [{"source": source, "target": target, "port": port} for source, target, port in targets[:16]],
            },
        )
        return targets[:16]

    def _merge_direct_targets(
        self,
        first: list[tuple[Optional[str], str, int]],
        second: list[tuple[Optional[str], str, int]],
    ) -> list[tuple[Optional[str], str, int]]:
        merged: list[tuple[Optional[str], str, int]] = []
        seen = set()
        for item in first + second:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged[:24]

    def _source_ips_for_host(self, host: str, interfaces: list[dict[str, Any]]) -> list[Optional[str]]:
        matches: list[tuple[int, str]] = []
        fallbacks: list[tuple[int, str]] = []
        try:
            peer = ipaddress.ip_address(host)
        except ValueError:
            peer = None
        for iface in interfaces:
            source = iface.get("address")
            if not source:
                continue
            priority = int(iface.get("priority") or self._interface_priority(iface.get("interface") or ""))
            fallbacks.append((priority, source))
            if peer is None:
                continue
            try:
                prefixlen = int(iface.get("prefixlen") or 32)
                network = ipaddress.ip_interface(f"{source}/{prefixlen}").network
            except ValueError:
                continue
            if peer in network:
                matches.append((priority, source))
        selected = matches or fallbacks
        selected.sort(key=lambda item: (-item[0], item[1]))
        return [source for _priority, source in selected] or [None]

    def _is_ignored_interface(self, name: str) -> bool:
        return is_ignored_interface(name)

    def _interface_path_type(self, name: str) -> str:
        return interface_path_type(name)

    def _interface_priority(self, name: str) -> int:
        return interface_priority(name)

    def _is_usable_ipv4(self, address: Optional[str]) -> bool:
        return is_usable_ipv4(address)

    def _local_ipv4_addresses(self) -> set[str]:
        addresses = {"127.0.0.1"}
        for iface in self._network_interfaces():
            address = iface.get("address")
            if address:
                addresses.add(str(address))
        return addresses

    def _is_local_host(self, host: str) -> bool:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        if ip.is_loopback:
            return True
        return str(ip) in self._local_ipv4_addresses()

    def _record_discovery_received(self, addr: tuple[str, int], body: dict[str, Any]) -> None:
        device_id = body.get("deviceId")
        if not device_id:
            return
        now = int(time.time())
        item = {
            "device_id": device_id,
            "device_name": body.get("deviceName"),
            "device_type": body.get("deviceType"),
            "host": addr[0],
            "udp_source_port": addr[1],
            "tcp_port": body.get("tcpPort"),
            "protocol_version": body.get("protocolVersion"),
            "last_seen": now,
        }
        with self.state_lock:
            self.diagnostics["last_discovery_received"] = item
            self.diagnostics.setdefault("discovered_devices", {})[device_id] = item
        self._write_event("discovery_received", item)
        self._remember_trusted_device_metadata(device_id, addr[0], body, connected=False, udp_source_port=addr[1])

    def _remember_trusted_device_metadata(
        self,
        device_id: Optional[str],
        host: str,
        identity: dict[str, Any],
        connected: bool,
        udp_source_port: Optional[int] = None,
    ) -> None:
        if not device_id:
            return
        trusted = self._trusted_devices()
        data = trusted.get(device_id)
        if not isinstance(data, dict):
            return
        now = int(time.time())
        data.update(
            {
                "device_name": identity.get("deviceName") or data.get("device_name"),
                "device_type": identity.get("deviceType") or data.get("device_type"),
                "protocol_version": identity.get("protocolVersion") or data.get("protocol_version"),
                "tcp_port": identity.get("tcpPort") or data.get("tcp_port"),
                "last_host": host,
                "last_seen": now,
            }
        )
        if udp_source_port:
            data["udp_source_port"] = udp_source_port
        if connected:
            data["last_connected"] = now
        trusted[device_id] = data
        self._write_trusted_devices(trusted)
        self._write_event(
            "trusted_device_metadata_updated",
            {"device_id": device_id, "host": host, "connected": connected, "udp_source_port": udp_source_port},
        )

    def _set_diagnostic(self, key: str, value: Any) -> None:
        with self.state_lock:
            self.diagnostics[key] = value

    def _trusted_devices(self) -> dict[str, Any]:
        if not self.trusted_path.exists():
            return {}
        try:
            data = json.loads(self.trusted_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_trusted_devices(self, data: dict[str, Any]) -> None:
        self.trusted_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    EVENT_BUFFER_FLUSH_SIZE = 64

    def _write_event(self, event: str, details: dict[str, Any]) -> None:
        payload = {"time": int(time.time()), "event": event, **details}
        with self.event_buffer_lock:
            try:
                self._rotate_event_log_if_needed()
            except OSError:
                pass
            self.event_buffer.append(payload)
            if len(self.event_buffer) >= self.EVENT_BUFFER_FLUSH_SIZE:
                self._flush_event_buffer_locked()
        self._log("KDE receiver event %s %s", event, details)

    def _flush_event_buffer(self) -> None:
        with self.event_buffer_lock:
            self._flush_event_buffer_locked()

    def _flush_event_buffer_locked(self) -> None:
        """Must be called with event_buffer_lock held."""
        if not self.event_buffer:
            return
        try:
            with self.event_log_path.open("a", encoding="utf-8") as log:
                for payload in self.event_buffer:
                    log.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self.event_buffer.clear()

    def _rotate_event_log_if_needed(self) -> None:
        try:
            if not self.event_log_path.exists() or self.event_log_path.stat().st_size < EVENT_LOG_MAX_BYTES:
                return
            for stale in self.event_log_path.parent.glob(f"{self.event_log_path.name}.*"):
                try:
                    index = int(stale.name.rsplit(".", 1)[1])
                except (IndexError, ValueError):
                    continue
                if index > EVENT_LOG_BACKUPS:
                    stale.unlink()
            oldest = self.event_log_path.with_name(f"{self.event_log_path.name}.{EVENT_LOG_BACKUPS}")
            if oldest.exists():
                oldest.unlink()
            for index in range(EVENT_LOG_BACKUPS - 1, 0, -1):
                source = self.event_log_path.with_name(f"{self.event_log_path.name}.{index}")
                target = self.event_log_path.with_name(f"{self.event_log_path.name}.{index + 1}")
                if source.exists():
                    source.replace(target)
            self.event_log_path.replace(self.event_log_path.with_name(f"{self.event_log_path.name}.1"))
            self.event_log_path.write_text("", encoding="utf-8")
        except OSError:
            pass

    def _tail_events(self, limit: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with self.event_buffer_lock:
            events.extend(self.event_buffer[-limit:])
        disk_limit = limit - len(events)
        if disk_limit > 0 and self.event_log_path.exists():
            try:
                lines = self.event_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            for line in lines[-disk_limit:]:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events[-limit:]

    def send_share_request_to_peer(self, file_path: str, device_id: str) -> dict[str, Any]:
        trusted = self._trusted_devices().get(device_id)
        if not trusted:
            return {"ok": False, "error": {"code": "not_trusted", "message": "Device is not trusted."}}
        host = trusted.get("last_host")
        if not host:
            return {"ok": False, "error": {"code": "unknown_host", "message": "No known host for this device."}}
        source = Path(file_path)
        if not source.is_file():
            return {"ok": False, "error": {"code": "file_not_found", "message": "File not found."}}
        file_size = source.stat().st_size
        if file_size == 0:
            return {"ok": False, "error": {"code": "empty_file", "message": "File is empty."}}
        if file_size > MAX_FILE_BYTES:
            return {"ok": False, "error": {"code": "file_too_large", "message": f"File exceeds {MAX_FILE_BYTES} bytes."}}

        stop_event = threading.Event()
        file_port, server_thread = self._serve_file_tls(source, stop_event)
        if file_port is None:
            return {"ok": False, "error": {"code": "file_server_failed", "message": "Could not start file server."}}

        self._write_event("share_send_attempt", {"device_id": device_id, "host": host, "file": source.name, "size": file_size, "port": file_port})

        try:
            interfaces = self._network_interfaces()
            source_ips = self._source_ips_for_host(host, interfaces)
            source_ip = source_ips[0] if source_ips else None
            raw = socket.create_connection((host, 1716), timeout=5, source_address=(source_ip, 0) if source_ip else None)
        except OSError:
            self._cleanup_file_server(stop_event, server_thread)
            return {"ok": False, "error": {"code": "peer_unreachable", "message": "Could not connect to phone."}}

        try:
            hello = self._identity_packet()
            raw.sendall(self._encode_packet(hello))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            tls = context.wrap_socket(raw, server_hostname=device_id, server_side=False, do_handshake_on_connect=True)

            share = {
                "type": PACKET_SHARE_REQUEST,
                "body": {
                    "filename": source.name,
                    "payloadSize": file_size,
                    "numberOfFiles": 1,
                },
                "payloadTransferInfo": {"port": file_port},
            }
            tls.sendall(self._encode_packet(share))
            self._write_event("share_send_sent", {"device_id": device_id, "file": source.name, "size": file_size, "port": file_port})
            self._set_diagnostic("last_share_send", {"device_id": device_id, "file": source.name, "size": file_size, "time": int(time.time())})

            server_thread.join(timeout=60)
            if server_thread.is_alive():
                self._cleanup_file_server(stop_event, server_thread)
                return {"ok": False, "error": {"code": "transfer_timeout", "message": "File transfer timed out."}}

            return {"ok": True, "file": source.name, "size": file_size}
        except Exception as exc:
            self._cleanup_file_server(stop_event, server_thread)
            return {"ok": False, "error": {"code": "send_failed", "message": str(exc)}}
        finally:
            try:
                tls.close()
            except Exception:
                pass

    def _serve_file_tls(self, file_path: Path, stop_event: threading.Event) -> tuple[Optional[int], threading.Thread]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", 0))
        except OSError:
            return None, threading.Thread()
        port = sock.getsockname()[1]
        sock.listen(1)
        sock.settimeout(5)

        def _serve() -> None:
            data = b""
            try:
                data = file_path.read_bytes()
            except OSError:
                pass
            if not data:
                try:
                    sock.close()
                except OSError:
                    pass
                return
            try:
                conn, _ = sock.accept()
            except (OSError, socket.timeout):
                try:
                    sock.close()
                except OSError:
                    pass
                return
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.verify_mode = ssl.CERT_NONE
                context.load_cert_chain(str(self.cert_path), str(self.key_path))
                tls_sock = context.wrap_socket(conn, server_side=True, do_handshake_on_connect=True)
                tls_sock.settimeout(30)
                tls_sock.sendall(data)
                try:
                    tls_sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                tls_sock.close()
            except OSError:
                pass
            finally:
                try:
                    sock.close()
                except OSError:
                    pass

        thread = threading.Thread(target=_serve, daemon=True)
        thread.start()
        return port, thread

    def _cleanup_file_server(self, stop_event: threading.Event, thread: threading.Thread) -> None:
        stop_event.set()
        thread.join(timeout=2)

    def _log(self, message: str, *args: Any) -> None:
        if self.logger:
            self.logger.info(message, *args)


"""KDEck KDE Connect receiver orchestration.

This class owns the mutable runtime state for KDE Connect in Game Mode:
listeners, sockets, TLS sessions, connection threads, diagnostics, and event
logging.  Stateless protocol, network, discovery, trust, TLS, and transfer
helpers live in sibling ``kdeck_kde_*`` modules so they can be tested without
opening sockets or changing receiver lifecycle behavior.
"""

import ipaddress
import json
import os
import queue
import secrets
import select
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from kdeck_diagnostics import diagnostic_error

# Import connection-state helpers.  Socket and TLS operations stay in the
# receiver; this module only makes small deterministic lifecycle decisions.
from kdeck_kde_connection import peer_connect_decision as _peer_connect_decision_standalone

# Import discovery helpers.  These helpers calculate target lists only; the
# receiver remains responsible for socket I/O, event logging, and diagnostics.
from kdeck_kde_discovery import (
    recent_discovery_targets as _recent_discovery_targets_standalone,
)
from kdeck_kde_discovery import (
    trusted_direct_targets as _trusted_direct_targets_standalone,
)

# Import event logger.
from kdeck_kde_events import EventLogger

# Import network utility functions from the network module.
from kdeck_kde_network import (  # noqa: F401
    bind_available_tcp_port as _bind_available_tcp_port_standalone,
)
from kdeck_kde_network import (
    broadcast_targets as _broadcast_targets_standalone,
)
from kdeck_kde_network import (
    identity_reply_ports as _identity_reply_ports_standalone,
)
from kdeck_kde_network import (
    interface_path_type as _interface_path_type_standalone,
)
from kdeck_kde_network import (
    interface_priority as _interface_priority_standalone,
)
from kdeck_kde_network import (
    is_ignored_interface as _is_ignored_interface_standalone,
)
from kdeck_kde_network import (
    is_usable_ipv4 as _is_usable_ipv4_standalone,
)
from kdeck_kde_network import (
    merge_direct_targets as _merge_direct_targets_standalone,
)
from kdeck_kde_network import (
    network_interfaces as _network_interfaces_standalone,
)
from kdeck_kde_network import (
    peer_tls_mode as _peer_tls_mode_standalone,
)
from kdeck_kde_network import (
    source_ips_for_host as _source_ips_for_host_standalone,
)

# Import protocol constants & packet codec from the protocol module.
# Re-export at module level so tests that patch kdeck_kde_receiver.TCP_PORT_MIN
# etc. continue to work.
from kdeck_kde_protocol import (  # noqa: F401
    ANDROID_DEVICE_TYPES,
    BROADCAST_INTERVAL_SECONDS,
    CAPABILITIES,
    DEVICE_NAME,
    DEVICE_TYPE,
    EVENT_LOG_BACKUPS,
    EVENT_LOG_MAX_BYTES,
    FILE_CHUNK_BYTES,
    FILE_RECV_TOTAL_TIMEOUT_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    MAX_FILE_BYTES,
    MAX_PACKET_BYTES,
    MIN_FREE_SPACE_BYTES,
    PACKET_CLIPBOARD,
    PACKET_CLIPBOARD_CONNECT,
    PACKET_IDENTITY,
    PACKET_PAIR,
    PACKET_PING,
    PACKET_SHARE_REQUEST,
    PAYLOAD_RECEIVE_MAX_RETRIES,
    PAYLOAD_RECEIVE_RETRY_DELAY,
    PEER_CONNECT_COOLDOWN_SECONDS,
    PROTOCOL_VERSION,
    RECENT_DISCOVERY_DIRECT_SECONDS,
    RECONNECT_BASE_DELAY,
    RECONNECT_MAX_DELAY,
    SOCKET_BUFFER_BYTES,
    SEND_PROGRESS_MIN_BYTES,
    SEND_PROGRESS_MIN_INTERVAL_SECONDS,
    STARTUP_BROADCAST_DELAYS,
    TCP_PORT_MAX,
    TCP_PORT_MIN,
    TRUSTED_DEVICE_DIRECT_SECONDS,
    TRUSTED_PEER_CONNECT_COOLDOWN_SECONDS,
    UDP_PORT,
)
from kdeck_kde_protocol import (
    encode_packet as _encode_packet_standalone,
)
from kdeck_kde_protocol import (
    identity_packet as _identity_packet_standalone,
)
from kdeck_kde_protocol import (
    packet_payload_size as _packet_payload_size_standalone,
)
from kdeck_kde_protocol import (
    payload_port as _payload_port_standalone,
)
from kdeck_kde_state import state_transition

# Import TLS utilities.
from kdeck_kde_tls import (  # noqa: F401
    ensure_certificate as _ensure_certificate_standalone,
)
from kdeck_kde_tls import (
    peer_fingerprint as _peer_fingerprint_standalone,
)

# Import file-transfer utilities.
from kdeck_kde_transfer import (
    connect_to_peer_control_socket as _connect_to_peer_control_socket_standalone,
)
from kdeck_kde_transfer import (
    has_enough_space as _has_enough_space_standalone,
)
from kdeck_kde_transfer import (
    record_file_failure as _record_file_failure_standalone,
)
from kdeck_kde_transfer import (
    safe_filename as _safe_filename_standalone,
)
from kdeck_kde_transfer import (
    unique_destination as _unique_destination_standalone,
)

# Import trust management helpers.
from kdeck_kde_trust import (
    accept_pair_record as _accept_pair_record_standalone,
)
from kdeck_kde_trust import (
    is_trusted_device as _is_trusted_device_standalone,
)
from kdeck_kde_trust import (
    read_trusted_devices as _read_trusted_devices_standalone,
)
from kdeck_kde_trust import (
    remember_trusted_device_metadata as _remember_trusted_device_metadata_standalone,
)
from kdeck_kde_trust import (
    write_trusted_devices as _write_trusted_devices_standalone,
)

# Bluetooth constants: use numeric fallbacks since PyBluez (which monkey-patches
# socket.AF_BLUETOOTH / BTPROTO_RFCOMM via import bluetooth) may not be
# available in Deckys embedded Python.
BT_AF = getattr(socket, "AF_BLUETOOTH", None) or 31
BT_BTPROTO = getattr(socket, "BTPROTO_RFCOMM", None) or 3


class KDEckKdeReceiver:
    """Manages the KDE Connect protocol for a Steam Deck plugin.

    Handles UDP discovery, TCP/TLS connection lifecycle, pairing/trust,
    clipboard sync, and file transfer.  Stateless helpers (protocol codec,
    network discovery, TLS certificate management) are delegated to the
    ``kdeck_kde_protocol``, ``kdeck_kde_network``, and ``kdeck_kde_tls``
    modules respectively.
    """

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
        self.peer_connections: dict[str, dict[str, Any]] = {}
        self.state_lock = threading.Lock()
        self.data_lock = threading.Lock()
        self.on_file_received: Optional[Callable[[dict[str, Any]], None]] = None
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.device_id = self._device_id()
        self.events = EventLogger(self.event_log_path, self._log, default_device_id=self.device_id)
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
            "last_state_transition": None,
            "connection_states": {},
            "interfaces": [],
            "discovered_devices": {},
        }

    def start(self) -> dict[str, Any]:
        """Initialise TLS certificates, spawn TCP/UDP/BT servers and start broadcasting."""
        if self.threads:
            return self.status()
        try:
            self._ensure_certificate()
        except Exception as exc:
            self._log("KDE receiver certificate init failed: %s", exc)
            self._set_diagnostic("last_error", diagnostic_error("certificate_init_failed", "certificate", str(exc)))
            self.events.write_event("certificate_init_failed", {"error": str(exc)})
            return {"ok": False, "running": False, "error": {"code": "certificate_init_failed", "message": str(exc)}}
        self.stop_event.clear()
        with self.data_lock:
            self.tcp_port = None
        self._set_connection_state(self.device_id, "idle", "receiver_starting")
        self.events.write_event("receiver_starting", {"udp_port": UDP_PORT, "tcp_port_range": f"{TCP_PORT_MIN}-{TCP_PORT_MAX}"})
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
        """Signal all threads to stop, close sockets, and flush the event log."""
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
        current_state = None
        with self.state_lock:
            current = (self.diagnostics.get("connection_states") or {}).get(self.device_id)
            if isinstance(current, dict):
                current_state = current.get("state")
        if current_state != "paused_desktop":
            self._set_connection_state(self.device_id, "idle", "receiver_stopped")
        self.events.flush()
        self.events.write_event("receiver_stopped", {})
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
        """Re-broadcast identity so trusted devices can reconnect."""
        with self.data_lock:
            port = self.tcp_port
        if not port:
            self.events.write_event("trusted_reannounce_skipped", {"reason": reason, "skip_reason": "tcp_not_ready"})
            return {"ok": False, "reason": "tcp_not_ready"}
        self._broadcast_identity(reason=reason)
        return {"ok": True, "reason": reason}

    def status(self) -> dict[str, Any]:
        """Return a full status snapshot for the frontend."""
        trusted = self._trusted_devices()
        valid_trusted = {
            device_id: data
            for device_id, data in trusted.items()
            if isinstance(data, dict) and (data.get("fingerprint") or data.get("trust_mode") == "device_id")
        }
        with self.state_lock:
            diagnostics = json.loads(json.dumps(self.diagnostics, ensure_ascii=False))
        with self.data_lock:
            peer_connections = {
                device_id: {"host": data.get("host")}
                for device_id, data in self.peer_connections.items()
                if isinstance(data, dict)
            }
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
            "peer_connections": peer_connections,
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
            "last_state_transition": diagnostics.get("last_state_transition"),
            "connection_states": diagnostics.get("connection_states", {}),
            "paired": bool(valid_trusted),
            "trusted_device": next((item for item in discovered if item.get("device_id") in valid_trusted), None),
            "trusted_devices": valid_trusted,
            "legacy_trusted_devices": [device_id for device_id in trusted if device_id not in valid_trusted],
            "last_events": self.events.tail(20),
        }

    def _bluetooth_server(self) -> None:
        """Listen on RFCOMM for incoming Bluetooth connections."""
        bt_channel = 22
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kdeck_bt_helper.py")

        if not os.path.exists(helper) or shutil.which("sdptool") is None:
            self.events.write_event("bluetooth_init_failed", {"error": "helper missing or sdptool not installed"})
            self._set_diagnostic("bt_working", False)
            return

        # The helper runs under system Python (which has PyBluez) and forwards
        # Bluetooth RFCOMM connections to a local TCP port inside the Deck.
        # sys.executable is the PyInstaller-wrapped PluginLoader binary in Decky's
        # embedded Python, NOT a general-purpose Python interpreter. Always use
        # the system Python instead.
        system_python = shutil.which("python") or "/usr/bin/python"
        bt_tcp_port = self._bind_available_tcp_port(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM), port_low=1730, port_mid=1740
        )

        try:
            helper_proc = subprocess.Popen(
                [system_python, helper, str(bt_tcp_port)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        except OSError as exc:
            self.events.write_event("bluetooth_init_failed", {"error": f"helper spawn failed: {exc}"})
            self._set_diagnostic("bt_working", False)
            return

        self._bt_helper_proc = helper_proc

        # Read one line to confirm startup.
        line = helper_proc.stdout.readline() if helper_proc.stdout else ""
        if "BT listening" not in line:
            self.events.write_event("bluetooth_init_failed", {"error": f"helper startup failed: {line.strip()}"})
            self._set_diagnostic("bt_working", False)
            try:
                helper_proc.kill()
            except OSError:
                pass
            self._bt_helper_proc = None
            return

        self._set_diagnostic("bt_working", True)
        self._set_diagnostic("bt_error", None)
        self.events.write_event("bluetooth_listening", {"channel": bt_channel})

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
                lambda c=conn, a=addr: self._handle_incoming_bt(c, str(a)),
                f"KDEckBtHandler-{addr}",
            )

    def _handle_incoming_bt(self, conn: socket.socket, addr: str) -> None:
        """Handle a single Bluetooth connection: read identity, upgrade to TLS, then enter packet loop."""
        bt_id = str(addr).replace(":", "")[:16]
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.events.write_event("incoming_bt_connected", {"addr": str(addr)})
            identity = self._read_plain_packet(conn)
            body = identity.get("body") or {}
            peer_id = body.get("deviceId")
            if identity.get("type") != PACKET_IDENTITY or not peer_id:
                self.events.write_event("incoming_bt_identity_invalid", {"addr": str(addr), "packet_type": identity.get("type")})
                conn.close()
                return
            self.events.write_event("incoming_bt_identity_received", {"addr": str(addr), "device_id": peer_id, "device_name": body.get("deviceName")})
            # TLS: Bluetooth uses client-side TLS (same as incoming TCP)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            self.events.write_event("incoming_bt_tls_start", {"addr": str(addr), "device_id": peer_id})
            tls = context.wrap_socket(conn, server_hostname=peer_id, do_handshake_on_connect=True)
            self.events.write_event("incoming_bt_tls_done", {"addr": str(addr), "device_id": peer_id})
            self._after_tls(tls, peer_id, peer_host=bt_id, send_identity_first=True)
        except Exception as exc:
            self._log("KDE receiver BT connection failed from %s: %s", addr, exc)
            error = {"stage": "incoming_bt", "addr": str(addr), "error_type": type(exc).__name__, "message": str(exc), "time": int(time.time())}
            self._set_diagnostic("last_error", error)
            self.events.write_event("incoming_bt_failed", error)
            try:
                conn.close()
            except OSError:
                pass

    def _tcp_server(self) -> None:
        """Bind a TCP socket and accept incoming KDE Connect connections."""
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
            hint = "KDE Connect ports {}-{} are all occupied, check for other KDE Connect instances.".format(TCP_PORT_MIN, TCP_PORT_MAX)
            error = diagnostic_error(
                "tcp_listener_bind_failed",
                "tcp",
                str(exc),
                port_range=f"{TCP_PORT_MIN}-{TCP_PORT_MAX}",
                hint=hint,
            )
            self._set_diagnostic("tcp_working", False)
            self._set_diagnostic("tcp_error", error)
            self._set_diagnostic("last_error", error)
            self.events.write_event("tcp_bind_failed", error)
            return
        self._set_diagnostic("tcp_working", True)
        self._set_diagnostic("tcp_error", None)
        self.events.write_event("tcp_listening", {"host": "0.0.0.0", "port": tcp_port})

        while not self.stop_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._start_connection_thread(lambda c=conn, a=addr: self._handle_incoming_tcp(c, a), f"KDEckTcpHandler-{addr[0]}:{addr[1]}")

    def _udp_server(self) -> None:
        """Bind a UDP socket and process incoming discovery broadcasts."""
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind(("0.0.0.0", UDP_PORT))
            udp.settimeout(1)
            self.udp_socket = udp
        except OSError as exc:
            self._log("KDE receiver UDP start failed: %s", exc)
            error = diagnostic_error("discovery_udp_bind_failed", "discovery", str(exc), port=UDP_PORT)
            self._set_diagnostic("udp_working", False)
            self._set_diagnostic("udp_error", error)
            self._set_diagnostic("last_error", error)
            self.events.write_event("udp_bind_failed", error)
            return
        self._set_diagnostic("udp_working", True)
        self._set_diagnostic("udp_error", None)
        self.events.write_event("udp_listening", {"host": "0.0.0.0", "port": UDP_PORT})

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
                self.events.write_event(
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
        """Periodically broadcast identity packets over UDP."""
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
        """Send a single identity broadcast to all reachable subnets."""
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
        self.events.write_event("discovery_sent", details)

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
            self.events.write_event("identity_reply_skipped", {"host": host, "reason": "tcp_not_ready"})
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
        self.events.write_event(
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
        """Process one incoming TCP connection: read plain identity, perform TLS handshake, then enter packet loop."""
        peer_id = None
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.events.write_event("incoming_tcp_connected", {"host": addr[0], "port": addr[1]})
            self._set_diagnostic("last_tcp_success", {"host": addr[0], "port": addr[1], "stage": "incoming", "time": int(time.time())})
            if self._is_local_host(addr[0]):
                self.events.write_event("incoming_tcp_rejected", {"host": addr[0], "port": addr[1], "reason": "local_host"})
                conn.close()
                return
            identity = self._read_plain_packet(conn)
            body = identity.get("body") or {}
            peer_id = body.get("deviceId")
            if identity.get("type") != PACKET_IDENTITY or not peer_id:
                self.events.write_event("incoming_plain_identity_invalid", {"host": addr[0], "port": addr[1], "packet_type": identity.get("type")})
                conn.close()
                return
            self._set_connection_state(peer_id, "connecting", "incoming_plain_identity_received", host=addr[0], port=addr[1])
            self.events.write_event(
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
                self.events.write_event("incoming_tcp_rejected", {"host": addr[0], "port": addr[1], "device_id": peer_id, "target_device_id": target})
                conn.close()
                return
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            tls_started = time.monotonic()
            self.events.write_event("incoming_tls_handshake_start", {"host": addr[0], "port": addr[1], "device_id": peer_id, "tls_mode": "client"})
            tls = context.wrap_socket(conn, server_hostname=peer_id, do_handshake_on_connect=True)
            self._set_diagnostic("last_tls_success", {"host": addr[0], "port": addr[1], "device_id": peer_id, "stage": "incoming", "time": int(time.time())})
            self._set_connection_state(peer_id, "connected", "incoming_tls_ready", host=addr[0], port=addr[1])
            self.events.write_event(
                "incoming_tls_handshake_done",
                {"host": addr[0], "port": addr[1], "device_id": peer_id, "tls_mode": "client", "duration_ms": int((time.monotonic() - tls_started) * 1000)},
            )
            self._after_tls(tls, peer_id, peer_host=addr[0], send_identity_first=True)
        except Exception as exc:
            self._log("KDE receiver incoming connection failed from %s: %s", addr, exc)
            error = diagnostic_error(
                "tls_handshake_failed",
                "tls",
                str(exc),
                host=addr[0],
                port=addr[1],
                error_type=type(exc).__name__,
                direction="incoming",
                device_id=peer_id,
            )
            self._set_diagnostic("last_error", error)
            self._set_diagnostic("last_tls_error", error)
            if error.get("device_id"):
                self._set_connection_state(error["device_id"], "failed", "incoming_tls_failed", host=addr[0], port=addr[1])
            self.events.write_event("incoming_tcp_failed", error)
            try:
                conn.close()
            except OSError:
                pass

    def _connect_to_peer(self, host: str, port: int, peer_identity: dict[str, Any]) -> bool:
        """Initiate an outgoing TCP+TLS connection to a discovered peer."""
        peer_id = peer_identity.get("deviceId")
        if not peer_id:
            return False
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
        self._set_connection_state(peer_id, "connecting", "peer_connect_attempt", host=host, port=port)
        self.events.write_event(
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
        tls = None
        raw = None
        try:
            tcp_started = time.monotonic()
            raw = socket.create_connection((host, port), timeout=5, source_address=(source_ip, 0) if source_ip else None)
            raw.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._set_diagnostic("last_tcp_success", {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "time": int(time.time())})
            self.events.write_event(
                "peer_tcp_connected",
                {"host": host, "port": port, "device_id": peer_id, "source_ip": source_ip, "duration_ms": int((time.monotonic() - tcp_started) * 1000)},
            )
            hello = self._identity_packet(target_device_id=peer_id, target_protocol_version=peer_identity.get("protocolVersion"))
            raw.sendall(self._encode_packet(hello))
            self.events.write_event(
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
            self.events.write_event(
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
            self._set_connection_state(peer_id, "connected", "peer_tls_ready", host=host, port=port, source_ip=source_ip)
            self.events.write_event(
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
            return True
        except Exception as exc:
            self._log("KDE receiver peer connection failed %s:%s: %s", host, port, exc)
            code = "tcp_connect_timeout" if isinstance(exc, TimeoutError) else "tcp_connect_failed"
            if isinstance(exc, ssl.SSLError):
                code = "tls_handshake_failed"
            error = diagnostic_error(
                code,
                "tls" if code == "tls_handshake_failed" else "tcp",
                str(exc),
                host=host,
                port=port,
                device_id=peer_id,
                device_type=peer_identity.get("deviceType"),
                source_ip=source_ip,
                tls_mode=tls_mode,
                error_type=type(exc).__name__,
            )
            self._set_diagnostic("last_connect_error", error)
            self._set_diagnostic("last_error", error)
            if code == "tls_handshake_failed":
                self._set_diagnostic("last_tls_error", error)
            self._set_connection_state(peer_id, "failed", code, host=host, port=port)
            self.events.write_event("peer_connect_failed", error)
            try:
                if tls is not None:
                    tls.close()
                elif raw is not None:
                    raw.close()
            except Exception:
                pass
            if device_type in ANDROID_DEVICE_TYPES:
                self.events.write_event(
                    "identity_reply_skipped",
                    {"host": host, "port": UDP_PORT, "target_device_id": peer_id, "reason": "android_failure_fallback_suppressed"},
                )
                return False
            self._send_udp_identity(
                host,
                UDP_PORT,
                target_device_id=peer_id,
                target_protocol_version=peer_identity.get("protocolVersion"),
                reason="peer_connect_failed_fallback",
                peer_identity=peer_identity,
            )
            return False

    def _after_tls(self, tls: ssl.SSLSocket, peer_id: str, peer_host: str, send_identity_first: bool) -> None:
        """Post-TLS handshake: exchange secure identities and enter the packet loop or reconnect loop."""
        try:
            tls.settimeout(60)
            fingerprint = self._peer_fingerprint(tls)
            if send_identity_first:
                tls.sendall(self._encode_packet(self._identity_packet()))
                self.events.write_event("secure_identity_sent", {"host": peer_host, "device_id": peer_id})
            secure_identity = self._read_tls_packet(tls)
            if secure_identity.get("type") == PACKET_IDENTITY:
                secure_body = secure_identity.get("body") or {}
                peer_id = secure_body.get("deviceId") or peer_id
                self._remember_trusted_device_metadata(peer_id, peer_host, secure_body, connected=True)
                self.events.write_event(
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
                self.events.write_event("secure_identity_missing", {"host": peer_host, "device_id": peer_id, "packet_type": secure_identity.get("type")})
            self._packet_loop(tls, peer_id, peer_host, fingerprint)
        except Exception as exc:
            self.events.write_event("peer_session_error", {"host": peer_host, "device_id": peer_id, "error_type": type(exc).__name__, "message": str(exc)})
            self._log("KDE receiver session error %s: %s", peer_id, exc)
        finally:
            try:
                tls.close()
            except Exception:
                pass
            # Active reconnect for trusted devices
            if not self.stop_event.is_set() and self._trusted_devices().get(peer_id):
                t = threading.Thread(
                    target=self._active_reconnect_loop,
                    args=(peer_id, peer_host),
                    name=f"KDEckReconnect-{peer_id[:8]}",
                    daemon=True,
                )
                t.start()
                self.threads.append(t)

    def _active_reconnect_loop(self, peer_id: str, last_host: str) -> None:
        """Immediately try to reconnect to a trusted device that just disconnected."""
        delay = RECONNECT_BASE_DELAY
        attempt = 0
        while not self.stop_event.is_set():
            self.stop_event.wait(delay)
            if self.stop_event.is_set():
                return
            # Skip if already reconnected
            with self.data_lock:
                if peer_id in self.peer_connections:
                    return
            self._set_connection_state(peer_id, "backoff", "reconnect_wait", host=last_host, delay=delay, attempt=attempt)
            self.events.write_event("reconnect_attempt", {"device_id": peer_id, "host": last_host, "delay": delay, "attempt": attempt})
            if self._connect_to_peer(last_host, UDP_PORT, {"deviceId": peer_id}):
                return  # Success — _after_tls will handle the rest
            attempt += 1
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    def _packet_loop(self, tls: ssl.SSLSocket, peer_id: str, peer_host: str, fingerprint: Optional[str]) -> None:
        """Read and dispatch packets from an established TLS connection."""
        buffer = b""
        send_queue: queue.Queue = queue.Queue()
        with self.data_lock:
            self.peer_connections[peer_id] = {"tls": tls, "send_queue": send_queue, "host": peer_host}
        last_send_time = time.monotonic()
        try:
            while not self.stop_event.is_set():
                # Use select to check for incoming data (non-blocking on the raw socket)
                try:
                    readable, _, _ = select.select([tls], [], [], 1.0)
                except (OSError, ValueError):
                    break

                if readable:
                    try:
                        chunk = tls.recv(65536)
                    except socket.timeout:
                        chunk = None
                    except OSError:
                        break
                    if not chunk:
                        break
                    buffer += chunk
                    if len(buffer) > MAX_PACKET_BYTES and b"\n" not in buffer:
                        self.events.write_event(
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
                            self.events.write_event(
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
                        try:
                            self._handle_packet(tls, peer_id, peer_host, packet, fingerprint)
                        except Exception as exc:
                            self.events.write_event("packet_handler_error", {"device_id": peer_id, "host": peer_host, "packet_type": packet.get("type"), "error_type": type(exc).__name__, "message": str(exc)})
                            self._log("KDE receiver packet handler error: %s", exc)

                # Drain send queue — packets submitted by other threads (e.g. share requests)
                while True:
                    try:
                        data = send_queue.get_nowait()
                        tls.sendall(data)
                        last_send_time = time.monotonic()
                    except queue.Empty:
                        break
                    except OSError:
                        return

                # Heartbeat — send kdeconnect.ping periodically
                if time.monotonic() - last_send_time > HEARTBEAT_INTERVAL_SECONDS:
                    try:
                        tls.sendall(self._encode_packet({"type": "kdeconnect.ping", "body": {}}))
                        last_send_time = time.monotonic()
                    except OSError:
                        break
        finally:
            with self.data_lock:
                self.peer_connections.pop(peer_id, None)
            self._set_connection_state(peer_id, "trusted" if self._trusted_devices().get(peer_id) else "discovered", "session_closed", host=peer_host)

    def _handle_packet(
        self,
        tls: ssl.SSLSocket,
        peer_id: str,
        peer_host: str,
        packet: dict[str, Any],
        fingerprint: Optional[str],
    ) -> None:
        """Dispatch a single decoded packet to the appropriate handler."""
        packet_type = packet.get("type")
        body = packet.get("body") or {}
        if packet_type == PACKET_PAIR:
            if body.get("pair") is False:
                trusted = self._trusted_devices()
                trusted.pop(peer_id, None)
                self._write_trusted_devices(trusted)
                self._set_diagnostic("last_pair", {"device_id": peer_id, "paired": False, "time": int(time.time())})
                self._set_connection_state(peer_id, "discovered", "unpaired", host=peer_host)
                self.events.write_event("unpaired", {"device_id": peer_id})
                self._set_diagnostic("pending_pair", None)
                return
            if self._is_trusted_device(peer_id, fingerprint):
                self._accept_pair_inner(tls, peer_id, peer_host, fingerprint)
                return
            self._accept_pair_inner(tls, peer_id, peer_host, fingerprint)
            return
        if not self._is_trusted_device(peer_id, fingerprint):
            self.events.write_event("untrusted_packet_rejected", {"device_id": peer_id, "packet_type": packet_type})
            return
        if packet_type == PACKET_PING:
            try:
                tls.sendall(self._encode_packet({"type": PACKET_PING, "body": {}}))
                self.events.write_event("ping_reply_sent", {"device_id": peer_id})
            except OSError:
                pass
            return
        if packet_type in (PACKET_CLIPBOARD, PACKET_CLIPBOARD_CONNECT):
            content = str(body.get("content") or "")
            if content:
                self.on_clipboard(content, peer_id)
                self._set_diagnostic("last_clipboard", {"device_id": peer_id, "length": len(content), "time": int(time.time())})
                self.events.write_event("clipboard_received", {"device_id": peer_id, "length": len(content)})
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
        """Accept a pairing request and store the peer as a trusted device."""
        trusted = self._trusted_devices()
        now = int(time.time())
        trusted, trust_mode = _accept_pair_record_standalone(trusted, peer_id, peer_host, fingerprint, now)
        self._write_trusted_devices(trusted)
        tls.sendall(self._encode_packet({"type": PACKET_PAIR, "body": {"pair": True}}))
        self._log("KDE receiver paired with %s", peer_id)
        self._set_diagnostic("last_pair", {"device_id": peer_id, "paired": True, "time": now, "trust_mode": trust_mode})
        self._set_connection_state(peer_id, "trusted", "pair_accepted", host=peer_host, trust_mode=trust_mode)
        self.events.write_event(
            "paired",
            {
                "device_id": peer_id,
                "fingerprint": fingerprint,
                "trust_mode": trust_mode,
                "weak_trust_fallback": fingerprint is None,
            },
        )

    def _identity_packet(self, target_device_id: Optional[str] = None, target_protocol_version: Any = None) -> dict[str, Any]:
        return _identity_packet_standalone(
            self.device_id,
            tcp_port=self._tcp_port_value(),
            target_device_id=target_device_id,
            target_protocol_version=target_protocol_version,
        )

    def _should_connect_to_peer(self, host: str, port: int, peer_identity: dict[str, Any]) -> bool:
        device_id = peer_identity.get("deviceId")
        now = time.monotonic()
        cooldown = TRUSTED_PEER_CONNECT_COOLDOWN_SECONDS if self._trusted_devices().get(device_id) else PEER_CONNECT_COOLDOWN_SECONDS
        with self.data_lock:
            allowed, key, skipped_event = _peer_connect_decision_standalone(
                device_id,
                host,
                port,
                now,
                self.peer_connect_attempts,
                cooldown,
            )
            if allowed:
                self.peer_connect_attempts[key] = now
        if skipped_event:
            self.events.write_event("peer_connect_skipped", skipped_event)
            return False
        return allowed

    def _identity_reply_ports(self, source_port: int, peer_identity: dict[str, Any]) -> list[int]:
        return _identity_reply_ports_standalone(source_port, peer_identity)

    def _peer_tls_mode(self, device_type: str) -> str:
        return _peer_tls_mode_standalone(device_type)

    def _device_id(self) -> str:
        if self.device_id_path.exists():
            value = self.device_id_path.read_text(encoding="utf-8").strip()
            if 32 <= len(value) <= 38:
                return value
        value = secrets.token_hex(16)
        self.device_id_path.write_text(value, encoding="utf-8")
        return value

    def _ensure_certificate(self) -> None:
        existing = _ensure_certificate_standalone(self.cert_path, self.key_path, self.device_id)
        self.events.write_event("certificate_ready", {"cert": str(self.cert_path), "existing": existing})

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
            self.events.write_event("packet_rejected", {"stage": "plain_identity", "reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES})
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
            self.events.write_event("packet_rejected", {"stage": "secure_identity", "reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES})
            return {}
        return self._decode_packet(data, context={"stage": "secure_identity"})

    def _encode_packet(self, packet: dict[str, Any]) -> bytes:
        return _encode_packet_standalone(packet)

    def _decode_packet(self, data: bytes, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if len(data) > MAX_PACKET_BYTES:
            self.events.write_event("packet_rejected", {"reason": "packet_too_large", "size": len(data), "max_size": MAX_PACKET_BYTES, **(context or {})})
            return {}
        try:
            packet = json.loads(data.decode("utf-8", errors="replace").strip())
        except json.JSONDecodeError:
            self.events.write_event("packet_decode_failed", {"reason": "invalid_json", "size": len(data), **(context or {})})
            return {}
        if not isinstance(packet, dict):
            self.events.write_event("packet_decode_failed", {"reason": "not_object", "size": len(data), **(context or {})})
            return {}
        if "type" in packet and "body" in packet and not isinstance(packet.get("body"), dict):
            self.events.write_event("packet_decode_failed", {"reason": "body_not_object", "packet_type": packet.get("type"), **(context or {})})
            return {}
        return packet

    def _receive_share_request(self, peer_id: str, peer_host: str, packet: dict[str, Any]) -> None:
        """Handle an incoming share request: receive text or download a file over TLS."""
        body = packet.get("body") or {}
        transfer_info = packet.get("payloadTransferInfo") or {}
        payload_size = self._packet_payload_size(packet)
        if payload_size is None:
            self.events.write_event("share_ignored", {"device_id": peer_id, "reason": "invalid_payload_size", "payload_size": packet.get("payloadSize")})
            return
        if body.get("text"):
            text = str(body.get("text") or "")
            self.on_clipboard(text, peer_id)
            self.events.write_event("shared_text_received", {"device_id": peer_id, "length": len(text)})
            return
        if not transfer_info or "port" not in transfer_info:
            self.events.write_event("share_ignored", {"device_id": peer_id, "reason": "missing_payload"})
            return

        filename = self._safe_filename(str(body.get("filename") or f"kdeck-{int(time.time())}"))
        destination = self._unique_destination(filename)
        partial_destination = destination.with_name(f"{destination.name}.part")
        port = self._payload_port(transfer_info)
        if port is None:
            self.events.write_event("share_ignored", {"device_id": peer_id, "file": filename, "reason": "invalid_payload_port", "port": transfer_info.get("port")})
            return
        if payload_size > MAX_FILE_BYTES:
            self._record_file_failure(peer_id, filename, "file_too_large", expected=payload_size, max_size=MAX_FILE_BYTES)
            return
        if not self._has_enough_space(payload_size):
            self._record_file_failure(peer_id, filename, "not_enough_space", expected=payload_size, min_free_space=MIN_FREE_SPACE_BYTES)
            return

        for attempt in range(1 + PAYLOAD_RECEIVE_MAX_RETRIES):
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                context.load_cert_chain(str(self.cert_path), str(self.key_path))
                raw = socket.create_connection((peer_host, port), timeout=30)
                # TCP keepalive — detect dead connections faster than the TLS timeout
                raw.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                try:
                    raw.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_BYTES)
                except OSError:
                    pass
                with context.wrap_socket(raw, server_hostname=peer_id) as tls:
                    payload_fingerprint = self._peer_fingerprint(tls)
                    if not self._is_trusted_device(peer_id, payload_fingerprint):
                        payload_error = {"device_id": peer_id, "file": filename, "error": "untrusted_payload_certificate", "time": int(time.time())}
                        self._set_diagnostic("last_payload_error", payload_error)
                        self.events.write_event("file_receive_failed", payload_error)
                        return
                    tls.settimeout(30)
                    written = 0
                    deadline = time.monotonic() + FILE_RECV_TOTAL_TIMEOUT_SECONDS
                    self.incoming_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        partial_destination.unlink()
                    except FileNotFoundError:
                        pass
                    buf = bytearray(min(FILE_CHUNK_BYTES, payload_size))
                    with partial_destination.open("wb") as output:
                        while written < payload_size:
                            if time.monotonic() > deadline:
                                raise TimeoutError(f"Download exceeded overall timeout ({FILE_RECV_TOTAL_TIMEOUT_SECONDS}s)")
                            nbytes = tls.recv_into(buf, min(len(buf), payload_size - written))
                            if nbytes == 0:
                                break
                            output.write(buf[:nbytes])
                            written += nbytes
                if written != payload_size:
                    try:
                        partial_destination.unlink()
                    except OSError:
                        pass
                    raise ConnectionError(f"Payload incomplete: {written}/{payload_size}")
                partial_destination.replace(destination)
                file_event = {"device_id": peer_id, "file": destination.name, "path": str(destination), "size": written}
                self._set_diagnostic("last_file", {"status": "received", "time": int(time.time()), **file_event})
                self.events.write_event("file_received", file_event)
                if self.on_file_received:
                    self.on_file_received(file_event)
                return  # Success
            except Exception as exc:
                try:
                    partial_destination.unlink()
                except OSError:
                    pass
                if attempt < PAYLOAD_RECEIVE_MAX_RETRIES:
                    self.events.write_event("payload_receive_retry", {"device_id": peer_id, "file": filename, "error": str(exc), "attempt": attempt + 1})
                    self._log("KDE receiver payload receive failed (attempt %d/%d), retrying: %s", attempt + 1, 1 + PAYLOAD_RECEIVE_MAX_RETRIES, exc)
                    time.sleep(PAYLOAD_RECEIVE_RETRY_DELAY)
                    continue
                # Final attempt failed
                self._set_diagnostic(
                    "last_file",
                    {"device_id": peer_id, "file": filename, "status": "failed", "error": str(exc), "time": int(time.time())},
                )
                self._set_diagnostic("last_payload_error", {"device_id": peer_id, "file": filename, "error": str(exc), "time": int(time.time())})
                self.events.write_event("file_receive_failed", {"device_id": peer_id, "file": filename, "error": str(exc)})
                self._log("KDE receiver file transfer failed after %d attempts: %s", 1 + PAYLOAD_RECEIVE_MAX_RETRIES, exc)

    def _safe_filename(self, filename: str) -> str:
        return _safe_filename_standalone(filename)

    def _unique_destination(self, filename: str) -> Path:
        return _unique_destination_standalone(self.incoming_dir, filename)

    def _packet_payload_size(self, packet: dict[str, Any]) -> Optional[int]:
        return _packet_payload_size_standalone(packet)

    def _payload_port(self, transfer_info: dict[str, Any]) -> Optional[int]:
        return _payload_port_standalone(transfer_info)

    def _has_enough_space(self, payload_size: int) -> bool:
        return _has_enough_space_standalone(self.incoming_dir, payload_size, MIN_FREE_SPACE_BYTES)

    def _record_file_failure(self, peer_id: str, filename: str, reason: str, **details: Any) -> None:
        _record_file_failure_standalone(
            self._set_diagnostic, self.events.write_event,
            peer_id, filename, reason, **details,
        )

    def _network_interfaces(self) -> list[dict[str, Any]]:
        return _network_interfaces_standalone()

    def _bind_available_tcp_port(self, server: socket.socket, port_low: int = None, port_mid: int = None) -> int:
        lo = port_low if port_low is not None else TCP_PORT_MIN
        hi = port_mid if port_mid is not None else TCP_PORT_MAX
        return _bind_available_tcp_port_standalone(server, port_low=lo, port_mid=hi)

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
        return _peer_fingerprint_standalone(tls)

    def _is_trusted_device(self, peer_id: str, fingerprint: Optional[str]) -> bool:
        return _is_trusted_device_standalone(self._trusted_devices(), peer_id, fingerprint)

    def _broadcast_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str]]:
        return _broadcast_targets_standalone(interfaces)

    def _recent_discovery_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str, int]]:
        now = int(time.time())
        with self.state_lock:
            devices = list((self.diagnostics.get("discovered_devices") or {}).values())
        return _recent_discovery_targets_standalone(devices, interfaces, now, self._source_ips_for_host)

    def _trusted_direct_targets(self, interfaces: list[dict[str, Any]]) -> list[tuple[Optional[str], str, int]]:
        now = int(time.time())
        targets, events = _trusted_direct_targets_standalone(
            self._trusted_devices(),
            interfaces,
            now,
            self._source_ips_for_host,
        )
        for event in events:
            self.events.write_event(
                "trusted_device_reannounce_target",
                event,
            )
        self._set_diagnostic(
            "last_reannounce_targets",
            {
                "time": int(time.time()),
                "reason": "trusted_direct_targets",
                "targets": [{"source": source, "target": target, "port": port} for source, target, port in targets[:16]],
            },
        )
        return targets

    def _merge_direct_targets(
        self,
        first: list[tuple[Optional[str], str, int]],
        second: list[tuple[Optional[str], str, int]],
    ) -> list[tuple[Optional[str], str, int]]:
        return _merge_direct_targets_standalone(first, second)

    def _source_ips_for_host(self, host: str, interfaces: list[dict[str, Any]]) -> list[Optional[str]]:
        return _source_ips_for_host_standalone(host, interfaces)

    def _is_ignored_interface(self, name: str) -> bool:
        return _is_ignored_interface_standalone(name)

    def _interface_path_type(self, name: str) -> str:
        return _interface_path_type_standalone(name)

    def _interface_priority(self, name: str) -> int:
        return _interface_priority_standalone(name)

    def _is_usable_ipv4(self, address: Optional[str]) -> bool:
        return _is_usable_ipv4_standalone(address)

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
        self.events.write_event("discovery_received", item)
        self._set_connection_state(device_id, "discovered", "discovery_received", host=addr[0], port=addr[1])
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
        if not isinstance(trusted.get(device_id), dict):
            return
        _remember_trusted_device_metadata_standalone(
            trusted, device_id, host, identity, connected, udp_source_port,
        )
        self._write_trusted_devices(trusted)
        self.events.write_event(
            "trusted_device_metadata_updated",
            {"device_id": device_id, "host": host, "connected": connected, "udp_source_port": udp_source_port},
        )
        if connected:
            self._set_connection_state(device_id, "connected", "trusted_metadata_connected", host=host)

    def _set_diagnostic(self, key: str, value: Any) -> None:
        with self.state_lock:
            self.diagnostics[key] = value

    def set_connection_state(self, device_id: str, state: str, reason: str, **details: Any) -> None:
        """Public wrapper used by the backend when state is known outside receiver threads."""
        self._set_connection_state(device_id, state, reason, **details)

    def _set_connection_state(self, device_id: str, state: str, reason: str, **details: Any) -> None:
        device_key = device_id or self.device_id
        now = int(time.time())
        with self.state_lock:
            states = self.diagnostics.setdefault("connection_states", {})
            current = states.get(device_key) if isinstance(states, dict) else None
            current_state = current.get("state") if isinstance(current, dict) else None
            transition = state_transition(current_state, state, reason, device_key, now, **details)
            if isinstance(states, dict):
                states[device_key] = {
                    "device_id": device_key,
                    "state": state,
                    "reason": reason,
                    "time": now,
                    **details,
                }
            if transition is None:
                return
            self.diagnostics["last_state_transition"] = transition
        self.events.write_event("connection_state_changed", transition)

    def _trusted_devices(self) -> dict[str, Any]:
        return _read_trusted_devices_standalone(self.trusted_path)

    def _write_trusted_devices(self, data: dict[str, Any]) -> None:
        def _on_error(exc: OSError) -> None:
            self.events.write_event("trusted_devices_write_failed", {"error": str(exc)})
            self._log("KDE receiver trusted devices write failed: %s", exc)
        _write_trusted_devices_standalone(self.trusted_path, data, on_error=_on_error)


    def send_share_request_to_peer(
        self,
        file_path: str,
        device_id: str,
        progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """Send a file to a trusted peer: start a TLS file server, then deliver the share request via persistent or new connection."""
        def _progress(phase: str, **details: Any) -> None:
            if progress_callback:
                progress_callback({"phase": phase, **details})

        def _transfer_completed(state: dict[str, Any], expected_size: int) -> bool:
            return bool(state.get("completed")) and int(state.get("bytes_sent") or 0) >= expected_size

        def _transfer_incomplete_error(state: dict[str, Any], expected_size: int) -> dict[str, Any]:
            sent = int(state.get("bytes_sent") or 0)
            return {
                "ok": False,
                "error": {
                    "code": "transfer_incomplete",
                    "message": f"File transfer incomplete: {sent}/{expected_size} bytes sent.",
                },
                "bytes_sent": sent,
                "total_bytes": expected_size,
            }

        def _record_send_failure(code: str, message: str, stage: str = "transfer", **details: Any) -> None:
            error = diagnostic_error(code, stage, message, device_id=device_id, file=Path(file_path).name, **details)
            self._set_diagnostic("last_payload_error", error)
            self._set_diagnostic("last_error", error)

        trusted = self._trusted_devices().get(device_id)
        if not trusted:
            _progress("failed", error_code="not_trusted", error_message="Device is not trusted.")
            return {"ok": False, "error": {"code": "not_trusted", "message": "Device is not trusted."}}
        host = trusted.get("last_host")
        if not host:
            _progress("failed", error_code="unknown_host", error_message="No known host for this device.")
            return {"ok": False, "error": {"code": "unknown_host", "message": "No known host for this device."}}
        source = Path(file_path)
        if not source.is_file():
            _progress("failed", error_code="file_not_found", error_message="File not found.")
            return {"ok": False, "error": {"code": "file_not_found", "message": "File not found."}}
        file_size = source.stat().st_size
        if file_size == 0:
            _progress("failed", error_code="empty_file", error_message="File is empty.")
            return {"ok": False, "error": {"code": "empty_file", "message": "File is empty."}}
        if file_size > MAX_FILE_BYTES:
            _progress("failed", error_code="file_too_large", error_message=f"File exceeds {MAX_FILE_BYTES} bytes.")
            return {"ok": False, "error": {"code": "file_too_large", "message": f"File exceeds {MAX_FILE_BYTES} bytes."}}

        _progress("preparing", bytes_sent=0, total_bytes=file_size)
        stop_event = threading.Event()
        file_port, server_thread, _serve_state = self._serve_file_tls(source, stop_event, progress_callback=_progress)
        if file_port is None:
            _progress("failed", error_code="file_server_failed", error_message="Could not start file server.")
            return {"ok": False, "error": {"code": "file_server_failed", "message": "Could not start file server."}}

        self.events.write_event("share_send_attempt", {"device_id": device_id, "host": host, "file": source.name, "size": file_size, "port": file_port})

        # Try persistent connection first (avoids new TCP+TLS handshake)
        with self.data_lock:
            peer_link = self.peer_connections.get(device_id)
        if peer_link is not None:
            try:
                share = {
                    "type": PACKET_SHARE_REQUEST,
                    "body": {
                        "filename": source.name,
                        "numberOfFiles": 1,
                        "totalPayloadSize": file_size,
                    },
                    "payloadSize": file_size,
                    "payloadTransferInfo": {"port": file_port},
                }
                peer_link["send_queue"].put(self._encode_packet(share))
                self.events.write_event("share_send_via_persistent", {"device_id": device_id, "file": source.name, "size": file_size, "port": file_port})
                self._set_diagnostic("last_share_send", {"device_id": device_id, "file": source.name, "size": file_size, "time": int(time.time()), "via": "persistent"})
                _progress("waiting_peer", bytes_sent=0, total_bytes=file_size)
                server_thread.join(timeout=90)
                if server_thread.is_alive():
                    self._cleanup_file_server(stop_event, server_thread)
                    _record_send_failure("transfer_timeout", "File transfer timed out.", bytes_sent=int(_serve_state.get("bytes_sent") or 0), total_bytes=file_size, via="persistent")
                    _progress("failed", error_code="transfer_timeout", error_message="File transfer timed out.")
                    return {"ok": False, "error": {"code": "transfer_timeout", "message": "File transfer timed out."}}
                if not _serve_state.get("accepted"):
                    _record_send_failure("transfer_timeout", "Peer did not connect to download the file.", bytes_sent=0, total_bytes=file_size, via="persistent")
                    _progress("failed", error_code="transfer_timeout", error_message="Peer did not connect to download the file.")
                    return {"ok": False, "error": {"code": "transfer_timeout", "message": "Peer did not connect to download the file."}}
                if not _transfer_completed(_serve_state, file_size):
                    result = _transfer_incomplete_error(_serve_state, file_size)
                    _record_send_failure("transfer_incomplete", result["error"]["message"], bytes_sent=result["bytes_sent"], total_bytes=file_size, via="persistent")
                    _progress("failed", bytes_sent=result["bytes_sent"], total_bytes=file_size, error_code="transfer_incomplete", error_message=result["error"]["message"])
                    return result
                _progress("finished", bytes_sent=_serve_state.get("bytes_sent", file_size), total_bytes=file_size)
                return {"ok": True, "file": source.name, "size": file_size}
            except Exception as exc:
                self.events.write_event("share_send_persistent_failed", {"device_id": device_id, "error": str(exc)})

        # Fallback: create a new connection
        try:
            _progress("connecting", bytes_sent=0, total_bytes=file_size)
            interfaces = self._network_interfaces()
            source_ips = self._source_ips_for_host(host, interfaces)
            raw = self._connect_to_peer_control_socket(host, trusted, source_ips)
            if raw is None:
                self._cleanup_file_server(stop_event, server_thread)
                _record_send_failure("tcp_connect_failed", "Could not connect to phone.", stage="tcp", host=host)
                _progress("failed", error_code="peer_unreachable", error_message="Could not connect to phone.")
                return {"ok": False, "error": {"code": "peer_unreachable", "message": "Could not connect to phone."}}
        except OSError:
            self._cleanup_file_server(stop_event, server_thread)
            _record_send_failure("tcp_connect_failed", "Could not connect to phone.", stage="tcp", host=host)
            _progress("failed", error_code="peer_unreachable", error_message="Could not connect to phone.")
            return {"ok": False, "error": {"code": "peer_unreachable", "message": "Could not connect to phone."}}

        try:
            _progress("announcing", bytes_sent=0, total_bytes=file_size)
            hello = self._identity_packet(target_device_id=device_id)
            raw.sendall(self._encode_packet(hello))
            # Match TLS role to peer device type (same logic as _connect_to_peer)
            device_type = str(trusted.get("device_type") or "").lower()
            tls_mode = self._peer_tls_mode(device_type)
            use_tls_client = tls_mode == "client"
            if use_tls_client:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            else:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.verify_mode = ssl.CERT_NONE
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            tls = None
            tls = context.wrap_socket(
                raw,
                server_hostname=device_id if use_tls_client else None,
                server_side=not use_tls_client,
                do_handshake_on_connect=True,
            )

            # Post-TLS identity exchange (with timeout protection)
            tls.settimeout(5)
            try:
                tls.sendall(self._encode_packet(self._identity_packet(target_device_id=device_id)))
                peer_secure = self._read_tls_packet(tls)
                if peer_secure.get("type") == PACKET_IDENTITY:
                    peer_body = peer_secure.get("body") or {}
                    self._remember_trusted_device_metadata(device_id, host, peer_body, connected=True)
                    self.events.write_event("share_send_peer_identity", {"device_id": device_id, "device_name": peer_body.get("deviceName")})
            except (socket.timeout, OSError):
                self.events.write_event("share_send_no_peer_identity", {"device_id": device_id, "host": host})

            share = {
                "type": PACKET_SHARE_REQUEST,
                "body": {
                    "filename": source.name,
                    "numberOfFiles": 1,
                    "totalPayloadSize": file_size,
                },
                "payloadSize": file_size,
                "payloadTransferInfo": {"port": file_port},
            }
            tls.sendall(self._encode_packet(share))
            self.events.write_event("share_send_sent", {"device_id": device_id, "file": source.name, "size": file_size, "port": file_port})
            self._set_diagnostic("last_share_send", {"device_id": device_id, "file": source.name, "size": file_size, "time": int(time.time())})

            server_thread.join(timeout=60)
            if server_thread.is_alive():
                self._cleanup_file_server(stop_event, server_thread)
                _record_send_failure("transfer_timeout", "File transfer timed out.", bytes_sent=int(_serve_state.get("bytes_sent") or 0), total_bytes=file_size)
                _progress("failed", error_code="transfer_timeout", error_message="File transfer timed out.")
                return {"ok": False, "error": {"code": "transfer_timeout", "message": "File transfer timed out."}}
            if not _serve_state.get("accepted"):
                _record_send_failure("transfer_timeout", "Peer did not connect to download the file.", bytes_sent=0, total_bytes=file_size)
                _progress("failed", error_code="transfer_timeout", error_message="Peer did not connect to download the file.")
                return {"ok": False, "error": {"code": "transfer_timeout", "message": "Peer did not connect to download the file."}}
            if not _transfer_completed(_serve_state, file_size):
                result = _transfer_incomplete_error(_serve_state, file_size)
                _record_send_failure("transfer_incomplete", result["error"]["message"], bytes_sent=result["bytes_sent"], total_bytes=file_size)
                _progress("failed", bytes_sent=result["bytes_sent"], total_bytes=file_size, error_code="transfer_incomplete", error_message=result["error"]["message"])
                return result

            _progress("finished", bytes_sent=_serve_state.get("bytes_sent", file_size), total_bytes=file_size)
            return {"ok": True, "file": source.name, "size": file_size}
        except Exception as exc:
            self._cleanup_file_server(stop_event, server_thread)
            _record_send_failure("tls_send_failed", str(exc), stage="tls")
            _progress("failed", error_code="send_failed", error_message=str(exc))
            return {"ok": False, "error": {"code": "send_failed", "message": str(exc)}}
        finally:
            try:
                if tls is not None:
                    tls.close()
                elif raw is not None:
                    raw.close()
            except Exception:
                pass

    def _serve_file_tls(
        self,
        file_path: Path,
        stop_event: threading.Event,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> tuple[Optional[int], threading.Thread, dict[str, Any]]:
        """Start a background TLS server that streams a file to the requesting peer."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_BUFFER_BYTES)
        except OSError:
            pass
        state: dict[str, Any] = {"accepted": False, "completed": False, "bytes_sent": 0}
        # KDE Connect payload ports: 1739-1764
        bound = False
        for payload_port in range(1739, 1765):
            try:
                sock.bind(("0.0.0.0", payload_port))
                bound = True
                break
            except OSError:
                continue
        if not bound:
            # Fallback to ephemeral port
            try:
                sock.bind(("0.0.0.0", 0))
                bound = True
            except OSError:
                pass
        if not bound:
            return None, threading.Thread(), state
        port = sock.getsockname()[1]
        sock.listen(3)
        sock.settimeout(20)

        def _serve() -> None:
            conn = None
            tls_sock = None
            last_progress_time = 0.0
            last_progress_bytes = 0

            def _report_progress(force: bool = False) -> None:
                nonlocal last_progress_time, last_progress_bytes
                if not progress_callback:
                    return
                now = time.monotonic()
                sent = int(state.get("bytes_sent") or 0)
                if (
                    force
                    or sent - last_progress_bytes >= SEND_PROGRESS_MIN_BYTES
                    or now - last_progress_time >= SEND_PROGRESS_MIN_INTERVAL_SECONDS
                ):
                    progress_callback("transferring", bytes_sent=sent, total_bytes=file_size)
                    last_progress_time = now
                    last_progress_bytes = sent

            try:
                if not file_path.is_file():
                    return
                file_size = file_path.stat().st_size
                if file_size > MAX_FILE_BYTES:
                    self.events.write_event("file_serve_aborted", {"file": str(file_path), "reason": "file_too_large", "size": file_size})
                    return
                # Accept with retry — allow up to 3 connection attempts
                for attempt in range(3):
                    if stop_event.is_set():
                        return
                    try:
                        conn, _ = sock.accept()
                        state["accepted"] = True
                        _report_progress(force=True)
                    except socket.timeout:
                        self.events.write_event("file_serve_accept_timeout", {"file": str(file_path), "attempt": attempt + 1})
                        conn = None
                        continue
                    except OSError:
                        conn = None
                        return
                    # TLS handshake
                    try:
                        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        context.verify_mode = ssl.CERT_NONE
                        context.load_cert_chain(str(self.cert_path), str(self.key_path))
                        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        try:
                            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_BUFFER_BYTES)
                        except OSError:
                            pass
                        tls_sock = context.wrap_socket(conn, server_side=True, do_handshake_on_connect=True)
                        tls_sock.settimeout(30)
                        break  # TLS handshake succeeded
                    except (OSError, ssl.SSLError) as exc:
                        self.events.write_event("file_serve_tls_handshake_failed", {"file": str(file_path), "attempt": attempt + 1, "error": str(exc)})
                        try:
                            conn.close()
                        except OSError:
                            pass
                        conn = None
                        tls_sock = None
                        continue
                if conn is None or tls_sock is None:
                    return
                with file_path.open("rb") as f:
                    while not stop_event.is_set():
                        chunk = f.read(FILE_CHUNK_BYTES)
                        if not chunk:
                            break
                        tls_sock.sendall(chunk)
                        state["bytes_sent"] += len(chunk)
                        _report_progress()
                state["completed"] = True
                _report_progress(force=True)
                try:
                    tls_sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            except OSError as exc:
                self.events.write_event("file_serve_error", {"file": str(file_path), "error": str(exc)})
            finally:
                try:
                    if tls_sock is not None:
                        tls_sock.close()
                    elif conn is not None:
                        conn.close()
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass

        thread = threading.Thread(target=_serve, daemon=True)
        thread.start()
        return port, thread, state

    def _cleanup_file_server(self, stop_event: threading.Event, thread: threading.Thread) -> None:
        stop_event.set()
        thread.join(timeout=2)

    # ------------------------------------------------------------------
    # Public API wrappers (for tests and backend facade)
    # ------------------------------------------------------------------

    def flush_events(self) -> None:
        self.events.flush()

    def _write_event(self, event: str, details: dict[str, Any]) -> None:
        """Backward-compatible delegate to ``EventLogger.write_event``."""
        self.events.write_event(event, details)

    def _tail_events(self, limit: int) -> list[dict[str, Any]]:
        """Backward-compatible delegate to ``EventLogger.tail``."""
        return self.events.tail(limit)

    def write_trusted_devices(self, data: dict[str, Any]) -> None:
        self._write_trusted_devices(data)

    def trusted_devices(self) -> dict[str, Any]:
        return self._trusted_devices()

    def _connect_to_peer_control_socket(self, host: str, trusted_info: dict[str, Any], source_ips: list[Optional[str]]) -> Optional[socket.socket]:
        return _connect_to_peer_control_socket_standalone(host, trusted_info, source_ips)

    def _log(self, message: str, *args: Any) -> None:
        if self.logger:
            self.logger.info(message, *args)

"""KDEck KDE Connect protocol — constants, packet codec, and identity builder.

All functions here are stateless. The orchestrator (kdeck_kde_receiver) holds
mutable state and delegates encoding / decoding to this module.
"""

import json
import time
from typing import Any, Optional

# ── Port & protocol ──────────────────────────────────────────────
UDP_PORT = 1716
TCP_PORT_MIN = 1714
TCP_PORT_MAX = 1764
PROTOCOL_VERSION = 8
DEVICE_NAME = "KDEck"
DEVICE_TYPE = "desktop"

# ── Packet type identifiers ──────────────────────────────────────
PACKET_IDENTITY = "kdeconnect.identity"
PACKET_PAIR = "kdeconnect.pair"
PACKET_CLIPBOARD = "kdeconnect.clipboard"
PACKET_CLIPBOARD_CONNECT = "kdeconnect.clipboard.connect"
PACKET_SHARE_REQUEST = "kdeconnect.share.request"
PACKET_PING = "kdeconnect.ping"
CAPABILITIES = [
    PACKET_PING,
    PACKET_CLIPBOARD,
    PACKET_CLIPBOARD_CONNECT,
    PACKET_SHARE_REQUEST,
]

# ── Timing constants ─────────────────────────────────────────────
STARTUP_BROADCAST_DELAYS = (0, 1, 2, 5, 10, 15, 20, 25, 30)
BROADCAST_INTERVAL_SECONDS = 20
RECENT_DISCOVERY_DIRECT_SECONDS = 180
TRUSTED_DEVICE_DIRECT_SECONDS = 7 * 24 * 60 * 60
PEER_CONNECT_COOLDOWN_SECONDS = 30
TRUSTED_PEER_CONNECT_COOLDOWN_SECONDS = 5
HEARTBEAT_INTERVAL_SECONDS = 15
RECONNECT_BASE_DELAY = 2
RECONNECT_MAX_DELAY = 60

# ── Size & transfer limits ────────────────────────────────────────
MAX_PACKET_BYTES = 64 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
FILE_CHUNK_BYTES = 512 * 1024
SOCKET_BUFFER_BYTES = 4 * 1024 * 1024
MIN_FREE_SPACE_BYTES = 64 * 1024 * 1024
FILE_RECV_TOTAL_TIMEOUT_SECONDS = 600
PAYLOAD_RECEIVE_MAX_RETRIES = 2
PAYLOAD_RECEIVE_RETRY_DELAY = 3
SEND_PROGRESS_MIN_INTERVAL_SECONDS = 0.2
SEND_PROGRESS_MIN_BYTES = 1024 * 1024

# ── Event log ────────────────────────────────────────────────────
EVENT_LOG_MAX_BYTES = 2 * 1024 * 1024
EVENT_LOG_BACKUPS = 3

# ── Device types ─────────────────────────────────────────────────
ANDROID_DEVICE_TYPES = {"phone", "tablet"}

# ── Network interface classification ─────────────────────────────
IGNORED_INTERFACE_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "vmnet", "mihomo", "clash")

INTERFACE_PRIORITIES = {
    "lan": 100,
    "easytier": 80,
    "zerotier": 70,
    "tailscale": 60,
    "vpn": 40,
    "other": 10,
}


def encode_packet(packet: dict[str, Any]) -> bytes:
    """Encode a KDE Connect packet as newline-delimited JSON."""
    payload = dict(packet)
    payload["id"] = int(time.time() * 1000)
    payload.setdefault("body", {})
    return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode_packet(data: bytes) -> dict[str, Any]:
    """Decode raw bytes into a KDE Connect packet dict.

    Returns an empty dict when the data exceeds the size limit, is not valid
    JSON, or has an unexpected structure.
    """
    if len(data) > MAX_PACKET_BYTES:
        return {}
    try:
        packet = json.loads(data.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return {}
    if not isinstance(packet, dict):
        return {}
    if "type" in packet and "body" in packet and not isinstance(packet.get("body"), dict):
        return {}
    return packet


def identity_packet(
    device_id: str,
    tcp_port: Optional[int] = None,
    target_device_id: Optional[str] = None,
    target_protocol_version: Any = None,
) -> dict[str, Any]:
    """Build a kdeconnect.identity packet."""
    body: dict[str, Any] = {
        "deviceId": device_id,
        "deviceName": DEVICE_NAME,
        "deviceType": DEVICE_TYPE,
        "protocolVersion": PROTOCOL_VERSION,
        "incomingCapabilities": CAPABILITIES,
        "outgoingCapabilities": CAPABILITIES,
    }
    if tcp_port:
        body["tcpPort"] = tcp_port
    if target_device_id:
        body["targetDeviceId"] = target_device_id
    if target_protocol_version:
        body["targetProtocolVersion"] = target_protocol_version
    return {"type": PACKET_IDENTITY, "body": body}


def packet_payload_size(packet: dict[str, Any]) -> Optional[int]:
    """Extract the payload size from a share request packet, or None."""
    try:
        size = int(packet.get("payloadSize") or 0)
    except (TypeError, ValueError):
        return None
    return size if size >= 0 else None


def payload_port(transfer_info: dict[str, Any]) -> Optional[int]:
    """Extract and validate the payload port from transfer info, or None."""
    try:
        port = int(transfer_info.get("port"))
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None

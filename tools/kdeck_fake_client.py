#!/usr/bin/env python3
"""Windows/Linux/macOS development client for KDEck's minimal KDE Connect receiver."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


UDP_PORT = 1716
TCP_PORT_MIN = 1714
TCP_PORT_MAX = 1764
PROTOCOL_VERSION = 8
MAX_PACKET_BYTES = 64 * 1024
DEFAULT_TIMEOUT = 8.0
CAPABILITIES = [
    "kdeconnect.clipboard",
    "kdeconnect.clipboard.connect",
    "kdeconnect.share.request",
]


class ClientError(RuntimeError):
    pass


def default_state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "KDEckFakeClient"
    return Path.home() / ".kdeck-fake-client"


def load_or_create_device_id(state_dir: Path) -> str:
    path = state_dir / "device-id"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if 32 <= len(value) <= 38:
            return value
    value = secrets.token_hex(16)
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return value


def ensure_certificate(state_dir: Path, device_id: str, force: bool = False) -> tuple[Path, Path]:
    cert_path = state_dir / "fake-client.crt"
    key_path = state_dir / "fake-client.key"
    if not force and cert_path.exists() and key_path.exists():
        return cert_path, key_path

    openssl = find_openssl()
    if not openssl:
        raise ClientError(
            "找不到 openssl，无法生成测试证书。请安装 Git for Windows/OpenSSL，"
            "或用 --cert 和 --key 指定已有自签名证书。"
        )

    state_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "3650",
            "-subj",
            f"/CN={device_id}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return cert_path, key_path


def find_openssl() -> str | None:
    from_path = shutil.which("openssl")
    if from_path:
        return from_path
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "openssl.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "OpenSSL-Win64" / "bin" / "openssl.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "OpenSSL-Win32" / "bin" / "openssl.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def packet(packet_type: str, body: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    payload = {
        "id": int(time.time() * 1000),
        "type": packet_type,
        "body": body or {},
    }
    payload.update(extra)
    return payload


def encode_packet(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def read_packet(sock: socket.socket | ssl.SSLSocket, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    sock.settimeout(timeout)
    data = b""
    while b"\n" not in data and len(data) <= MAX_PACKET_BYTES:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    if not data:
        return {}
    if len(data) > MAX_PACKET_BYTES:
        raise ClientError(f"收到的 packet 超过 {MAX_PACKET_BYTES} bytes")
    try:
        return json.loads(data.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError as exc:
        raise ClientError(f"收到无效 JSON packet: {exc}") from exc


def identity_body(device_id: str, device_name: str, tcp_port: int | None = None, target_device_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "deviceId": device_id,
        "deviceName": device_name,
        "deviceType": "desktop",
        "protocolVersion": PROTOCOL_VERSION,
        "incomingCapabilities": [],
        "outgoingCapabilities": CAPABILITIES,
    }
    if tcp_port is not None:
        body["tcpPort"] = tcp_port
    if target_device_id:
        body["targetDeviceId"] = target_device_id
        body["targetProtocolVersion"] = PROTOCOL_VERSION
    return body


def find_available_kde_port() -> int:
    for port in range(TCP_PORT_MIN, TCP_PORT_MAX + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise ClientError(f"找不到空闲的 KDE Connect TCP 测试端口 {TCP_PORT_MIN}-{TCP_PORT_MAX}")


def discover(args: argparse.Namespace, context: "ClientContext") -> list[dict[str, Any]]:
    fake_tcp_port = args.fake_tcp_port or find_available_kde_port()
    payload = packet("kdeconnect.identity", identity_body(context.device_id, args.name, fake_tcp_port))
    replies: list[dict[str, Any]] = []
    timeout = float(args.timeout)
    if args.command != "discover":
        timeout = min(timeout, 2.0)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.settimeout(timeout)
        udp.sendto(encode_packet(payload), (args.host, UDP_PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = udp.recvfrom(65535)
            except socket.timeout:
                break
            except OSError:
                break
            try:
                reply = json.loads(data.decode("utf-8", errors="replace").strip())
            except json.JSONDecodeError:
                continue
            body = reply.get("body") or {}
            if reply.get("type") != "kdeconnect.identity":
                continue
            if body.get("deviceId") == context.device_id:
                continue
            replies.append(
                {
                    "host": addr[0],
                    "udp_source_port": addr[1],
                    "device_id": body.get("deviceId"),
                    "device_name": body.get("deviceName"),
                    "device_type": body.get("deviceType"),
                    "tcp_port": body.get("tcpPort"),
                    "protocol_version": body.get("protocolVersion"),
                }
            )
            if not args.wait_all:
                break
    return replies


def resolve_deck(args: argparse.Namespace, context: "ClientContext") -> tuple[str, int, str | None]:
    if args.port:
        return args.host, args.port, args.target_device_id
    replies = discover(args, context)
    if not replies:
        scanned = scan_kdeck_tcp_port(args, context)
        if scanned:
            return scanned
        raise ClientError("未收到 KDEck identity 回包，也没有在 1714-1764 扫到 KDEck TCP。请确认 Deck IP、KDEck 接收状态和局域网防火墙。")
    reply = replies[0]
    tcp_port = int(reply.get("tcp_port") or 0)
    if not (TCP_PORT_MIN <= tcp_port <= TCP_PORT_MAX):
        raise ClientError(f"KDEck 回包 TCP 端口无效: {tcp_port}")
    return str(reply["host"]), tcp_port, str(reply.get("device_id") or "") or None


class ClientContext:
    def __init__(self, args: argparse.Namespace):
        self.state_dir = Path(args.state_dir).expanduser()
        self.device_id = args.device_id or load_or_create_device_id(self.state_dir)
        self.cert_path: Path | None = None
        self.key_path: Path | None = None
        if args.command != "discover":
            if args.cert and args.key:
                self.cert_path = Path(args.cert).expanduser()
                self.key_path = Path(args.key).expanduser()
            else:
                self.cert_path, self.key_path = ensure_certificate(self.state_dir, self.device_id, args.regen_cert)

    def server_ssl_context(self) -> ssl.SSLContext:
        if not self.cert_path or not self.key_path:
            raise ClientError("当前命令需要 TLS 证书，请提供 --cert/--key 或安装 openssl 自动生成。")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.verify_mode = ssl.CERT_NONE
        context.load_cert_chain(str(self.cert_path), str(self.key_path))
        return context


class SecureSession:
    def __init__(self, args: argparse.Namespace, context: ClientContext):
        self.args = args
        self.context = context
        self.host, self.port, self.target_device_id = resolve_deck(args, context)
        self.tls: ssl.SSLSocket | None = None

    def __enter__(self) -> "SecureSession":
        raw = socket.create_connection((self.host, self.port), timeout=self.args.timeout)
        raw.sendall(
            encode_packet(
                packet(
                    "kdeconnect.identity",
                    identity_body(self.context.device_id, self.args.name, target_device_id=self.target_device_id),
                )
            )
        )
        self.tls = self.context.server_ssl_context().wrap_socket(raw, server_side=True, do_handshake_on_connect=True)
        deck_identity = read_packet(self.tls, self.args.timeout)
        if deck_identity.get("type") != "kdeconnect.identity":
            raise ClientError(f"TLS 后未收到 KDEck secure identity: {deck_identity}")
        self.tls.sendall(encode_packet(packet("kdeconnect.identity", identity_body(self.context.device_id, self.args.name))))
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        if self.tls:
            try:
                self.tls.close()
            except OSError:
                pass

    def send(self, payload: dict[str, Any]) -> None:
        if not self.tls:
            raise ClientError("TLS session 尚未建立")
        self.tls.sendall(encode_packet(payload))

    def read(self) -> dict[str, Any]:
        if not self.tls:
            raise ClientError("TLS session 尚未建立")
        return read_packet(self.tls, self.args.timeout)


def scan_kdeck_tcp_port(args: argparse.Namespace, context: ClientContext) -> tuple[str, int, str | None] | None:
    if args.command == "discover":
        return None
    probe_timeout = min(float(args.timeout), 0.2)
    for port in range(TCP_PORT_MIN, TCP_PORT_MAX + 1):
        try:
            with socket.create_connection((args.host, port), timeout=probe_timeout) as raw:
                raw.settimeout(probe_timeout)
                raw.sendall(encode_packet(packet("kdeconnect.identity", identity_body(context.device_id, args.name))))
                tls = context.server_ssl_context().wrap_socket(raw, server_side=True, do_handshake_on_connect=True)
                with tls:
                    deck_identity = read_packet(tls, probe_timeout)
                    body = deck_identity.get("body") or {}
                    if deck_identity.get("type") == "kdeconnect.identity" and body.get("deviceName") == "KDEck":
                        return args.host, port, str(body.get("deviceId") or "") or None
        except (OSError, ssl.SSLError, ClientError, TimeoutError):
            continue
    return None


def pair_with_deck(args: argparse.Namespace, context: ClientContext) -> dict[str, Any]:
    with SecureSession(args, context) as session:
        session.send(packet("kdeconnect.pair", {"pair": True}))
        response = session.read()
    if response.get("type") != "kdeconnect.pair" or not (response.get("body") or {}).get("pair"):
        raise ClientError(f"配对响应异常: {response}")
    return {"ok": True, "host": session.host, "port": session.port, "device_id": context.device_id}


def send_clipboard(args: argparse.Namespace, context: ClientContext) -> dict[str, Any]:
    with SecureSession(args, context) as session:
        if args.pair:
            session.send(packet("kdeconnect.pair", {"pair": True}))
            response = session.read()
            if response.get("type") != "kdeconnect.pair" or not (response.get("body") or {}).get("pair"):
                raise ClientError(f"配对响应异常: {response}")
        session.send(packet("kdeconnect.clipboard", {"content": args.text}))
    return {"ok": True, "host": session.host, "port": session.port, "text_length": len(args.text)}


class PayloadServer:
    def __init__(self, context: ClientContext, data: bytes, timeout: float):
        self.context = context
        self.data = data
        self.timeout = timeout
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error: Exception | None = None
        self.port = 0
        self.thread = threading.Thread(target=self._serve_once, name="KDEckFakePayloadServer", daemon=True)

    def start(self) -> int:
        self.thread.start()
        if not self.ready.wait(self.timeout):
            raise ClientError("payload server 启动超时")
        if self.error:
            raise ClientError(f"payload server 启动失败: {self.error}")
        return self.port

    def wait(self) -> None:
        self.thread.join(self.timeout + 2)
        if self.thread.is_alive():
            raise ClientError("KDEck 未在超时时间内连接 payload server")
        if self.error:
            raise ClientError(f"payload 发送失败: {self.error}")

    def _serve_once(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("0.0.0.0", 0))
                server.listen(1)
                server.settimeout(self.timeout)
                self.port = int(server.getsockname()[1])
                self.ready.set()
                raw, _addr = server.accept()
                with raw:
                    tls = self.context.server_ssl_context().wrap_socket(raw, server_side=True, do_handshake_on_connect=True)
                    with tls:
                        tls.settimeout(self.timeout)
                        tls.sendall(self.data)
        except Exception as exc:  # noqa: BLE001 - CLI 需要把底层 socket/SSL 错误原样汇报。
            self.error = exc
            self.ready.set()
        finally:
            self.done.set()


def send_file(args: argparse.Namespace, context: ClientContext) -> dict[str, Any]:
    file_path = Path(args.file).expanduser()
    data = file_path.read_bytes()
    payload_server = PayloadServer(context, data, args.timeout)
    payload_port = payload_server.start()
    with SecureSession(args, context) as session:
        if args.pair:
            session.send(packet("kdeconnect.pair", {"pair": True}))
            response = session.read()
            if response.get("type") != "kdeconnect.pair" or not (response.get("body") or {}).get("pair"):
                raise ClientError(f"配对响应异常: {response}")
        session.send(
            packet(
                "kdeconnect.share.request",
                {"filename": file_path.name},
                payloadSize=len(data),
                payloadTransferInfo={"port": payload_port},
            )
        )
        payload_server.wait()
    return {"ok": True, "host": session.host, "port": session.port, "file": file_path.name, "size": len(data)}


def send_bad_packet(args: argparse.Namespace, context: ClientContext) -> dict[str, Any]:
    with SecureSession(args, context) as session:
        if args.kind == "invalid-json":
            assert session.tls is not None
            session.tls.sendall(b"{not-json}\n")
        elif args.kind == "bad-body":
            session.send({"id": int(time.time() * 1000), "type": "kdeconnect.clipboard", "body": "bad"})
        elif args.kind == "oversized":
            assert session.tls is not None
            session.tls.sendall(b"x" * (MAX_PACKET_BYTES + 1) + b"\n")
        else:
            raise ClientError(f"未知 bad packet 类型: {args.kind}")
    return {"ok": True, "host": session.host, "port": session.port, "kind": args.kind}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KDEck Windows/desktop fake KDE Connect client for integration testing.")
    parser.add_argument("--state-dir", default=str(default_state_dir()), help="保存 fake client device-id 和证书的目录")
    parser.add_argument("--device-id", help="指定 fake client deviceId；默认持久化自动生成")
    parser.add_argument("--name", default="KDEck Fake Windows", help="发送给 KDEck 的设备名")
    parser.add_argument("--cert", help="自定义 TLS 证书路径")
    parser.add_argument("--key", help="自定义 TLS 私钥路径")
    parser.add_argument("--regen-cert", action="store_true", help="重新生成默认测试证书")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="网络操作超时时间，单位秒")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_target(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--host", required=True, help="Steam Deck / KDEck IP")
        subparser.add_argument("--port", type=int, help="KDEck TCP 端口；不填则先通过 UDP discovery 获取")
        subparser.add_argument("--target-device-id", help="KDEck deviceId；通常不用手动指定")
        subparser.add_argument("--fake-tcp-port", type=int, help="discovery identity 里声明的 fake client TCP 端口")
        subparser.add_argument("--wait-all", action="store_true", help="discovery 阶段等待完整超时时间并收集多个回包")
        subparser.add_argument("--timeout", type=float, help="网络操作超时时间，单位秒")

    discover_parser = subparsers.add_parser("discover", help="向指定 Deck IP 发送 UDP identity 并等待 KDEck 回包")
    discover_parser.add_argument("--host", required=True, help="Steam Deck / KDEck IP")
    discover_parser.add_argument("--fake-tcp-port", type=int, help="discovery identity 里声明的 fake client TCP 端口")
    discover_parser.add_argument("--wait-all", action="store_true", help="等待完整超时时间并收集多个回包")
    discover_parser.add_argument("--timeout", type=float, help="网络操作超时时间，单位秒")

    pair_parser = subparsers.add_parser("pair", help="通过真实 TCP/TLS 会话发送 kdeconnect.pair")
    add_target(pair_parser)

    clipboard_parser = subparsers.add_parser("clipboard", help="发送 kdeconnect.clipboard 文本")
    add_target(clipboard_parser)
    clipboard_parser.add_argument("--text", required=True, help="要发送到 KDEck 的剪贴板文本")
    clipboard_parser.add_argument("--pair", action="store_true", help="发送剪贴板前先在同一 TLS 会话里配对")

    file_parser = subparsers.add_parser("send-file", help="发送 kdeconnect.share.request 文件")
    add_target(file_parser)
    file_parser.add_argument("--file", required=True, help="要发送到 Deck Downloads 的文件")
    file_parser.add_argument("--pair", action="store_true", help="发送文件前先在同一 TLS 会话里配对")

    bad_parser = subparsers.add_parser("bad-packet", help="发送异常 packet，用于验证 KDEck 拒绝路径")
    add_target(bad_parser)
    bad_parser.add_argument("kind", choices=["invalid-json", "bad-body", "oversized"], help="异常 packet 类型")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout is None:
        args.timeout = DEFAULT_TIMEOUT
    try:
        context = ClientContext(args)
        if args.command == "discover":
            result: Any = discover(args, context)
        elif args.command == "pair":
            result = pair_with_deck(args, context)
        elif args.command == "clipboard":
            result = send_clipboard(args, context)
        elif args.command == "send-file":
            result = send_file(args, context)
        elif args.command == "bad-packet":
            result = send_bad_packet(args, context)
        else:
            parser.error(f"未知命令: {args.command}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ClientError, OSError, ssl.SSLError, subprocess.CalledProcessError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

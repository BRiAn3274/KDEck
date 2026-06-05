#!/usr/bin/env python3
"""KDEck Bluetooth RFCOMM helper — runs under system Python with PyBluez.

Usage: python kdeck_bt_helper.py <tcp_port>

Creates a Bluetooth RFCOMM server on channel 22, registers SDP, accepts
incoming connections and forwards them to localhost:<tcp_port>.
"""
import socket
import subprocess
import sys
import threading

from bluetooth import RFCOMM, BluetoothSocket

BT_CHANNEL = 22


def register_sdp(channel: int) -> None:
    subprocess.run(
        ["sdptool", "add", "--channel", str(channel), "SP"],
        capture_output=True, timeout=5,
    )


def forward(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            src.close()
        except OSError:
            pass
        try:
            dst.close()
        except OSError:
            pass


def main():
    tcp_port = int(sys.argv[1]) if len(sys.argv) > 1 else 1730
    register_sdp(BT_CHANNEL)

    bt_sock = BluetoothSocket(RFCOMM)
    bt_sock.bind(("", BT_CHANNEL))
    bt_sock.listen(5)
    print(f"BT listening on channel {BT_CHANNEL}", flush=True)

    while True:
        conn, addr = bt_sock.accept()
        print(f"BT connected from {addr}", flush=True)
        try:
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.connect(("127.0.0.1", tcp_port))
        except OSError as e:
            print(f"TCP connect failed: {e}", flush=True)
            conn.close()
            continue

        t1 = threading.Thread(target=forward, args=(conn, tcp), daemon=True)
        t2 = threading.Thread(target=forward, args=(tcp, conn), daemon=True)
        t1.start()
        t2.start()


if __name__ == "__main__":
    main()

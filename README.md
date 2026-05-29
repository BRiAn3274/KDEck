# KDEck

English | [简体中文](README.zh-CN.md)

KDEck is a Decky Loader plugin for Steam Deck game mode. It lets a phone running KDE Connect send clipboard text and files to the Steam Deck without switching to KDE Plasma desktop mode.

Author: RainsListener  
License: BSD-3-Clause

## Features

- Receive clipboard text from a phone and show it in a compact text field
- Receive files from a phone and save them to the Steam Deck `Downloads` directory
- Show the current Deck IP as a fallback for manual device entry in KDE Connect
- Show the latest received file

KDEck only focuses on receiving text and files. It does not implement notifications, SMS, remote input, media control, or the full KDE Connect desktop feature set.

When Plasma desktop mode is active, KDEck pauses its game-mode receiver and releases the KDE Connect LAN discovery port. The receiver resumes after returning to game mode. This isolation is designed to avoid interfering with the official desktop-mode KDE Connect service.

## Installation

1. Download `KDEck.zip` from GitHub Releases or CNB Releases.
2. Open Decky Loader on the Steam Deck.
3. Import and install `KDEck.zip`.
4. Open KDEck and confirm that it is receiving.

If the plugin behaves unexpectedly after an overwrite install, restart the plugin in Decky Loader and open KDEck again.

## Pairing A Phone

1. Keep the phone and Steam Deck on the same Wi-Fi network or the same hotspot when possible.
2. Open KDE Connect on the phone.
3. Find `KDEck` in the device list and start pairing.
4. After pairing, the phone can send clipboard text or files to KDEck.

If the phone cannot discover KDEck automatically, manually add the Deck IP shown in the KDEck panel. Campus networks, guest Wi-Fi, AP isolation, proxies, VPNs, and overlay networks can all affect automatic discovery.

## Usage

Send text:

1. Copy text on the phone.
2. Open KDE Connect and choose KDEck.
3. Use the clipboard sending action.
4. The KDEck text field shows the latest received text.

Send a file:

1. Share a file from the phone.
2. Choose KDE Connect.
3. Choose KDEck.
4. The file is saved to the Steam Deck `Downloads` directory.

## FAQ

### The phone cannot find KDEck

Check these first:

- The Steam Deck and phone are on the same Wi-Fi network or hotspot
- AP isolation is disabled on the network
- KDE Connect on the phone does not still have an old KDEck pairing
- KDEck is open and receiving
- The manually added IP matches the Deck IP shown by KDEck

### The phone says paired but content is not received

Unpair KDEck in the phone KDE Connect app, then pair again. Older versions may leave incompatible pairing state on the phone.

### Where are received files saved?

By default:

```text
/home/deck/Downloads
```

This is the user's `Downloads` directory in Steam Deck desktop mode.

## Current Status

KDEck is still early software. Clipboard receive and file receive have been verified on real hardware, but automatic discovery may still vary across networks. Manual IP entry remains the fallback.

KDEck uses its own device ID, certificate, and configuration directory. It does not register `org.kde.kdeconnect` and does not write to the desktop-mode KDE Connect pairing configuration.

## Attribution

KDEck's design goal and protocol compatibility are based on the KDE Connect ecosystem. KDE Connect is a cross-device connectivity project developed by the KDE community:

- Website: `https://kdeconnect.kde.org/`
- Desktop repository: `https://invent.kde.org/network/kdeconnect-kde`
- Android repository: `https://invent.kde.org/network/kdeconnect-android`

KDEck is an independent project. It is not affiliated with KDE e.V. or the KDE Connect project, and it is not an official KDE release. KDEck implements only the minimal compatible receiver needed for clipboard text and shared files. It does not include KDE Connect source code or provide the full KDE Connect feature set.

## Development

Source repositories:

- GitHub: `https://github.com/BRiAn3274/KDEck`
- CNB: `https://cnb.cool/RainsLIstener/KDEck`

Local checks:

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

Development fake client:

```bash
python tools/kdeck_fake_client.py discover --host 192.0.2.37
python tools/kdeck_fake_client.py pair --host 192.0.2.37
python tools/kdeck_fake_client.py clipboard --host 192.0.2.37 --pair --text "hello from pc"
python tools/kdeck_fake_client.py send-file --host 192.0.2.37 --pair --file ./test.txt
python tools/kdeck_fake_client.py bad-packet --host 192.0.2.37 bad-body
```

This tool is only for development verification. It simulates a minimal KDE Connect desktop client and sends packets through the real UDP, TCP, and TLS protocol path. On first run it creates its own persistent `device-id` and self-signed certificate in the local user state directory. It does not read or write desktop KDE Connect configuration.

If Windows is visible to KDEck but `discover` returns an empty array, Windows is probably blocking inbound UDP replies or routing them through a different interface. `pair`, `clipboard`, and `send-file` automatically scan KDEck TCP ports `1714-1764` as a fallback.

Connection diagnostics:

KDEck records whether the receiver is expected to run, whether it is paused by desktop mode, whether UDP/TCP listeners are active, the latest discovery, recent connection errors, recent clipboard status, and recent file status. The exported log package includes this redacted diagnostic data in `manifest.json`, making it easier to identify whether a problem is in discovery, connection, TLS, pairing, or file transfer.

Hidden developer commands:

```text
:kdeck export logs
:kdeck logs
```

Enter either command in the KDEck clipboard text field and press Enter to export a redacted log package to the Steam Deck `Downloads` directory. The command text is not saved as clipboard content.

The generated plugin package is:

```text
release/KDEck.zip
```

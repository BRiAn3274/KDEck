# KDEck

English | [简体中文](README.zh-CN.md)

KDEck is a Decky Loader plugin for Steam Deck game mode. It provides a focused KDE Connect-compatible bridge for clipboard text and file transfer, so paired phones or computers can exchange content with the Steam Deck without switching to Plasma desktop mode.

Author: RainsListener

License: BSD-3-Clause

Version: 0.9.6

## Features

- Receive KDE Connect clipboard text in the Decky quick access panel.
- Receive shared files and save them to the Steam Deck `Downloads` directory.
- Send screenshots, recordings, logs, save files, and redacted diagnostic bundles from the Deck to a paired KDE Connect device.
- Browse sendable files in a Decky-style page with categories, search, sorting, thumbnails, online/offline device status, progress, speed, and ETA.
- Pause the game-mode receiver while Plasma desktop mode is active, then resume when returning to game mode.
- Keep a separate KDEck device identity, certificate, trusted-device store, and plugin data directory.

KDEck intentionally covers only clipboard text and file transfer. It does not implement KDE Connect notifications, SMS, remote input, media control, or other full desktop features.

## Installation

1. Download `KDEck.zip` from the project release package.
2. Open Decky Loader on the Steam Deck.
3. Import and install `KDEck.zip`.
4. Open KDEck from the Decky quick access menu and confirm that the receiver is running.

If an overwrite install behaves unexpectedly, restart KDEck from Decky Loader and open the panel again.

## Pairing

1. Keep the Steam Deck and the KDE Connect device on the same Wi-Fi network or hotspot.
2. Open KDE Connect on the phone or computer.
3. Find `KDEck` and start pairing.
4. After pairing, send clipboard text or shared files to KDEck.

If automatic discovery fails, manually add the Deck IP shown in the KDEck panel. Guest Wi-Fi, AP isolation, VPNs, overlay networks, and multi-interface routing can affect KDE Connect discovery.

KDEck keeps its own identity and trusted-device store. Overwrite installs should normally preserve existing pairings. To intentionally start over, enter `:kdeck reset identity` in the KDEck text field, restart KDEck, and pair again.

## Usage

Receive clipboard text:

1. Send clipboard text from KDE Connect to `KDEck`.
2. KDEck shows the latest received text in the panel.

Receive a file:

1. Share a file to KDE Connect.
2. Choose `KDEck`.
3. The file is saved to `/home/deck/Downloads`.

Send a file from the Deck:

1. Open KDEck in the Decky sidebar.
2. Choose **Send File**.
3. Select Screenshots, Recordings, Logs, or Saves.
4. Choose a target device when more than one paired device is available.
5. Select a file or diagnostic bundle to send.

## Troubleshooting

If the device cannot discover KDEck:

- Confirm both devices are on the same network or hotspot.
- Disable AP isolation on the router if possible.
- Try manual IP entry using the address shown in KDEck.
- Remove old KDEck pairings from the KDE Connect device and pair again.
- Restart KDEck from Decky Loader after an overwrite install.

Received files are saved to:

```text
/home/deck/Downloads
```

Redacted diagnostics can be exported with hidden commands:

```text
:kdeck status
:kdeck devices
:kdeck logs
:kdeck export logs
:kdeck reset identity
```

The exported log package is designed for issue reports. It redacts sensitive paths, commands, fingerprints, clipboard content, private keys, and full device identifiers.

## SteamOS And KDE Connect Isolation

KDEck does not register `org.kde.kdeconnect` and does not write to the desktop-mode KDE Connect pairing configuration. It runs a separate game-mode receiver for the plugin.

When Plasma desktop mode is detected, KDEck pauses its receiver and releases the KDE Connect LAN discovery port. Returning to game mode lets KDEck resume. This reduces conflicts with the official desktop-mode KDE Connect service.

## Root Flag

KDEck uses the Decky `_root` flag because the backend needs to inspect Decky/game-mode process state, bind KDE Connect LAN ports, and run a small number of commands in the `deck` user session. The plugin does not restart the system, modify system services, delete user downloads, or write to the desktop KDE Connect configuration.

## Development

Repository:

- GitHub: `https://github.com/BRiAn3274/KDEck`

Recommended checks:

```bash
pnpm build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py backend/src/kdeck_kde_discovery.py backend/src/kdeck_kde_events.py backend/src/kdeck_kde_state.py backend/src/kdeck_kde_connection.py backend/src/kdeck_kde_network.py backend/src/kdeck_kde_protocol.py backend/src/kdeck_kde_tls.py backend/src/kdeck_kde_trust.py backend/src/kdeck_kde_trust_migration.py backend/src/kdeck_kde_transfer.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

On Windows, `tools/verify-release.ps1` runs the release verification flow and prints the package SHA256.

The generated package is:

```text
release/KDEck.zip
```

## Attribution

KDEck is an independent project inspired by the KDE Connect ecosystem. It is not affiliated with KDE e.V. or the KDE Connect project, does not bundle KDE Connect source code, and implements only the compatibility needed for clipboard text and file transfer.

Useful references:

- `https://kdeconnect.kde.org/`
- `https://invent.kde.org/network/kdeconnect-kde`
- `https://invent.kde.org/network/kdeconnect-android`

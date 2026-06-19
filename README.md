# KDEck

English | [简体中文](README.zh-CN.md)

KDEck is a Decky Loader plugin for Steam Deck game mode. It lets a KDE Connect device send clipboard text and files to the Steam Deck without switching to KDE Plasma desktop mode.

Author: RainsListener  
License: BSD-3-Clause

## Features

- Receive clipboard text from a phone and show it in a compact text field
- Receive files from a phone and save them to the Steam Deck `Downloads` directory
- Send files from the Steam Deck to a KDE Connect device: browse screenshots, recordings, logs, and save files with search, sorting, filtering, thumbnails, live progress, speed, and ETA
- Send a redacted diagnostic bundle directly from the Logs page
- Show the current Deck IP as a fallback for manual device entry in KDE Connect
- Show the latest received file
- Native on-screen keyboard support via `@decky/ui` TextField in both the QAM panel and the send-file route page

KDEck focuses on clipboard text and file transfer in both directions. It does not implement notifications, SMS, remote input, media control, or the full KDE Connect desktop feature set.

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

KDEck keeps its own KDE Connect device identity, certificate, and trusted-device store. After an overwrite install or uninstall/reinstall, already paired phones or computers should normally keep working without unpairing first. To intentionally clear KDEck identity and pairings, use the hidden command `:kdeck reset identity`, then restart KDEck and pair again.

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

Send a file from the Deck to a phone:

1. Open the KDEck panel in the Decky sidebar.
2. Choose "Send File" to open the file management page.
3. Select a category (Screenshots / Recordings / Logs / Saves), then search, sort, or filter the list.
4. Choose a target device if multiple are available, then select a file to send.
5. KDEck shows the current transfer phase, sent bytes, speed, and estimated remaining time.

Send diagnostics:

1. Open "Send File" and switch to the Logs page.
2. Choose "Send Diagnostics".
3. KDEck exports the redacted log bundle and sends the zip through the same tracked transfer flow.

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

To reset from the KDEck side, enter `:kdeck reset identity` in the KDEck text field and press Enter. This removes KDEck's device ID, certificate, private key, trusted-device store, and preferred send target. Restart KDEck and pair devices again after using it.

### Where are received files saved?

By default:

```text
/home/deck/Downloads
```

This is the user's `Downloads` directory in Steam Deck desktop mode.

## Current Status

KDEck is under active development. Clipboard receive, file receive, and file send (screenshots, recordings, logs, saves) have been verified on real hardware with multiple phone models. Automatic discovery works on most home Wi-Fi networks; manual IP entry remains the fallback for restricted or multi-interface environments.

KDEck uses its own device ID, certificate, and configuration directory. It does not register `org.kde.kdeconnect` and does not write to the desktop-mode KDE Connect pairing configuration.

## Attribution

KDEck's design goal and protocol compatibility are based on the KDE Connect ecosystem. KDE Connect is a cross-device connectivity project developed by the KDE community:

- Website: `https://kdeconnect.kde.org/`
- Desktop repository: `https://invent.kde.org/network/kdeconnect-kde`
- Android repository: `https://invent.kde.org/network/kdeconnect-android`

KDEck is an independent project. It is not affiliated with KDE e.V. or the KDE Connect project, and it is not an official KDE release. KDEck implements only the minimal compatible receiver needed for bidirectional clipboard text and file transfer. It does not include KDE Connect source code or provide the full KDE Connect feature set.

## Development

Source repositories:

- GitHub: `https://github.com/BRiAn3274/KDEck`
- CNB: `https://cnb.cool/RainsLIstener/KDEck`

Local checks:

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py tools/kdeck_fake_client.py
ruff check
python tools/package_release.py
```

Development fake client:

```bash
python tools/kdeck_fake_client.py discover --host 192.0.2.37
python tools/kdeck_fake_client.py pair --host 192.0.2.37
python tools/kdeck_fake_client.py clipboard --host 192.0.2.37 --pair --text "hello from pc"
python tools/kdeck_fake_client.py send-file --host 192.0.2.37 --pair --file ./sample.txt
python tools/kdeck_fake_client.py bad-packet --host 192.0.2.37 bad-body
```

This tool is only for development verification. It simulates a minimal KDE Connect desktop client and sends packets through the real UDP, TCP, and TLS protocol path. On first run it creates its own persistent `device-id` and self-signed certificate in the local user state directory. It does not read or write desktop KDE Connect configuration.

If Windows is visible to KDEck but `discover` returns an empty array, Windows is probably blocking inbound UDP replies or routing them through a different interface. `pair`, `clipboard`, and `send-file` automatically scan KDEck TCP ports `1714-1764` as a fallback.

Connection diagnostics:

KDEck records whether the receiver is expected to run, whether it is paused by desktop mode, whether UDP/TCP listeners are active, the latest UDP discovery source, recent TCP success/failure, recent TLS success/failure, recent pair state, trusted-device reannounce targets, recent clipboard status, recent file status, send-job state, recent payload transfer errors, and connection-state transitions. Event logs include `event`, `stage`, `device_id`, and `time`; repeated high-frequency errors are rate limited, and sensitive path, command, and fingerprint fields are redacted. The exported log package includes redacted diagnostics in `manifest.json` and `status-snapshot.json`, making it easier to identify whether a problem is in discovery, connection, TLS, pairing, or file transfer.

Hidden developer commands:

```text
:kdeck help
:kdeck status
:kdeck devices
:kdeck reannounce
:kdeck export logs
:kdeck logs
:kdeck share logs
:kdeck reset identity
:kdeck update <https-url> <sha256>
```

Enter one command in the KDEck clipboard text field and press Enter, or double-click the "Sync Text" button. These commands are intentionally hidden so normal users still see the field as a simple clipboard display, while testers can use it as a small diagnostic console. The command text is not saved as clipboard content.

- `:kdeck help` lists available hidden commands.
- `:kdeck status` shows the receiver diagnostic summary.
- `:kdeck devices` shows discovered and trusted device counts.
- `:kdeck reannounce` sends an immediate trusted-device reannounce.
- `:kdeck logs` and `:kdeck export logs` export a redacted log package to the Steam Deck `Downloads` directory.
- `:kdeck share logs` also exports logs, but does not directly send them back to a phone or computer. KDEck is an isolated receiver and does not keep a reliable reverse-send session; using desktop KDE Connect for this would reintroduce the desktop service dependency KDEck avoids.
- `:kdeck reset identity` clears KDEck's managed KDE Connect identity, certificate, trusted-device store, and preferred send target. Use it only when you want to pair from scratch.
- `:kdeck update <https-url> <sha256>` downloads and installs a development update package. The URL must use HTTPS and the SHA256 checksum must match the downloaded zip.

The log package can be attached to a GitHub issue. Bug report and test report templates are available in the repository.

The generated plugin package is:

```text
release/KDEck.zip
```

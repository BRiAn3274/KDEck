# KDEck

English | [简体中文](README.zh-CN.md)

<img width="1976" height="1233" alt="KDEck主界面" src="https://github.com/user-attachments/assets/4e553d66-6273-4e4c-936a-f082b70823d7" />

<img width="1865" height="1167" alt="KDEck发送页面" src="https://github.com/user-attachments/assets/e4ea8abf-7560-41d0-a986-382343c16955" />

KDEck is a Decky Loader plugin for Steam Deck game mode.

It implements a small KDE Connect-compatible receiver for two use cases:

- clipboard text
- file transfer

KDEck is not a full KDE Connect replacement. It does not implement
notifications, SMS, remote input, media control, or desktop integration.

Author: RainsListener

License: BSD-3-Clause

Version: 0.9.6

## Supported Functions

- Receive clipboard text from a paired KDE Connect device.
- Receive files shared from a paired KDE Connect device.
- Save received files to `/home/deck/Downloads`.
- Send screenshots, recordings, logs, save files, and diagnostic bundles from
  the Steam Deck to a paired KDE Connect device.
- Show target device status, file progress, transfer speed, and estimated
  remaining time.
- Pause the KDEck game-mode receiver when Plasma desktop mode is detected.

## Limits

- KDEck uses its own device ID, certificate, trusted-device store, and plugin
  data directory.
- KDEck does not register `org.kde.kdeconnect`.
- KDEck does not write to the desktop-mode KDE Connect pairing configuration.
- KDEck does not modify system services.
- KDEck does not delete files from the user downloads directory.
- KDEck only supports the KDE Connect behavior needed for clipboard text and
  file transfer.

## Installation

1. Download `KDEck.zip` from the release package.
2. Open Decky Loader on the Steam Deck.
3. Import and install `KDEck.zip`.
4. Open KDEck from the Decky quick access menu.

After an overwrite install, restart KDEck from Decky Loader if the panel shows
stale state.

## Pairing

1. Put the Steam Deck and the KDE Connect device on the same Wi-Fi network or
   hotspot.
2. Open KDE Connect on the phone or computer.
3. Select `KDEck`.
4. Accept the pairing request.

If discovery does not work, manually add the Steam Deck IP address shown in the
KDEck panel. Guest Wi-Fi, AP isolation, VPNs, overlay networks, 和 routing
rules can prevent KDE Connect discovery.

To reset KDEck identity and pairing data, enter this command in the KDEck text
field and restart the plugin:

```text
:kdeck reset identity
```

## File Locations

Received files:

```text
/home/deck/Downloads
```

Plugin data is stored in the Decky plugin data directory. KDEck keeps this data
separate from desktop-mode KDE Connect.

## Hidden Diagnostic Commands

The panel text field accepts these diagnostic commands:

```text
:kdeck status
:kdeck devices
:kdeck logs
:kdeck export logs
:kdeck reset identity
```

Diagnostic exports are intended for issue reports. They redact sensitive paths,
commands, fingerprints, clipboard content, private keys, 和 full device
identifiers.

## Root Flag

KDEck uses the Decky `_root` flag for backend process-state checks, managing the
KDEck receiver process, and running limited commands in the `deck` user session.

The plugin does not restart the system, modify system services, delete user
downloads, or write to the desktop-mode KDE Connect configuration.

## Development Checks

Recommended local checks:

```bash
pnpm build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py backend/src/kdeck_kde_discovery.py backend/src/kdeck_kde_events.py backend/src/kdeck_kde_state.py backend/src/kdeck_kde_connection.py backend/src/kdeck_kde_network.py backend/src/kdeck_kde_protocol.py backend/src/kdeck_kde_tls.py backend/src/kdeck_kde_trust.py backend/src/kdeck_kde_trust_migration.py backend/src/kdeck_kde_transfer.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

On Windows, the release check can also be run with:

```powershell
tools/verify-release.ps1
```

The release package is generated at:

```text
release/KDEck.zip
```

## Acknowledgements

The send page layout and Decky-style interaction model were reviewed against
other open-source Decky plugins, including:

- `https://github.com/chenx-dust/DeckyClash`
- `https://github.com/jinzhongjia/decky-music`

These projects were used as UI references. KDEck does not include their source
code.

## Project Notes

KDEck is an independent project that interoperates with a limited part of the
KDE Connect protocol. It is not affiliated with KDE e.V. or the KDE Connect
project and does not bundle KDE Connect source code.

References:

- `https://kdeconnect.kde.org/`
- `https://invent.kde.org/network/kdeconnect-kde`
- `https://invent.kde.org/network/kdeconnect-android`

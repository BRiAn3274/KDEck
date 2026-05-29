# Third Party Notices

KDEck is distributed under BSD-3-Clause. See `LICENSE`.

## KDE Connect

KDEck is inspired by and compatible with a small part of the KDE Connect ecosystem:

- Website: `https://kdeconnect.kde.org/`
- Desktop repository: `https://invent.kde.org/network/kdeconnect-kde`
- Android repository: `https://invent.kde.org/network/kdeconnect-android`

KDE Connect is developed by the KDE community. KDEck is an independent project and is not affiliated with, endorsed by, or maintained by KDE e.V. or the KDE Connect project.

KDEck does not bundle KDE Connect source code. It implements only the minimal receiver behavior needed for KDE Connect-compatible pairing, clipboard receive, and file receive.

## Runtime Dependencies Not Bundled

KDEck keeps its game mode receiver separate from the SteamOS desktop KDE Connect pairing data. Some legacy backend diagnostics can call KDE Connect components already installed on SteamOS:

- `kdeconnectd`
- `kdeconnect-cli`
- KDE Connect DBus interfaces

These components are not copied into this plugin package. Their licenses and security updates are provided by the operating system packages. The ordinary user-facing receive path uses KDEck's own minimal LAN receiver and saves incoming files to `/home/deck/Downloads`.

## JavaScript Dependencies

The release package includes the compiled Decky frontend output from the dependencies declared in `package.json`, including Decky UI/API packages, React type packages used at build time, Rollup, TypeScript, `tslib`, and `react-icons`.

Use `pnpm list --depth -1` in the project directory to inspect the exact dependency versions installed for a build.

## Protocol Boundary

KDEck implements only the small KDE Connect-compatible LAN receiver surface needed for pairing, clipboard receive, and file receive:

- `kdeconnect.identity`
- `kdeconnect.pair`
- `kdeconnect.clipboard`
- `kdeconnect.clipboard.connect`
- `kdeconnect.share.request`

It does not provide notifications, SMS, remote input, media control, or the full KDE Connect desktop feature set.


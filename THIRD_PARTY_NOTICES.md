# Third Party Notices

KDEck is distributed under BSD-3-Clause. See `LICENSE`.

## Runtime Dependencies Not Bundled

KDEck calls the KDE Connect components already installed on SteamOS:

- `kdeconnectd`
- `kdeconnect-cli`
- KDE Connect DBus interfaces

These components are not copied into this plugin package. Their licenses and security updates are provided by the operating system packages.

## JavaScript Dependencies

The release package includes the compiled Decky frontend output from the dependencies declared in `package.json`, including Decky UI/API packages, React type packages used at build time, Rollup, TypeScript, `tslib`, and `react-icons`.

Use `pnpm list --depth -1` in the project directory to inspect the exact dependency versions installed for a build.

## Protocol Boundary

KDEck does not bundle or reimplement the KDE Connect protocol. Clipboard and file transfer are delegated to the system KDE Connect daemon and CLI/DBus layer.


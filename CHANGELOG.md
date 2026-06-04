# Changelog

## 0.5.3 - 2026-05-30

- Added send-file-to-phone feature: browse Steam screenshots from the Decky panel and send them to a paired phone via KDE Connect share.request.
- Backend: `list_steam_screenshots()` scans `/home/deck/.local/share/Steam/userdata` for screenshot files.
- Backend: `send_file_to_phone()` connects to a trusted phone over TLS and sends a share.request with a temporary TLS file server for the phone to download.
- Frontend: dual-view layout with a "Send File" button that switches to a screenshot browser page. Back button returns to the main panel.
- Removed placeholder `defaults/defaults.txt` per Decky Plugin Store review requirements.
- Version bumped to `0.5.3`.

## 0.5.2 - 2026-05-30

- Frontend version fix: `APP_VERSION` now matches `package.json` at 0.5.2.
- Auto-accept pairing: non-trusted devices are now auto-accepted directly instead of being stored as pending_pair. Connection experience matches v0.4.2 and earlier.
- README status descriptions updated to reflect current maturity. `STORE_SUBMISSION.md` verification steps now include ruff check.
- Branch cleanup: removed stale remote tracking and local branches.

## 0.5.1 - 2026-05-30

- Stability convergence: default auto-accept pairing restored. New device connection experience matches previous versions. Reverted unfinished manual confirmation experiment.
- Diagnostic log fix: event buffer is flushed before log export, ensuring the zip contains the latest TCP/TLS/pair events.
- Repo cleanup: removed `test.txt` accidentally tracked in version control.
- CI retained: GitHub Actions test workflow continues to be maintained for automated testing.
- Frontend structure retained: types.ts / i18n.ts / utils.ts / components.tsx split kept without UI behavior changes.
- Safety fixes retained: `_tail_file()` seek-to-end scanning, `_is_owned_plugin_dir()` exact name matching, clipboard fallback chain, thread lock protection, and join cleanup.

## 0.4.3 - 2026-05-30

- Pairing security hardening: first-time pairing no longer auto-accepted. User must confirm "Accept Pair" on Deck before writing to trusted devices whitelist; previously paired devices continue to auto-accept.
- Thread safety: receiver TCP port, connection cooldown dict, and anonymous connection threads now protected by locks to avoid race conditions.
- Anonymous connection threads now tracked for management; properly joined on receiver stop to prevent socket leaks.
- Event log changed to in-memory buffered writes (64 entries or flush on stop) to reduce eMMC/SD card write amplification.
- Clipboard read now uses `wl-paste`/`wl-copy` → `xclip` → tkinter fallback chain for broader environment compatibility.
- `_tail_file` changed to seek-to-end scanning instead of full file reads, reducing memory overhead on large log files.
- Interface classification logic (`interface_path_type` / `interface_priority` / `is_usable_ipv4`) extracted as module-level functions, eliminating duplicate code between `kdeck_backend.py` and `kdeck_kde_receiver.py`.
- `_is_owned_plugin_dir` changed to exact directory name matching (`== "kdeck"` or `startswith("kdeck-")`) to avoid accidentally removing unrelated directories containing "kdeck" in their names.
- Backend error messages switched to English fallback. Frontend `errors` dictionary now has complete Chinese-English bilingual mappings. Non-Chinese users no longer see Chinese error messages.
- Frontend split into five files: `types.ts` / `i18n.ts` / `utils.ts` / `components.tsx` / `index.tsx`.
- Added ruff lint configuration (`pyproject.toml`) and GitHub Actions CI (`test.yml`). All code passes lint.
- Version bumped to `0.4.3`.

## 0.4.2 - 2026-05-30

- Added GitHub Issues templates: Bug report and Test report for collecting Deck model, SteamOS channel, phone OS, KDE Connect version, network environment, and log packages.
- Clipboard hidden dev commands expanded to `:kdeck help`, `:kdeck status`, `:kdeck devices`, `:kdeck reannounce`, `:kdeck logs`, `:kdeck export logs`, and `:kdeck share logs`.
- `:kdeck share logs` exports redacted logs to Downloads and explicitly notes that the isolated receiver does not directly reverse-send logs to a phone or computer.
- Diagnostic summary now includes recent TCP successes, TLS successes/failures, pairing, trusted-device reannounce, and file payload error info.
- Receiver adds trusted-device reannounce cadence during the first 30 seconds after start; immediately triggers a trusted-device reannounce upon returning from desktop mode to game mode.
- README / README.zh-CN updated with hidden command usage, limitations, and diagnostic field descriptions.
- Version bumped to `0.4.2`.

## 0.4.1 - 2026-05-30

- Default `README.md` changed to English homepage. Added `README.zh-CN.md` for Chinese documentation.
- Plugin frontend now has lightweight bilingual text, auto-selecting Chinese or English based on `navigator.language`. Chinese environments show Chinese; other environments show English.
- Frontend adds English fallback display for common backend error codes, reducing raw Chinese error messages in English interfaces.
- Release packaging script now includes `README.zh-CN.md`.
- Version bumped to `0.4.1`.

## 0.4.0 - 2026-05-30

- Paired device's most recent host, UDP source port, TCP port, device name, and connection time are now written to trusted device state for targeted reannounce after receiver restart or game mode recovery.
- Paired device active connection cooldown reduced from 30 seconds to 5 seconds for regular devices, reducing the chance of fast reconnection being blocked by cooldown after network jitter.
- Discovery broadcast now merges short-term discovered devices and persistent trusted device targets. Even after receiver restart, directional identity is preferentially sent to the most recent trusted devices.
- `managed_kde` status now includes `diagnostic_summary`, centrally reporting whether the receiver is expected to run, whether it is paused, whether UDP/TCP is working, whether devices are discovered, whether paired, and recent clipboard and file status.
- Added tests for paired device reconnection, trusted device metadata, and diagnostic summary.
- Version bumped to `0.4.0`.

## 0.3.9 - 2026-05-30

- Added `tools/kdeck_fake_client.py`, a Windows/desktop development fake client that tests discovery, pair, clipboard, share.request file sending, and malformed packet rejection paths through real UDP, TCP, and TLS flows.
- Fake client uses its own persistent `device-id` and self-signed certificate by default. Does not read or write KDE Connect desktop configuration.
- Fake client auto-scans KDEck TCP `1714-1764` ports as a fallback when Windows cannot receive UDP identity replies.
- Clipboard text field now supports hidden dev commands: type `:kdeck export logs` or `:kdeck logs` and press Enter to export a redacted log package to the Steam Deck `Downloads` directory.
- Clipboard text sent from phone continues to be written into the KDEck text field and simultaneously attempts to write to the Deck's current graphical session clipboard.
- README updated with fake client usage instructions.
- Version bumped to `0.3.9`.

## 0.3.8 - 2026-05-29

- Isolate local desktop-mode KDE Connect discovery: ignore identities from Deck's own IP or loopback, no longer showing the local desktop client as an external device in game mode.
- Incoming TCP now rejects connections from local sources, preventing desktop KDE Connect processes from connecting back to the KDEck receiver from the same machine.
- After phone sends clipboard, backend continues to save to KDEck text field while also attempting to write to the Deck's graphical session clipboard. Frontend uses existing polling toast, no new UI entry.
- Optimized hidden log export: includes manifest, receiver rotated logs, recent Decky main logs, redacted clipboard summary, redacted transfer history, and redacted trusted device summary.
- Log export no longer includes `device-id`, `trusted-devices.json`, certificates, or private keys by default, reducing troubleshooting package leak risk.
- Added tests for local isolation, clipboard sync, and log export redaction.
- Version bumped to `0.3.8`.

## 0.3.7 - 2026-05-29

- Without changing existing pairing acceptance policy, first strengthen protocol input protection and regression tests.
- Packet decoding now enforces maximum size, JSON structure validation, and structured rejection events to prevent malformed packets from entering protocol handling.
- File receive now validates `payloadSize`, enforces 2 GiB limit, checks available disk space, and writes to `.part` temporary file before replacing the final file.
- File receive failure events now broken down into file too large, insufficient space, incomplete payload, invalid payload size, and TLS/write failure.
- Receiver event log now has simple rotation: `receiver-events.jsonl` keeps 3 historical backups when exceeding 2 MiB.
- Added tests for packet limits, file protection, `.part` avoidance, recent discovery directional reply, and log rotation.
- Version bumped to `0.3.7`.

## 0.3.6 - 2026-05-28

- Auto-pause KDEck receiver when Plasma desktop mode is detected, releasing the KDE Connect LAN discovery port to avoid interfering with the official desktop mode KDE Connect.
- After leaving desktop mode, if the plugin is still in desired-receive state, the KDEck receiver automatically resumes.
- Discovery startup broadcast changed to `0s, 1s, 2s, 5s, 10s, 15s`, with regular broadcast interval changed to 20 seconds.
- Added short-term directional identity reply for recently discovered devices, improving reconnection stability under network jitter or multi-interface environments.
- Version bumped to `0.3.6`.

## 0.3.5 - 2026-05-28

- Prepared source structure for Decky plugin store: backend modules moved to `backend/src`, root retains Decky Python entry point `main.py`.
- Release packaging script now includes `backend/src`, continuing to generate a manually importable `release/KDEck.zip`.
- README simplified for general users, reducing internal implementation and debugging details.
- Version bumped to `0.3.5`.

## 0.3.4 - 2026-05-28

- Cleaned real private LAN IP examples from public repository, replacing with documentation-only addresses or textual placeholders to avoid exposing local network information.
- Version bumped to `0.3.4`.

## 0.3.3 - 2026-05-28

- Organized GitHub / CNB public repository metadata: added `repository`, `bugs`, `homepage`. Updated `plugin.json` publish description and image URL.
- Removed Decky template legacy C backend example files and VS Code deployment scripts to avoid misleading public repository visitors.
- README added source repository and release package distribution notes, clarifying that `release/` and `dist/` are not committed to the source repository.
- Version bumped to `0.3.3`.

## 0.3.2 - 2026-05-28

- Corrected Android path based on 0.3.1 hardware logs: phone discovery, Deck reply, and Deck active TCP all work, but `tls_mode=client` still times out during TLS handshake.
- Android phone active connection path reverted to TLS server mode closer to the old version. Desktop KDE Connect keeps the same server mode.
- Android discovery only replies to the phone's source port, no longer additionally replies to UDP `1716`. Desktop keeps source port + `1716` dual reply.
- Connection logs now include device type, protocol version, TLS mode, TCP/TLS stage duration, exception type, identity reply strategy, and secure identity content for continued Android debugging.
- Version bumped to `0.3.2`.

## 0.3.1 - 2026-05-28

- Corrected Android connection strategy based on hardware logs: 0.3.0 could receive phone discovery and reply correctly, but the phone did not actively connect to the Deck TCP port.
- Android phone path restored active connection to phone `1716`, but TLS handshake switched to client mode. Desktop KDE Connect keeps original server mode to avoid impacting already-working PC file transfer.
- `peer_tls_handshake_start/done` logs now include `tls_mode` to distinguish between Android client mode and desktop server mode.
- Version bumped to `0.3.1`.

## 0.3.0 - 2026-05-28

- Unified network path priority for the receiver: same Wi-Fi / wired LAN first, then EasyTier, ZeroTier, Tailscale, finally regular VPN / other interfaces. Filtered out `lo`, Docker, virtual bridges, proxy reserved ranges, and other invalid addresses.
- Discovery broadcast, identity reply, active TCP connection, and frontend `Deck IP` all use the same path selection logic, reducing source IP mis-selection in multi-interface environments.
- Android phone discovery no longer triggers active connection to phone `1716` by default. Instead replies with identity and waits for the phone to connect to the Deck TCP port. Desktop KDE Connect keeps the active connection path.
- Discovery logs now include path type. `peer_connect_skipped` records the skip reason for Android compatibility mode, making it easier to judge whether the connection entered incoming TCP.
- Version bumped to `0.3.0`.

## 0.2.9 - 2026-05-28

- When replying identity to a specific phone, the receiver now prefers a same-subnet source IP (e.g. `192.0.2.144 -> 192.0.2.153`), avoiding replies from wrong source addresses like ZeroTier/EasyTier in multi-interface environments.
- `identity_reply_sent` log now includes the actual sent source IP. Active TCP connections also bind to the same-subnet source IP.
- Receiver now has phased connection logs: incoming TCP, plaintext identity, TLS handshake start/done, secure identity send/receive, making it easier to identify where Android KDE Connect gets stuck.
- Frontend further compressed: title shows version number, bottom version area removed, `Deck IP` shows only address, received file changed to single line `File: KDEck.zip -> Downloads`.

## 0.2.8 - 2026-05-28

- Frontend connection area changed to unified row layout, fixing misalignment between `Device` row and `Deck IP` row in the Decky panel.
- `Receive Directory` moved from connection area to new `Received Files` module with `Recent File`, stably showing the most recent file receive result.
- File receive notification now based on backend `last_file` state, no longer relying on the recent event list that gets overwritten by discovery logs.
- After receiving phone identity via discovery, reply is now preferentially sent to the source port, with UDP 1716 kept as fallback, improving Android KDE Connect discovery and pairing probability.
- Identity packets now uniformly carry the current actual TCP port. Active TCP connections to the same device now have a short cooldown to reduce duplicate TLS connection failure interference.
- Noted 0.2.8 hardware issue: content exceeding panel height is touch-scrollable but gamepad buttons cannot scroll to the bottom. Decky focus navigation and scroll layout needs future adjustment.

## 0.2.7 - 2026-05-28

- Frontend device row reverted to Decky `Field` alignment, fixing misalignment with Deck IP and receive directory.
- Device row now only shows device name, no longer showing status text like "waiting to pair". Status dot follows device name: green for connected, dimmed for disconnected or connecting.
- Clipboard input field on focus or click attempts to invoke the Steam Deck virtual keyboard interface while keeping normal input focus behavior.
- Noted that Android KDE Connect still cannot discover KDEck under current non-hotspot same-subnet conditions. Further debugging needed based on network path and receiver logs.

## 0.2.6 - 2026-05-28

- Fixed 0.2.4/0.2.5 pairing regression: `kdeconnect.pair` no longer rejected when TLS peer certificate fingerprint is missing, preventing KDE Connect clients from being stuck at `Pair requested`.
- Pairing trust policy changed to prefer certificate fingerprint. When fingerprint is unavailable, records `device_id` trust mode and writes an event log.
- Frontend connection area simplified: removed top version row, merged status and device into single `Device` row with green/yellow/gray status dot.
- Device name display now truncated to prevent long device names from stretching the Decky panel.

## 0.2.5 - 2026-05-28

- Project renamed: `DeckyLink` unified to `KDEck`, including plugin display name, KDE Connect device name, frontend title, README, third-party notices, and release package directory.
- Python backend files renamed to `kdeck_backend.py` and `kdeck_kde_receiver.py`. Packaging script updated accordingly.
- Release package changed to `release/KDEck.zip`, with zip internal top-level directory changed to `KDEck/`.

## 0.2.4 - 2026-05-27

- Receiver saves peer certificate SHA-256 fingerprint after pairing. Clipboard and file receive now require matching `deviceId + certificate fingerprint`. Untrusted devices are only allowed to initiate pairing.
- Old fingerprint-less pairing records no longer shown as valid pairings. Upgrading from 0.2.3 or earlier requires re-pairing with `KDEck`.
- TCP listen port changed to auto-select an available port within the KDE Connect `1714-1764` range. Identity, status, and logs all use the actual port.
- Receiver `running` status now based on actual UDP/TCP listen state. Stop closes sockets and waits for threads to exit, reducing residual listeners after reload or overwrite install.
- `stop_daemon()` changed to only stop KDEck-recorded processes with the `KDECK_MANAGED_DAEMON=1` marker, no longer globally `pkill kdeconnectd`.
- Frontend version number now shown in the "Connection" section in addition to the bottom area to avoid the bottom area being invisible in the Decky panel.
- Added `packageManager: pnpm@9.15.9`. Added tests for receiver trust validation, dynamic port, filename sanitization, and daemon stop protection.

## 0.2.3 - 2026-05-27

- Corrected file receive test record: new version file receive re-tested and confirmed working. Previous report of "phone shows no completion, Deck didn't receive file" was from old version mis-testing.
- README updated to record current verification status: clipboard receive and phone file sending to `/home/deck/Downloads` both verified working.

## 0.2.2 - 2026-05-27

- Recorded a file receive anomaly test result: phone KDE Connect sending a file to `KDEck` showed no completion prompt, and Deck's `/home/deck/Downloads` did not receive the file.
- This record was corrected in 0.2.3: the anomaly was from an old version mis-test and does not represent the new version's file receive status.

## 0.2.1 - 2026-05-27

- Enhanced `KDEck` isolated receiver LAN discovery: after startup, broadcasts at `0s, 2s, 5s, 10s` intensive intervals, then every 30 seconds.
- Discovery broadcast changed to bind source IP per local IPv4 interface, targeting `255.255.255.255` and each interface's own broadcast address.
- After receiving phone `kdeconnect.identity`, immediately replies with `KDEck` identity. Falls back to UDP identity reply when active TCP connection to phone fails.
- Backend status now includes UDP/TCP listen state, listen port, current IP list, interface list, recently discovered phones, recent discovery send/receive, recent connection failures, recent clipboard length, and recent file receive results.
- Receiver JSONL log now includes start/stop, certificate, UDP/TCP bind, discovery, connection attempt, pairing, clipboard, and file receive events.
- Frontend connection area now shows `phone name` as simplified status. Bottom area now shows `KDEck v0.2.1` version number.

## 0.2.0 - 2026-05-27

- Connection status changed to a single summary, directly showing device name and availability, avoiding frontend misjudgment from separating backend and device.
- Added Deck IP display, prioritizing EasyTier, ZeroTier, Tailscale, and wireless interfaces, making it easier to manually add devices from the phone.
- Added isolated `KDEck` KDE Connect-compatible receiver using independent device ID, certificate, and configuration directory.
- Phone KDE Connect can separately pair with the `KDEck` device. Subsequent "send clipboard" writes to the KDEck text field.
- Added phone KDE Connect file receive, supporting `kdeconnect.share.request` payload download and save to `/home/deck/Downloads`.
- Added receiver event log recording pairing, clipboard, and file receive successes and failures.
- Clipboard frontend simplified to a single-line text field and copy button. Removed send text, send file, and export log entries not needed by regular users.
- Optimized clipboard text field: left-aligned, normal weight, fixed single-line height. Button changed to `Sync Text`.
- Added `get_connection_summary()` returning status, device, Deck IP, receive directory, and default device in one call.
- Added `start_managed_kde()`, `stop_managed_kde()`, `get_managed_kde_status()`, `get_deck_ips()`, `get_notebook()`, `save_notebook()`, `export_logs()` RPC methods.
- Added diagnostic log export zip containing `kdeconnectd.log`, transfer history, notebook, and plugin-managed daemon pid.
- Added plugin uninstall cleanup logic that only removes KDEck's own settings, runtime, and log directories, not KDE Connect pairing configuration or received files.
- Added plugin-launched daemon pid recording. Uninstall only attempts to stop `kdeconnectd` instances launched by KDEck.
- Removed `debug` flag from publish manifest. Kept `_root` for necessary privilege-dropped `deck` user session calls.
- Added release packaging script generating `KDEck-0.2.0.zip` importable directly through Decky Loader plugin import.
- Release package now uses Python `zipfile` to enforce `/` internal paths, avoiding Windows backslash issues on SteamOS.
- Release package filename fixed to `KDEck.zip` without version number for easier Decky Loader manual overwrite install.

## 0.1.1 - 2026-05-27

- Changed template debug frontend to simplified KDEck operation panel.
- Frontend only shows start/refresh, device selection, clipboard, text and file send entry points.
- Removed frontend JSON diagnostic output. Diagnostic details handled by backend APIs and logs.
- Fixed `kdeconnect-cli` device reachability judgment when only returning `paired`.
- Fixed asyncio cleanup warnings after background launch of `kdeconnectd`.
- Fixed backend module import path in Decky Python sandbox.
- Compatible with Decky Loader hardware environment plugin settings and runtime directory constant names.
- Added `QT_QPA_PLATFORM=wayland` and `WAYLAND_DISPLAY=gamescope-0` for game mode to prevent `kdeconnectd` from using xcb and core dumping.
- Device list query no longer calls `kdeconnect-cli` when daemon is not ready, avoiding DBus auto-activation repeatedly launching with wrong Qt platform.
- Changed `kdeconnectd` launch to explicit `setsid` with log retention. DBus readiness wait increased from 5 to 15 seconds.
- KDE Connect commands now use clean environment to avoid inheriting Decky/PyInstaller's `/tmp/_MEI...` dynamic library path that causes OpenSSL version conflicts.

## 0.1.0 - 2026-05-27

- First KDEck Python backend.
- KDE Connect backend detection, start, stop, restart, and DBus readiness check.
- Device refresh, device list, pairing, unpairing.
- Clipboard send, text share, Deck current clipboard read/write.
- Single file share, common directory browsing, and recent send history.
- Network, DBus, and KDE Connect component diagnostics.

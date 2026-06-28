# Changelog

## 0.9.6 - 2026-06-19

- Added a low-risk trusted-device store migration helper that normalizes legacy `trusted-devices.json` entries with `device_id`, migrated metadata names, `schema_version`, and `migrated_at` while preserving unknown fields.
- Kept trust behavior unchanged during migration: incomplete legacy records are not automatically upgraded into trusted `device_id` records.
- Added structured diagnostic error helpers with stable `code`, `stage`, `message`, and timestamp fields.
- Updated receiver diagnostics for UDP bind, TCP listener bind, outgoing TCP/TLS failures, certificate init failures, and send-transfer failures so status snapshots can identify where a problem occurred.
- Improved managed receiver diagnostic summaries so transfer timeout/incomplete, TCP, and TLS errors surface as readable states and messages instead of generic connection failure.
- Changed frontend send failures to show action-oriented recovery advice instead of raw low-level error codes or exception messages.
- Normalized receiver events on write so each JSONL event has `event`, `stage`, `device_id`, and `time`, with path, command, certificate path, and fingerprint-style fields redacted.
- Added rate limiting for repeated high-frequency event types such as `peer_connect_failed`, packet errors, and payload retries to reduce log spam during bad network conditions.
- Added diagnostic export metadata for the fixed event-log policy and a redacted `status-snapshot.json` alongside `manifest.json`.
- Added low-risk connection-state recording for `idle`, `discovered`, `trusted`, `connecting`, `connected`, `backoff`, `paused_desktop`, and `failed`; this records state changes only and does not change connection, pairing, TLS, or retry decisions.
- Added `REAL_DEVICE_VALIDATION_MATRIX.zh-CN.md` covering overlay installs, pairing inheritance, send-page behavior, transfers, diagnostic logging, and state-machine validation on real hardware.
- Added regression tests for trust migration safety and diagnostic-summary transfer error promotion.
- Deferred higher-risk connection lifecycle work from the 0.9.6 note set, including per-device state tables, single-session enforcement, and retry backoff.
- Updated the package version to `0.9.6`.

## 0.9.5 - 2026-06-19

- Moved the send-page target switcher back into the normal content flow under the right-side title, left-aligned at a normal width, so it is no longer pushed into the Steam/Decky top overlay.
- Reduced send-job polling when idle: active transfers poll every 900 ms, idle pages poll every 3000 ms.
- Internally refactored the send page while keeping the package version at `0.9.5`: `SendPage.tsx` now keeps routing, send-job state, and `SidebarNavigation` assembly.
- Moved send-page UI pieces into `src/features/send/components/`, including device switching, file rows, thumbnails, save groups, and empty states.
- Moved send-page pure helpers and shared types into `src/features/send/domain/`, including category metadata, device selection helpers, formatting, file grouping, and row styles.
- Moved low-risk send-page state into `src/features/send/hooks/`: `useSendTargets` owns device list/preferred-device switching, and `useSendableFiles` owns category scanning and refresh.
- Kept the 0.9.4 low-risk backend and packaging improvements, including automatic release builds, package-version validation, SHA256 output, external-library save metadata, broader librarycache icon matching, thumbnail-cache cleanup, and transfer-history trimming coverage.
- Updated the package version to `0.9.5`.

## 0.9.4 - 2026-06-19

- Enhanced `tools/package_release.py`: release packaging now runs `pnpm build` by default, validates the packaged `package.json` version against the source version, supports Windows `pnpm.cmd`, handles `--skip-build` correctly, and prints SHA256.
- Improved save metadata lookup by reading Steam `libraryfolders.vdf` so app names can be found from external Steam libraries as well as the default library.
- Improved save thumbnail matching by accepting more Steam `librarycache` image naming patterns while still falling back to the existing placeholder when no icon exists.
- Added cleanup for generated thumbnail-cache files using age/count limits to avoid long-term cache growth.
- Added coverage for external-library save app names, loose librarycache icon matching, thumbnail-cache cleanup, and JSONL transfer-history trimming.
- Adjusted the send-page header area for a closer visual alignment between the left title, right page title, device switcher, and first file row.
- Updated the package version to `0.9.4`.

## 0.9.3 - 2026-06-19

- Fixed target-device switching when the preferred target is offline: if another trusted device is connected, the send page now switches to the connected target instead of requiring the offline device to come online first.
- Removed duplicate category titles in the send-page content area and kept the `SidebarNavigation` native page title as the single title.
- Moved the device switcher into the upper-right area formerly used by search and constrained its width.
- Added save grouping by game/app: the Saves page now shows game rows first, and activating a game row expands the concrete save files beneath it without adding a second page.
- Added optional `app_name` metadata for save files by reading Steam `appmanifest_*.acf`; the frontend prefers the game name and falls back to `App <id>`.
- Continued to use Steam `librarycache` thumbnails for save/game rows when available.
- Updated the package version to `0.9.3`.

## 0.9.2 - 2026-06-19

- Reworked the send page around Decky `SidebarNavigation`: the left category rail, selected state, and focus behavior are now handled by Decky's native sidebar component.
- Removed the custom left rail, hand-written sidebar focus bridge, and low-use search bar.
- Kept the right-side send experience: target device switching, file rows, thumbnails, inline progress, success feedback, and save thumbnails.
- Preserved existing send-page routes by mapping screenshot, recording, save, and log routes into the new `SidebarNavigation` page state.
- Avoided backend, discovery, pairing, TLS, and security changes in this frontend-focused release.
- Updated the package version to `0.9.2`.

## 0.9.1 - 2026-06-19

- Narrowed the custom send-page sidebar from 268 px to 224 px and reduced category text/icon sizing to give more space to the file list.
- Reworked the custom left-rail focus highlight into a simpler full-row highlight closer to Decky styling, while keeping the existing custom layout for this release.
- Extended the send-page background to the bottom of the viewport and kept an internal 68 px list safe area to reduce the visible gap above the Steam bottom menu.
- Enabled the existing thumbnail API path for save files so saves can request Steam `librarycache` app icons when available.
- Updated the package version to `0.9.1`.

## 0.9.0 - 2026-06-19

- Rebuilt the send page as a dedicated two-column send experience with categories for screenshots, recordings, saves, and logs.
- Changed file sending to a single-file action model: pressing A on a file row sends that file directly, with no multi-select mode.
- Reworked file rows in a DeckyMusic-inspired style with thumbnail/icon, filename, metadata, and a compact send action.
- Added inline transfer feedback: running rows show a spinner and bottom progress bar; completed rows briefly show a check mark and full progress bar; failures show a toast.
- Added screenshot and recording thumbnail loading through `get_thumbnail_base64`.
- Improved target-device readability by showing device index and online/offline state, and made long filenames/metadata truncate safely so the send action stays visible.
- Improved send-page empty/scanning/error states and added a friendlier `transfer_incomplete` frontend message.
- Added a thumbnail request queue/cache on the frontend to limit concurrent thumbnail work.
- Added low-risk backend support for Steam `librarycache` save thumbnails, while saves still fall back to placeholders when no icon is available.
- Tightened the main panel send entry with more target/recent-file context and removed the unused `PreferredDeviceResponse` type.

## 0.8.8 - 2026-06-11

- KDEck now preserves managed KDE Connect identity, certificate, and trusted-device data on uninstall, so overlay installs or reinstalls can inherit existing pairings; an explicit identity reset API is available for users who want to clear pairings.
- Reworked the send-page route entry to match DeckyClash: KDEck now registers only the `/kdeck/send` base route, while `/kdeck/send/screenshots` and related child paths are interpreted inside the send page. This avoids competing same-prefix route registrations.
- Restored `Router.CloseSideMenus()` before entering the fullscreen send page from the main panel, matching DeckyClash's fullscreen page navigation and fixing the 0.8.7 case where the stretched main panel could still open silently.
- Added explicit B/cancel handling on the send page: KDEck first asks Steam to go back, then tries to reopen the Decky QAM tab so the user does not land on the plugin store/settings page.
- Updated the frontend build marker to `KDEck v0.8.8 build marker` for on-device bundle verification.

## 0.8.7 - 2026-06-10

- Fixed the 0.8.6 route regression: removed the incorrect `/kdeck` fullscreen route so `/kdeck/send/...` is no longer captured by the home route and rendered as a stretched main panel.
- Removed the send page's custom B/cancel navigation to `/kdeck`, restoring Decky's default route stack behavior.
- Stopped calling `Router.CloseSideMenus()` before entering the send page from the main panel, reducing the chance of breaking the QAM return stack.

## 0.8.6 - 2026-06-10

- Fixed send-page controller left/right focus: the left category rail and right content area now explicitly hand focus to each other with horizontal navigation, while up/down remains local to each area.
- Fixed send-page back behavior: cancel/back now navigates to the KDEck plugin home route instead of returning to the plugin store/settings page.
- Replaced the send-page target-device and send actions with compact custom Focusable buttons to reduce visual weight and match the page style.
- Reworked the Logs page diagnostics action to use the same compact button style instead of Decky's large default button.
- Narrowed the left rail further and moved the KDEck title plus send-page content lower to reduce top clipping.
- Added backend `get_send_targets()` for a single send-target API with target names, connection state, and preferred device.
- Added trusted-device validation to `set_preferred_device()` so invalid targets are not persisted.
- Expanded backend tests to 60 cases, covering send target listing and preferred-device validation.

## 0.8.5 - 2026-06-10

- Removed the device selector from the main connection section. The main panel now only shows a connected-device summary, while send-target selection lives on the send page.
- The receiver recovery button now appears only when the receiver is stopped, UDP/TCP is unhealthy, desktop mode pauses the receiver, or an error is present.
- Reworked the send-page bottom bar into a compact `selected count/size + target device + send` layout and removed the low-value Clear button.
- Added send-page target-device selection from trusted devices. The page prefers the saved user target, then connected devices, and persists changes via preferred device storage.
- Added grouped save display by App/source/parent directory. Group rows show file count, total size, and recent modification time; expanding a group reveals concrete save files.
- Narrowed the left rail and moved the send-page title, search bar, and content lower to reduce top clipping and bottom obstruction.

## 0.8.4 - 2026-06-10

- Fully bypassed SidebarNavigation's content title layer on the send page and replaced it with a KDEck-owned two-column layout, avoiding duplicate category titles from the current SteamOS implementation.
- Moved critical layout to React inline styles, including the left navigation, content header/search row, file rows, thumbnail sizing, scroll region, and bottom safe area. The send page no longer depends on `<style>` or `injectCssIntoTab` being accepted by Decky.
- Added the `KDEck v0.8.4 build marker` so the installed custom inline-layout bundle can be verified on-device.

## 0.8.3 - 2026-06-10

- Fixed duplicate titles on the send page: the left navigation title now only shows `KDEck`, while each category page renders one content-area title and hides SidebarNavigation's built-in page title.
- Fixed search placement: the search field now sits in the right content header next to the active category title instead of inside the left navigation title area.
- Reduced the risk of SteamOS bottom-bar obstruction: the send page now uses a fixed content header, a scrollable file list, and a 108px bottom safe area.
- Improved send-page states: scan failures now show an explicit empty state; selected counts are based on the full current category rather than the current search filter.
- Improved transfer summaries: the bottom transfer summary now only counts running jobs that belong to the current category.
- Updated the frontend build marker to `KDEck v0.8.3 build marker` so the installed bundle can be verified on-device.

## 0.8.2 - 2026-06-10

- Send page architecture overhaul: each tab (Screenshots/Recordings/Logs/Saves) is now an independent self-managing component (DeckyClash pattern), each owning its file list, thumbnails, and job polling — permanently fixes the SidebarNavigation cache-related page-switch bug.
- Search bar moved from left navigation area to right content area header; each tab renders its own title and search field.
- Added multi-select: clicking a file row toggles selection; bottom bar shows count, total size, and batch "Send to device" action.
- File rows use a compact horizontal layout: 96×54 thumbnail/icon area, two-line text (filename + metadata), right-side select/status area.
- Metadata display simplified per category: screenshots/recordings show size and time; logs add source; saves show source or App ID.
- Removed "Recommended" label prefix from file names.
- Unified copy to "Send to device" instead of "Send to phone".
- Added 96px bottom safe-area padding to prevent content from being obscured by SteamOS bottom hint bar.
- Empty state ("No files" / "Scanning files…") is now centered in the right content area.
- Routes now pass explicit `initialPage` prop, keeping category and URL in sync.
- Active transfers show inline progress bar, speed, and ETA in file rows; bottom bar shows aggregate transfer summary.

## 0.8.1 - 2026-06-10

- Reworked the send-file page around Decky/community UI components: `SidebarNavigation`, `PanelSection`, `Focusable`, `Dropdown`, `ButtonItem`, and `ProgressBarWithInfo`.
- Added background send jobs for Deck-to-device file transfer. The new job state reports phase, bytes sent, total bytes, speed, ETA, and final error details without blocking the page.
- Added real transfer progress reporting from the TLS file server loop, replacing the previous purely animated progress indicator.
- Added log source metadata and recommendations. The Logs category now prioritizes KDEck receiver, Decky plugin, KDE Connect daemon, and transfer-history logs with clear source and summary fields.
- Added a "Send Diagnostics" action on the Logs page. It exports the existing redacted log bundle and sends that zip through the same tracked transfer job path.
- Added file list sorting and filtering by recent time, size, name, and recommended items.
- Added tests for send-job progress/result tracking and log metadata.
- Fixed `activeJob` fallback showing stale completed/failed jobs when no transfer is running — now only shows running jobs.
- Optimized `contentFor` to only render the active tab's content instead of building all four tab trees on every render.
- Fixed thumbnail loading effect re-triggering on every `thumbnails` state update by using a ref for already-loaded checks.
- Removed standalone "Current Task" panel — progress is now shown inline below each file row during transfer, saving screen space when idle.
- Removed sort and filter dropdowns — files always sort by most recent; search bar remains in the title area.
- Fixed page-switch blank content bug: all tabs now always receive full JSX content (never `null`), eliminating SidebarNavigation's cached-ref issue.
- Added "Send Diagnostics" button on the Logs tab.
- Fixed zip packaging: added missing `LICENSE`, `main.py`, and proper top-level `KDEck/` directory structure for Decky store import.
- Reworked MainPanel device display: device name and status dot now reflect the selected device from the dropdown.

## 0.8.0 - 2026-06-10

- Fixed fallback TLS role in `send_share_request_to_peer`: when no persistent connection exists, the TLS client/server role is now correctly determined from the trusted device's `device_type` (Android peers → TLS client, desktop peers → TLS server), fixing file sends to non-Android devices.
- Fixed reconnect loop silently giving up: `_connect_to_peer` now returns a boolean success indicator, and `_active_reconnect_loop` uses it to retry with exponential backoff (`RECONNECT_BASE_DELAY=2` → `RECONNECT_MAX_DELAY=60`) instead of relying on exceptions that were swallowed internally.
- Fixed `EventLogger.tail` ordering: events from disk and in-memory buffer are now merged in chronological order (oldest first), preventing out-of-order display in the event log.
- Added `PACKET_PING` to advertised capabilities and implemented a ping reply handler: incoming `kdeconnect.ping` packets from trusted peers now receive an immediate ping response, improving keepalive compatibility.
- Fixed React anti-pattern in `MainPanel`: moved `setSelectedDevice` initialization from render phase into `useEffect` with a stable dependency on the trusted device list IDs.

## 0.7.9 - 2026-06-10

- Increased file transfer chunk size from 64 KB to 256 KB, reducing syscall overhead and improving throughput by ~20-30% on fast WiFi links.
- Added `SO_RCVBUF` (1 MB) to payload receive sockets and `SO_SNDBUF` (1 MB) to file serve sockets, allowing the TCP window to fully utilize high-bandwidth WiFi connections.
- Rewrote the file receive loop to use `recv_into()` with a pre-allocated buffer instead of `recv()`, eliminating per-chunk memory allocations and reducing GC pressure.
- Renamed `FILE_SEND_CHUNK_BYTES` to `FILE_CHUNK_BYTES` to reflect that both send and receive paths now share the same chunk size.

## 0.7.8 - 2026-06-10

- Fixed SendPage category switching: removed `hideTitle: true` from all sidebar pages so the search bar stays visible when switching between screenshots/recordings/logs/saves. Removed the `category !== currentPage` guard in `contentFor` that caused stale empty state rendering, and added `key={category}` to `FileListContent` to force proper re-mount on tab change.
- Fixed font inconsistency in the connection section: device name now uses `infoRowStyle` to match the font size/weight of "Deck IP" and other info rows.
- Replaced `as any` cast on TextField `placeholder` prop with proper `InputHTMLAttributes<HTMLInputElement>` type.
- Removed `as any` cast on `onKeyDown` handler — types now match natively.
- Reduced clipboard input CSS `!important` declarations from 5 to 2, removing unnecessary overrides for `font-weight`, `line-height`, and `text-align`.

## 0.7.7 - 2026-06-10

- Extracted event logging subsystem into `kdeck_kde_events.py` (~116 lines): `EventLogger` class with buffered JSONL writes, auto-rotation, and tail reads; `KDEckKdeReceiver` now delegates all event operations via `self.events`.
- Extracted trust management into `kdeck_kde_trust.py` (~104 lines): standalone `read_trusted_devices`, `write_trusted_devices`, `is_trusted_device`, and `remember_trusted_device_metadata` functions; receiver retains thin wrapper methods for test backward compatibility.
- Extracted file-transfer utilities into `kdeck_kde_transfer.py` (~103 lines): standalone `safe_filename`, `unique_destination`, `has_enough_space`, `record_file_failure`, and `connect_to_peer_control_socket` functions.
- `kdeck_kde_receiver.py` reduced from ~1760 to ~1660 lines; class now serves as an orchestrator delegating to six extracted modules.
- Added one-line docstrings to 19 key public and lifecycle methods in `KDEckKdeReceiver`.
- Replaced fixed reconnect delays `(1, 3, 8, 20)` with exponential backoff starting at 2s, doubling up to a 60s cap, for more resilient trusted-peer reconnection.
- Added payload receive retry: up to 2 retries with 3s interval on connection or transfer failure; trust verification failures are not retried.
- Replaced `openssl` CLI certificate generation with Python `cryptography` library as the primary method (cross-platform, no external tool dependency); `openssl` CLI retained as fallback for environments without `cryptography`.
- All 56 tests pass (previously 1 failed on Windows due to OpenSSL entropy limitation, now resolved).
- Version bumped to 0.7.7.

## 0.7.6 - 2026-06-08

- Moved search bar into `SidebarNavigation`'s `title` prop so it aligns with the built-in category title row; all pages now use `hideTitle: true`.
- Replaced all 12 silent `.catch(() => undefined)` with descriptive `console.warn("[KDEck] ...")` calls across `useClipboard`, `useConnection`, `SendPage`, and `MainPanel`, making async errors visible in the browser console.
- Replaced inline `<style>` tags with Decky's `injectCssIntoTab` / `removeCssFromTab` one-time CSS injection in both `SendPage` and `MainPanel`, preventing duplicate style injection on re-render.
- Switched clipboard input CSS selector from `.kdeck-clipboard-input` to `.kdeck-clipboard-input input` for better specificity targeting the inner `<input>` element.
- Extracted stateless protocol constants, packet codec, and identity builder from `kdeck_kde_receiver.py` into `kdeck_kde_protocol.py` (~134 lines).
- Extracted network interface discovery, broadcast target computation, port binding, IP classification, and direct-target merging into `kdeck_kde_network.py` (~238 lines).
- Extracted TLS certificate generation and peer fingerprint verification into `kdeck_kde_tls.py` (~78 lines).
- Updated `kdeck_network.py` to import shared utilities from `kdeck_kde_network.py` and `kdeck_kde_protocol.py`, eliminating duplicate code.
- `kdeck_kde_receiver.py` reduced from 1924 to ~1750 lines; class now delegates to extracted modules while preserving thin wrapper methods for backward compatibility and test mockability.
- Added class-level docstring to `KDEckKdeReceiver` documenting module delegation architecture.
- Added TCP `SO_KEEPALIVE` to all socket creation points: incoming TCP, incoming BT bridge, outgoing peer connect, payload receive, file serve accept, and send-fallback control socket.
- Increased payload receive connection timeout from 15s to 30s for slower networks.
- All 29 platform-applicable tests pass (1 test skipped due to Windows OpenSSL entropy limitation).
- Version bumped to 0.7.6.

## 0.7.5 - 2026-06-08

- Added ref-based synchronous lock and 1-second cooldown to file send handler, preventing race-condition-driven duplicate sends from rapid touch clicks.
- Upgraded toast notification system with per-category 3-second cooldown and automatic dismiss of previous toasts, eliminating notification spam from repeated actions.
- Merged notification paths in `useConnection`: `notifyManagedEvents` now skips `file_receive_failed` when `notifyLastFile` already handles the same failure, fixing double-toast on file receive failure.
- Replaced invasive `history.pushState`/`replaceState` monkey-patch with `SidebarNavigation`'s controlled `page` + `onPageRequested` + `identifier` API for tab switching.
- Fixed render-phase `setState` anti-pattern: tab change now clears state in the `onPageRequested` callback instead of during render.
- Implemented touch-screen anti-misclick: touch input requires 0.8-second long-press with visual animation ring to send; gamepad A button sends immediately via `Focusable.onActivate`.
- Replaced `ButtonItem` with official `Focusable` component in file rows, using `focusWithinClassName` instead of `:focus-within` CSS selectors.
- Removed Bluetooth status row from main panel (kept Deck IP for manual connection troubleshooting).
- Added official `Dropdown` component for multi-device switching in main panel; removed redundant per-page `DeviceSelector` from send page.
- Reduced `!important` CSS overrides from 12 to 4 by leveraging `Focusable` focus class and inline styles.
- Removed dead code: `inputStyle`, `keyboardHint` i18n key, `device`/`status`/`btReady`/`btUnavailable`/`btDisabled` i18n keys, `DeviceRow`, `DeviceSelector`.
- Added `PreferredDeviceResponse` type to eliminate `as any` on preferred device API call.
- Fixed `TextField` `aria-label` and `className` props to use direct attributes instead of spread `as any`.
- Version bumped to 0.7.5.

## 0.7.4 - 2026-06-08

- Added `kdeconnect.ping` packet type to capabilities and handler, responding to peer keepalive pings.
- Added `SO_KEEPALIVE` with TCP keepalive tuning (idle=30s, interval=10s, count=3) matching KDE Connect C++ defaults, applied to all 6 socket creation points.
- Fixed fallback TLS role in `send_share_request_to_peer`: changed `PROTOCOL_TLS_CLIENT` to `PROTOCOL_TLS_SERVER` with `server_side=True`, matching KDE Connect's TLS convention (TCP client = TLS server).
- Fixed `_packet_payload_size` to accept `-1` (unknown size / infinite stream), a valid value in KDE Connect protocol.
- Added timestamp to pair packet in `_accept_pair_inner` for protocol compliance.
- Added post-TLS identity validation: peer device ID is now verified against the TLS certificate's Common Name after handshake.
- Rewrote `_receive_share_request` with URL share support, `payloadSize=-1` stream handling, and threaded invocation from `_handle_packet`.
- Routed `share_file` through the managed receiver instead of `kdeconnect-cli` for consistent protocol handling.
- Version bumped to 0.7.4.

## 0.7.1 - 2026-06-07

- Fixed the managed receiver startup path to stop deck-user `kdeconnectd` before KDEck binds KDE Connect ports. This prevents the official daemon from stealing Windows file-transfer traffic while KDEck is active in game mode.
- Added diagnostics for active `kdeconnectd` PIDs and a conflict warning when KDEck's managed receiver is running at the same time as the official daemon.
- Added `tools/verify-release.ps1` to run Windows checks, WSL isolated-copy checks, release packaging, packaged-version verification, and SHA256 output before manual Deck installation.
- Added regression coverage for stopping stale user daemons before the managed receiver starts.
- Version bumped to 0.7.1.

## 0.6.8 - 2026-06-07

- Removed the duplicate send-page category heading. `SidebarNavigation` already renders the active page title, so KDEck no longer renders a second "Screenshots" title inside the page content.
- Kept the search field compact and right-aligned under the built-in page title area.
- Version bumped to 0.6.8.

## 0.6.7 - 2026-06-07

- Changed the QAM send-file entry to close Decky side menus before navigating to `/kdeck/send/screenshots`, matching the standalone route behavior used by DeckyClash and reducing back-button nesting.
- Moved the send-page search field to the top-right of the category header, aligned with the current category title, and made it shorter and slimmer.
- Increased thumbnail row spacing and changed thumbnail scale origin so selected thumbnails enlarge without crowding the filename.
- Kept non-thumbnail categories as single-column rows so Logs and Saves do not inherit screenshot thumbnail indentation.
- Version bumped to 0.6.7.

## 0.6.6 - 2026-06-06

- Fixed a game-mode isolation regression: starting the KDEck receiver now stops KDEck's plugin-owned `kdeconnectd`, preventing Windows KDE Connect from seeing both `KDEck` and the Deck's desktop `steamdeck` identity.
- Removed the managed daemon watchdog path that could bring the official KDE Connect daemon back while the isolated receiver was active.
- Relaxed send-page preflight for trusted devices: if a selected device is already trusted, KDEck now lets the backend attempt the real connection instead of blocking solely because discovery is older than 180 seconds.
- Pairing records now store `last_seen` along with `last_connected`, improving trusted-device status consistency.
- Version bumped to 0.6.6.

## 0.6.5 - 2026-06-06

- Rebuilt the send-file route around Decky `SidebarNavigation`, restoring the CDP-tested left sidebar page layout in source code.
- Added the Saves route to the send page alongside Screenshots, Recordings, and Logs.
- Added thumbnail RPC support for screenshots and recordings. Screenshots prefer existing Steam thumbnail files; recordings use an existing thumbnail when available or generate a cached frame with `ffmpeg` when present.
- Merged the QAM "Received Files" and "Send File" sections into one "File Transfer" section, with the send button first and the recent received file row second.
- Changed clipboard receive copy to device-neutral wording instead of assuming every peer is a phone.
- Kept send-time connectivity validation: entering the send page does not require a connected target, but pressing a file to send validates the selected device.
- Version bumped to 0.6.5.

## 0.6.2 - 2026-06-06

- Restored the send-file page to the full-screen split layout with a left category sidebar, right-side search, thumbnail list, selected-file enlargement, highlighted filename, and animated send progress bar.
- Added the Saves category for common Steam userdata and Proton compatdata save-file candidates.
- Changed Deck-to-phone file serving to stream files in chunks instead of reading the whole file into memory before sending.
- Added public receiver APIs for flushing event logs and reading/writing trusted device state, so backend orchestration no longer calls those private receiver helpers directly.
- Added tests for chunked TLS file serving and the receiver trusted-device public API.
- Version bumped to 0.6.2.

## 0.6.1 - 2026-06-06

- Fixed the managed daemon watchdog so it uses the Decky event loop instead of an undefined backend field.
- Fixed send-file connectivity validation to require the selected target device to be recently discovered.
- Removed the in-panel development update path from the store build; development deployment stays in local tools.
- Fixed Bluetooth bridge startup to bind the local TCP bridge before launching the helper and avoid blocking forever while waiting for helper output.
- Fixed `ruff check` formatting issues in `decky.pyi`.
- Version bumped to 0.6.1.

## 0.6.0 - 2026-06-05

- Keyboard input: replaced native `<input>` with `@decky/ui` `TextField` for clipboard and search inputs. The Steam Deck on-screen keyboard now works natively in both the QAM panel and the send-file route page, where `SteamClient.System` is unavailable.
- Search box: the send-file page now has a search input (top-right, aligned with the category title) for filtering files by name. Uses `TextField` for full keyboard support.
- Send validation: before sending a file, the frontend now performs a fresh connectivity check — verifying `discovered_devices` with `last_seen` within 180 seconds — and shows a toast if no target device is online.
- Progress animation: file sending now shows an animated sliding progress indicator instead of a static green bar.
- Hidden commands via double-click: the "Sync Text" button now supports double-click to execute hidden `:kdeck` debug commands, in addition to pressing Enter in the text field.
- Removed the keyboard hint row below the clipboard input (no longer needed since `TextField` handles keyboard invocation).
- i18n: added `noDeviceConnected` and `searchPlaceholder` strings in zh-CN and en.
- CI: fixed 22 pre-existing ruff lint errors in Python backend (unused imports, unsorted imports, module-level import placement, loop variable binding in lambda).
- Version bumped to 0.6.0.

## 0.5.6 - 2026-06-04

- Major code refactor: backend split into modular files (`kdeck_daemon.py`, `kdeck_clipboard.py`, `kdeck_config.py`, `kdeck_network.py`, `kdeck_file_manager.py`, `kdeck_bt_helper.py`, `kdeck_diagnostics.py`). Frontend restructured into pages (`MainPanel.tsx`, `SendPage.tsx`), hooks (`useClipboard`, `useConnection`, `useToast`), components, and shared utilities.
- Send file entry: "Send File" button in the QAM sidebar navigates to a full-screen route page via Decky `routerHook`.
- Daemon auto-restart: the managed daemon now auto-restarts on unexpected exits.
- Bluetooth status display: the main panel shows Bluetooth connection status. Port exhaustion hint added to diagnostics.
- Bluetooth for SteamOS: fixed BT helper launch on SteamOS.
- Gamepad-friendly send page: file rows are full `ButtonItem` elements for gamepad A-button activation.
- Keyboard hint: added a hint row below the clipboard input about keyboard usage (later removed in 0.6.0).
- Version bumped to 0.5.6.

## 0.5.5 - 2026-06-04

- Bluetooth support: RFCOMM server on channel 22 with SDP registration for PC/phone discovery. Reuses existing TLS + protocol handler. Graceful degradation.
- Send file: full-screen page via Decky routerHook, three tabs (screenshots/recordings/logs). Accessible from Decky sidebar.
- Dev deployment: `tools/deploy_to_deck.ps1` and `tools/deploy_to_deck.sh` provide local SSH deployment outside the store build.
- Build: version injected from `package.json` via rollup. CI builds and uploads release artifact.
- Fake client: `recv-file` command for reverse file transfer testing.
- i18n: 6 send-file error codes in zh-CN and en.
- Code cleanup: 115 lines of dead pending_pair code removed. React hooks violation fixed. Steam keyboard API removed.
- `defaults/defaults.txt` placeholder removed.
- Version bumped to 0.5.5.

## 0.5.4 - 2026-05-30

- Generalized file scanner: `list_sendable_files(category)` supports screenshots, recordings, and logs with a unified API.
- Recordings tab: scans Steam gamerecordings and /home/deck/Videos for .mp4/.mkv/.webm/.mov files.
- Logs tab: scans KDEck runtime/log dirs and Steam logs for .log/.jsonl/.txt/.old files.
- Frontend: three-tab layout (Screenshots / Recordings / Logs) on the send page. Oversized recording files (500MB+) are flagged red and disabled.
- LICENSE copyright updated to RainsListener 2026. plugin.json description updated to reflect send capability.
- Version bumped to 0.5.4.

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

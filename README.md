# KDEck

KDEck 是一个面向 Steam Deck 游戏模式的 Decky Loader 插件。0.3.4 版聚焦手机向 Steam Deck 发送剪贴板和文件，不内置完整 KDE 桌面环境，不注册系统 `org.kde.kdeconnect` 服务。

作者：RainsListener
许可证：BSD-3-Clause

## 功能范围

- 显示合并后的连接状态，绿灯则代表连接成功，暗淡则说明未连接
- 显示 Deck 当前 IP，优先展示同 Wi-Fi / 有线局域网，其次是 EasyTier、ZeroTier、Tailscale
- 在接收文件模块用一行显示最近收到的文件和保存目录，例如 `文件: KDEck.zip -> Downloads`
- 提供隔离的 `KDEck` KDE Connect 兼容接收端
- 启动和刷新 KDEck 隔离接收端
- 提供一行剪贴板文本框，显示手机 KDE Connect 发送过来的最新文本
- 将文本框内容复制到 Deck 当前剪贴板
- 接收手机 KDE Connect 发送的文件，保存到 `/home/deck/Downloads`
- 前端标题显示当前插件版本号

## 验证状态

- 2026-05-27 复测确认：新版本使用手机 KDE Connect 向 `KDEck` 发送文件可以正常接收，之前“手机无完成提示、Deck 未收到文件”的记录来自老版本误测。
- 剪贴板接收链路已验证可用：手机 KDE Connect 发送剪贴板后，KDEck 文本框能收到内容。
- 文件接收链路已验证可用：手机 KDE Connect 发送文件后，Deck 保存到 `/home/deck/Downloads`。

## 已知问题

- 2026-05-28 实机发现：0.2.8 页面内容超出 Decky 面板高度时，触摸屏可以继续向下滚动，但手柄按键无法继续翻到更下面的内容。初步判断是前端焦点导航链没有把底部内容纳入按键滚动路径，后续需要压缩面板高度或改用更适合 Decky 按键导航的可聚焦布局。
- 2026-05-28 实机发现：Android KDE Connect 在同网段下能向 KDEck 发出 discovery，Deck 能收到并回发 identity；0.3.0 等待手机主动连入未触发 incoming TCP，0.3.1 主动连接手机但 TLS client 模式超时。0.3.2 回到旧版更接近的主动连接 + TLS server 模式继续验证。

## 后端边界

主路径使用 KDEck 自己的最小 KDE Connect LAN 协议兼容接收端。旧的系统 `kdeconnectd` RPC 仍保留在后端用于兼容和诊断，但普通前端不再把它作为主要交互路径。

插件不会启动 Plasma 桌面 UI，也不会删除用户的 KDE Connect 配对配置。卸载时只清理 KDEck 自己的设置、运行时文件和日志。

## 隔离接收端

SteamOS 游戏模式下，系统 KDE Connect 原生剪贴板接收可能无法写入 gamescope 可用的系统剪贴板。KDEck 因此提供一个隔离的 KDE Connect 兼容接收端：

```text
设备名：KDEck
独立设备 ID
独立证书
独立配置目录
```

手机 KDE Connect 里会看到一台名为 `KDEck` 的新设备。手机和这台设备配对后，点击 KDE Connect App 的“发送剪贴板”，KDEck 会把收到的剪贴板内容保存到插件文本框。发送文件会保存到 `/home/deck/Downloads`。桌面模式原有的 `steamdeck` KDE Connect 配置不与 KDEck 共用。

热点场景下，Deck 连接手机热点后，手机和 Deck 通常处在同一局域网，`KDEck` 可以通过 KDE Connect LAN 发现和连接。若手机同时处于 EasyTier、ZeroTier、Tailscale 等网络中，以手机能 ping 通的 Deck IP 为准。

0.2.1 起，接收端会在启动后按 `0 秒、2 秒、5 秒、10 秒` 密集广播 identity，之后每 30 秒广播一次。广播会覆盖 `255.255.255.255` 和每个 IPv4 网卡自己的 broadcast 地址，并尽量按网卡源 IP 分别发送。收到手机 identity 后，KDEck 会立即回发 identity；主动 TCP 连接手机失败时，会再发一次 UDP identity 作为回退。

0.2.4 起，接收端会在 KDE Connect 端口范围 `1714-1764` 中选择空闲 TCP 端口，并在 identity、状态和日志中使用实际端口。配对后会优先保存手机证书 SHA-256 指纹；如果当前 TLS 角色拿不到对端证书，会记录 `device_id` 信任模式，避免 KDE Connect 客户端卡在配对请求界面。

0.3.0 起，接收端统一使用网络路径优先级：同 Wi-Fi / 有线局域网优先，其次 EasyTier、ZeroTier、Tailscale，最后普通 VPN / 其他接口。

0.3.2 起，Android 手机 discovery 后会继续主动连接手机 `1716`，TLS 握手回到旧版更接近的 server 模式；Android discovery 只回包到手机来包源端口，减少重复 identity 对手机状态机的干扰。桌面 KDE Connect 仍使用原有 server 模式和 `1716` 回包兜底。

从 0.2.3 或更早版本覆盖升级到 0.2.4 后，旧的 KDEck 配对记录没有证书指纹。手机端如显示已配对但无法投递内容，需要在手机 KDE Connect 中取消 `KDEck` 配对后重新配对一次。

## SteamOS 游戏模式环境

后端默认目标用户是 SteamOS 的 `deck` 用户，并使用：

```bash
DISPLAY=:0
XDG_RUNTIME_DIR=/run/user/1000
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
QT_QPA_PLATFORM=wayland
WAYLAND_DISPLAY=gamescope-0
```

保留 Decky `_root` 标记的原因是：Decky 后端有时以 root 运行，插件需要降权到 `deck` 用户调用 KDE Connect，避免生成 root 用户的 KDE Connect 配置。插件第一版不调用 `sudo`，不需要 sudo 密码。

## 安装包

Decky Loader 插件导入 zip 需要包含顶层目录 `KDEck/`，目录内至少包含：

- `plugin.json`
- `package.json`
- `main.py`
- `kdeck_backend.py`
- `kdeck_kde_receiver.py`
- `dist/index.js`
- `assets/`
- `defaults/`
- `py_modules/`
- `README.md`
- `LICENSE`
- `CHANGELOG.md`
- `THIRD_PARTY_NOTICES.md`

生成发布包：

```bash
pnpm run build
python tools/package_release.py
```

生成的 zip 位于 `release/KDEck.zip`。可以在 Decky Loader 的插件导入入口手动导入该 zip，也可以覆盖安装同名插件。发布脚本只生成本机 zip，不会自动同步到 Steam Deck。

## 源码仓库

推荐主仓库：

- GitHub：`https://github.com/BRiAn3274/KDEck`
- CNB：`https://cnb.cool/RainsLIstener/KDEck`

`release/` 和 `dist/` 不提交到源码仓库。需要分发安装包时，先在本地执行构建和打包命令，再把 `release/KDEck.zip` 上传到 GitHub Release 或 CNB Release 附件。

当前仓库保留 Python 后端在项目根目录，便于 Decky 手动导入 zip。提交 Decky 插件商店前，还需要按商店 CI 要求整理后端构建结构。

## Decky RPC 方法

前端可通过 Decky server API 调用：

- `get_connection_summary()`
- `start_managed_kde()`
- `stop_managed_kde()`
- `get_managed_kde_status()`
- `get_status()`
- `diagnose()`
- `ensure_daemon()`
- `start_daemon()`
- `stop_daemon()`
- `restart_daemon()`
- `refresh_devices()`
- `list_devices()`
- `pair_device(device_id)`
- `unpair_device(device_id)`
- `send_clipboard(device_id)`
- `share_text(device_id, text)`
- `get_clipboard(max_chars)`
- `set_clipboard(text)`
- `share_file(device_id, path)`
- `list_files(directory, limit)`
- `get_common_directories()`
- `get_incoming_directories()`
- `get_transfer_history(limit)`
- `get_deck_ips()`
- `get_notebook()`
- `save_notebook(text)`
- `export_logs()`

## 诊断重点

后端会明确区分这些问题：

- `missing_cli`：找不到 `kdeconnect-cli`
- `missing_daemon`：找不到 `kdeconnectd`
- `missing_dbus`：`/run/user/1000/bus` 不存在
- `daemon_stopped`：后台服务未运行
- `dbus_service_unavailable`：进程存在但 DBus 服务未就绪
- `no_paired_device`：没有已配对设备
- `paired_not_reachable`：已配对但设备不可达

隔离接收端会自动写入 JSONL 事件日志，覆盖接收端启停、证书、UDP/TCP 监听、discovery 收发、连接失败、配对、信任校验拒绝、剪贴板和文件接收结果。前端只展示简化状态，日志用于 SSH 排查。

KDE Connect 使用 TCP/UDP `1714-1764`。KDEck 当前固定监听 UDP `1716`，TCP 在 `1714-1764` 中自动选择空闲端口。手机热点、访客 Wi-Fi、AP 隔离、VPN 或组网路由都可能导致设备不可见。EasyTier 场景下，手机 KDE Connect 手动添加 Deck 地址时应填写 Deck 的 EasyTier IP，不要填写带网段后缀的地址。

## 验证

本地验证：

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py kdeck_backend.py kdeck_kde_receiver.py tools/package_release.py
```

Steam Deck 游戏模式 SSH 验证：

```bash
DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus kdeconnect-cli --list-devices
```

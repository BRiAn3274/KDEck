# KDEck

[English](README.md) | 简体中文

KDEck 是一个用于 Steam Deck 游戏模式的 Decky Loader 插件。它提供一个聚焦剪贴板文本和文件传输的 KDE Connect 兼容桥接能力，让已配对的手机或电脑可以在不切换到 Plasma 桌面模式的情况下和 Steam Deck 交换内容。

作者：RainsListener

许可证：BSD-3-Clause

版本：0.9.6

## 主要功能

- 在 Decky 快速访问面板中接收 KDE Connect 剪贴板文本。
- 接收 KDE Connect 分享的文件，并保存到 Steam Deck 的 `Downloads` 目录。
- 从 Deck 向已配对 KDE Connect 设备发送截图、录像、日志、存档和脱敏诊断包。
- 使用接近 Decky 原生风格的发送页浏览文件，支持分类、搜索、排序、缩略图、设备在线/离线状态、进度、速率和预计剩余时间。
- 进入 Plasma 桌面模式时暂停游戏模式 receiver，回到游戏模式后自动恢复。
- 使用独立的 KDEck 设备身份、证书、可信设备记录和插件数据目录。

KDEck 只覆盖剪贴板文本和文件传输，不实现 KDE Connect 的通知、短信、远程输入、媒体控制等完整桌面功能。

## 安装

1. 下载项目发布包中的 `KDEck.zip`。
2. 在 Steam Deck 上打开 Decky Loader。
3. 使用插件导入功能安装 `KDEck.zip`。
4. 从 Decky 快速访问菜单打开 KDEck，确认 receiver 正在运行。

如果覆盖安装后状态异常，可以在 Decky Loader 中重启 KDEck，再重新打开面板。

## 配对

1. 让 Steam Deck 和 KDE Connect 设备处在同一个 Wi-Fi 或同一个热点下。
2. 打开手机或电脑上的 KDE Connect。
3. 找到 `KDEck` 并发起配对。
4. 配对后即可向 KDEck 发送剪贴板文本或分享文件。

如果自动发现失败，可以在 KDE Connect 中手动添加 KDEck 面板显示的 Deck IP。访客 Wi-Fi、AP 隔离、VPN、组网中转和多网卡路由都可能影响 KDE Connect 自动发现。

KDEck 会保留自己的设备身份和可信设备记录。覆盖安装通常会保留已有配对。如果需要主动重新开始，可以在 KDEck 文本框输入 `:kdeck reset identity`，重启 KDEck 后重新配对。

## 使用

接收剪贴板文本：

1. 从 KDE Connect 向 `KDEck` 发送剪贴板文本。
2. KDEck 会在面板中显示最新收到的文本。

接收文件：

1. 将文件分享到 KDE Connect。
2. 选择 `KDEck`。
3. 文件会保存到 `/home/deck/Downloads`。

从 Deck 发送文件：

1. 在 Decky 侧边栏打开 KDEck。
2. 选择“发送文件”。
3. 选择“截图”“录像”“日志”或“存档”分类。
4. 如果有多个已配对设备，先选择目标设备。
5. 选择文件或诊断包发送。

## 常见问题

如果设备搜不到 KDEck：

- 确认两台设备在同一个网络或热点下。
- 尽量关闭路由器的 AP 隔离。
- 使用 KDEck 面板显示的地址手动添加 IP。
- 删除 KDE Connect 设备端残留的旧 KDEck 配对，再重新配对。
- 覆盖安装后从 Decky Loader 重启 KDEck。

接收文件默认保存到：

```text
/home/deck/Downloads
```

可以用隐藏命令导出脱敏诊断信息：

```text
:kdeck status
:kdeck devices
:kdeck logs
:kdeck export logs
:kdeck reset identity
```

导出的日志包用于 issue 排查，会脱敏敏感路径、命令、fingerprint、剪贴板正文、私钥和完整设备标识。

## SteamOS 与 KDE Connect 隔离

KDEck 不注册 `org.kde.kdeconnect`，不写入桌面模式 KDE Connect 的配对配置。它为插件单独运行游戏模式 receiver。

检测到 Plasma 桌面模式后，KDEck 会暂停自己的 receiver 并释放 KDE Connect 局域网发现端口。回到游戏模式后，KDEck 会恢复运行。这能减少和桌面模式官方 KDE Connect 服务的冲突。

## root 权限说明

KDEck 使用 Decky `_root` flag，因为后端需要检测 Decky/游戏模式进程状态、绑定 KDE Connect 局域网端口，并在少数场景下降权到 `deck` 用户会话执行命令。插件不会重启系统、修改系统服务、删除用户下载目录，也不会写入桌面模式 KDE Connect 配置。

## 开发

仓库：

- GitHub：`https://github.com/BRiAn3274/KDEck`

推荐检查：

```bash
pnpm build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py backend/src/kdeck_kde_discovery.py backend/src/kdeck_kde_events.py backend/src/kdeck_kde_state.py backend/src/kdeck_kde_connection.py backend/src/kdeck_kde_network.py backend/src/kdeck_kde_protocol.py backend/src/kdeck_kde_tls.py backend/src/kdeck_kde_trust.py backend/src/kdeck_kde_trust_migration.py backend/src/kdeck_kde_transfer.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

Windows 下可以运行 `tools/verify-release.ps1` 执行发布验证流程并输出安装包 SHA256。

生成的安装包位于：

```text
release/KDEck.zip
```

## 致谢与来源

KDEck 是受 KDE Connect 生态启发的独立项目，不隶属于 KDE e.V. 或 KDE Connect 项目，不包含 KDE Connect 源码，只实现剪贴板文本和文件传输所需的兼容能力。

相关参考：

- `https://kdeconnect.kde.org/`
- `https://invent.kde.org/network/kdeconnect-kde`
- `https://invent.kde.org/network/kdeconnect-android`

# KDEck

[English](README.md) | 简体中文

KDEck 是一个用于 Steam Deck 游戏模式的 Decky Loader 插件。

它实现了一个小型 KDE Connect 兼容 receiver，主要用于两个场景：

- 剪贴板文本
- 文件传输

KDEck 不是完整的 KDE Connect 替代品。它不实现通知、短信、远程输入、媒体控制或桌面集成。

作者：RainsListener

许可证：BSD-3-Clause

版本：0.9.6

## 支持功能

- 从已配对 KDE Connect 设备接收剪贴板文本。
- 从已配对 KDE Connect 设备接收分享文件。
- 将接收文件保存到 `/home/deck/Downloads`。
- 从 Steam Deck 向已配对 KDE Connect 设备发送截图、录像、日志、存档和诊断包。
- 显示目标设备状态、文件进度、传输速度和预计剩余时间。
- 检测到 Plasma 桌面模式时暂停 KDEck 游戏模式 receiver。

## 限制

- KDEck 使用自己的设备 ID、证书、可信设备记录和插件数据目录。
- KDEck 不注册 `org.kde.kdeconnect`。
- KDEck 不写入桌面模式 KDE Connect 的配对配置。
- KDEck 不修改系统服务。
- KDEck 不删除用户下载目录中的文件。
- KDEck 只支持剪贴板文本和文件传输所需的 KDE Connect 行为。

## 安装

1. 下载发布包中的 `KDEck.zip`。
2. 在 Steam Deck 上打开 Decky Loader。
3. 导入并安装 `KDEck.zip`。
4. 从 Decky 快速访问菜单打开 KDEck。

覆盖安装后，如果面板显示旧状态，可以从 Decky Loader 重启 KDEck。

## 配对

1. 让 Steam Deck 和 KDE Connect 设备处在同一个 Wi-Fi 网络或同一个热点下。
2. 打开手机或电脑上的 KDE Connect。
3. 选择 `KDEck`。
4. 接受配对请求。

如果自动发现不可用，可以在 KDE Connect 中手动添加 KDEck 面板显示的 Steam Deck IP。访客 Wi-Fi、AP 隔离、VPN、组网中转和路由规则都可能阻止 KDE Connect 自动发现。

如需重置 KDEck 身份和配对数据，在 KDEck 文本框输入以下命令并重启插件：

```text
:kdeck reset identity
```

## 文件位置

接收文件：

```text
/home/deck/Downloads
```

插件数据保存在 Decky 插件数据目录中。KDEck 将这些数据和桌面模式 KDE Connect 分开保存。

## 隐藏诊断命令

面板文本框支持以下诊断命令：

```text
:kdeck status
:kdeck devices
:kdeck logs
:kdeck export logs
:kdeck reset identity
```

诊断导出用于 issue 排查。导出内容会脱敏敏感路径、命令、fingerprint、剪贴板正文、私钥和完整设备标识。

## root 权限说明

KDEck 使用 Decky `_root` flag，用于后端进程状态检查、管理 KDEck receiver 进程，以及在 `deck` 用户会话中执行有限命令。

插件不会重启系统、修改系统服务、删除用户下载目录，也不会写入桌面模式 KDE Connect 配置。

## 开发检查

推荐本地检查：

```bash
pnpm build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py backend/src/kdeck_kde_discovery.py backend/src/kdeck_kde_events.py backend/src/kdeck_kde_state.py backend/src/kdeck_kde_connection.py backend/src/kdeck_kde_network.py backend/src/kdeck_kde_protocol.py backend/src/kdeck_kde_tls.py backend/src/kdeck_kde_trust.py backend/src/kdeck_kde_trust_migration.py backend/src/kdeck_kde_transfer.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

Windows 下也可以运行：

```powershell
tools/verify-release.ps1
```

发布包生成位置：

```text
release/KDEck.zip
```

## 致谢

发送页布局和 Decky 风格交互参考过其他开源 Decky 插件，包括：

- `https://github.com/chenx-dust/DeckyClash`
- `https://github.com/jinzhongjia/decky-music`

这些项目仅作为 UI 参考。KDEck 不包含它们的源码。

## 项目说明

KDEck 是一个独立项目，与 KDE Connect 协议的一小部分进行互操作。它不隶属于 KDE e.V. 或 KDE Connect 项目，也不包含 KDE Connect 源码。

参考：

- `https://kdeconnect.kde.org/`
- `https://invent.kde.org/network/kdeconnect-kde`
- `https://invent.kde.org/network/kdeconnect-android`

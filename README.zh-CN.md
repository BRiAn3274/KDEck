# KDEck

[English](README.md) | 简体中文

KDEck 是一个给 Steam Deck 游戏模式使用的 Decky Loader 插件。它让手机 KDE Connect 可以把文本和文件发送到 Steam Deck，不需要打开 KDE 桌面模式。

作者：RainsListener  
许可证：BSD-3-Clause

## 主要功能

- 手机发送剪贴板文本，KDEck 会显示在插件的一行文本框里
- 手机发送文件，KDEck 会保存到 Steam Deck 的 `Downloads` 目录
- 插件内显示 Deck 当前可用 IP，可以为手机手动添加设备做兜底
- 插件内显示最近收到的文件

KDEck 目前只做了接收文本和接收文件，未做通知、短信、远程输入、媒体控制等完整 KDE Connect 桌面功能。

进入 Plasma 桌面模式时，KDEck 会暂停自己的游戏模式接收端，释放 KDE Connect 局域网发现端口，避免干扰桌面模式的官方 KDE Connect。回到游戏模式后，接收端会自动恢复。

## 安装

1. 在 GitHub Release 或 CNB Release 下载 `KDEck.zip`。
2. 打开 Steam Deck 的 Decky Loader。
3. 使用插件导入功能安装 `KDEck.zip`。
4. 安装后打开 KDEck，确认状态显示为接收中。

如果覆盖安装后状态异常，可以先在 Decky Loader 中重启插件，再重新打开 KDEck。

## 手机配对

1. 让手机和 Steam Deck 尽量处在同一个 Wi-Fi 或同一个热点下。
2. 打开手机 KDE Connect。
3. 在设备列表里找到 `KDEck` 并发起配对。
4. 配对成功后，手机可以向 KDEck 发送剪贴板或文件。

如果手机搜不到设备，可以在 KDE Connect 里手动添加 KDEck 显示的 Deck IP。校园网、访客 Wi-Fi、AP 隔离、代理、VPN 或组网中转都可能影响自动发现。

## 使用方式

发送文本：

1. 在手机上复制一段文字。
2. 打开 KDE Connect，选择 KDEck。
3. 使用“发送剪贴板”。
4. KDEck 插件文本框会显示最新收到的文本。

发送文件：

1. 在手机上选择文件分享。
2. 分享到 KDE Connect。
3. 选择 KDEck。
4. 文件会保存到 Steam Deck 的 `Downloads` 目录。

## 常见问题

### 手机搜不到 KDEck

优先确认这几件事：

- Steam Deck 和手机在同一个 Wi-Fi 或同一个热点下
- 网络没有开启 AP 隔离
- 手机 KDE Connect 没有残留旧的 KDEck 配对记录
- KDEck 插件已经打开并处于接收中
- 手动添加的 IP 是 KDEck 页面显示的 Deck IP

### 手机显示已配对但收不到内容

在手机 KDE Connect 里取消 KDEck 配对，然后重新配对一次。旧版本升级后，手机端可能保留了不兼容的旧配对记录。

### 文件保存在哪里

默认保存到：

```text
/home/deck/Downloads
```

在 Steam Deck 桌面模式中就是用户的 `Downloads` 目录。

## 当前状态

KDEck 正持续开发中。剪贴板接收和文件接收已经过多款手机实机验证。自动发现在大多数家用 Wi-Fi 下正常工作；受限或多网卡环境下仍可手动添加 Deck IP 作为兜底。

KDEck 使用独立的设备 ID、证书和配置目录，不注册 `org.kde.kdeconnect`，不写入桌面模式 KDE Connect 的配对配置。

## 致谢与来源

KDEck 的设计目标和协议兼容性来自 KDE Connect 生态。KDE Connect 是 KDE 社区开发的跨设备连接项目：

- 官网：`https://kdeconnect.kde.org/`
- 桌面端仓库：`https://invent.kde.org/network/kdeconnect-kde`
- Android 仓库：`https://invent.kde.org/network/kdeconnect-android`

KDEck 是独立项目，不隶属于 KDE e.V. 或 KDE Connect 项目，也不代表 KDE 官方发布。KDEck 只实现接收剪贴板文本和接收分享文件所需的最小兼容接收端，不包含 KDE Connect 源码，也不提供完整 KDE Connect 功能集。

## 开发

源码仓库：

- GitHub：`https://github.com/BRiAn3274/KDEck`
- CNB：`https://cnb.cool/RainsLIstener/KDEck`

本地验证：

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

开发用假客户端：

```bash
python tools/kdeck_fake_client.py discover --host 192.0.2.37
python tools/kdeck_fake_client.py pair --host 192.0.2.37
python tools/kdeck_fake_client.py clipboard --host 192.0.2.37 --pair --text "hello from pc"
python tools/kdeck_fake_client.py send-file --host 192.0.2.37 --pair --file ./sample.txt
python tools/kdeck_fake_client.py bad-packet --host 192.0.2.37 bad-body
```

这个工具只用于开发验证，会模拟一个最小 KDE Connect 桌面端，通过真实 UDP、TCP 和 TLS 协议路径向 KDEck 发送 packet。首次运行会在用户本地状态目录生成独立 `device-id` 和自签名证书，不读取或写入桌面模式 KDE Connect 的配置。

如果 Windows 能被 KDEck 发现，但 `discover` 返回空数组，通常是 Windows 入站 UDP 回包被防火墙或多网卡路径拦截。`pair`、`clipboard` 和 `send-file` 会在这种情况下自动扫描 KDEck 的 TCP `1714-1764` 端口继续连接。

连接诊断：

KDEck 后端会记录 receiver 是否期望运行、是否因为桌面模式暂停、UDP/TCP 是否监听、最近 UDP discovery 来源、最近 TCP 成功/失败、最近 TLS 成功/失败、最近配对状态、可信设备 reannounce 目标、最近剪贴板状态、最近文件状态和最近 payload 传输错误。日志导出包里的 `manifest.json` 会包含这些脱敏诊断信息，方便判断问题卡在发现、连接、TLS、配对还是文件传输阶段。

隐藏开发命令：

```text
:kdeck help
:kdeck status
:kdeck devices
:kdeck reannounce
:kdeck export logs
:kdeck logs
:kdeck share logs
```

在 KDEck 剪贴板文本框输入其中一条并按 Enter。隐藏命令的意义是：普通用户仍把这个文本框当作剪贴板展示框，测试者可以把它当作一个很小的诊断控制台。命令文本不会作为剪贴板内容保存。

- `:kdeck help` 显示可用隐藏命令。
- `:kdeck status` 显示 receiver 诊断摘要。
- `:kdeck devices` 显示已发现设备和可信设备数量。
- `:kdeck reannounce` 立即触发一轮可信设备 reannounce。
- `:kdeck logs` 和 `:kdeck export logs` 会把脱敏日志包导出到 Steam Deck 的 `Downloads` 目录。
- `:kdeck share logs` 也会导出日志，但不会直接反向发送到手机或电脑。KDEck 当前是隔离接收端，不保存可靠的反向发送会话；如果改用桌面 KDE Connect 发送，会重新引入 KDEck 正在避免的桌面服务依赖。

导出的日志包可以附到 GitHub issue。仓库里提供了 Bug report 和 Test report 模板。

生成的安装包位于：

```text
release/KDEck.zip
```

# KDEck

KDEck 是一个给 Steam Deck 游戏模式使用的 Decky Loader 插件。它让手机 KDE Connect 可以把文本和文件发送到 Steam Deck，不需要打开 KDE 桌面模式。

作者：RainsListener  
许可证：BSD-3-Clause

## 主要功能

- 手机发送剪贴板文本，KDEck 会显示在插件的一行文本框里
- 手机发送文件，KDEck 会保存到 Steam Deck 的 `Downloads` 目录
- 插件内显示 Deck 当前可用 IP，可以为手机手动添加设备做兜底
- 插件内显示最近收到的文件

KDEck 目前只做了接收文本和接收文件，未做通知、短信、远程输入、媒体控制等完整 KDE Connect 桌面功能。

进入 Plasma 桌面模式时，KDEck 会暂停自己的游戏模式接收端，释放 KDE Connect 局域网发现端口，避免干扰桌面模式的官方 KDE Connect。回到游戏模式后，接收端会自动恢复。目前隔离相对完整，但测试样本较少，如果发现未完全隔离的情况请反馈。

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

KDEck 目前仍处于早期版本。剪贴板接收和文件接收已经过实机验证，但不同网络环境下的自动发现仍可能不稳定。手动添加 Deck IP 是保留的兜底方式。

KDEck 使用独立的设备 ID、证书和配置目录，不注册 `org.kde.kdeconnect`，不写入桌面模式 KDE Connect 的配对配置。

## 开发

源码仓库：

- GitHub：`https://github.com/BRiAn3274/KDEck`
- CNB：`https://cnb.cool/RainsLIstener/KDEck`

本地验证：

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py
python tools/package_release.py
```

生成的安装包位于：

```text
release/KDEck.zip
```

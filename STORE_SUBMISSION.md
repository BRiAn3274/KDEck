# Decky 插件商店提交清单

KDEck 提交 Decky 插件商店前，按下面顺序检查。

## 仓库结构

- `main.py` 保留在仓库根目录，作为 Decky Python 后端入口。
- 后端模块放在 `backend/src`。
- 前端源码放在 `src`。
- 构建产物 `dist/` 不提交到源码仓库。
- 手动安装包 `release/KDEck.zip` 不提交到源码仓库。

## 本地验证

```bash
pnpm run build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

## 提交前检查

- `package.json` 已按语义化版本更新。
- `src/index.tsx` 中显示的版本号和 `package.json` 一致。
- `CHANGELOG.md` 已记录本次改动。
- `plugin.json` 的 `publish.description`、`publish.tags`、`publish.image` 可用。
- `LICENSE` 存在。
- `README.md` 默认为英文主页，`README.zh-CN.md` 提供中文说明。
- `release/KDEck.zip` 可以手动导入 Decky Loader。

## 审核说明

- KDEck 有 Python 后端，核心功能是游戏模式里的最小 KDE Connect 兼容接收端。
- KDEck 只接收手机发送到 Deck 的剪贴板文本和文件，不提供通知、短信、远程输入、媒体控制等完整 KDE Connect 功能。
- KDEck 使用独立设备 ID、证书和配置目录，不注册 `org.kde.kdeconnect`，不写入桌面模式 KDE Connect 的配对配置。
- 进入 Plasma 桌面模式时，KDEck 会暂停 receiver 并释放 KDE Connect LAN discovery 端口；回到游戏模式后自动恢复。
- KDEck 的协议兼容性来自 KDE Connect 生态，但 KDEck 是独立项目，不隶属于 KDE e.V. 或 KDE Connect 项目，也不包含 KDE Connect 源码。
- `_root` flag 用于在 Decky 后端环境中检测进程、绑定 KDE Connect LAN 端口，并在需要调用系统工具时降权到 `deck` 用户会话；卸载时只停止 KDEck 自己记录并带有 `KDECK_MANAGED_DAEMON=1` 标记的进程。
- KDEck 不会删除用户下载目录，不会重启系统，不会修改系统服务。
- 第三方运行时依赖说明见 `THIRD_PARTY_NOTICES.md`。

## 实机提交前验证

- SteamOS Stable：安装后能加载插件。
- SteamOS Stable：手机 KDE Connect 能发现 `KDEck` 并配对。
- SteamOS Stable：手机发送剪贴板后，KDEck 文本框显示最新文本。
- SteamOS Stable：手机发送文件后，文件保存到 `/home/deck/Downloads`。
- SteamOS Stable：切到 Plasma 桌面模式后，KDEck receiver 暂停并释放 UDP `1716`。
- SteamOS Stable：回到游戏模式后，KDEck receiver 自动恢复。
- SteamOS Beta / Preview：如无法覆盖测试，在 PR 中如实填写未测试。

## PR 描述草稿

```text
KDEck is a Decky Loader plugin for Steam Deck game mode. It provides a minimal KDE Connect-compatible receiver so a phone can send clipboard text into the Decky panel and files into /home/deck/Downloads.

Scope:
- Receives KDE Connect clipboard text from a phone.
- Receives KDE Connect shared files from a phone.
- Does not provide notifications, SMS, remote input, media control, or the full KDE Connect desktop feature set.

Isolation:
- Uses a separate KDEck device ID, certificate, and plugin data directory.
- Does not register org.kde.kdeconnect.
- Does not write to the desktop KDE Connect pairing configuration.
- Pauses its receiver in Plasma desktop mode and resumes in game mode.

Attribution:
- Inspired by and compatible with a small part of the KDE Connect ecosystem.
- Independent project; not affiliated with KDE e.V. or the KDE Connect project.
- Does not bundle KDE Connect source code.

Backend:
- Python backend.
- Uses root flag for Decky backend process inspection, LAN port binding, and controlled deck-user command execution where needed.
- Does not modify system services, reboot the system, or delete user downloads.
```

## 插件数据库 PR

Decky 插件商店不是直接上传 zip，而是向 `SteamDeckHomebrew/decky-plugin-database` 提交 PR，将本仓库作为 submodule 加到 `plugins/KDEck`。

参考：

- `https://github.com/SteamDeckHomebrew/decky-plugin-template`
- `https://github.com/SteamDeckHomebrew/decky-plugin-database`

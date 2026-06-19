# Decky 插件商店提交材料

本文档用于准备 KDEck 向 `SteamDeckHomebrew/decky-plugin-database` 提交 PR。Decky 插件商店不是直接上传 zip，而是在插件数据库仓库中把本仓库作为 submodule 加到 `plugins/KDEck`。

## 当前提交版本

- KDEck 版本：`0.9.6`
- 仓库：`https://github.com/BRiAn3274/KDEck`
- 许可证：BSD-3-Clause
- 插件包：`release/KDEck.zip`
- 本次验证 SHA256：`12F10D9EA2BADF35084B896FF9E9AF97563138375C8546D49B4B3A022233DFC4`

## 发布前检查

```bash
pnpm build
python -m unittest discover -s tests
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py backend/src/kdeck_kde_discovery.py backend/src/kdeck_kde_events.py backend/src/kdeck_kde_state.py backend/src/kdeck_kde_connection.py backend/src/kdeck_kde_network.py backend/src/kdeck_kde_protocol.py backend/src/kdeck_kde_tls.py backend/src/kdeck_kde_trust.py backend/src/kdeck_kde_trust_migration.py backend/src/kdeck_kde_transfer.py tools/package_release.py tools/kdeck_fake_client.py
python tools/package_release.py
```

已验证：

- 前端构建通过。
- 后端单元测试通过：`85 passed, 1 skipped`。
- Python 编译检查通过。
- 打包脚本通过，zip 内版本为 `0.9.6`。
- 公开提交内容已扫描，不包含本机路径、固定内网 IP、私钥、证书、邮箱或个人敏感信息。

## 仓库结构

- `main.py`：Decky Python 后端入口。
- `src/`：前端源码。
- `backend/src/`：后端源码。
- `tests/`：后端单元测试。
- `tools/`：发布、验证和本地调试工具。
- `assets/logo.png`：插件图标。
- `README.md`、`README.zh-CN.md`：公开说明。
- `CHANGELOG.md`、`CHANGELOG.zh-CN.md`：版本变更记录。
- `THIRD_PARTY_NOTICES.md`：第三方依赖说明。
- `PROJECT_STRUCTURE.zh-CN.md`：仓库结构和可再生成产物边界。
- `REAL_DEVICE_VALIDATION_MATRIX.zh-CN.md`：实机验证矩阵。

不提交：

- `release/`
- `dist/`
- `backups/`
- `node_modules/`
- `.pnpm-store/`
- Python/ruff/test 缓存
- 本地过程型方案文档

## 插件范围

KDEck 是一个 Steam Deck 游戏模式 Decky Loader 插件，提供最小 KDE Connect 兼容能力：

- 接收 KDE Connect 剪贴板文本。
- 接收 KDE Connect 分享文件并保存到 `/home/deck/Downloads`。
- 从 Deck 向已配对 KDE Connect 设备发送截图、录像、日志、存档和脱敏诊断包。
- 显示发送进度、速率、预计剩余时间和设备在线/离线状态。

不提供：

- 通知同步
- 短信
- 远程输入
- 媒体控制
- 完整 KDE Connect 桌面功能

## 隔离与权限说明

- KDEck 使用独立设备 ID、证书和插件数据目录。
- 不注册 `org.kde.kdeconnect`。
- 不写入桌面模式 KDE Connect 配对配置。
- 进入 Plasma 桌面模式时暂停 receiver 并释放 KDE Connect LAN discovery 端口。
- 回到游戏模式后自动恢复 receiver。
- `_root` flag 用于 Decky 后端进程状态检测、KDE Connect LAN 端口绑定和必要的 `deck` 用户会话命令。
- 插件不会重启系统、修改系统服务、删除用户下载目录或写入桌面 KDE Connect 配置。

## 实机验证摘要

- 覆盖安装后插件可加载，版本号正确。
- KDEck 可被 Windows KDE Connect 识别，并保持已配对状态。
- Deck 发文件到 Windows PC 成功。
- 手机/电脑文件接收和发送页基础流程已按 `REAL_DEVICE_VALIDATION_MATRIX.zh-CN.md` 验证。
- 诊断包导出包含 `manifest.json`、`status-snapshot.json` 和 receiver 事件日志，并进行敏感字段脱敏。

## Decky 插件数据库 PR 要点

1. Fork `SteamDeckHomebrew/decky-plugin-database`。
2. 新建分支，例如 `add/kdeck`。
3. 将本仓库作为 submodule 加到 `plugins/KDEck`。
4. 确认 `.gitmodules` 和 `plugins/KDEck` 都进入提交。
5. PR 描述中说明功能范围、root 用途、隔离策略、实机验证和已知限制。

参考：

- `https://github.com/SteamDeckHomebrew/decky-plugin-database`
- `https://wiki.deckbrew.xyz/en/plugin-dev/submitting-plugins`
- `https://wiki.deckbrew.xyz/plugin-dev/review-and-testing`

## PR 描述草稿

```text
KDEck is a Decky Loader plugin for Steam Deck game mode. It provides a focused KDE Connect-compatible bridge for clipboard text and file transfer.

Scope:
- Receives KDE Connect clipboard text.
- Receives KDE Connect shared files into /home/deck/Downloads.
- Sends screenshots, recordings, logs, save files, and redacted diagnostic bundles from the Deck to paired KDE Connect devices.
- Does not provide notifications, SMS, remote input, media control, or the full KDE Connect desktop feature set.

Isolation:
- Uses a separate KDEck device ID, certificate, trusted-device store, and plugin data directory.
- Does not register org.kde.kdeconnect.
- Does not write to desktop-mode KDE Connect pairing configuration.
- Pauses its game-mode receiver while Plasma desktop mode is active and resumes in game mode.

Root usage:
- Required for Decky backend process-state checks, KDE Connect LAN port binding, and controlled deck-user session commands.
- Does not restart the system, modify system services, delete user downloads, or write to desktop KDE Connect configuration.

Validation:
- pnpm build passed.
- Python unit tests passed: 85 passed, 1 skipped.
- Python compile check passed.
- Release package generated and version checked as 0.9.6.
- Real-device validation performed for pairing, file send, file receive, diagnostics, and desktop-mode pause/resume paths.
```

# Changelog

## 0.5.5 - 2026-06-04

- 蓝牙支持：RFCOMM 通道 22 + SDP 服务注册，PC/手机可通过蓝牙发现并连接。复用现有 TLS + 协议处理，蓝牙不可用时自动降级。
- 发送文件：全屏独立页面（Decky routerHook），三标签切换截图/录像/日志，从 Decky 侧边栏进入。
- 开发部署：`:kdeck update <url>` 隐藏命令下载安装 zip。`tools/deploy_to_deck.ps1` SSH 一键部署。
- 构建：rollup 从 package.json 注入版本号。CI 自动构建并上传 artifact。
- 假客户端：`recv-file` 命令反向测试文件传输。
- i18n：6 个发送错误码中英文补全。
- 代码清理：删除 115 行死代码。修复 React hooks 违规。移除不可用的 Steam 键盘 API。
- 删除 `defaults/defaults.txt` 占位文件。
- 版本更新到 0.5.5。

## 0.5.4 - 2026-05-30

- 文件扫描器通用化：`list_sendable_files(category)` 支持截图、录像、日志三种类别，统一接口。
- 录像标签：扫描 Steam gamerecordings 和 /home/deck/Videos 中的 .mp4/.mkv/.webm/.mov 文件。
- 日志标签：扫描 KDEck 运行时/日志目录和 Steam 日志中的 .log/.jsonl/.txt/.old 文件。
- 前端：发送页面三标签布局（截图/录像/日志），超大录像文件（500MB+）标红禁用。
- LICENSE 版权更新为 RainsListener 2026。plugin.json 描述更新为支持收发。
- 版本更新到 0.5.4。

## 0.5.3 - 2026-05-30

- 新增发送文件到手机功能：在 Decky 面板中浏览 Steam 截图，通过 KDE Connect share.request 发送到已配对手机。
- 后端：`list_steam_screenshots()` 扫描 `/home/deck/.local/share/Steam/userdata` 下的截图文件。
- 后端：`send_file_to_phone()` 通过 TLS 连接手机，发送 share.request 并开启临时 TLS 文件端口供手机下载。
- 前端：双视图布局，"发送文件"按钮切换到截图浏览页面，返回按钮回到主面板。
- 移除占位文件 `defaults/defaults.txt`，符合 Decky 插件商店审核要求。
- 版本更新到 `0.5.3`。

## 0.5.2 - 2026-05-30

- 前端版本号修正：`APP_VERSION` 与 `package.json` 同步为 0.5.2。
- 默认自动接受配对：非信任设备直接 auto-accept，不再存入 pending_pair，连接体验与 v0.4.2 及更早版本一致。
- README 状态描述更新，反映当前成熟度；`STORE_SUBMISSION.md` 验证步骤补充 ruff check。
- 仓库分支整理：清理已过期的远程跟踪和本地分支。

## 0.5.1 - 2026-05-30

- 稳定性收敛：默认保持自动接受配对，新增设备连接体验与旧版一致；撤销未完成的实验性手动确认开关。
- 诊断日志修复：导出日志包前强制刷盘事件缓冲区，确保 zip 内包含最新 TCP/TLS/pair 事件。
- 仓库清理：移除误入版本控制的 `test.txt`。
- CI 保留：GitHub Actions 测试工作流继续维护，后续自动跑测试。
- 前端结构整理：保留 types.ts / i18n.ts / utils.ts / components.tsx 拆分，不改 UI 行为。
- 安全修复保留：`_tail_file()` 尾部读取、`_is_owned_plugin_dir()` 精确匹配、剪贴板降级链、线程锁保护和 join 清理。

## 0.4.3 - 2026-05-30

- 配对安全加固：首次配对不再自动接受，需用户在 Deck 端点"接受配对"确认后才写入白名单；已配对设备后续连接自动通过。
- 线程安全修复：receiver TCP 端口、连接冷却字典、匿名连接线程加锁保护，避免竞态条件。
- 匿名连接线程改为追踪管理，receiver 停止时正确 join 清理，防止 socket 泄漏。
- 事件日志改为内存缓冲写入（64 条或停止时刷盘），减少 eMMC/SD 卡写放大。
- 剪贴板读取优先使用 `wl-paste`/`wl-copy` → `xclip` → tkinter 降级，兼容更多环境。
- `_tail_file` 改为 seek 尾部扫描替代全量读取，降低大日志文件内存开销。
- 接口分类逻辑（`interface_path_type` / `interface_priority` / `is_usable_ipv4`）提取为模块级公共函数，消除 `kdeck_backend.py` 和 `kdeck_kde_receiver.py` 之间的重复代码。
- `_is_owned_plugin_dir` 改为精确目录名匹配（`== "kdeck"` 或 `startswith("kdeck-")`），避免误删包含 "kdeck" 字符串的无关目录。
- 后端错误信息全部改为英文 fallback，前端 `errors` 字典补全中英双语映射，非中文用户不再看到中文错误提示。
- 前端拆分为 `types.ts` / `i18n.ts` / `utils.ts` / `components.tsx` / `index.tsx` 五文件结构。
- 新增 ruff lint 配置（`pyproject.toml`）和 GitHub Actions CI（`test.yml`），所有代码通过 lint。
- 版本更新到 `0.4.3`。

## 0.4.2 - 2026-05-30

- 新增 GitHub Issues 模板：Bug report 和 Test report，便于收集 Deck 型号、SteamOS 通道、手机系统、KDE Connect 版本、网络环境和日志包。
- 剪贴板隐藏开发命令扩展为 `:kdeck help`、`:kdeck status`、`:kdeck devices`、`:kdeck reannounce`、`:kdeck logs`、`:kdeck export logs` 和 `:kdeck share logs`。
- `:kdeck share logs` 会导出脱敏日志到 Downloads，并明确说明当前隔离 receiver 不直接反向发送日志到手机或电脑。
- 诊断摘要补充最近 TCP 成功、TLS 成功/失败、配对、trusted-device reannounce 和文件 payload 错误信息。
- receiver 启动前 30 秒增加 trusted-device reannounce 节奏；从桌面模式恢复到游戏模式后会立即触发一轮可信设备 reannounce。
- README / README.zh-CN 补充隐藏命令用途、限制和诊断字段说明。
- 版本更新到 `0.4.2`。

## 0.4.1 - 2026-05-30

- GitHub 默认 `README.md` 改为英文主页，并新增 `README.zh-CN.md` 作为中文说明。
- 插件前端新增轻量中英双语文本，根据 `navigator.language` 自动选择中文或英文；中文环境显示中文，其他环境显示英文。
- 前端常见后端错误码增加英文显示兜底，减少英文界面直接露出中文错误信息。
- 发布打包脚本同步包含 `README.zh-CN.md`。
- 版本更新到 `0.4.1`。

## 0.4.0 - 2026-05-30

- 已配对设备的最近 `host`、UDP 源端口、TCP 端口、设备名和连接时间会写入受信设备状态，用于 receiver 重启或游戏模式恢复后的定向 reannounce。
- 已配对设备主动连接冷却从普通设备的 30 秒缩短为 5 秒，减少网络抖动后快速重连被 cooldown 拦住的概率。
- discovery 广播会合并短期发现设备和持久化受信设备目标；即使 receiver 重启，仍会优先向最近可信设备发定向 identity。
- `managed_kde` 状态新增 `diagnostic_summary`，集中给出 receiver 是否期望运行、是否暂停、UDP/TCP 是否工作、是否发现设备、是否配对、最近剪贴板和文件状态。
- 补充已配对设备重连、受信设备元数据、诊断 summary 测试。
- 版本更新到 `0.4.0`。

## 0.3.9 - 2026-05-30

- 新增 `tools/kdeck_fake_client.py`，提供 Windows / 桌面端开发假客户端，可通过真实 UDP、TCP 和 TLS 流程测试 discovery、pair、clipboard、share.request 文件发送和异常 packet 拒绝路径。
- 假客户端默认使用独立持久化 `device-id` 和自签名证书，不读取或写入 KDE Connect 桌面端配置。
- 假客户端在 Windows 收不到 UDP identity 回包时，会自动扫描 KDEck TCP `1714-1764` 端口作为兜底。
- 剪贴板文本框新增隐藏开发命令：输入 `:kdeck export logs` 或 `:kdeck logs` 后按 Enter，可将脱敏日志包导出到 Steam Deck 的 `Downloads` 目录。
- 手机发来的剪贴板文本继续写入 KDEck 文本框，并同步尝试写入 Deck 当前图形会话剪贴板。
- README 补充假客户端使用方式。
- 版本更新到 `0.3.9`。

## 0.3.8 - 2026-05-29

- 隔离本机桌面模式 KDE Connect discovery：忽略来自 Deck 本机 IP 或 loopback 的 identity，不再把本机桌面端显示为游戏模式里的外部设备。
- incoming TCP 增加本机来源拒绝，避免桌面 KDE Connect 进程从本机回连 KDEck receiver。
- 手机发送剪贴板后，后端继续保存到 KDEck 文本框，同时尝试写入 Deck 当前图形会话剪贴板；前端沿用现有轮询 toast，不新增 UI 入口。
- 优化隐藏日志导出：包含 manifest、receiver 轮转日志、最近 Decky 主日志、脱敏剪贴板摘要、脱敏传输历史和脱敏受信设备摘要。
- 日志导出不再默认包含 `device-id`、`trusted-devices.json`、证书或私钥，减少排障包泄露风险。
- 补充本机隔离、剪贴板同步和日志导出脱敏测试。
- 版本更新到 `0.3.8`。

## 0.3.7 - 2026-05-29

- 不改变现有配对接受策略，先补强协议输入保护和回归测试。
- packet 解码新增大小上限、JSON 结构校验和结构化拒绝事件，避免异常 packet 进入协议处理。
- 文件接收新增 `payloadSize` 校验、2 GiB 上限、剩余空间检查和 `.part` 临时文件写入，完成后再替换到最终文件。
- 文件接收失败事件细分为文件过大、空间不足、payload 不完整、无效 payload size 和 TLS/写入失败。
- receiver 事件日志新增简单轮转，`receiver-events.jsonl` 超过 2 MiB 后保留 3 份历史文件。
- 补充 packet 限制、文件保护、`.part` 避让、最近 discovery 定向回包和日志轮转测试。
- 版本更新到 `0.3.7`。

## 0.3.6 - 2026-05-28

- 检测到 Plasma 桌面模式时自动暂停 KDEck receiver，释放 KDE Connect LAN discovery 端口，避免干扰桌面模式官方 KDE Connect。
- 离开桌面模式后，如插件仍处于期望接收状态，会自动恢复 KDEck receiver。
- discovery 启动广播改为 `0 秒、1 秒、2 秒、5 秒、10 秒、15 秒`，常规广播间隔改为 20 秒。
- 对最近发现过的设备增加短期定向 identity 回包，提升网络抖动或多网卡环境下的重新连接稳定性。
- 版本更新到 `0.3.6`。

## 0.3.5 - 2026-05-28

- 为 Decky 插件商店准备源码结构：后端模块迁移到 `backend/src`，根目录保留 Decky Python 入口 `main.py`。
- 发布打包脚本同步包含 `backend/src`，继续生成可手动导入的 `release/KDEck.zip`。
- README 改为面向普通玩家的简版，减少内部实现和调试细节。
- 版本更新到 `0.3.5`。

## 0.3.4 - 2026-05-28

- 清理公开仓库中的实测私网 IP 示例，改为文档专用地址或文字占位，避免暴露本地网络信息。
- 版本更新到 `0.3.4`。

## 0.3.3 - 2026-05-28

- 整理 GitHub / CNB 公开仓库元数据：补充 `repository`、`bugs`、`homepage`，更新 `plugin.json` 发布描述和图片地址。
- 删除 Decky 模板遗留的 C 后端示例文件和 VS Code 部署脚本，避免公开仓库误导为同时包含 C 后端或旧模板部署流程。
- README 新增源码仓库和发布包分发说明，明确 `release/` 与 `dist/` 不提交到源码仓库。
- 版本更新到 `0.3.3`。

## 0.3.2 - 2026-05-28

- 根据 0.3.1 实机日志修正 Android 路径：手机 discovery、Deck 回包、Deck 主动 TCP 都正常，但 `tls_mode=client` 仍在 TLS 握手阶段超时。
- Android 手机主动连接路径回到旧版更接近的 TLS server 模式，桌面 KDE Connect 保持同一 server 模式。
- Android discovery 只回包到手机来包源端口，不再额外回 UDP `1716`；桌面端仍保留源端口 + `1716` 双回包。
- 连接日志补充设备类型、协议版本、TLS 模式、TCP/TLS 阶段耗时、异常类型、identity 回包策略和 secure identity 内容，便于继续定位 Android 卡点。
- 版本更新到 `0.3.2`。

## 0.3.1 - 2026-05-28

- 根据实机日志修正 Android 连接策略：0.3.0 能收到手机 discovery 并正确回包，但手机没有主动连入 Deck TCP 端口。
- Android 手机路径恢复主动连接手机 `1716`，但 TLS 握手改用 client 模式；桌面 KDE Connect 保持原有 server 模式，避免影响已可用的电脑文件传输。
- `peer_tls_handshake_start/done` 日志新增 `tls_mode`，用于区分 Android client 模式和桌面 server 模式。
- 版本更新到 `0.3.1`。

## 0.3.0 - 2026-05-28

- 接收端统一网络路径优先级：同 Wi-Fi / 有线局域网优先，其次 EasyTier、ZeroTier、Tailscale，最后普通 VPN / 其他接口，并过滤 `lo`、Docker、虚拟桥、代理保留网段等无效地址。
- discovery 广播、identity 回包、主动 TCP 连接、前端 `Deck IP` 使用同一套路径选择逻辑，减少多网卡环境下选错源 IP。
- Android 手机 discovery 后默认不再主动连接手机 `1716`，改为回发 identity 并等待手机连入 Deck TCP 端口；桌面 KDE Connect 仍保留主动连接路径。
- discovery 日志新增路径类型，`peer_connect_skipped` 会记录 Android 兼容模式的跳过原因，方便继续实机判断连接是否进入 incoming TCP。
- 版本更新到 `0.3.0`。

## 0.2.9 - 2026-05-28

- 接收端向指定手机回发 identity 时优先选择同网段源 IP，例如 `192.0.2.144 -> 192.0.2.153`，避免多网卡环境下从 ZeroTier/EasyTier 等错误源地址回包。
- `identity_reply_sent` 日志新增实际发送源 IP；主动 TCP 连接也会绑定同网段源 IP。
- 接收端新增分阶段连接日志：incoming TCP、明文 identity、TLS handshake start/done、secure identity 收发，便于定位 Android KDE Connect 卡在哪一步。
- 前端进一步压缩页面：标题显示版本号，移除底部版本区域，`Deck IP` 只显示地址，接收文件改为一行 `文件: KDEck.zip -> Downloads`。

## 0.2.8 - 2026-05-28

- 前端连接区改为统一行布局，修正 `设备` 行和 `Deck IP` 行在 Decky 面板里左侧不对齐的问题。
- `接收目录` 从连接区移到新的 `接收文件` 模块，模块内新增 `最近文件`，稳定显示最近一次文件接收结果。
- 文件接收提示改为基于后端 `last_file` 状态，不再依赖容易被 discovery 日志覆盖的最近事件列表。
- discovery 收到手机 identity 后优先回发到来包源端口，同时保留 UDP 1716 兜底，提高 Android KDE Connect 发现和配对概率。
- identity 包统一携带当前实际 TCP 端口，并对同一设备的主动 TCP 连接增加短时间冷却，减少重复 TLS 连接失败干扰。
- 记录 0.2.8 实机问题：页面内容超出高度时触摸屏可滚动，但手柄按键无法继续翻到底部内容，后续需要调整 Decky 焦点导航和滚动布局。

## 0.2.7 - 2026-05-28

- 前端设备行改回 Decky `Field` 对齐方式，修正和 Deck IP、接收目录不对齐的问题。
- 设备行只显示设备名，不再显示“待配对”等状态文案；状态灯紧跟设备名，绿色表示已连接，灰暗表示未连接或连接中。
- 剪贴板输入框聚焦或点击时会尝试调用 Steam Deck 虚拟键盘接口，同时保留普通输入框 focus 行为。
- 记录 Android KDE Connect 在当前非热点同网段下仍扫不到 KDEck，后续需要按网络路径和 receiver 日志继续定位。
## 0.2.6 - 2026-05-28

- 修复 0.2.4/0.2.5 配对回归：TLS 对端证书指纹缺失时不再拒绝 `kdeconnect.pair`，避免 KDE Connect 客户端卡在 `Pair requested`。
- 配对信任策略改为优先使用证书指纹；拿不到指纹时记录 `device_id` 信任模式并写入事件日志。
- 前端连接区精简：删除上方版本行，将状态和设备合并为 `设备` 一行，并增加绿/黄/灰状态灯。
- 设备名显示增加截断，避免长设备名撑开 Decky 面板。
## 0.2.5 - 2026-05-28

- 项目更名：`DeckyLink` 统一改为 `KDEck`，包括插件显示名、KDE Connect 设备名、前端标题、README、第三方声明和发布包目录。
- Python 后端文件更名为 `kdeck_backend.py` 和 `kdeck_kde_receiver.py`，打包脚本同步更新。
- 发布包改为 `release/KDEck.zip`，zip 内顶层目录改为 `KDEck/`。
## 0.2.4 - 2026-05-27

- 接收端配对后保存对端证书 SHA-256 指纹；剪贴板和文件接收必须匹配 `deviceId + 证书指纹`，未信任设备只允许发起配对。
- 旧版无指纹配对记录不再显示为有效配对；从 0.2.3 或更早版本升级后需要重新配对 `KDEck`。
- TCP 监听端口改为在 KDE Connect `1714-1764` 范围内自动选择空闲端口，identity、状态和日志均使用实际端口。
- 接收端 `running` 状态改为基于 UDP/TCP 实际监听状态；停止时关闭 socket 并等待线程退出，减少重载或覆盖安装后的残留监听。
- `stop_daemon()` 改为只停止 KDEck 记录并带有 `KDECK_MANAGED_DAEMON=1` 标记的进程，不再全局 `pkill kdeconnectd`。
- 前端版本号除底部外同步显示在“连接”区，避免底部区域在 Decky 面板中不可见。
- 新增 `packageManager: pnpm@9.15.9`，并补充 receiver 信任校验、动态端口、文件名清理和 daemon 停止保护测试。

## 0.2.3 - 2026-05-27

- 修正文件接收测试记录：新版本文件接收已复测可用，之前“手机无完成提示、Deck 未收到文件”来自老版本误测。
- README 改为记录当前验证状态：剪贴板接收和手机发文件到 `/home/deck/Downloads` 均已验证可用。

## 0.2.2 - 2026-05-27

- 记录过一条文件接收异常测试结果：手机 KDE Connect 向 `KDEck` 发送文件时没有完成提示，Deck 的 `/home/deck/Downloads` 未收到文件。
- 该记录已在 0.2.3 更正：异常来自老版本误测，不代表新版本文件接收状态。

## 0.2.1 - 2026-05-27

- 增强 `KDEck` 隔离接收端的 LAN discovery：启动后按 `0 秒、2 秒、5 秒、10 秒` 密集广播，之后每 30 秒广播一次。
- discovery 广播改为按本地 IPv4 网卡分别绑定源 IP 发送，目标覆盖 `255.255.255.255` 和每个网卡自己的 broadcast 地址。
- 收到手机 `kdeconnect.identity` 后立即回发 `KDEck` identity；主动 TCP 连接手机失败时补发 UDP identity 作为回退。
- 后端状态新增 UDP/TCP 监听状态、监听端口、当前 IP 列表、网卡列表、最近发现手机、最近 discovery 收发、最近连接失败、最近剪贴板长度和最近文件接收结果。
- 接收端 JSONL 日志新增启停、证书、UDP/TCP bind、discovery、连接尝试、配对、剪贴板和文件接收事件。
- 前端连接区新增 `手机名` 简化状态，底部新增 `KDEck v0.2.1` 版本号。

## 0.2.0 - 2026-05-27

- 将连接状态改为单一摘要，直接显示设备名和可用状态，避免前端把后台和设备拆开造成误判。
- 新增 Deck IP 展示，优先显示 EasyTier、ZeroTier、Tailscale、无线网接口，方便手机端手动添加设备。
- 新增隔离的 `KDEck` KDE Connect 兼容接收端，使用独立设备 ID、证书和配置目录。
- 手机 KDE Connect 可单独配对 `KDEck` 设备，后续“发送剪贴板”会写入 KDEck 文本框。
- 新增手机 KDE Connect 文件接收，支持 `kdeconnect.share.request` payload 下载并保存到 `/home/deck/Downloads`。
- 新增接收端事件日志，记录配对、剪贴板、文件接收成功和失败。
- 剪贴板前端收敛为一行文本框和复制按钮，移除普通用户不需要的发送文本、发送文件和导出日志入口。
- 优化前端剪贴板文本框：左对齐、普通字重、固定一行高度，并将按钮改为 `同步文本框`。
- 新增 `get_connection_summary()`，一次返回状态、设备、Deck IP、接收目录和默认设备。
- 新增 `start_managed_kde()`、`stop_managed_kde()`、`get_managed_kde_status()`、`get_deck_ips()`、`get_notebook()`、`save_notebook()`、`export_logs()` RPC。
- 新增诊断日志导出 zip，包含 `kdeconnectd.log`、传输历史、记事本和插件管理的 daemon pid。
- 新增插件卸载清理逻辑，只删除 KDEck 自己的设置、运行时和日志目录，不删除 KDE Connect 配对配置和接收文件。
- 新增插件拉起 daemon 的 pid 记录，卸载时只尝试停止由 KDEck 拉起的 `kdeconnectd`。
- 移除发布清单中的 `debug` 标记，保留 `_root` 用于必要时降权调用 `deck` 用户会话。
- 新增发布打包脚本，生成可由 Decky Loader 插件导入入口直接导入的 `KDEck-0.2.0.zip`。
- 发布包改用 Python `zipfile` 生成，强制 zip 内部路径使用 `/`，避免 Windows 反斜杠导致 SteamOS 侧识别失败。
- 发布包文件名固定为 `KDEck.zip`，不再带版本号，便于 Decky Loader 手动覆盖安装。

## 0.1.1 - 2026-05-27

- 将模板调试前端改为简约 KDEck 操作面板。
- 前端只保留启动/刷新、设备选择、剪贴板、文本和文件发送入口。
- 移除前端 JSON 诊断输出，诊断细节由后端接口和日志负责。
- 修正 `kdeconnect-cli` 仅返回 `paired` 时的设备可达性判断。
- 修正后台拉起 `kdeconnectd` 后的 asyncio 清理警告。
- 修正 Decky Python 沙箱中后端模块导入路径。
- 兼容 Decky Loader 实机环境中的插件设置和运行时目录常量名。
- 为游戏模式补齐 `QT_QPA_PLATFORM=wayland` 和 `WAYLAND_DISPLAY=gamescope-0`，避免 `kdeconnectd` 走 xcb 后 core dump。
- 设备列表查询在 daemon 未就绪时不再调用 `kdeconnect-cli`，避免 DBus 自动激活用错误 Qt 平台反复拉起失败。
- 将 `kdeconnectd` 启动改为 `setsid` 明确拉起并保留日志，等待 DBus 就绪时间从 5 秒提高到 15 秒。
- KDE Connect 命令改用干净环境启动，避免继承 Decky/PyInstaller 的 `/tmp/_MEI...` 动态库路径导致 OpenSSL 版本冲突。

## 0.1.0 - 2026-05-27

- 建立 KDEck 第一版 Python 后端。
- 支持 KDE Connect 后台检测、启动、停止、重启和 DBus 就绪检查。
- 支持设备刷新、设备列表、配对、取消配对。
- 支持剪贴板发送、文本分享、Deck 当前剪贴板读写。
- 支持单文件分享、常用目录浏览和最近发送记录。
- 支持网络、DBus、KDE Connect 组件诊断。





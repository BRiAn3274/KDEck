# Changelog

## 0.9.6 - 2026-06-19

- 新增低风险可信设备存储迁移 helper：规范旧 `trusted-devices.json` 条目，补充 `device_id`、旧字段映射、`schema_version` 和 `migrated_at`，同时保留未知字段。
- 迁移时保持信任行为不变：字段不完整的旧记录不会被自动升级成受信的 `device_id` 记录。
- 新增结构化诊断错误 helper，统一 `code`、`stage`、`message` 和时间戳字段。
- receiver 诊断补充结构化错误：覆盖 UDP 绑定、TCP 监听绑定、主动 TCP/TLS 连接失败、证书初始化失败和发送传输失败。
- 优化 managed receiver 诊断摘要：传输超时、传输不完整、TCP 和 TLS 错误会显示明确状态和可读消息，不再只落到泛化连接失败。
- 前端发送失败提示改为按用户动作给建议，不再直接显示底层错误码或原始异常文案。
- 事件日志规范化：写入时统一补齐 `event`、`stage`、`device_id`、`time` 字段，并对路径、命令、证书路径、fingerprint 等敏感字段做脱敏。
- 事件日志新增同类高频错误限流，降低网络异常时 `peer_connect_failed`、packet 错误和 payload 重试等事件刷屏风险。
- 诊断导出包新增固定日志策略 metadata 和 `status-snapshot.json`，manifest/status 快照均使用脱敏版本。
- 新增低风险连接状态记录：用有限状态值记录 `idle`、`discovered`、`trusted`、`connecting`、`connected`、`backoff`、`paused_desktop`、`failed` 的变化，但不改变连接、配对、TLS 或重试决策。
- 新增 `REAL_DEVICE_VALIDATION_MATRIX.zh-CN.md`，覆盖覆盖安装、配对继承、发送页、传输、诊断日志和状态机的实机验收项。
- 补充回归测试，覆盖 trust 迁移安全边界和传输错误诊断摘要。
- 暂缓高风险连接生命周期项：per-device 状态表、单 session 约束和退避重试不放入 0.9.6。
- 版本更新到 `0.9.6`。

## 0.9.5 - 2026-06-19

- 发送页设备切换放回右侧标题下方的正常布局流，左对齐、正常宽度，不再负上移到 Steam/Decky 顶部遮罩范围内。
- 发送任务轮询降频：有运行中任务时每 900 ms 刷新，空闲时每 3000 ms 刷新，减少无意义轮询。
- 发送页做内部结构拆分，但版本仍归入 `0.9.5`：`SendPage.tsx` 现在保留路由、发送任务状态和 `SidebarNavigation` 装配。
- 发送页 UI 组件移动到 `src/features/send/components/`，包括设备切换、文件行、缩略图、存档分组和空状态。
- 发送页纯函数和共享类型移动到 `src/features/send/domain/`，包括分类元数据、设备选择辅助函数、格式化、文件分组和行样式。
- 发送页低风险状态移动到 `src/features/send/hooks/`：`useSendTargets` 管理设备列表和首选设备切换，`useSendableFiles` 管理分类扫描和刷新。
- 保留 0.9.4 的低风险后端和发布增强：发布脚本自动构建、包内版本校验、SHA256 输出、外置库存档元数据、更多 librarycache 图标匹配、缩略图缓存清理和传输历史裁剪测试。
- 版本更新到 `0.9.5`。

## 0.9.4 - 2026-06-19

- 增强 `tools/package_release.py`：打包默认执行 `pnpm build`，校验包内 `package.json` 版本和源码版本一致，兼容 Windows `pnpm.cmd`，正确处理 `--skip-build`，并自动输出 SHA256。
- 增强存档游戏名识别：读取 Steam `libraryfolders.vdf`，支持从默认库和外置 Steam 库查找 appmanifest。
- 增强存档缩略图命中率：补充更多 Steam `librarycache` 图片命名匹配规则，找不到时仍回落占位图标。
- 新增缩略图缓存清理：按时间和数量限制清理生成的 thumbnail-cache，避免长期积累。
- 补充外置库游戏名、宽松 librarycache 图标匹配、缩略图缓存清理和 JSONL 传输历史裁剪测试。
- 调整发送页顶部区域，尽量让左侧标题、右侧页面标题、设备切换和第一行文件卡片处于更接近的视觉高度。
- 版本更新到 `0.9.4`。

## 0.9.3 - 2026-06-19

- 修复设备切换 bug：当前首选目标离线、但另一个可信设备在线时，发送页会切到在线设备，不再要求离线设备也连接后才能切换。
- 删除发送页内容区重复分类标题，保留 `SidebarNavigation` 原生页面标题作为唯一标题。
- 将设备切换移动到原搜索栏所在的右上区域，并限制宽度。
- 存档页新增按游戏/App 分组：先显示游戏行，按 A 展开后显示该游戏下的具体存档文件，不新增二级页面。
- 后端为存档文件补充可选 `app_name`，从 Steam `appmanifest_*.acf` 读取游戏名；前端优先显示游戏名，找不到时回退 `App <id>`。
- 存档/游戏行继续复用 Steam `librarycache` 缩略图逻辑，命中时显示游戏图标。
- 版本更新到 `0.9.3`。

## 0.9.2 - 2026-06-19

- 发送页整体改用 Decky `SidebarNavigation`：左侧分类栏、选中态和焦点行为交给 Decky 原生侧栏组件处理。
- 删除自绘左栏、手写侧栏焦点桥接和低频搜索栏。
- 右侧发送体验继续保留：设备切换、文件列表、缩略图、行内进度、成功反馈和存档缩略图逻辑。
- 保留原有发送页路由兼容，将截图、录像、存档、日志路由映射到新的 `SidebarNavigation` 页面状态。
- 本版只处理发送页前端，不改后端、发现、配对、TLS 或安全策略。
- 版本更新到 `0.9.2`。

## 0.9.1 - 2026-06-19

- 自绘发送页左栏从 268 px 收窄到 224 px，分类文字和图标同步缩小，为右侧文件列表留出更多空间。
- 将左栏焦点高亮从明显自绘的渐变/边框改为更克制的整行高亮，尽量贴近 Decky 风格。
- 页面背景铺到底部，列表内部保留 68 px 安全空间，减少与 Steam 底部菜单之间的可见缝隙。
- 让存档文件也走现有缩略图接口，可在 Steam `librarycache` 命中时显示游戏图标。
- 版本更新到 `0.9.1`。

## 0.9.0 - 2026-06-19

- 发送页重做为独立左右分栏体验，分类包含截图、录像、存档和日志。
- 文件发送改为单文件操作：文件行按 A 直接发送当前文件，不再使用多选模式。
- 文件行改为接近 DeckyMusic 的结构：缩略图/图标、文件名、元信息和紧凑发送按钮。
- 新增行内传输反馈：发送中显示 Spinner 和底部进度条，成功时短暂显示完成图标和满进度条，失败时 toast 提示。
- 截图和录像使用 `get_thumbnail_base64` 加载缩略图。
- 设备切换增强可读性，显示当前设备序号和在线/离线状态；长文件名和元信息安全省略，避免挤出发送按钮。
- 优化发送页空态、扫描失败态和 `transfer_incomplete` 前端错误文案。
- 前端缩略图请求新增队列和缓存，限制并发，降低录像较多时同时触发后端缩略图生成的压力。
- 后端低风险补充 Steam `librarycache` 存档缩略图支持，找不到图时仍回落占位。
- 主面板发送入口增加目标/最近文件上下文，并清理未使用的 `PreferredDeviceResponse` 类型。

## 0.8.8 - 2026-06-11

- 卸载 KDEck 时保留 managed KDE Connect 身份、证书和可信设备数据，覆盖安装或重装后可继承原有配对；新增显式重置身份入口供用户主动清除配对。
- 发送页路由改为 DeckyClash 同款结构：只注册 `/kdeck/send` 一个基线路由，`/kdeck/send/screenshots` 等子路径由发送页内部识别，避免多个同前缀路由互相抢匹配。
- 主页点击“发送文件”恢复 `Router.CloseSideMenus()` 后再进入全屏发送页，和 DeckyClash 的全屏页面入口保持一致，修复 0.8.7 仍可能静默打开被拉伸主页的问题。
- 发送页按 B/返回时先走 Steam 路由返回，随后尝试打开 Decky QAM 标签，避免返回到插件商店/设置页面。
- 构建标记更新为 `KDEck v0.8.8 build marker`，便于实机确认已加载 0.8.8 前端 bundle。

## 0.8.7 - 2026-06-10

- 修复 0.8.6 的路由回归：删除错误的 `/kdeck` 全屏路由，避免 `/kdeck/send/...` 被主页路由抢先匹配，导致点击“发送文件”进入被拉伸的主页。
- 发送页不再自定义 B 键返回到 `/kdeck`，恢复 Decky 默认返回栈处理。
- 从主页进入发送页时不再调用 `Router.CloseSideMenus()`，减少破坏 QAM 返回栈的风险。

## 0.8.6 - 2026-06-10

- 修复发送页手柄左右焦点：左侧分类栏与右侧内容区现在通过左右方向键切换焦点，上下键继续负责区域内移动。
- 修复发送页返回行为：发送页按返回键时导航到 KDEck 插件主页路由，避免回到插件商店/设置页面。
- 发送页底部目标设备和“发送到设备”改为紧凑自绘 Focusable 按钮，减少面积并统一页面风格。
- 日志页“发送诊断包”改为同一套紧凑按钮样式，不再使用 Decky 默认大按钮。
- 左侧栏进一步收窄，`KDEck` 标题和发送页内容整体下移，降低顶部裁切风险。
- 后端新增 `get_send_targets()`，统一返回发送页目标设备列表、连接状态和 preferred device。
- `set_preferred_device()` 新增可信设备校验，避免保存无效目标设备。
- 后端测试增加到 60 个，覆盖发送目标列表和 preferred device 校验。

## 0.8.5 - 2026-06-10

- 主页连接区移除设备选择下拉框，改为只显示当前已连接设备概览，发送目标交互收敛到发送页。
- “重启接收”按钮仅在接收器未运行、UDP/TCP 异常、桌面模式暂停或存在错误时显示，正常状态下不再占用主页空间。
- 发送页底部栏移除“清空”按钮，改为“已选数量/大小 + 目标设备 + 发送到设备”的紧凑结构。
- 发送页目标设备支持多设备选择：从可信设备列表读取设备名，优先使用用户偏好，其次使用已连接设备；切换后同步保存为 preferred device。
- 存档页新增按 App/source/父目录分组显示。分组行显示文件数量、总大小和最近修改时间，展开后显示具体存档文件。
- 左侧栏收窄，发送页标题、搜索栏和内容区整体下移，减少顶部裁切和底部遮挡风险。

## 0.8.4 - 2026-06-10

- 发送页彻底绕开 `SidebarNavigation` 内容标题层，改为 KDEck 自绘两栏布局，避免 SteamOS 当前实现强制重复渲染“截图”等页面标题。
- 关键布局全部改为 React 内联样式，包括左侧导航、右侧标题搜索栏、文件行、缩略图尺寸、滚动区域和底部安全距离，不再依赖 `<style>` 或 `injectCssIntoTab` 是否被 Decky 接受。
- 保留 `KDEck v0.8.4 build marker`，用于实机确认加载的是自绘内联布局版本。

## 0.8.3 - 2026-06-10

- 修复发送页标题重复：左侧导航标题只保留 `KDEck`，右侧内容区由每个分类页独立渲染唯一标题，SidebarNavigation 内置页面标题不再重复显示。
- 修复搜索框位置：搜索框移到右侧内容区标题行，保持“分类标题 + 搜索文件”的布局，避免挤在左侧导航标题区域。
- 修复发送页下半屏黑色遮挡风险：内容区改为固定头部、可滚动文件列表和底部安全区，底部安全距离提升到 108px。
- 优化发送页状态处理：扫描失败时显示明确的失败空状态；选中数量按当前分类完整文件集计算，不再受搜索过滤影响。
- 优化发送任务汇总：底部传输汇总只统计当前分类中的运行任务，避免切换分类时显示无关任务。
- 发布包标记更新为 `KDEck v0.8.3 build marker`，便于实机确认是否加载了最新前端 bundle。

## 0.8.2 - 2026-06-10

- 发送页架构重构：每个标签页（截图/录像/日志/存档）改为独立自管理组件（DeckyClash 模式），各自维护文件列表、缩略图和任务轮询状态，根治 SidebarNavigation 缓存导致的切换不刷新问题。
- 搜索框从左侧导航区移至右侧内容区顶部，每个标签页独立渲染标题和搜索栏。
- 新增文件多选功能：点击文件行切换选中状态，底部显示已选数量和总大小，支持批量"发送到设备"。
- 文件行布局改为横向紧凑结构：96×54 缩略图/图标区、两行文字（文件名 + 元信息）、右侧选择/状态区。
- 元信息按分类精简显示：截图/录像显示大小和时间，日志显示来源、大小和时间，存档显示来源或 App ID、大小和时间。
- 移除"推荐"标记，文件名前不再显示推荐字样。
- 文案统一为"发送到设备"，不再使用"发送到手机"。
- 底部增加 96px 安全距离，避免被 SteamOS 底部操作提示栏遮挡。
- 空状态"暂无文件"和"正在扫描文件…"在右侧内容区居中显示。
- 路由显式传入 `initialPage` 参数，分类与 URL 保持一致。
- 传输中的文件行内联显示进度条、速率和剩余时间；底部栏显示整体传输汇总。

## 0.8.1 - 2026-06-10

- 发送文件页面重构为基于 Decky/社区组件的简洁结构：使用 `SidebarNavigation`、`PanelSection`、`Focusable`、`Dropdown`、`ButtonItem` 和 `ProgressBarWithInfo`。
- 新增 Deck 到设备的后台发送任务。任务状态会返回阶段、已发送字节、总字节、速率、预计剩余时间和最终错误详情，页面不再阻塞等待发送结束。
- TLS 文件服务发送循环新增真实进度回报，替代旧版只显示动画、不显示速率的进度提示。
- 日志列表新增来源和摘要元数据。日志分类会优先展示 KDEck Receiver、Decky 插件、KDE Connect daemon 和传输历史相关日志。
- 日志页新增“发送诊断包”操作：先导出现有脱敏日志 zip，再通过同一套可追踪发送任务发给手机或电脑。
- 文件列表新增最近修改、文件大小、文件名排序，以及“全部/推荐”过滤。
- 补充发送任务进度/结果和日志元数据测试。
- 修复 `activeJob` 回退逻辑：无运行中任务时不再显示已完成的旧任务信息。
- 优化 `contentFor` 仅渲染当前激活标签页的内容，避免每次渲染都构建全部四个标签页的 JSX 树。
- 修复缩略图加载 effect 因依赖 `thumbnails` 状态而反复重触发的问题，改用 ref 检查已加载项。
- 移除独立的"当前任务"面板——传输进度现以内联进度条显示在文件行下方，空闲时不占空间。
- 移除排序和过滤下拉框——文件始终按最近修改排序，搜索栏保留在标题区域。
- 根治切换标签页内容空白 bug：所有标签页始终提供完整 JSX 内容（不再使用 `null`），彻底解决 SidebarNavigation 缓存引用问题。
- 日志页新增"发送诊断包"按钮。
- 修复 zip 打包：补充缺失的 `LICENSE`、`main.py`，并使用正确的顶层 `KDEck/` 目录结构以兼容 Decky 商店导入。
- 连接页设备显示重构：设备名和状态灯现绑定到下拉框选中的设备。

## 0.8.0 - 2026-06-10

- 修复 `send_share_request_to_peer` 中 fallback TLS 角色错误：当没有持久连接时，根据受信设备的 `device_type` 正确判断 TLS 客户端/服务端角色（Android → TLS 客户端，桌面设备 → TLS 服务端），修复向非 Android 设备发送文件失败的问题。
- 修复重连循环静默放弃：`_connect_to_peer` 现返回布尔值，`_active_reconnect_loop` 据此进行指数退避重试（`RECONNECT_BASE_DELAY=2` → `RECONNECT_MAX_DELAY=60`），不再依赖内部被吞掉的异常。
- 修复 `EventLogger.tail` 排序：磁盘日志与内存 buffer 的事件现按时间顺序合并（从旧到新），修复事件日志显示乱序问题。
- 新增 `PACKET_PING` 到广播能力列表，并实现 ping 回复处理器：受信设备的 `kdeconnect.ping` 包将立即收到 ping 回复，提升保活兼容性。
- 修复 `MainPanel` 中 React 反模式：将 `setSelectedDevice` 初始化从渲染阶段移入 `useEffect`，依赖项为受信设备列表 ID 的稳定序列化值。

## 0.7.9 - 2026-06-10

- 文件传输 chunk 从 64 KB 增大到 256 KB，减少系统调用开销，在高速 WiFi 下吞吐量提升约 20-30%。
- 文件接收 socket 新增 `SO_RCVBUF`（1 MB），文件发送 socket 新增 `SO_SNDBUF`（1 MB），让 TCP 窗口充分利用高带宽 WiFi 连接。
- 文件接收循环改用 `recv_into()` + 预分配 buffer，消除每个 chunk 的内存分配，降低 GC 压力。
- `FILE_SEND_CHUNK_BYTES` 重命名为 `FILE_CHUNK_BYTES`，发送和接收路径共用同一 chunk 大小。

## 0.7.8 - 2026-06-10

- 修复发送页面切换分类时搜索框消失的问题：移除所有页面配置的 `hideTitle: true`，确保切换截图/录像/日志/存档时搜索栏始终可见。
- 修复发送页面切换分类时文件列表不刷新的问题：移除 `contentFor` 中 `category !== currentPage` 的守卫判断，并为 `FileListContent` 添加 `key={category}` 强制重新挂载。
- 修复连接区域字体不一致：设备名现在使用 `infoRowStyle`，与 "Deck IP" 等行的字体大小和粗细统一。
- 移除 TextField `placeholder` 属性上的 `as any` 类型断言，改用 `InputHTMLAttributes<HTMLInputElement>` 正确类型。
- 移除 `onKeyDown` 处理器上的 `as any` 类型断言，类型现已原生匹配。
- 剪贴板输入框 CSS 的 `!important` 声明从 5 个减少到 2 个，移除了 `font-weight`、`line-height`、`text-align` 上不必要的覆盖。

## 0.7.7 - 2026-06-10

- 提取事件日志子系统到 `kdeck_kde_events.py`（~116 行）：`EventLogger` 类，支持缓冲 JSONL 写入、自动轮转和尾部读取；`KDEckKdeReceiver` 通过 `self.events` 委托所有事件操作。
- 提取信任管理到 `kdeck_kde_trust.py`（~104 行）：独立的 `read_trusted_devices`、`write_trusted_devices`、`is_trusted_device` 和 `remember_trusted_device_metadata` 函数；接收器保留薄包装方法以保持测试兼容性。
- 提取文件传输工具到 `kdeck_kde_transfer.py`（~103 行）：独立的 `safe_filename`、`unique_destination`、`has_enough_space`、`record_file_failure` 和 `connect_to_peer_control_socket` 函数。
- `kdeck_kde_receiver.py` 从 ~1760 行减至 ~1660 行，类现在作为编排器委托给六个提取模块。
- 为 `KDEckKdeReceiver` 中 19 个关键公开和生命周期方法添加单行文档字符串。
- 将固定重连延迟 `(1, 3, 8, 20)` 替换为指数退避，从 2 秒开始翻倍，上限 60 秒，提升可信对端重连弹性。
- 新增 payload 接收重试：连接或传输失败时最多重试 2 次，间隔 3 秒；信任验证失败不重试。
- TLS 证书生成改用 Python `cryptography` 库为主方法（跨平台，无需外部工具）；`openssl` CLI 作为无 `cryptography` 环境的回退方案保留。
- 全部 56 个测试通过（此前因 Windows OpenSSL 熵源不足导致 1 个失败，已修复）。
- 版本更新到 0.7.7。

## 0.7.6 - 2026-06-08

- 搜索框移入 `SidebarNavigation` 的 `title` prop，与内置分类标题行对齐；所有页面设置 `hideTitle: true`。
- 12 处静默 `.catch(() => undefined)` 全部替换为带描述的 `console.warn("[KDEck] ...")` 调用，涵盖 `useClipboard`、`useConnection`、`SendPage` 和 `MainPanel`。
- `SendPage` 和 `MainPanel` 中的 `<style>` 标签改为 Decky 官方 `injectCssIntoTab` / `removeCssFromTab` 一次性注入，避免重复渲染时重复插入样式。
- 剪贴板输入框 CSS 选择器从 `.kdeck-clipboard-input` 改为 `.kdeck-clipboard-input input`，更精确地覆盖内部 `<input>` 元素样式。
- 从 `kdeck_kde_receiver.py` 提取协议常量和包编解码到 `kdeck_kde_protocol.py`（~134 行）。
- 提取网络接口发现、广播目标计算、端口绑定、IP 分类到 `kdeck_kde_network.py`（~238 行）。
- 提取 TLS 证书生成和对端指纹校验到 `kdeck_kde_tls.py`（~78 行）。
- `kdeck_network.py` 改为从新模块导入共享工具函数，消除重复代码。
- `kdeck_kde_receiver.py` 从 1924 行减至 ~1750 行，类通过薄包装方法委托到提取模块，保持测试兼容性。
- `KDEckKdeReceiver` 类新增 docstring 说明模块委托架构。
- 所有 socket 创建点新增 `SO_KEEPALIVE`：incoming TCP、incoming BT 桥接、outgoing peer 连接、payload 接收、文件发送 accept、发送回退控制 socket。
- payload 接收连接超时从 15 秒增加到 30 秒，兼容较慢网络。
- 29 个平台可用测试全部通过（1 个因 Windows OpenSSL 熵源不足跳过）。
- 版本更新到 0.7.6。

## 0.7.5 - 2026-06-08

- 文件发送新增 ref 同步锁和 1 秒冷却，防止触屏连击触发重复发送。
- 通知系统升级：同类通知 3 秒冷却 + 自动关闭上一条，避免通知刷屏。
- 合并 `useConnection` 通知路径：`notifyManagedEvents` 在 `notifyLastFile` 已处理同一失败时跳过，修复文件接收失败双重通知。
- 用 `SidebarNavigation` 的 `page` + `onPageRequested` + `identifier` 受控 API 替代侵入性的 `history.pushState`/`replaceState` monkey-patch。
- 修复渲染阶段 `setState` 反模式：tab 切换改在 `onPageRequested` 回调中清空状态。
- 触屏防误触：触摸输入需要长按 0.8 秒并显示动画进度环才触发发送，手柄 A 键通过 `Focusable.onActivate` 直接发送。
- 文件行从 `ButtonItem` 切换到官方 `Focusable` 组件，用 `focusWithinClassName` 替代 `:focus-within` CSS 选择器。
- 主面板移除蓝牙状态行（保留 Deck IP 用于手动连接排障）。
- 主面板新增官方 `Dropdown` 组件做多设备切换；发送页移除冗余的 `DeviceSelector`。
- `!important` CSS 覆盖从 12 处减至 4 处，利用 `Focusable` 焦点类和 inline style。
- 清理死代码：`inputStyle`、`keyboardHint`、`device`/`status`/`btReady`/`btUnavailable`/`btDisabled` 等 i18n key、`DeviceRow`、`DeviceSelector`。
- 新增 `PreferredDeviceResponse` 类型，消除首选设备 API 的 `as any`。
- TextField 的 `aria-label` 和 `className` 改为直接属性传递，不再用 spread `as any`。
- 版本更新到 0.7.5。

## 0.7.4 - 2026-06-08

- 新增 `kdeconnect.ping` 包类型到能力和处理器，响应 peer 的 keepalive ping。
- 所有 6 个 socket 创建点新增 `SO_KEEPALIVE` 和 TCP keepalive 调优（idle=30s, interval=10s, count=3），匹配 KDE Connect C++ 默认值。
- 修复 `send_share_request_to_peer` 回退 TLS 角色：`PROTOCOL_TLS_CLIENT` 改为 `PROTOCOL_TLS_SERVER` + `server_side=True`，匹配 KDE Connect TLS 约定（TCP 客户端 = TLS 服务端）。
- 修复 `_packet_payload_size` 接受 `-1`（未知大小/无限流），这是 KDE Connect 协议中的合法值。
- 配对包新增 timestamp 字段，符合协议规范。
- TLS 握手后新增身份验证：peer 设备 ID 与证书 Common Name 比对。
- 重写 `_receive_share_request`，支持 URL 分享、`payloadSize=-1` 流式接收，并在 `_handle_packet` 中线程化调用。
- `share_file` 改为通过托管接收器发送，不再依赖 `kdeconnect-cli`。
- 版本更新到 0.7.4。

## 0.7.1 - 2026-06-07

- 修复托管接收器启动路径：KDEck 绑定 KDE Connect 端口前，会先停止 deck 用户下的 `kdeconnectd`，避免游戏模式里官方 daemon 抢走 Windows 文件传输流量。
- 诊断信息新增当前 `kdeconnectd` PID，并在 KDEck 托管接收器与官方 daemon 同时运行时给出冲突提示。
- 新增 `tools/verify-release.ps1`，在手动安装到 Deck 前统一执行 Windows 检查、WSL 临时副本检查、release 打包、包内版本校验和 SHA256 输出。
- 新增回归测试，覆盖托管接收器启动前清理残留用户 daemon 的行为。
- 版本更新到 0.7.1。

## 0.6.8 - 2026-06-07

- 移除发送页重复分类标题。`SidebarNavigation` 已经会渲染当前页面标题，KDEck 不再在内容区额外渲染第二个“截图”。
- 保留右侧紧凑搜索框，放在内置页面标题区域下方并右对齐。
- 版本更新到 0.6.8。

## 0.6.7 - 2026-06-07

- QAM 面板里的发送文件入口改为先关闭 Decky 侧边栏，再跳转到 `/kdeck/send/screenshots`，对齐 DeckyClash 的独立路由行为，减少返回键层级。
- 发送页搜索框移动到分类标题右上角，与当前分类标题同一行，并缩短、变细。
- 增加缩略图文件行的安全间距，并调整缩略图放大原点，选中放大后不再贴近文件名。
- 无缩略图分类保持单列文件行，日志和存档不再继承截图列表的缩略图缩进。
- 版本更新到 0.6.7。

## 0.6.6 - 2026-06-06

- 修复游戏模式隔离回归：启动 KDEck receiver 时会停止 KDEck 自己拉起的 `kdeconnectd`，避免 Windows KDE Connect 同时看到 `KDEck` 和桌面端 `steamdeck` 身份。
- 移除 managed daemon watchdog 自动拉起官方 KDE Connect daemon 的路径，避免隔离 receiver 运行时官方 daemon 被重新带起来。
- 放宽发送页可信设备预检：当前选择设备已在 KDEck trusted 列表中时，不再只因为 discovery 超过 180 秒就提前拦截，而是交给后端进行真实连接尝试。
- 配对记录新增 `last_seen`，与 `last_connected` 一起用于保持可信设备状态一致。
- 版本更新到 0.6.6。

## 0.6.5 - 2026-06-06

- 发送文件页面改为基于 Decky `SidebarNavigation` 的独立左侧栏页面，把之前 CDP 调试出的布局落实到源码。
- 发送页补齐“存档”路由，与截图、录像、日志并列显示。
- 新增缩略图 RPC：截图优先读取 Steam 已有缩略图；录像优先读取已有缩略图，找不到时在系统存在 `ffmpeg` 的情况下抽帧并缓存。
- QAM 主面板把“接收文件”和“发送文件”合并为“收发文件”，第一行是发送按钮，第二行是最近接收文件和目录。
- 剪贴板接收提示改为设备中性文案，不再默认写成“手机剪贴板”。
- 保留发送瞬间连接校验：进入发送页不要求已连接目标，按 A 或点击文件发送时再校验当前选择设备是否在线。
- 版本更新到 0.6.5。

## 0.6.2 - 2026-06-06

- 发送文件页面恢复为全屏左右分栏布局：左侧分类栏，右侧搜索和缩略图列表，选中文件缩略图放大、文件名高亮，发送时显示波动进度条。
- 新增“存档”分类，扫描常见 Steam userdata 和 Proton compatdata 存档候选文件。
- Deck 到手机的文件服务改为分块流式发送，不再在发送前把整个文件一次性读入内存。
- 新增 receiver 公共 API，用于刷新事件日志和读写可信设备状态，backend 编排层不再直接调用这些 receiver 私有 helper。
- 补充分块 TLS 文件服务和 receiver 可信设备公共 API 测试。
- 版本更新到 0.6.2。

## 0.6.1 - 2026-06-06

- 修复受管 daemon watchdog：改为使用 Decky 传入的事件循环，不再引用未定义的 backend 字段。
- 修复发送文件前的在线校验：现在必须是当前选择的目标设备在最近 180 秒内被发现。
- 从商店构建中移除面板内开发更新路径；开发部署保留在本地工具脚本中。
- 修复蓝牙桥接启动：先绑定本地 TCP 桥接端口再启动 helper，并避免等待 helper 输出时无限阻塞。
- 修复 `decky.pyi` 的 `ruff check` 格式问题。
- 版本更新到 0.6.1。

## 0.6.0 - 2026-06-05

- 键盘输入：剪贴板和搜索框从原生 `<input>` 改为 `@decky/ui` `TextField`，Steam Deck 屏幕键盘在 QAM 面板和收发文件路由页面都能正常唤起（路由页面没有 `SteamClient.System`）。
- 搜索框：收发文件页面右上角新增搜索输入框，与分类标题对齐，可按文件名过滤。使用 `TextField` 保证键盘支持。
- 发送前验证：发送文件前会重新检查 `discovered_devices` 的 `last_seen` 是否在 180 秒内，如果没有在线设备会弹 toast 提示。
- 进度动画：发送文件时显示滑动渐变进度条，替代原来的静态绿条。
- 隐藏命令双击触发："同步文本框"按钮现在支持双击执行 `:kdeck` 隐藏调试命令，与在文本框按 Enter 等效。
- 移除剪贴板下方的键盘提示行（`TextField` 已原生处理键盘唤起）。
- i18n：新增 `noDeviceConnected` 和 `searchPlaceholder` 中英文字符串。
- CI：修复 Python 后端 22 个预先存在的 ruff lint 错误（未使用 import、import 排序、模块级 import 位置、lambda 循环变量绑定）。
- 版本更新到 0.6.0。

## 0.5.6 - 2026-06-04

- 大规模代码重构：后端拆分为模块文件（`kdeck_daemon.py`、`kdeck_clipboard.py`、`kdeck_config.py`、`kdeck_network.py`、`kdeck_file_manager.py`、`kdeck_bt_helper.py`、`kdeck_diagnostics.py`）。前端重构为页面（`MainPanel.tsx`、`SendPage.tsx`）、hooks（`useClipboard`、`useConnection`、`useToast`）、组件和共享工具函数。
- 发送文件入口：QAM 侧边栏"发送文件"按钮通过 Decky `routerHook` 跳转到全屏路由页面。
- daemon 自动重启：受管 daemon 异常退出后会自动重启。
- 蓝牙状态显示：主面板显示蓝牙连接状态，诊断信息新增端口耗尽提示。
- SteamOS 蓝牙修复：修复 BT helper 在 SteamOS 上的启动问题。
- 手柄友好发送页：文件行改为完整 `ButtonItem`，支持手柄 A 键直接触发发送。
- 键盘提示：剪贴板输入框下方新增键盘使用提示行（后在 0.6.0 移除）。
- 版本更新到 0.5.6。

## 0.5.5 - 2026-06-04

- 蓝牙支持：RFCOMM 通道 22 + SDP 服务注册，PC/手机可通过蓝牙发现并连接。复用现有 TLS + 协议处理，蓝牙不可用时自动降级。
- 发送文件：全屏独立页面（Decky routerHook），三标签切换截图/录像/日志，从 Decky 侧边栏进入。
- 开发部署：`tools/deploy_to_deck.ps1` 和 `tools/deploy_to_deck.sh` 提供商店构建之外的本地 SSH 部署。
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

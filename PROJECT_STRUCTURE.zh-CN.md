# KDEck 项目结构

本文档用于区分源码、测试、工具和可再生成产物，避免发布包、缓存或依赖目录混入仓库根目录。

## 核心源码

- `src/`：Decky 前端源码，包含主面板、发送页面、hooks、组件、类型和本地化文本。
- `backend/src/`：后端 Python 源码，包含 Decky API facade、KDE Connect receiver、文件管理、诊断、网络、剪贴板、更新等模块。
- `main.py`：Decky 插件入口，负责初始化后端并暴露前后端调用方法。
- `plugin.json`：Decky 插件元信息。

## 测试与工具

- `tests/`：后端单元测试。
- `tools/`：打包、部署、发布校验和本地调试工具。
- `.github/`：GitHub issue 模板和 CI workflow。

## 配置与依赖锁定

- `package.json`、`pnpm-lock.yaml`：前端构建依赖和锁定版本。
- `rollup.config.js`、`tsconfig.json`：前端构建与 TypeScript 配置。
- `pyproject.toml`：Python 工具配置。
- `decky.pyi`：Decky Python API 类型提示。

## 文档与发布材料

- `README.md`、`README.zh-CN.md`：项目说明。
- `CHANGELOG.md`、`CHANGELOG.zh-CN.md`：版本变更记录。
- `REAL_DEVICE_VALIDATION_MATRIX.zh-CN.md`：实机验证矩阵。
- `STORE_SUBMISSION.md`：插件商店提交材料。
- `THIRD_PARTY_NOTICES.md`：第三方依赖声明。
- `LICENSE`：许可证。

## 可再生成产物

以下内容不应提交到 Git：

- `node_modules/`、`.pnpm-store/`：Node 依赖缓存，可通过 `pnpm install` 恢复。
- `dist/`：前端构建产物，可通过 `pnpm build` 生成。
- `release/`：发布包输出目录，可通过 `tools/package_release.py` 或对应 PowerShell 脚本生成。
- `.pytest_cache/`、`.ruff_cache/`、`__pycache__/`：测试和 Python 缓存。
- `KDEck-v*.zip`：历史发布包。如需本地保留，放在 `release/archive/`，仍不提交。

## 常用命令

```powershell
pnpm install
pnpm build
python -m unittest discover -s tests
python tools/package_release.py
```

## 本地验证流程

修改后建议按影响范围执行验证：

- 只改 Python 后端：运行 `python -m unittest discover -s tests` 和 `python -m ruff check`。
- 只改前端源码：运行 `pnpm build`。
- 修改打包、发布或插件入口：运行完整发布验证。

完整发布验证：

```powershell
pnpm install
pnpm build
python -m unittest discover -s tests
python -m ruff check
python tools/package_release.py
```

`tools/package_release.py` 会生成 `release/KDEck.zip`，并校验包内最小必需文件：

- `KDEck/plugin.json`
- `KDEck/package.json`
- `KDEck/main.py`
- `KDEck/dist/index.js`
- `KDEck/assets/logo.png`
- `KDEck/py_modules/.keep`
- `KDEck/backend/src/kdeck_backend.py`
- `KDEck/backend/src/kdeck_kde_receiver.py`

发布前确认 `dist/` 与 `release/` 都由当前源码重新生成，不手工修改构建产物。

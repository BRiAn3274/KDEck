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
python -m py_compile main.py backend/src/kdeck_backend.py backend/src/kdeck_kde_receiver.py tools/package_release.py
python tools/package_release.py
```

## 提交前检查

- `package.json` 已按语义化版本更新。
- `src/index.tsx` 中显示的版本号和 `package.json` 一致。
- `CHANGELOG.md` 已记录本次改动。
- `plugin.json` 的 `publish.description`、`publish.tags`、`publish.image` 可用。
- `LICENSE` 存在。
- `README.md` 面向普通用户，避免塞入内部调试日志。
- `release/KDEck.zip` 可以手动导入 Decky Loader。

## 插件数据库 PR

Decky 插件商店不是直接上传 zip，而是向 `SteamDeckHomebrew/decky-plugin-database` 提交 PR，将本仓库作为 submodule 加到 `plugins/KDEck`。

参考：

- `https://github.com/SteamDeckHomebrew/decky-plugin-template`
- `https://github.com/SteamDeckHomebrew/decky-plugin-database`

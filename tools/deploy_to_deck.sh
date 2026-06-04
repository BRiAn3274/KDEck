#!/usr/bin/env bash
# KDEck 一键部署到 Steam Deck
# 用法: bash tools/deploy_to_deck.sh <deck-ip>
# 依赖: ssh 已配置 (Deck 的 deck 用户密码或密钥)

set -e

DECK_IP="${1:-10.70.21.37}"
DECK_USER="deck"
PLUGIN_DIR="/home/deck/homebrew/plugins/KDEck"
ZIP_FILE="release/KDEck.zip"

echo "=== 构建 KDEck ==="
pnpm run build
python -m unittest discover -s tests
python tools/package_release.py

echo "=== 部署到 $DECK_IP ==="
scp "$ZIP_FILE" "${DECK_USER}@${DECK_IP}:~/Downloads/KDEck.zip"

echo "=== 安装插件 ==="
ssh "${DECK_USER}@${DECK_IP}" bash << 'ENDSCRIPT'
    PLUGIN_DIR="/home/deck/homebrew/plugins/KDEck"
    # 备份旧版本
    if [ -d "$PLUGIN_DIR" ]; then
        rm -rf "${PLUGIN_DIR}.bak"
        cp -r "$PLUGIN_DIR" "${PLUGIN_DIR}.bak"
        rm -rf "$PLUGIN_DIR"
    fi
    mkdir -p "$PLUGIN_DIR"
    cd "$PLUGIN_DIR"
    unzip -o ~/Downloads/KDEck.zip
    echo "KDEck 已安装到 $PLUGIN_DIR"
    # 重启 plugin_loader
    sudo systemctl restart plugin_loader || echo "请手动: sudo systemctl restart plugin_loader"
ENDSCRIPT

echo "=== 完成 ==="

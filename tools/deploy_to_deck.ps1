# KDEck 一键部署到 Steam Deck (Windows PowerShell)
# 用法: .\tools\deploy_to_deck.ps1 -DeckIp 10.70.21.37
# 前提: Deck 已开启 SSH (桌面模式 → Konsole → sudo systemctl start sshd)

param(
    [string]$DeckIp = "10.70.21.37",
    [string]$DeckUser = "deck"
)

$PluginDir = "/home/deck/homebrew/plugins/KDEck"
$ZipFile = "release/KDEck.zip"

Write-Host "=== 构建 KDEck ===" -ForegroundColor Cyan
pnpm run build
if ($LASTEXITCODE -ne 0) { throw "构建失败" }
python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "测试失败" }
python tools/package_release.py

Write-Host "=== 传输到 Deck ===" -ForegroundColor Cyan
scp $ZipFile "${DeckUser}@${DeckIp}:~/Downloads/KDEck.zip"

Write-Host "=== 安装 ===" -ForegroundColor Cyan
ssh "${DeckUser}@${DeckIp}" @"
    if [ -d "$PluginDir" ]; then
        rm -rf "${PluginDir}.bak"
        cp -r "$PluginDir" "${PluginDir}.bak"
        rm -rf "$PluginDir"
    fi
    mkdir -p "$PluginDir"
    cd "$PluginDir"
    unzip -o ~/Downloads/KDEck.zip
    echo "done"
    sudo systemctl restart plugin_loader 2>/dev/null || echo "请手动重启 Decky"
"@

Write-Host "=== 完成 ===" -ForegroundColor Green

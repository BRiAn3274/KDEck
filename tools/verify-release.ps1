param(
    [switch]$SkipWsl
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RootPath = $Root.Path

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host "==> $Name"
    & $Body
}

Set-Location $Root

Invoke-Step "Windows frontend build" {
    pnpm run build
}

Invoke-Step "Windows backend tests" {
    python -m unittest discover -s tests
}

Invoke-Step "Windows ruff" {
    python -m ruff check
}

if (-not $SkipWsl) {
    Invoke-Step "WSL full verification in isolated temp copy" {
        $wslRoot = (& wsl -e wslpath -a $RootPath).Trim()
        wsl -e bash -lc @"
set -euo pipefail
rm -rf /tmp/kdeck-wsl-verify
mkdir -p /tmp/kdeck-wsl-verify
cd '$wslRoot'
tar --exclude=node_modules --exclude=.git --exclude=dist --exclude=release -cf - . | tar -C /tmp/kdeck-wsl-verify -xf -
cd /tmp/kdeck-wsl-verify
pnpm install --frozen-lockfile
pnpm run build
python3 -m unittest discover -s tests
python3 -m ruff check
python3 -m py_compile main.py backend/src/*.py
"@
    }
}

Invoke-Step "Package release zip" {
    python tools/package_release.py
}

Invoke-Step "Verify packaged version" {
    $package = Get-Content -LiteralPath "package.json" -Encoding UTF8 | ConvertFrom-Json
    $tmp = Join-Path $env:TEMP ("kdeck_release_verify_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Expand-Archive -LiteralPath "release\KDEck.zip" -DestinationPath $tmp
        $packed = Get-Content -LiteralPath (Join-Path $tmp "KDEck\package.json") -Encoding UTF8 | ConvertFrom-Json
        if ($packed.version -ne $package.version) {
            throw "Packaged version $($packed.version) does not match package.json $($package.version)."
        }
        Get-FileHash -LiteralPath "release\KDEck.zip" -Algorithm SHA256
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

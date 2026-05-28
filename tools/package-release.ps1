param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$script = Join-Path $PSScriptRoot "package_release.py"

$pythonExe = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonExe) {
    $pythonExe = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonExe) {
    throw "python or python3 is required to create the release zip."
}

if ($Version) {
    & $pythonExe.Source $script $Version
} else {
    & $pythonExe.Source $script
}

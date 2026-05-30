#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Help) {
    @"
Usage: scripts\start-dev-win.ps1 [options]

Start TenderWord in Windows-native mode.

Options:
  -BackendOnly  Start only the Windows backend.
  -Help         Show this help.

This is the explicit Windows entrypoint. It delegates to scripts\start-dev.ps1,
which switches Windows dependencies into frontend\node_modules before starting
Next.js.
"@
    exit 0
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $repoRoot "scripts\start-dev.ps1"

$args = @("-ExecutionPolicy", "Bypass", "-File", $launcher)
if ($BackendOnly) {
    $args += "-BackendOnly"
}

& powershell.exe @args
exit $LASTEXITCODE

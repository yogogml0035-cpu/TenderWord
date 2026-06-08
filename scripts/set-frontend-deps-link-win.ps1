#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("win", "wsl")]
    [string]$Target = "",
    [string]$RepoRoot = "",
    [switch]$UnlinkOnly,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: scripts\set-frontend-deps-link-win.ps1 -Target win|wsl

Switch frontend\node_modules for a runtime mode.

Targets:
  win  -> make frontend\node_modules the Windows dependency directory
  wsl  -> point frontend\node_modules at frontend\node_modules-wsl

Options:
  -UnlinkOnly  Remove frontend\node_modules when it is a link/junction, then exit.
"@
}

function Test-ReparsePoint {
    param([Parameter(Mandatory = $true)]$Item)

    return (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Remove-DirectoryLink {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        [System.IO.Directory]::Delete($Path)
    } catch {
        throw "Failed to remove existing frontend\node_modules link: $($_.Exception.Message)"
    }
}

function Get-NodeModulesPlatform {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (Test-Path -LiteralPath (Join-Path $Path "lightningcss-win32-x64-msvc")) {
        return "win"
    }

    if ((Test-Path -LiteralPath (Join-Path $Path "lightningcss-linux-x64-gnu")) -or
        (Test-Path -LiteralPath (Join-Path $Path "lightningcss-linux-x64-musl"))) {
        return "wsl"
    }

    return ""
}

function Assert-PathWithinDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Directory
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullDirectory = [System.IO.Path]::GetFullPath($Directory).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($fullDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside frontend: $fullPath"
    }
}

function Remove-GeneratedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Assert-PathWithinDirectory -Path $Path -Directory $frontendRoot
    Remove-Item -LiteralPath $Path -Recurse -Force
}

if ($Help) {
    Show-Usage
    exit 0
}

if (-not $Target -and -not $UnlinkOnly) {
    throw "Target is required. Use -Target win or -Target wsl."
}

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$frontendRoot = Join-Path $RepoRoot "frontend"
$linkPath = Join-Path $frontendRoot "node_modules"
$targetName = if ($Target -eq "win") { "node_modules-win" } else { "node_modules-wsl" }
$oppositeName = if ($Target -eq "win") { "node_modules-wsl" } else { "node_modules-win" }
$targetPath = Join-Path $frontendRoot $targetName

if (Test-Path -LiteralPath $linkPath) {
    $item = Get-Item -LiteralPath $linkPath -Force
    if ($item.LinkType -in @("Junction", "SymbolicLink") -or (Test-ReparsePoint $item)) {
        Write-Host "[deps] removing existing frontend\node_modules link"
        Remove-DirectoryLink $linkPath
    } elseif ($UnlinkOnly) {
        throw "frontend\node_modules is a real directory; -UnlinkOnly only removes a link/junction."
    }
}

if ($UnlinkOnly) {
    Write-Host "[deps] frontend\node_modules link removed"
    exit 0
}

if (Test-Path -LiteralPath $linkPath) {
    $detectedPlatform = Get-NodeModulesPlatform -Path $linkPath

    if ($Target -eq "win" -and $detectedPlatform -eq "win") {
        Write-Host "[deps] frontend\node_modules is already active for win"
        exit 0
    }

    $preserveName = if ($detectedPlatform) { "node_modules-$detectedPlatform" } else { $oppositeName }
    $preservePath = Join-Path $frontendRoot $preserveName

    if (-not (Test-Path -LiteralPath $preservePath)) {
        Write-Host "[deps] preserving real frontend\node_modules as $preserveName"
        Rename-Item -LiteralPath $linkPath -NewName $preserveName
    } elseif ($detectedPlatform -and $detectedPlatform -ne $Target) {
        Write-Host "[deps] removing $detectedPlatform frontend\node_modules because frontend\$preserveName already exists"
        Remove-GeneratedDirectory -Path $linkPath
    } else {
        $detectedText = if ($detectedPlatform) { " detected as $detectedPlatform" } else { "" }
        throw "frontend\node_modules is a real directory$detectedText and frontend\$preserveName already exists. Move or remove one before switching dependency modes."
    }
}

if ($Target -eq "win") {
    if (Test-Path -LiteralPath $targetPath) {
        Write-Host "[deps] activating frontend\node_modules-win as frontend\node_modules"
        Rename-Item -LiteralPath $targetPath -NewName "node_modules"
    } elseif (-not (Test-Path -LiteralPath $linkPath)) {
        Write-Host "[deps] creating empty frontend\node_modules for Windows dependencies"
        New-Item -ItemType Directory -Path $linkPath | Out-Null
    }

    Write-Host "[deps] frontend\node_modules active for win"
    exit 0
}

if (-not (Test-Path -LiteralPath $targetPath)) {
    New-Item -ItemType Directory -Path $targetPath | Out-Null
}

$cmd = "mklink /J `"$linkPath`" `"$targetPath`""
& cmd.exe /c $cmd | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create junction frontend\node_modules -> $targetName"
}

Write-Host "[deps] frontend\node_modules -> $targetName"

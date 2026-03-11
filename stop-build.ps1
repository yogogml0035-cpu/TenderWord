Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ScriptName = "stop-build"
$script:RepoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$script:RuntimeDir = Join-Path $script:RepoRoot ".runtime\build"
$script:BackendPidFile = Join-Path $script:RuntimeDir "backend.pid"
$script:FrontendPidFile = Join-Path $script:RuntimeDir "frontend.pid"
$script:StateFile = Join-Path $script:RuntimeDir "state.json"

function Write-Info {
    param([string]$Message)

    Write-Host "[$script:ScriptName] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)

    Write-Host "[$script:ScriptName] $Message" -ForegroundColor Green
}

function Read-PidFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $raw = (Get-Content -LiteralPath $Path -Raw).Trim()
    if (-not $raw) {
        return $null
    }

    $pidValue = 0
    if (-not [int]::TryParse($raw, [ref]$pidValue)) {
        return $null
    }

    return $pidValue
}

function Test-ProcessRunning {
    param([int]$Pid)

    return [bool](Get-Process -Id $Pid -ErrorAction SilentlyContinue)
}

function Stop-ProcessTreeById {
    param(
        [int]$Pid,
        [string]$Label
    )

    if (-not (Test-ProcessRunning -Pid $Pid)) {
        Write-Info "$Label 进程（PID: $Pid）已不在运行，清理记录即可。"
        return
    }

    Write-Info "停止 $Label 进程树（PID: $Pid）..."
    $null = taskkill /PID $Pid /T /F 2>$null
}

function Remove-IfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

$stoppedAny = $false

if (-not (Test-Path -LiteralPath $script:RuntimeDir)) {
    Write-Info "未找到 .runtime\build 目录，没有可停止的部署态进程。"
    exit 0
}

$frontendPid = Read-PidFile -Path $script:FrontendPidFile
if ($frontendPid) {
    Stop-ProcessTreeById -Pid $frontendPid -Label "frontend"
    $stoppedAny = $true
}

$backendPid = Read-PidFile -Path $script:BackendPidFile
if ($backendPid) {
    Stop-ProcessTreeById -Pid $backendPid -Label "backend"
    $stoppedAny = $true
}

Remove-IfExists -Path $script:FrontendPidFile
Remove-IfExists -Path $script:BackendPidFile
Remove-IfExists -Path $script:StateFile

if ($stoppedAny) {
    Write-Success "部署态进程已停止，PID 记录已清理。日志文件保留在 .runtime\build。"
} else {
    Write-Info "未找到可停止的 PID 记录，仅清理了残留状态文件。"
}

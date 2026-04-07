param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8502,
    [switch]$ForcePortCleanup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ScriptName = "stop-build"
$script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:ScriptRelativePath = "scripts\stop-build.ps1"
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

function Get-PortOccupant {
    param([int]$Port)

    $line = netstat -ano -p tcp |
        Select-String -Pattern "[:.]$Port\s+.*LISTENING\s+(\d+)" |
        Select-Object -First 1

    if (-not $line) {
        return $null
    }

    $processId = [int]$line.Matches[0].Groups[1].Value
    $processName = ""
    $processPath = ""

    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
        $processName = $process.ProcessName
        $processPath = $process.Path
    } catch {
    }

    return [pscustomobject]@{
        Port = $Port
        Pid = $processId
        ProcessName = $processName
        ProcessPath = $processPath
    }
}

function Read-PidFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $rawContent = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $rawContent) {
        return $null
    }

    $raw = $rawContent.Trim()
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
    param([int]$ProcessId)

    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Stop-ProcessTreeById {
    param(
        [int]$ProcessId,
        [string]$Label
    )

    if (-not (Test-ProcessRunning -ProcessId $ProcessId)) {
        Write-Info "$Label 进程（PID: $ProcessId）已不在运行，清理记录即可。"
        return
    }

    Write-Info "停止 $Label 进程树（PID: $ProcessId）..."
    $null = taskkill /PID $ProcessId /T /F 2>$null
}

function Stop-OrphanPortOccupant {
    param(
        [int]$Port,
        [string]$Label
    )

    $occupant = Get-PortOccupant -Port $Port
    if (-not $occupant) {
        return $false
    }

    $allowedNames = @("python", "node", "cmd", "powershell", "pwsh")
    $processName = if ($occupant.ProcessName) { $occupant.ProcessName.ToLowerInvariant() } else { "" }
    $isExpectedProcess = $allowedNames -contains $processName

    if (-not $ForcePortCleanup -and -not $isExpectedProcess) {
        $displayName = if ($occupant.ProcessName) { $occupant.ProcessName } else { "unknown" }
        Write-Info "检测到 $Label 端口 $Port 被 $displayName（PID: $($occupant.Pid)）占用，但它不在默认可回收进程名单中。若确认可清理，请执行 .\$script:ScriptRelativePath -ForcePortCleanup。"
        return $false
    }

    $displayPath = if ($occupant.ProcessPath) { "，路径: $($occupant.ProcessPath)" } else { "" }
    Write-Info "检测到 $Label 端口 $Port 上的孤儿进程：$($occupant.ProcessName)（PID: $($occupant.Pid)$displayPath）。"
    Stop-ProcessTreeById -ProcessId $occupant.Pid -Label "$Label orphan listener"
    return $true
}

function Remove-IfExists {
    param(
        [string]$Path,
        [int]$RetryCount = 3,
        [int]$RetryDelayMs = 400
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $true
    }

    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
            return $true
        } catch {
            if ($attempt -lt $RetryCount) {
                Start-Sleep -Milliseconds $RetryDelayMs
                continue
            }

            try {
                Clear-Content -LiteralPath $Path -Force -ErrorAction Stop
                Write-Info "无法删除文件：$Path。已清空内容并保留空文件。原因：$($_.Exception.Message)"
                return $true
            } catch {
                Write-Info "无法删除文件：$Path。请稍后手动清理。原因：$($_.Exception.Message)"
                return $false
            }
        }
    }
}

$stoppedAny = $false
$runtimeDirExists = Test-Path -LiteralPath $script:RuntimeDir

if (-not $runtimeDirExists) {
    Write-Info "未找到 .runtime\\build 目录，将仅检查端口 $BackendPort / $FrontendPort 上的孤儿进程。"
}

$frontendPid = Read-PidFile -Path $script:FrontendPidFile
if ($frontendPid) {
    Stop-ProcessTreeById -ProcessId $frontendPid -Label "frontend"
    $stoppedAny = $true
} elseif (Stop-OrphanPortOccupant -Port $FrontendPort -Label "frontend") {
    $stoppedAny = $true
}

$backendPid = Read-PidFile -Path $script:BackendPidFile
if ($backendPid) {
    Stop-ProcessTreeById -ProcessId $backendPid -Label "backend"
    $stoppedAny = $true
} elseif (Stop-OrphanPortOccupant -Port $BackendPort -Label "backend") {
    $stoppedAny = $true
}

$cleanupResults = @(
    (Remove-IfExists -Path $script:FrontendPidFile),
    (Remove-IfExists -Path $script:BackendPidFile),
    (Remove-IfExists -Path $script:StateFile)
)
$cleanupCompleted = ($cleanupResults -notcontains $false)

if ($stoppedAny) {
    if ($cleanupCompleted) {
        Write-Success "部署态进程已停止，运行状态记录已清理。日志文件保留在 .runtime\build。"
    } else {
        Write-Info "部署态进程已停止，但仍有状态文件未清理，请稍后手动处理 .runtime\build。"
    }
} else {
    if ($cleanupCompleted) {
        Write-Info "未找到可停止的 PID 记录，仅清理了残留状态文件。"
    } else {
        Write-Info "未找到可停止的 PID 记录，但仍有残留状态文件未清理。"
    }
}

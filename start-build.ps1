param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8502,
    [int]$BackendTimeoutSec = 90,
    [int]$FrontendTimeoutSec = 420
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ScriptName = "start-build"
$script:RepoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$script:RuntimeDir = Join-Path $script:RepoRoot ".runtime\build"
$script:BackendPidFile = Join-Path $script:RuntimeDir "backend.pid"
$script:FrontendPidFile = Join-Path $script:RuntimeDir "frontend.pid"
$script:StateFile = Join-Path $script:RuntimeDir "state.json"
$script:BackendStdoutLog = Join-Path $script:RuntimeDir "backend.stdout.log"
$script:BackendStderrLog = Join-Path $script:RuntimeDir "backend.stderr.log"
$script:FrontendStdoutLog = Join-Path $script:RuntimeDir "frontend.stdout.log"
$script:FrontendStderrLog = Join-Path $script:RuntimeDir "frontend.stderr.log"
$script:BackendProcess = $null
$script:FrontendProcess = $null

function Write-Info {
    param([string]$Message)

    Write-Host "[$script:ScriptName] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)

    Write-Host "[$script:ScriptName] $Message" -ForegroundColor Green
}

function Fail {
    param([string]$Message)

    throw [System.InvalidOperationException]::new($Message)
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$FailureMessage
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Fail $FailureMessage
    }
}

function Get-CommandPath {
    param(
        [string]$Name,
        [string]$FailureMessage
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) {
        Fail $FailureMessage
    }

    return $command.Source
}

function Get-PortOccupant {
    param([int]$Port)

    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $listener) {
            return $null
        }

        $processName = ""
        try {
            $processName = (Get-Process -Id $listener.OwningProcess -ErrorAction Stop).ProcessName
        } catch {
        }

        return [pscustomobject]@{
            Port = $Port
            Pid = $listener.OwningProcess
            ProcessName = $processName
        }
    }

    $line = netstat -ano -p tcp |
        Select-String -Pattern "[:.]$Port\s+.*LISTENING\s+(\d+)" |
        Select-Object -First 1

    if (-not $line) {
        return $null
    }

    $pid = [int]$line.Matches[0].Groups[1].Value
    $processName = ""
    try {
        $processName = (Get-Process -Id $pid -ErrorAction Stop).ProcessName
    } catch {
    }

    return [pscustomobject]@{
        Port = $Port
        Pid = $pid
        ProcessName = $processName
    }
}

function Assert-PortFree {
    param([int]$Port)

    $occupant = Get-PortOccupant -Port $Port
    if (-not $occupant) {
        return
    }

    $suffix = if ($occupant.ProcessName) {
        "（进程: $($occupant.ProcessName), PID: $($occupant.Pid)）"
    } else {
        "（PID: $($occupant.Pid)）"
    }

    Fail "端口 $Port 已被占用$suffix。请先释放端口，或执行 .\stop-build.ps1 清理旧进程。"
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

function Clear-Or-RejectPidFile {
    param(
        [string]$Label,
        [string]$PidFile
    )

    $pidValue = Read-PidFile -Path $PidFile
    if (-not $pidValue) {
        $null = Remove-IfExists -Path $PidFile
        return
    }

    if (Test-ProcessRunning -ProcessId $pidValue) {
        Fail "检测到已有运行中的 $Label 进程（PID: $pidValue）。请先执行 .\stop-build.ps1。"
    }

    $null = Remove-IfExists -Path $PidFile
}

function Get-LogTail {
    param(
        [string]$Path,
        [int]$Tail = 20
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $content = Get-Content -LiteralPath $Path -Tail $Tail -ErrorAction SilentlyContinue
    return ($content -join [Environment]::NewLine).Trim()
}

function Stop-ProcessTreeById {
    param(
        [int]$ProcessId,
        [string]$Label
    )

    if (-not (Test-ProcessRunning -ProcessId $ProcessId)) {
        return
    }

    Write-Info "停止 $Label 进程树（PID: $ProcessId）..."
    $null = taskkill /PID $ProcessId /T /F 2>$null
}

function Start-LoggedProcess {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$StdoutLog,
        [string]$StderrLog,
        [string]$PidFile
    )

    $null = Remove-IfExists -Path $StdoutLog
    $null = Remove-IfExists -Path $StderrLog

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII
    Write-Info "$Label 已启动，PID=$($process.Id)"
    return $process
}

function Wait-ForHttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSec,
        [System.Diagnostics.Process]$Process,
        [string]$StdoutLog,
        [string]$StderrLog
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $Process.Refresh()
        if ($Process.HasExited) {
            $stdoutTail = Get-LogTail -Path $StdoutLog
            $stderrTail = Get-LogTail -Path $StderrLog
            $details = @()
            if ($stdoutTail) {
                $details += "stdout:`n$stdoutTail"
            }
            if ($stderrTail) {
                $details += "stderr:`n$stderrTail"
            }
            $detailText = if ($details.Count -gt 0) {
                "`n" + ($details -join "`n`n")
            } else {
                ""
            }

            Fail "$Name 进程在健康检查通过前已退出。请检查日志。$detailText"
        }

        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Info "$Name 健康检查通过：$Url"
                return
            }
        } catch {
        }

        Start-Sleep -Seconds 2
    }

    $stdoutTail = Get-LogTail -Path $StdoutLog
    $stderrTail = Get-LogTail -Path $StderrLog
    $details = @()
    if ($stdoutTail) {
        $details += "stdout:`n$stdoutTail"
    }
    if ($stderrTail) {
        $details += "stderr:`n$stderrTail"
    }
    $detailText = if ($details.Count -gt 0) {
        "`n" + ($details -join "`n`n")
    } else {
        ""
    }

    Fail "$Name 健康检查超时（${TimeoutSec}s）：$Url$detailText"
}

function Write-StateFile {
    param(
        [int]$BackendPid,
        [int]$FrontendPid,
        [string]$BackendUrl,
        [string]$FrontendUrl
    )

    $state = [ordered]@{
        started_at = (Get-Date).ToString("o")
        backend_pid = $BackendPid
        frontend_pid = $FrontendPid
        backend_url = $BackendUrl
        frontend_url = $FrontendUrl
        backend_stdout_log = $script:BackendStdoutLog
        backend_stderr_log = $script:BackendStderrLog
        frontend_stdout_log = $script:FrontendStdoutLog
        frontend_stderr_log = $script:FrontendStderrLog
    }

    $state | ConvertTo-Json | Set-Content -LiteralPath $script:StateFile -Encoding UTF8
}

$backendDir = Join-Path $script:RepoRoot "backend"
$frontendDir = Join-Path $script:RepoRoot "frontend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendEnv = Join-Path $backendDir ".env"
$frontendEnv = Join-Path $frontendDir ".env.local"
$frontendPackage = Join-Path $frontendDir "package.json"
$frontendLockFile = Join-Path $frontendDir "package-lock.json"
$cmdPath = if ($env:ComSpec) { $env:ComSpec } else { Get-CommandPath -Name "cmd.exe" -FailureMessage "未找到 cmd.exe。" }
$backendUrl = "http://localhost:$BackendPort/health"
$frontendUrl = "http://localhost:$FrontendPort"
$frontendCommand = "set NODE_ENV=production && npm ci && npm run build && npm run start"

try {
    $currentDir = [System.IO.Path]::GetFullPath((Get-Location).Path)
    if ($currentDir -ne $script:RepoRoot) {
        Fail "请先进入仓库根目录后再运行：`ncd $script:RepoRoot`n.\start-build.ps1"
    }

    Assert-PathExists -Path $backendDir -FailureMessage "未找到 backend 目录。"
    Assert-PathExists -Path $frontendDir -FailureMessage "未找到 frontend 目录。"
    Assert-PathExists -Path $backendPython -FailureMessage "缺少 backend\.venv\Scripts\python.exe。请先在 backend 目录创建并安装虚拟环境。"
    Assert-PathExists -Path $backendEnv -FailureMessage "缺少 backend\.env。请先参考 backend\.env.example 创建环境文件。"
    Assert-PathExists -Path $frontendEnv -FailureMessage "缺少 frontend\.env.local。请先参考 frontend\.env.local.example 创建环境文件。"
    Assert-PathExists -Path $frontendPackage -FailureMessage "缺少 frontend\package.json。"
    Assert-PathExists -Path $frontendLockFile -FailureMessage "缺少 frontend\package-lock.json。`npm ci` 需要锁文件。"

    $null = Get-CommandPath -Name "npm" -FailureMessage "未找到 npm 命令。请先安装 Node.js。"

    New-Item -ItemType Directory -Path $script:RuntimeDir -Force | Out-Null

    Clear-Or-RejectPidFile -Label "backend" -PidFile $script:BackendPidFile
    Clear-Or-RejectPidFile -Label "frontend" -PidFile $script:FrontendPidFile
    $null = Remove-IfExists -Path $script:StateFile

    Assert-PortFree -Port $BackendPort
    Assert-PortFree -Port $FrontendPort

    Write-Info "运行后端预检查（固定使用 backend\.venv\Scripts\python.exe）..."
    $backendCheckOutput = & $backendPython -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $details = ($backendCheckOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        if ($details -match "WinError 10106|_overlapped") {
            Fail "后端预检查失败。检测到本机 Python/Windows 网络栈异常（_overlapped / WinError 10106），这不是当前仓库代码导入错误。请先修复本机 Python 或 Winsock 环境后再启动。`n$details"
        }
        Fail "后端预检查失败。请先修复 Python/依赖/本机环境问题后再启动。`n$details"
    }

    Write-Info "后台启动后端..."
    $script:BackendProcess = Start-LoggedProcess `
        -Label "backend" `
        -FilePath $backendPython `
        -ArgumentList @("-u", "main.py") `
        -WorkingDirectory $backendDir `
        -StdoutLog $script:BackendStdoutLog `
        -StderrLog $script:BackendStderrLog `
        -PidFile $script:BackendPidFile

    Wait-ForHttpReady `
        -Name "backend" `
        -Url $backendUrl `
        -TimeoutSec $BackendTimeoutSec `
        -Process $script:BackendProcess `
        -StdoutLog $script:BackendStdoutLog `
        -StderrLog $script:BackendStderrLog

    Write-Info "后台启动前端（npm ci -> npm run build -> npm run start）..."
    $script:FrontendProcess = Start-LoggedProcess `
        -Label "frontend" `
        -FilePath $cmdPath `
        -ArgumentList @("/d", "/c", $frontendCommand) `
        -WorkingDirectory $frontendDir `
        -StdoutLog $script:FrontendStdoutLog `
        -StderrLog $script:FrontendStderrLog `
        -PidFile $script:FrontendPidFile

    Wait-ForHttpReady `
        -Name "frontend" `
        -Url $frontendUrl `
        -TimeoutSec $FrontendTimeoutSec `
        -Process $script:FrontendProcess `
        -StdoutLog $script:FrontendStdoutLog `
        -StderrLog $script:FrontendStderrLog

    Write-StateFile `
        -BackendPid $script:BackendProcess.Id `
        -FrontendPid $script:FrontendProcess.Id `
        -BackendUrl $backendUrl `
        -FrontendUrl $frontendUrl

    Write-Success "部署态本地启动完成。"
    Write-Host "  Backend PID : $($script:BackendProcess.Id)" -ForegroundColor Green
    Write-Host "  Frontend PID: $($script:FrontendProcess.Id)" -ForegroundColor Green
    Write-Host "  Backend URL : http://localhost:$BackendPort" -ForegroundColor Green
    Write-Host "  Frontend URL: http://localhost:$FrontendPort" -ForegroundColor Green
    Write-Host "  Runtime Dir : $script:RuntimeDir" -ForegroundColor Green
    Write-Host "  Stop Cmd    : .\stop-build.ps1" -ForegroundColor Green
    Write-Host "  Backend Log : $script:BackendStdoutLog" -ForegroundColor Green
    Write-Host "  Frontend Log: $script:FrontendStdoutLog" -ForegroundColor Green
} catch {
    if ($script:FrontendProcess) {
        Stop-ProcessTreeById -ProcessId $script:FrontendProcess.Id -Label "frontend"
    } else {
        $frontendPid = Read-PidFile -Path $script:FrontendPidFile
        if ($frontendPid) {
            Stop-ProcessTreeById -ProcessId $frontendPid -Label "frontend"
        }
    }

    if ($script:BackendProcess) {
        Stop-ProcessTreeById -ProcessId $script:BackendProcess.Id -Label "backend"
    } else {
        $backendPid = Read-PidFile -Path $script:BackendPidFile
        if ($backendPid) {
            Stop-ProcessTreeById -ProcessId $backendPid -Label "backend"
        }
    }

    $null = Remove-IfExists -Path $script:BackendPidFile
    $null = Remove-IfExists -Path $script:FrontendPidFile
    $null = Remove-IfExists -Path $script:StateFile
    Write-Host "[$script:ScriptName] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
